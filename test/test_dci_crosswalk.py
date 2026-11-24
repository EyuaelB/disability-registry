"""The DCI templates must speak the SPDCI code directories — proven by rendering.

Every standard value in register_domain/models/dci_crosswalk.py is pushed through
the INBOUND template and must land on the enum the crosswalk says; every enum is
pushed through the OUTBOUND template and must come back as the standard label.
The previous templates guessed with substring matching and filed "Received, but
not enough" as fully received; this is the test that would have caught it.

Needs jinja2 (CI installs it). Skipped, not failed, where it is absent so the
other guards still run.
"""

import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import pytest

jinja2 = pytest.importorskip("jinja2")

REPO = pathlib.Path(__file__).resolve().parent.parent
EXT = REPO / "disability-extension/src/openg2p_registry_disability_extension"
TEMPLATES = EXT / "templates"


def _load_crosswalk():
    spec = importlib.util.spec_from_file_location("dci_crosswalk", EXT / "register_domain/models/dci_crosswalk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cw = _load_crosswalk()


def _env():
    env = jinja2.Environment()
    env.filters.setdefault("tojson", lambda v: json.dumps(v, ensure_ascii=False))
    return env


def render_outbound(record: dict) -> dict:
    template = _env().from_string((TEMPLATES / "dr_person_to_dci.json.j2").read_text())
    return json.loads(template.render(expanded=record))


def render_inbound(record: dict) -> dict:
    template = _env().from_string((TEMPLATES / "dci_to_dr_person.json.j2").read_text())
    return json.loads(template.render(expanded=record))


# Which crosswalk list drives which (outbound record field, inbound record path).
PERSON_FIELDS = {
    "DISABILITY_STATUS_LEVEL": ("disability_status_level", "disability_status_level",
                                "disability_status_and_assessment", "disability_status_level"),
    "TRANSPORT_REQUIREMENT": ("transport_requirement", "transport_requirement", "living_situation", "transport_requirement"),
    "HOUSING_TYPE": ("housing_type", "housing_type", "living_situation", "housing_type"),
}


# ── generated tables are current ─────────────────────────────────────────────


def test_generated_crosswalk_blocks_are_current():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts/generate-dci-crosswalk.py"), "--check"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_jinja_norm_matches_python_normalise():
    """The inbound lookup key is computed twice — in Python when the tables are
    generated and in Jinja at render time. They must agree on every key."""
    samples = set()
    for spec in cw.CROSSWALK.values():
        for code, label, _enum in spec["standard"]:
            samples.update({code, label})
        samples.update(spec["aliases"])
    samples = sorted(samples)
    head = (TEMPLATES / "dci_to_dr_person.json.j2").read_text().split("{%- macro cw(")[0]
    template = _env().from_string(head + "{% for s in probe %}<<{{ norm(s) }}>>{% endfor %}")
    rendered = re.findall(r"<<(.*?)>>", template.render(probe=samples), re.S)
    assert len(rendered) == len(samples)
    for sample, got in zip(samples, rendered):
        assert got == cw.normalise(sample), f"norm({sample!r}): jinja {got!r} != python {cw.normalise(sample)!r}"


# ── support rows: every standard value round-trips ───────────────────────────

SUPPORT_LISTS = {
    "HUMAN_ASSISTANCE_TYPE": ("human_assistance", "assistance_type", "human_assistance"),
    "ASSISTIVE_TECHNOLOGY_TYPE": ("assistive_technology", "assistive_technology_type", "assistive_technology"),
    "MEDICAL_CARE_TYPE": ("medical_care", "medical_care_type", "medical_care"),
    "HOUSING_SUPPORT_TYPE": ("housing_support", "housing_support_type", "housing_support"),
    "ANIMAL_ASSISTANCE_TYPE": ("animal_assistance", "animal_assistance_type", "animal_assistance"),
}


def _support_inbound(list_name: str, sub_key: str, row: dict) -> dict:
    return render_inbound({"personal_details": {}, "disability_support": [{sub_key: [row]}]})


@pytest.mark.parametrize("list_name", sorted(SUPPORT_LISTS))
def test_support_type_standard_values_round_trip(list_name):
    out_key, column, in_key = SUPPORT_LISTS[list_name]
    for code, label, enum in cw.CROSSWALK[list_name]["standard"]:
        # standard label and numeric code both land on the enum
        for incoming in (label, code):
            got = _support_inbound(list_name, in_key, {"type": incoming})[in_key][0][column]
            assert got == enum, f"{list_name}: inbound {incoming!r} -> {got!r}, expected {enum!r}"
        # the enum goes back out as the standard label (first entry for that enum)
        record = {"functional_record_id": "PWD-1", out_key: [{column: enum, "support_status": "REQUIRED"}]}
        rendered = render_outbound(record)
        block = rendered["disability_support"][0][in_key]
        emitted = block["type"] if isinstance(block, dict) else block[0]["type"]
        assert emitted == cw.outbound_map(list_name)[enum], f"{list_name}: outbound {enum!r} -> {emitted!r}"


def test_support_status_received_but_not_enough_is_unmet_need():
    """The finding that started this: 'Received, but not enough' must become
    PARTIALLY_RECEIVED, which utils/support_summary.py counts as unmet."""
    for incoming in ("Received, but not enough", "2", "received but not enough", "PARTIALLY_RECEIVED"):
        got = _support_inbound("x", "medical_care", {"type": "Rehabilitation", "support_status": incoming})
        assert got["medical_care"][0]["support_status"] == "PARTIALLY_RECEIVED", incoming
    for incoming, enum in (("Required", "REQUIRED"), ("0", "REQUIRED"), ("Received", "RECEIVED"),
                           ("1", "RECEIVED"), ("Not required", "NOT_REQUIRED"), ("3", "NOT_REQUIRED")):
        got = _support_inbound("x", "medical_care", {"type": "Rehabilitation", "support_status": incoming})
        assert got["medical_care"][0]["support_status"] == enum, incoming


def test_support_status_outbound_uses_only_the_four_standard_labels():
    allowed = {label for _c, label, _e in cw.CROSSWALK["SUPPORT_STATUS"]["standard"]} | {""}
    for enum in ("REQUIRED", "RECEIVING", "RECEIVED", "PARTIALLY_RECEIVED", "NOT_REQUIRED", "DISCONTINUED"):
        rendered = render_outbound({"functional_record_id": "P", "medical_care": [{"medical_care_type": "DIALYSIS", "support_status": enum}]})
        label = rendered["disability_support"][0]["medical_care"][0]["support_status"]
        assert label in allowed, f"{enum} -> {label!r} is not a CD.DR.05 label"
    assert render_outbound({"medical_care": [{"medical_care_type": "DIALYSIS", "support_status": "PARTIALLY_RECEIVED"}]})[
        "disability_support"][0]["medical_care"][0]["support_status"] == "Received, but not enough"


def test_frequency_none_is_none_not_occasional():
    got = _support_inbound("x", "human_assistance", {"type": "mobility", "frequency": "None"})
    assert got["human_assistance"][0]["frequency"] == "NONE"


def test_human_assistance_object_or_list_and_relationship_codes():
    single = render_inbound({"disability_support": {"human_assistance": {"type": "basic_activity", "relationship": "SPS"}}})
    assert single["human_assistance"][0]["assistance_type"] == "PERSONAL_CARE"
    assert single["human_assistance"][0]["caregiver_relationship"] == "SPOUSE"
    many = render_inbound({"disability_support": [{"human_assistance": [{"type": "decision_making"}, {"type": "multiple"}]}]})
    assert [r["assistance_type"] for r in many["human_assistance"]] == ["DECISION_MAKING_SUPPORT", "MULTIPLE"]


# ── disability details ───────────────────────────────────────────────────────


def test_impairment_lists_round_trip():
    for list_name, column in (("IMPAIRMENT_TYPE", "impairment_type"), ("IMPAIRMENT_LEVEL", "impairment_level"),
                              ("IMPAIRMENT_CAUSE", "impairment_cause")):
        for code, label, enum in cw.CROSSWALK[list_name]["standard"]:
            for incoming in (label, code):
                got = render_inbound({"disability_details": [{column: incoming}]})["disability_details"][0][column]
                assert got == enum, f"{list_name}: {incoming!r} -> {got!r} != {enum!r}"
            emitted = render_outbound({"disability_detail": [{column: enum}]})["disability_details"][0][column]
            assert emitted == cw.outbound_map(list_name)[enum], f"{list_name}: {enum!r} -> {emitted!r}"


def test_age_on_set_is_a_life_stage_not_a_number():
    # outbound: the band wins, else the integer is banded
    out = render_outbound({"disability_detail": [{"age_onset_band": "AT_BIRTH", "age_on_set": 0}]})
    assert out["disability_details"][0]["age_on_set"] == "Born with"
    assert out["disability_details"][0]["additional_attributes"][0]["age_on_set_years"] == 0
    out = render_outbound({"disability_detail": [{"age_on_set": 45}]})
    assert out["disability_details"][0]["age_on_set"] == "Working age"
    # inbound: the standard's label and code become the band; no bogus age 0
    for incoming, band in (("Childhood", "CHILDHOOD_6_12"), ("1", "CHILDHOOD_6_12"), ("Born with", "AT_BIRTH"),
                           ("0", "AT_BIRTH"), ("Working age", "ADULTHOOD_18_59"), ("Old age", "OLD_AGE_60_PLUS")):
        row = render_inbound({"disability_details": [{"age_on_set": incoming}]})["disability_details"][0]
        assert row["age_onset_band"] == band, incoming
        assert row["age_on_set"] is None, f"{incoming!r} must not become an integer age"
    # a legacy integer age still works
    row = render_inbound({"disability_details": [{"age_on_set": 7}]})["disability_details"][0]
    assert (row["age_onset_band"], row["age_on_set"]) == ("CHILDHOOD_6_12", 7)


# ── person-level fields ──────────────────────────────────────────────────────


def test_disability_status_cd_dr_14():
    assert render_outbound({"disability_status": "ASSESSED_DISABLED"})["disability_status"] == "Approved"
    assert render_outbound({"disability_status": "PENDING_ASSESSMENT"})["disability_status"] == "Pending approval"
    assert render_outbound({"disability_status": "EXPIRED"})["disability_status"] == "Expired"
    assert render_outbound({"disability_status": "ASSESSED_NOT_DISABLED"})["disability_status"] == ""
    for incoming, enum in (("Approved", "ASSESSED_DISABLED"), ("Pending approval", "PENDING_ASSESSMENT"),
                           ("Expired", "EXPIRED"), ("Yes", "ASSESSED_DISABLED"), ("gibberish", "UNKNOWN")):
        got = render_inbound({"disability_status": incoming})["disability_status_and_assessment"][0]["disability_status"]
        assert got == enum, incoming


def test_status_level_transport_housing_round_trip():
    for list_name, (out_field, in_field, section, in_col) in PERSON_FIELDS.items():
        for code, label, enum in cw.CROSSWALK[list_name]["standard"]:
            for incoming in (label, code):
                got = render_inbound({in_field: incoming})[section][0][in_col]
                assert got == enum, f"{list_name}: {incoming!r} -> {got!r}"
            assert render_outbound({out_field: enum})[out_field] == cw.outbound_map(list_name)[enum]


def test_personal_details_wrapper_both_layouts():
    standard = {
        "personal_details": {
            "member_identifier": [{"identifier_type": "UIN", "identifier_value": "NAT-1"}],
            "demographic_info": {"name": {"given_name": "Ama", "surname": "Bekele"}, "sex": "other",
                                 "birth_date": "1990-01-01T00:00:00Z"},
            "self_id_disability": 1, "marital_status": "married",
        },
        "disability_status": "Approved",
    }
    got = render_inbound(standard)
    assert (got["first_name"], got["last_name"], got["gender"]) == ("Ama", "Bekele", "OTHERS")
    assert got["birth_date"] == "1990-01-01"
    assert got["person_identifier"][0]["foundational_id"] == "NAT-1"
    assert got["disability_status_and_assessment"][0]["self_id_disability"] is True
    assert got["marital_status"] == "MARRIED"
    # legacy flat layout, with the registry number under UIN and the national id under NationalID
    legacy = {
        "member_identifier": [{"identifier_type": "UIN", "identifier_value": "PWD-9"}],
        "demographic_info": {"identifier": [{"identifier_type": "NationalID", "identifier_value": "NAT-2"}],
                             "name": {"given_name": "Ama"}, "sex": "female"},
    }
    got = render_inbound(legacy)
    assert got["person_identifier"][0]["foundational_id"] == "NAT-2"
    assert got["gender"] == "FEMALE"


def test_outbound_layout_follows_do_dr_03():
    rendered = render_outbound({
        "functional_record_id": "PWD-1", "foundational_id": "NAT-1", "first_name": "Ama", "last_name": "B",
        "gender": "OTHERS", "birth_date": "1990-01-01", "disability_certificate_number": "C-1",
        "related_person": [{"relationship_type": "SPOUSE", "related_person_name": "K", "is_legal_guardian": True}],
        "human_assistance": [{"assistance_type": "MOBILITY", "support_status": "REQUIRED"},
                             {"assistance_type": "PERSONAL_CARE", "support_status": "RECEIVED"}],
    })
    member = rendered["personal_details"]
    ids = {i["identifier_type"]: i["identifier_value"] for i in member["member_identifier"]}
    assert ids == {"UIN": "NAT-1", "DisabilityRegistryId": "PWD-1", "DisabilityCertificate": "C-1"}
    assert member["demographic_info"]["sex"] == "other"
    assert member["demographic_info"]["birth_date"] == "1990-01-01T00:00:00Z"
    assert member["related_person"][0]["relationship_type"] == "SPS"
    # DO.DR.05: a list; human_assistance 0..1 per element; nothing dropped
    support = rendered["disability_support"]
    assert isinstance(support, list) and len(support) == 2
    assert support[0]["human_assistance"]["type"] == "mobility"
    assert support[1]["human_assistance"]["type"] == "basic_activity"
    assert rendered["@type"] == "spdci-extensions-dci:DisabledPerson"
    # consent scopes (top-level keys) include what values.yaml consents to
    assert {"personal_details", "disability_details", "disability_support"} <= set(rendered)


def test_empty_record_renders_valid_json_both_ways():
    assert isinstance(render_outbound({}), dict)
    assert isinstance(render_inbound({}), dict)
