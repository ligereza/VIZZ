"""Fail-closed gate for measurement requests carrying MAK context."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .geometry import StereoGeometryError, validate_calibration_audit
from .operation_context import calibration_audit_sha256, validate_composed_context


SCHEMA = "vizz-measurement-gate-v1"


def evaluate_measurement_request(
    composed_context: Mapping[str, Any],
    calibration_audit: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Refuse metric measurement until physical calibration evidence exists.

    The request is intentionally checked before any triangulation call. A
    geometrically valid model or a structural receipt cannot authorize metric
    depth, so the refused result contains no point or distance.
    """

    validate_composed_context(composed_context)
    validate_calibration_audit(dict(calibration_audit))
    if composed_context["calibration"]["audit_sha256"] != calibration_audit_sha256(calibration_audit) or composed_context["calibration"]["provenance_ref"] != calibration_audit["evidence"]["provenance_ref"]:
        raise StereoGeometryError("measurement context calibration lineage is invalid")
    if not isinstance(request, Mapping) or request.get("operation") != "binocular_measurement":
        raise StereoGeometryError("measurement operation is not supported")
    if composed_context["controls"]["metric_depth_authorized"] is not False:
        raise StereoGeometryError("measurement context metric authorization is invalid")
    if calibration_audit["status"] != "CALIBRATION_EVIDENCE_REQUIRED":
        reason = "calibration required before metric measurement"
    else:
        reason = "physical calibration evidence required before metric measurement"
    result = {
        "schema": SCHEMA,
        "status": "MEASUREMENT_REFUSED",
        "reason": reason,
        "context": {
            "schema": composed_context["schema"],
            "source_ref": composed_context["mak_context"]["ref"],
            "dialect": composed_context["mak_context"]["dialect"],
            "calibration_status": calibration_audit["status"],
            "calibration_audit_sha256": composed_context["calibration"]["audit_sha256"],
            "calibration_provenance_ref": composed_context["calibration"]["provenance_ref"],
        },
        "execution": {
            "operation": request["operation"],
            "triangulation_attempted": False,
            "depth_result": None,
            "measurement_result": None,
        },
        "controls": {
            "metric_depth_authorized": False,
            "calibration_audit_required": True,
            "depth_publication": False,
            "publication": False,
            "selection_effect": "none",
        },
    }
    validate_measurement_gate(result)
    return result


def validate_measurement_gate(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA or payload.get("status") != "MEASUREMENT_REFUSED":
        raise StereoGeometryError("measurement gate header is invalid")
    expected = {"schema", "status", "reason", "context", "execution", "controls"}
    if set(payload) != expected:
        raise StereoGeometryError("measurement gate fields are invalid")
    context = payload["context"]
    if set(context) != {"schema", "source_ref", "dialect", "calibration_status", "calibration_audit_sha256", "calibration_provenance_ref"} or context["schema"] != "vizz-composed-context-v1" or not isinstance(context["source_ref"], str) or context["source_ref"] != "grammar-lab:Q-610:artifact" or context["dialect"] != "super-mario-feature-v1" or context["calibration_status"] not in {"CALIBRATION_EVIDENCE_REQUIRED", "CALIBRATION_REQUIRED"} or not isinstance(context["calibration_audit_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", context["calibration_audit_sha256"]) or (context["calibration_provenance_ref"] is not None and (not isinstance(context["calibration_provenance_ref"], str) or not context["calibration_provenance_ref"].strip())):
        raise StereoGeometryError("measurement gate context is invalid")
    execution = payload["execution"]
    if execution != {
        "operation": "binocular_measurement",
        "triangulation_attempted": False,
        "depth_result": None,
        "measurement_result": None,
    }:
        raise StereoGeometryError("measurement gate execution is invalid")
    if payload["controls"] != {
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
        "depth_publication": False,
        "publication": False,
        "selection_effect": "none",
    }:
        raise StereoGeometryError("measurement gate controls are invalid")
    if not isinstance(payload["reason"], str) or not payload["reason"]:
        raise StereoGeometryError("measurement gate reason is invalid")
    return True


__all__ = ["SCHEMA", "evaluate_measurement_request", "validate_measurement_gate"]
