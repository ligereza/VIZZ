"""Fail-closed adapter for the MAK VIZZ-facing portfolio context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .geometry import StereoGeometryError


MAK_SCHEMA = "mak-vizz-portfolio-read-only-context-v1"
SCHEMA = "vizz-portfolio-read-only-context-v1"
STATUS = "CONTEXT_ACCEPTED_FAIL_CLOSED"
_CONTROL = {
    "calibration_evidence_required": True,
    "metric_depth_authorized": False,
    "measurement_execution": False,
    "depth_publication": False,
    "publication": False,
    "semantic_equivalence_authorized": False,
    "domain_mix_authorized": False,
    "network_contact": False,
}
_CLAIMS = {"semantic_claim": False, "learning_demonstrated": False, "measurement_executed": False}
MEASUREMENT_SCHEMA = "vizz-portfolio-measurement-gate-v1"


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StereoGeometryError(f"{field} is required")
    return value.strip()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StereoGeometryError(f"{field} is invalid")
    return value


def _int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StereoGeometryError(f"{field} is invalid")
    return value


def adapt_portfolio_read_only_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Accept MAK's bounded context while preserving VIZZ refusal state."""
    if not isinstance(context, Mapping) or context.get("schema") != MAK_SCHEMA or context.get("available") is not True or context.get("read_only") is not True:
        raise StereoGeometryError("MAK VIZZ portfolio context is not available read-only")
    source = _mapping(context.get("source"), "context.source")
    measurement = _mapping(context.get("measurement"), "context.measurement")
    lineage = _mapping(context.get("lineage"), "context.lineage")
    delta = _mapping(context.get("delta"), "context.delta")
    preview = _mapping(context.get("preview"), "context.preview")
    boundary = _mapping(context.get("boundary"), "context.boundary")
    control = _mapping(context.get("control"), "context.control")
    if source.get("measurement_schema") != "mak-vizz-measurement-status-v1" or source.get("lineage_schema") != "mak-vizz-lineage-status-v1" or source.get("delta_schema") != "mak-structural-delta-status-v1" or source.get("preview_schema") != "mak-portfolio-work-preview-v1":
        raise StereoGeometryError("MAK VIZZ portfolio context source schemas are invalid")
    if measurement.get("status") != "unknown_measurement_refused" or measurement.get("calibration_status") != "CALIBRATION_EVIDENCE_REQUIRED" or measurement.get("triangulation_attempted") is not False or measurement.get("depth_result_present") is not False or measurement.get("claim_allowed") is not False:
        raise StereoGeometryError("MAK VIZZ portfolio measurement refusal is invalid")
    if lineage.get("status") != "revision_context_only" or lineage.get("current_status") != "unknown_measurement_refused" or lineage.get("revision_status") != "revision_accepted" or lineage.get("current_state_replaced") is not False:
        raise StereoGeometryError("MAK VIZZ portfolio lineage boundary is invalid")
    if delta.get("status") != "revision_only_delta" or delta.get("learning_demonstrated") is not False:
        raise StereoGeometryError("MAK VIZZ portfolio delta boundary is invalid")
    for field in ("shared_keys", "residue_keys", "serialized_savings_bytes"):
        _int(delta.get(field), f"delta.{field}")
    if preview.get("task_id") != "vizz_calibration" or preview.get("state") != "vizz_measurement_refused" or preview.get("human_gate") != "physical_calibration_evidence" or preview.get("preview_only") is not True or preview.get("execution_allowed") is not False or preview.get("task_execution") is not False:
        raise StereoGeometryError("MAK VIZZ portfolio preview boundary is invalid")
    if boundary != {"measurement_refused": True, "calibration_required": True, "lineage_is_not_authorization": True, "delta_is_structural_only": True, "preview_is_not_execution": True, "semantic_claim": False, "learning_demonstrated": False}:
        raise StereoGeometryError("MAK VIZZ portfolio context boundary is invalid")
    if control != {"database_write": False, "decision_write": False, "state_advance": False, "selection_effect": "none", "promotion": "none", "publication": False, "measurement_execution": False, "metric_depth_authorized": False, "network": False, "execution": False}:
        raise StereoGeometryError("MAK VIZZ portfolio context controls are invalid")
    result = {
        "schema": SCHEMA,
        "status": STATUS,
        "source": {
            "schema": MAK_SCHEMA,
            "measurement_schema": source["measurement_schema"],
            "lineage_schema": source["lineage_schema"],
            "delta_schema": source["delta_schema"],
            "preview_schema": source["preview_schema"],
        },
        "measurement": dict(measurement),
        "lineage": dict(lineage),
        "delta": dict(delta),
        "preview": dict(preview),
        "controls": dict(_CONTROL),
        "claims": dict(_CLAIMS),
    }
    validate_portfolio_read_only_context(result)
    return result


def validate_portfolio_read_only_context(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA or payload.get("status") != STATUS:
        raise StereoGeometryError("VIZZ portfolio context header is invalid")
    expected = {"schema", "status", "source", "measurement", "lineage", "delta", "preview", "controls", "claims"}
    if set(payload) != expected:
        raise StereoGeometryError("VIZZ portfolio context fields are invalid")
    source = payload["source"]
    if set(source) != {"schema", "measurement_schema", "lineage_schema", "delta_schema", "preview_schema"} or source["schema"] != MAK_SCHEMA:
        raise StereoGeometryError("VIZZ portfolio context source is invalid")
    for field in source:
        _text(source[field], f"source.{field}")
    measurement = payload["measurement"]
    if set(measurement) != {"status", "calibration_status", "triangulation_attempted", "depth_result_present", "claim_allowed"} or measurement != {"status": "unknown_measurement_refused", "calibration_status": "CALIBRATION_EVIDENCE_REQUIRED", "triangulation_attempted": False, "depth_result_present": False, "claim_allowed": False}:
        raise StereoGeometryError("VIZZ portfolio context measurement is invalid")
    lineage = payload["lineage"]
    if set(lineage) != {"status", "current_status", "revision_status", "current_state_replaced", "current_ref"} or lineage["status"] != "revision_context_only" or lineage["current_status"] != "unknown_measurement_refused" or lineage["revision_status"] != "revision_accepted" or lineage["current_state_replaced"] is not False:
        raise StereoGeometryError("VIZZ portfolio context lineage is invalid")
    for field in ("status", "current_status", "revision_status", "current_ref"):
        _text(lineage[field], f"lineage.{field}")
    delta = payload["delta"]
    if set(delta) != {"status", "shared_keys", "residue_keys", "serialized_savings_bytes", "learning_demonstrated"} or delta["status"] != "revision_only_delta" or delta["learning_demonstrated"] is not False:
        raise StereoGeometryError("VIZZ portfolio context delta is invalid")
    _text(delta["status"], "delta.status")
    _int(delta["shared_keys"], "delta.shared_keys"); _int(delta["residue_keys"], "delta.residue_keys"); _int(delta["serialized_savings_bytes"], "delta.serialized_savings_bytes")
    preview = payload["preview"]
    if set(preview) != {"task_id", "state", "human_gate", "project_id", "relation_status", "preview_only", "execution_allowed", "task_execution"} or preview["task_id"] != "vizz_calibration" or preview["state"] != "vizz_measurement_refused" or preview["human_gate"] != "physical_calibration_evidence" or preview["preview_only"] is not True or preview["execution_allowed"] is not False or preview["task_execution"] is not False:
        raise StereoGeometryError("VIZZ portfolio context preview is invalid")
    for field in ("task_id", "state", "human_gate", "relation_status"):
        _text(preview[field], f"preview.{field}")
    if preview["project_id"] is not None:
        _text(preview["project_id"], "preview.project_id")
    if payload["controls"] != _CONTROL or payload["claims"] != _CLAIMS:
        raise StereoGeometryError("VIZZ portfolio context controls are invalid")
    return True


def evaluate_portfolio_measurement_request(
    portfolio_context: Mapping[str, Any], request: Mapping[str, Any]
) -> dict[str, Any]:
    """Refuse metric measurement when the request originates at Portafolio.

    The portfolio context is intentionally not a composed geometry context.
    Returning a typed refusal keeps that boundary observable without letting a
    preview or structural delta reach triangulation.
    """
    validate_portfolio_read_only_context(portfolio_context)
    if not isinstance(request, Mapping) or request.get("operation") != "binocular_measurement":
        raise StereoGeometryError("portfolio measurement operation is not supported")
    result = {
        "schema": MEASUREMENT_SCHEMA,
        "status": "MEASUREMENT_REFUSED",
        "reason": "physical calibration evidence required before metric measurement",
        "context": {
            "schema": SCHEMA,
            "measurement_status": portfolio_context["measurement"]["status"],
            "calibration_status": portfolio_context["measurement"]["calibration_status"],
            "preview_only": portfolio_context["preview"]["preview_only"],
        },
        "execution": {
            "operation": request["operation"],
            "triangulation_attempted": False,
            "depth_result": None,
            "measurement_result": None,
        },
        "controls": {
            "metric_depth_authorized": False,
            "measurement_execution": False,
            "depth_publication": False,
            "publication": False,
            "semantic_equivalence_authorized": False,
            "selection_effect": "none",
        },
    }
    validate_portfolio_measurement_gate(result)
    return result


def validate_portfolio_measurement_gate(payload: Mapping[str, Any]) -> bool:
    """Validate the structured refusal emitted from a portfolio context."""
    if not isinstance(payload, Mapping) or payload.get("schema") != MEASUREMENT_SCHEMA or payload.get("status") != "MEASUREMENT_REFUSED":
        raise StereoGeometryError("portfolio measurement gate header is invalid")
    if set(payload) != {"schema", "status", "reason", "context", "execution", "controls"}:
        raise StereoGeometryError("portfolio measurement gate fields are invalid")
    if payload["context"] != {"schema": SCHEMA, "measurement_status": "unknown_measurement_refused", "calibration_status": "CALIBRATION_EVIDENCE_REQUIRED", "preview_only": True}:
        raise StereoGeometryError("portfolio measurement gate context is invalid")
    if payload["execution"] != {"operation": "binocular_measurement", "triangulation_attempted": False, "depth_result": None, "measurement_result": None}:
        raise StereoGeometryError("portfolio measurement gate execution is invalid")
    if payload["controls"] != {"metric_depth_authorized": False, "measurement_execution": False, "depth_publication": False, "publication": False, "semantic_equivalence_authorized": False, "selection_effect": "none"}:
        raise StereoGeometryError("portfolio measurement gate controls are invalid")
    if payload["reason"] != "physical calibration evidence required before metric measurement":
        raise StereoGeometryError("portfolio measurement gate reason is invalid")
    return True


__all__ = ["MAK_SCHEMA", "MEASUREMENT_SCHEMA", "SCHEMA", "STATUS", "adapt_portfolio_read_only_context", "evaluate_portfolio_measurement_request", "validate_portfolio_measurement_gate", "validate_portfolio_read_only_context"]
