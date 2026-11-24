#!/usr/bin/env python3
"""Write the DCI crosswalk tables into the two DCI Jinja templates.

Why this exists
---------------
The platform renders each template as a single document fetched from MinIO, so a
template cannot import Python or include another file. The tables that translate
this registry's enums to the SPDCI code directories therefore have to live INSIDE
each template — and two hand-maintained copies of the same table is how the
previous templates drifted into keyword guessing.

So the tables are DERIVED from one Python source,
``register_domain/models/dci_crosswalk.py``, and written into each template
between these markers::

    {# BEGIN GENERATED DCI CROSSWALK — ./scripts/generate-dci-crosswalk.py #}
    ...
    {# END GENERATED DCI CROSSWALK #}

Run it after editing dci_crosswalk.py; ``test/test_dci_crosswalk.py`` runs it
with --check and fails the build if a template is stale.

Usage:  ./scripts/generate-dci-crosswalk.py [--check]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
EXT = REPO / "disability-extension/src/openg2p_registry_disability_extension"
CROSSWALK_PY = EXT / "register_domain/models/dci_crosswalk.py"
TEMPLATES = EXT / "templates"

BEGIN = "{# BEGIN GENERATED DCI CROSSWALK — ./scripts/generate-dci-crosswalk.py #}"
END = "{# END GENERATED DCI CROSSWALK #}"

# Which tables each template needs. The outbound template only translates enum
# -> standard label; the inbound one only standard text -> enum.
TARGETS = {
    "dr_person_to_dci.json.j2": ("outbound",),
    "dci_to_dr_person.json.j2": ("inbound", "fallback"),
}


def load_crosswalk():
    spec = importlib.util.spec_from_file_location("dci_crosswalk", CROSSWALK_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jinja_dict(name: str, value: dict) -> str:
    # JSON is a valid Jinja literal for string->string / string->dict maps.
    return f"{{%- set {name} = {json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)} -%}}"


def render_block(kinds: tuple[str, ...]) -> str:
    cw = load_crosswalk()
    parts = [BEGIN]
    if "outbound" in kinds:
        parts.append(_jinja_dict("DCI_OUT", {name: cw.outbound_map(name) for name in cw.CROSSWALK}))
    if "inbound" in kinds:
        parts.append(_jinja_dict("DCI_IN", {name: cw.inbound_map(name) for name in cw.CROSSWALK}))
    if "fallback" in kinds:
        parts.append(_jinja_dict("DCI_FALLBACK", cw.fallbacks()))
    parts.append(END)
    return "\n".join(parts)


def splice(text: str, block: str, name: str) -> str:
    start = text.find(BEGIN)
    end = text.find(END)
    if start < 0 or end < 0 or end < start:
        raise SystemExit(f"{name}: BEGIN/END GENERATED DCI CROSSWALK markers not found")
    return text[:start] + block + text[end + len(END):]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if a template is stale")
    args = parser.parse_args()

    stale = []
    for name, kinds in TARGETS.items():
        path = TEMPLATES / name
        current = path.read_text()
        updated = splice(current, render_block(kinds), name)
        if updated != current:
            stale.append(name)
            if not args.check:
                path.write_text(updated)
    if args.check:
        if stale:
            print(f"stale DCI crosswalk in: {', '.join(stale)} — run ./scripts/generate-dci-crosswalk.py")
            return 1
        print("DCI crosswalk tables up to date")
        return 0
    print(f"wrote crosswalk tables into {', '.join(TARGETS) if stale else 'nothing (already current)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
