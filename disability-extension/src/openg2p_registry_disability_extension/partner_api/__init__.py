"""Disability-specific DCI endpoints (API.DR.05 - 07), attached to the partner API
when this extension's Initializer runs inside that process. See dr_controller.py."""

from .dr_controller import register_dr_controller

__all__ = ["register_dr_controller"]
