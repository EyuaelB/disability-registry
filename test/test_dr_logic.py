"""Unit tests for the pure logic behind the DR endpoints and the location columns.

Stdlib + pytest only: these modules import nothing from the platform, so they
run in CI without a database or the registry images.
"""

import importlib.util
import pathlib
from datetime import date

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
EXT = REPO / "disability-extension/src/openg2p_registry_disability_extension"


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, EXT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dr_query = _load("dr_query", "partner_api/dr_query.py")
geo_levels = _load("geo_levels", "register_domain/services/utils/geo_levels.py")


# ── disabled_criteria parsing (API.DR.05-07 request) ─────────────────────────


def test_standard_sample_criteria_parses_to_national_id_lookup():
    criteria = {"query_type": "string", "query": {"member.member_identifier": {"eq": "ABC451123"}}}
    assert dr_query.parse_disabled_criteria(criteria) == [("foundational_id", "ABC451123")]


def test_bare_value_and_dollar_eq_are_accepted():
    assert dr_query.parse_disabled_criteria({"query": {"uin": "U1"}}) == [("foundational_id", "U1")]
    assert dr_query.parse_disabled_criteria({"query": {"functional_record_id": {"$eq": "PWD-1"}}}) == [
        ("functional_record_id", "PWD-1")
    ]


def test_idtype_value_query_is_accepted():
    criteria = {"query_type": "idtype-value", "query": {"id_type": "certificate_number", "id_value": "C-9"}}
    assert dr_query.parse_disabled_criteria(criteria) == [("disability_certificate_number", "C-9")]


@pytest.mark.parametrize(
    "criteria",
    [
        {"query": {}},
        {"query": {"birth_date": {"eq": "1990-01-01"}}},  # not an identifier
        {"query": {"uin": {"gt": "1"}}},  # only equality
        {"query": {"uin": ""}},
        "not-an-object",
    ],
)
def test_bad_criteria_are_rejected(criteria):
    with pytest.raises(dr_query.InvalidDisabledCriteria):
        dr_query.parse_disabled_criteria(criteria)


# ── CD.DR.14 status derivation ───────────────────────────────────────────────

TODAY = date(2026, 11, 24)


@pytest.mark.parametrize(
    "status, expiry, expected",
    [
        ("ASSESSED_DISABLED", None, "Approved"),
        ("ASSESSED_DISABLED", "2030-01-01", "Approved"),
        ("ASSESSED_DISABLED", "2020-01-01", "Expired"),
        ("ASSESSED_DISABLED", date(2026, 11, 24), "Approved"),  # expires today: still valid
        ("EXPIRED", None, "Expired"),
        ("PENDING_ASSESSMENT", None, "Pending approval"),
        ("SELF_DECLARED", None, "Pending approval"),
        ("ASSESSED_NOT_DISABLED", None, ""),
        ("UNKNOWN", None, ""),
        (None, None, ""),
    ],
)
def test_standard_status(status, expiry, expected):
    assert dr_query.standard_disability_status(status, expiry, today=TODAY) == expected


def test_yes_only_for_current_approval():
    assert dr_query.disabled_yes_no("ASSESSED_DISABLED", "2030-01-01", today=TODAY) == "yes"
    assert dr_query.disabled_yes_no("ASSESSED_DISABLED", "2020-01-01", today=TODAY) == "no"
    assert dr_query.disabled_yes_no("PENDING_ASSESSMENT", None, today=TODAY) == "no"


def test_restrict_record_keeps_only_requested_blocks():
    record = {"personal_details": {}, "disability_details": [1], "disability_support": [2], "x": 1}
    assert dr_query.restrict_record(record, ("disability_details",)) == {"disability_details": [1]}


# ── per-level location codes ─────────────────────────────────────────────────


def test_level_codes_root_first():
    hierarchy = {"hierarchy": [
        {"level_value_id": "ETH", "level_value_mnemonic": "Ethiopia"},
        {"level_value_id": "ETH-OR", "level_value_mnemonic": "Oromia"},
        {"level_value_id": "ETH-OR-AR", "level_value_mnemonic": "Arsi"},
    ]}
    codes = geo_levels.level_codes(hierarchy)
    assert codes["geo_level_1_value_id"] == "ETH"
    assert codes["geo_level_2_value_id"] == "ETH-OR"
    assert codes["geo_level_3_value_id"] == "ETH-OR-AR"
    assert codes["geo_level_4_value_id"] is None
    assert codes["geo_level_5_value_id"] is None


def test_level_codes_accepts_json_string_and_garbage():
    assert geo_levels.level_codes('{"hierarchy":[{"level_value_id":"A"}]}')["geo_level_1_value_id"] == "A"
    assert all(v is None for v in geo_levels.level_codes(None).values())
    assert all(v is None for v in geo_levels.level_codes("not json").values())
    assert all(v is None for v in geo_levels.level_codes({"hierarchy": "x"}).values())


def test_apply_level_codes_sets_and_clears():
    class Row:
        geo_code_hierarchy_json = {"hierarchy": [{"level_value_id": "A"}, {"level_value_id": "B"}]}
        geo_level_1_value_id = None
        geo_level_2_value_id = "stale"
        geo_level_3_value_id = "stale"
        geo_level_4_value_id = None
        geo_level_5_value_id = None

    row = Row()
    assert geo_levels.apply_level_codes(row) is True
    assert (row.geo_level_1_value_id, row.geo_level_2_value_id, row.geo_level_3_value_id) == ("A", "B", None)
    assert geo_levels.apply_level_codes(row) is False  # idempotent
