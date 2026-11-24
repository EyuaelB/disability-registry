"""Pure helpers for the disability-specific DCI endpoints (API.DR.05 - 07).

Kept free of platform imports so they can be unit-tested with the standard
library alone. The controller in ``dr_controller.py`` does the HTTP, signature
and consent work and calls into here for the parts that are just logic.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

# Identifier keys the standard's sample and common sense allow in
# ``disabled_criteria.query``. Each maps to the registry column searched.
_IDENTIFIER_COLUMNS: dict[str, str] = {
    "member.member_identifier": "foundational_id",
    "member_identifier": "foundational_id",
    "identifier": "foundational_id",
    "uin": "foundational_id",
    "foundational_id": "foundational_id",
    "national_id": "foundational_id",
    "functional_record_id": "functional_record_id",
    "registry_id": "functional_record_id",
    "disability_registry_id": "functional_record_id",
    "disability_certificate_number": "disability_certificate_number",
    "certificate_number": "disability_certificate_number",
}

_EQ_OPERATORS = {"eq", "$eq", "equals", "="}


class InvalidDisabledCriteria(ValueError):
    """The request's ``disabled_criteria`` cannot be turned into a lookup."""


def parse_disabled_criteria(criteria: Any) -> list[tuple[str, str]]:
    """``disabled_criteria.query`` -> ``[(column, value), ...]``.

    The standard's sample is ``{"member.member_identifier": {"eq": "ABC451123"}}``.
    Also accepted: a bare value instead of ``{"eq": value}``, several identifiers
    (any match wins), and ``query_type`` of ``expression`` / ``idtype-value``
    (``{"id_type": ..., "id_value": ...}``), since the DR API inherits those
    from the common search.
    """
    if not isinstance(criteria, dict):
        raise InvalidDisabledCriteria("disabled_criteria must be an object")
    query = criteria.get("query")
    if isinstance(query, dict) and "id_value" in query:
        value = str(query.get("id_value") or "").strip()
        if not value:
            raise InvalidDisabledCriteria("query.id_value must be a non-empty string")
        id_type = str(query.get("id_type") or "").strip().lower()
        column = _IDENTIFIER_COLUMNS.get(id_type, "foundational_id")
        return [(column, value)]
    if isinstance(query, dict) and "expression" in query:
        query = (query.get("expression") or {}).get("query")
    if not isinstance(query, dict) or not query:
        raise InvalidDisabledCriteria("disabled_criteria.query is required and must be non-empty")

    lookups: list[tuple[str, str]] = []
    for key, operand in query.items():
        column = _IDENTIFIER_COLUMNS.get(str(key).strip().lower())
        if column is None:
            raise InvalidDisabledCriteria(
                f"'{key}' is not an identifier this registry can look up. "
                f"Use one of: {', '.join(sorted(_IDENTIFIER_COLUMNS))}"
            )
        if isinstance(operand, dict):
            value = None
            for op, candidate in operand.items():
                if str(op).lower() in _EQ_OPERATORS:
                    value = candidate
                    break
            if value is None:
                raise InvalidDisabledCriteria(
                    f"'{key}' supports only an equality operator (eq)"
                )
        else:
            value = operand
        value = str(value or "").strip()
        if not value:
            raise InvalidDisabledCriteria(f"'{key}' must have a non-empty value")
        lookups.append((column, value))
    return lookups


def _as_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def standard_disability_status(
    disability_status: Any, certificate_expiry_date: Any, today: Optional[date] = None
) -> str:
    """CD.DR.14: Approved / Pending approval / Expired, or '' when not stated.

    Approved means an assessment found the person disabled AND the certificate,
    if one is recorded, has not run out. The registry stores the outcome and the
    expiry separately, so Expired is derived here rather than stored.
    """
    status = str(getattr(disability_status, "value", disability_status) or "").strip().upper()
    today = today or date.today()
    expiry = _as_date(certificate_expiry_date)
    if status == "EXPIRED":
        return "Expired"
    if status == "ASSESSED_DISABLED":
        if expiry is not None and expiry < today:
            return "Expired"
        return "Approved"
    if status in {"PENDING_ASSESSMENT", "SELF_DECLARED"}:
        return "Pending approval"
    return ""


def disabled_yes_no(disability_status: Any, certificate_expiry_date: Any, today: Optional[date] = None) -> str:
    """API.DR.06 ``disabled_status``: 'yes' only for a current approval."""
    return "yes" if standard_disability_status(disability_status, certificate_expiry_date, today) == "Approved" else "no"


def restrict_record(record: dict, keep: Iterable[str]) -> dict:
    """Keep only the named top-level keys of a rendered DCI record."""
    allowed = set(keep)
    return {key: value for key, value in (record or {}).items() if key in allowed}
