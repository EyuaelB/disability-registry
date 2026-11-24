"""Flatten a record's geo hierarchy into one searchable column per level.

The platform stores location as ``geo_lowest_level_value_id`` (one code) plus
``geo_code_hierarchy_json`` (the whole path, root first). Neither can be filtered
by level: "everyone in region X" needs a column that holds the region code. The
levels themselves — how many there are and what they are called — come from the
Master Data country pack, so the columns are named by position
(``geo_level_1_value_id`` is the top level, usually the country) and the
extension, not the platform, decides they exist.

Pure function; the domain service calls it from its post-ingest / post-approve
hooks, the same way the support summary is recomputed.
"""

from __future__ import annotations

import json
from typing import Any

MAX_LEVELS = 5
COLUMNS = tuple(f"geo_level_{i}_value_id" for i in range(1, MAX_LEVELS + 1))


def level_codes(hierarchy_json: Any) -> dict[str, str | None]:
    """``{geo_level_1_value_id: ..., ..., geo_level_5_value_id: ...}``.

    Accepts the JSONB value as a dict, a JSON string, or ``None``. Both the
    platform's Master Data client and this repo's sample loader write the path
    root-first, so position n is level n. Missing levels are ``None``, never
    omitted, so a record that moved to a shallower location is cleared.
    """
    out: dict[str, str | None] = {column: None for column in COLUMNS}
    data = hierarchy_json
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except ValueError:
            return out
    if not isinstance(data, dict):
        return out
    hierarchy = data.get("hierarchy")
    if not isinstance(hierarchy, list):
        return out
    for index, node in enumerate(hierarchy[:MAX_LEVELS]):
        if not isinstance(node, dict):
            continue
        value_id = node.get("level_value_id")
        if value_id:
            out[COLUMNS[index]] = str(value_id)
    return out


def apply_level_codes(row: Any) -> bool:
    """Set the level columns on an ORM row (or any attribute bag) from its
    hierarchy. Returns True when something changed."""
    codes = level_codes(getattr(row, "geo_code_hierarchy_json", None))
    changed = False
    for column, value in codes.items():
        if getattr(row, column, None) != value:
            setattr(row, column, value)
            changed = True
    return changed
