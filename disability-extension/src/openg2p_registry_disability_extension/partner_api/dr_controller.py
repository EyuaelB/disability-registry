"""The disability-specific DCI endpoints (SPDCI dr_api_v1.0.0, Sync tag).

    POST /dci/registry/sync/get-disability-status   API.DR.06  -> disabled_status yes|no
    POST /dci/registry/sync/get-disability-details  API.DR.05  -> disability_details only
    POST /dci/registry/sync/get-disability-support  API.DR.07  -> disability_support only

Why they live in the extension and not the platform: these three exist only in
the DISABILITY part of the standard (the common registry API has search,
subscribe, notify and status), and "disabled: yes" is this registry's rule —
assessed disabled with a certificate that has not expired. The platform cannot
answer that for a generic register.

How they attach: the partner API's main program instantiates this extension's
Initializer before it builds the web app, and openg2p_fastapi_common attaches any
BaseController's router to the current app on ``post_init()``. So
``register_dr_controller()`` is called from ``app.Initializer.initialize`` and is
a no-op everywhere the partner API package is not installed (staff API, celery).

What is reused from the platform, deliberately: envelope signature verification,
Consent Manager validation, register/template resolution and record rendering
are the platform's helpers — the same code path the generic search uses. They
are internal to the partner API, so a platform upgrade can move them; the
registration is wrapped so a missing import disables these routes with a logged
warning instead of taking the whole service down.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from .dr_query import (
    InvalidDisabledCriteria,
    disabled_yes_no,
    parse_disabled_criteria,
    restrict_record,
)

_logger = logging.getLogger("g2p-dci-dr-controller")

STATUS_ROUTE = "/sync/get-disability-status"
DETAILS_ROUTE = "/sync/get-disability-details"
SUPPORT_ROUTE = "/sync/get-disability-support"

# Top-level keys of dr_person_to_dci.json.j2 each endpoint returns.
_DETAILS_KEYS = ("disability_details", "disability_status", "disability_status_level")
_SUPPORT_KEYS = ("disability_support",)


# ── request / response shapes (dr_api_v1.0.0) ────────────────────────────────


class DisabledCriteria(BaseModel):
    query_type: str = "expression"
    query: Dict[str, Any]

    class Config:
        extra = "allow"


class DisabledRequest(BaseModel):
    transaction_id: str = Field(..., max_length=99)
    disabled_criteria: DisabledCriteria
    reference_id: Optional[str] = None

    class Config:
        extra = "allow"


class DisabledRequestEnvelope(BaseModel):
    signature: str = ""
    header: Dict[str, Any]
    message: DisabledRequest

    class Config:
        extra = "allow"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_dr_controller() -> bool:
    """Attach the three routes to the running partner API app. Returns False
    (and logs) when this process is not the partner API."""
    try:
        from openg2p_fastapi_common.controller import BaseController
        from openg2p_registry_partner_api.config import Settings as PartnerSettings
        from openg2p_registry_partner_api.search.dci.helpers import (
            DciConsentHelper,
            DciKeymanagerHelper,
        )
        from openg2p_registry_partner_api.search.dci.services import G2PDciService
    except ImportError as exc:  # staff API, celery, bene API
        _logger.debug("DR endpoints not registered here (%s)", exc)
        return False

    from openg2p_fastapi_common.context import get_async_session_maker
    from openg2p_registry_core.errors import G2PRegistryErrorCodes, G2PRegistryException

    partner_config = PartnerSettings.get_config()

    class G2PDciDisabilityController(BaseController):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.router.tags += ["/dci/registry"]
            self.router.prefix = "/dci/registry"
            self.router.add_api_route(STATUS_ROUTE, self.get_disability_status, methods=["POST"])
            self.router.add_api_route(DETAILS_ROUTE, self.get_disability_details, methods=["POST"])
            self.router.add_api_route(SUPPORT_ROUTE, self.get_disability_support, methods=["POST"])

        # ── the three endpoints ──────────────────────────────────────────

        async def get_disability_status(self, envelope: DisabledRequestEnvelope, request: Request):
            return await self._handle(envelope, request, mode="status")

        async def get_disability_details(self, envelope: DisabledRequestEnvelope, request: Request):
            return await self._handle(envelope, request, mode="details")

        async def get_disability_support(self, envelope: DisabledRequestEnvelope, request: Request):
            return await self._handle(envelope, request, mode="support")

        # ── shared pipeline: signature → consent → lookup → render → answer ──

        async def _handle(self, envelope: DisabledRequestEnvelope, request: Request, mode: str):
            header = envelope.header or {}
            try:
                raw_body: Dict[str, Any] = await request.json()
                await self._verify_signature(envelope.signature, raw_body)
                scopes = await self._enforce_consent(raw_body, header)

                lookups = parse_disabled_criteria(envelope.message.disabled_criteria.model_dump())
                rows = await self._find_people(lookups)
                reference_id = envelope.message.reference_id or envelope.message.transaction_id

                if mode == "status":
                    payload = self._status_payload(envelope, reference_id, rows)
                else:
                    payload = await self._records_payload(envelope, reference_id, rows, mode, scopes)
                return self._success_envelope(header, payload, action=self._action(mode))
            except InvalidDisabledCriteria as exc:
                return self._error_envelope(header, envelope, "rjct.search_criteria.invalid", str(exc), mode)
            except G2PRegistryException as exc:
                return self._error_envelope(header, envelope, str(exc.code), str(exc.message), mode)
            except Exception:  # never leak internals to a partner
                _logger.exception("DR endpoint %s failed", mode)
                return self._error_envelope(header, envelope, "err.internal", "internal error", mode)

        async def _verify_signature(self, signature: str, raw_body: Dict[str, Any]) -> None:
            if not partner_config.signature_validation_enabled:
                _logger.warning("signature_validation_enabled=false — DR endpoint skipping signature check")
                return
            helper = DciKeymanagerHelper.get_component() or DciKeymanagerHelper()
            await helper.validate_signature(
                signature, raw_body.get("header") or {}, raw_body.get("message") or {}
            )

        async def _enforce_consent(self, raw_body: Dict[str, Any], header: Dict[str, Any]) -> Optional[List[str]]:
            """Returns the consented scopes, or None when enforcement is off.

            The DR request has no search_criteria.authorize, so the consent JWS
            is looked for at message.authorize.consent_jws, then
            message.disabled_criteria.authorize.consent_jws. Fail closed.
            """
            if not partner_config.consent_enforcement_enabled:
                _logger.warning("consent_enforcement_enabled=false — DR endpoint skipping consent check")
                return None
            message = (raw_body or {}).get("message") or {}
            consent_jws = None
            for container in (message, message.get("disabled_criteria") or {}):
                authorize = (container or {}).get("authorize") or {}
                if isinstance(authorize.get("consent_jws"), str):
                    consent_jws = authorize["consent_jws"]
                    break
            helper = DciConsentHelper.get_component() or DciConsentHelper()
            decision = await helper.validate(consent_jws=consent_jws, sender_id=header.get("sender_id", ""))
            if decision.get("decision") != "permit":
                raise G2PRegistryException(
                    code=G2PRegistryErrorCodes.REQUEST_VALIDATION_ERROR.value[1],
                    message=f"Consent denied: {decision.get('reason_code')} {decision.get('detail') or ''}".strip(),
                )
            return list(decision.get("effective_data_scopes") or [])

        async def _find_people(self, lookups: List[tuple]) -> list:
            service = G2PDciService.get_component() or G2PDciService()
            model = service._get_model_class("PersonWithDisability")
            conditions = []
            for column, value in lookups:
                attr = getattr(model, column, None)
                if attr is not None:
                    conditions.append(attr == value)
            if not conditions:
                return []
            from sqlalchemy import or_

            async with get_async_session_maker()() as session:
                query = select(model).where(or_(*conditions), model.record_status == "ACTIVE").limit(50)
                return list((await session.execute(query)).scalars().all())

        # ── payloads ─────────────────────────────────────────────────────

        @staticmethod
        def _status_payload(envelope: DisabledRequestEnvelope, reference_id: str, rows: list) -> Dict[str, Any]:
            answer = "no"
            for row in rows:
                if disabled_yes_no(
                    getattr(row, "disability_status", None),
                    getattr(row, "certificate_expiry_date", None),
                ) == "yes":
                    answer = "yes"
                    break
            return {
                "transaction_id": envelope.message.transaction_id,
                "correlation_id": uuid.uuid4().hex,
                "disabled_response": [
                    {
                        "reference_id": reference_id,
                        "timestamp": _now(),
                        "status": "succ",
                        "status_reason_message": "" if rows else "no matching registrant",
                        "disabled_status": answer,
                    }
                ],
            }

        async def _records_payload(
            self, envelope: DisabledRequestEnvelope, reference_id: str, rows: list, mode: str,
            scopes: Optional[List[str]],
        ) -> Dict[str, Any]:
            service = G2PDciService.get_component() or G2PDciService()
            register_id = await service._get_register_id("PersonWithDisability")
            data_model_id = await service._get_data_model_id()
            store_id, bucket = await service._get_template_store_id(register_id, data_model_id)
            keep = _DETAILS_KEYS if mode == "details" else _SUPPORT_KEYS
            if scopes is not None:
                keep = tuple(k for k in keep if k in set(scopes))

            from openg2p_registry_core.schemas import DeepSearchResultData

            records = []
            for row in rows:
                record_dict = row.to_dict()
                for key, value in list(record_dict.items()):
                    if hasattr(value, "isoformat"):
                        record_dict[key] = value.isoformat()
                rendered = service._render_reg_record_with_template(
                    DeepSearchResultData(**record_dict), store_id, bucket=bucket
                )
                records.append(restrict_record(rendered, keep))
            return {
                "transaction_id": envelope.message.transaction_id,
                "correlation_id": uuid.uuid4().hex,
                "search_response": [
                    {
                        "reference_id": reference_id,
                        "timestamp": _now(),
                        "status": "succ",
                        "data": {
                            "version": "1.0.0",
                            "reg_type": "ns:org:RegistryType:DR",
                            "reg_record_type": "spdci-extensions-dci:DisabledPerson",
                            "reg_records": records,
                        },
                        "pagination": {"page_size": len(records), "page_number": 1, "total_count": len(records)},
                        "locale": "eng",
                    }
                ],
            }

        # ── envelopes ────────────────────────────────────────────────────

        @staticmethod
        def _action(mode: str) -> str:
            return {"status": "get-disability-status", "details": "get-disability-details",
                    "support": "get-disability-support"}[mode]

        def _response_header(self, header: Dict[str, Any], action: str, status: str,
                             reason_code: str = "", reason_message: str = "") -> Dict[str, Any]:
            return {
                "version": "1.0.0",
                "message_id": header.get("message_id") or uuid.uuid4().hex,
                "message_ts": _now(),
                "action": action,
                "status": status,
                "status_reason_code": reason_code or None,
                "status_reason_message": reason_message or None,
                "sender_id": header.get("receiver_id") or "",
                "receiver_id": header.get("sender_id") or "",
                "total_count": 1,
                "completed_count": 1 if status == "succ" else 0,
                "is_msg_encrypted": False,
                "meta": {
                    "signature_validation": "enabled" if partner_config.signature_validation_enabled else "disabled",
                    "consent_enforcement": "enabled" if partner_config.consent_enforcement_enabled else "disabled",
                },
            }

        def _success_envelope(self, header: Dict[str, Any], payload: Dict[str, Any], action: str) -> Dict[str, Any]:
            response_header = self._response_header(header, action, "succ")
            return {"signature": "", "header": response_header, "message": payload}

        def _error_envelope(self, header: Dict[str, Any], envelope: DisabledRequestEnvelope,
                            code: str, message: str, mode: str) -> Dict[str, Any]:
            response_header = self._response_header(header, self._action(mode), "rjct", code, message)
            return {
                "signature": "",
                "header": response_header,
                "message": {
                    "transaction_id": getattr(envelope.message, "transaction_id", ""),
                    "correlation_id": uuid.uuid4().hex,
                    "disabled_response" if mode == "status" else "search_response": [
                        {
                            "reference_id": getattr(envelope.message, "reference_id", None)
                            or getattr(envelope.message, "transaction_id", ""),
                            "timestamp": _now(),
                            "status": "rjct",
                            "status_reason_code": code,
                            "status_reason_message": message,
                        }
                    ],
                },
            }

    G2PDciDisabilityController().post_init()
    _logger.info("DR endpoints registered: %s %s %s", STATUS_ROUTE, DETAILS_ROUTE, SUPPORT_ROUTE)
    return True
