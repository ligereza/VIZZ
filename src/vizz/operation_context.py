"""Adapt a MAK structural receipt into a bounded VIZZ context record."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .geometry import StereoGeometryError, validate_calibration_audit


SCHEMA = "vizz-operation-context-v1"
MAK_RECEIPT_SCHEMA = "mak-operation-receipt-v1"
COMPOSED_SCHEMA = "vizz-composed-context-v1"
MAK_DIRECTION_SCHEMA = "mak-portfolio-direction-context-v1"
DIRECTION_CONTEXT_SCHEMA = "vizz-portfolio-direction-context-v1"
MAK_WORK_PREVIEW_SCHEMA = "mak-portfolio-work-preview-v1"
VIZZ_WORK_PREVIEW_SCHEMA = "vizz-portfolio-work-preview-v1"


def calibration_audit_sha256(audit: Mapping[str, Any]) -> str:
    """Hash the calibration audit as provenance, never as authorization."""
    raw = json.dumps(dict(audit), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StereoGeometryError(f"{field} is required")
    return value.strip()


def _validate_receipt(receipt: Mapping[str, Any]) -> None:
    if not isinstance(receipt, Mapping) or receipt.get("schema") != MAK_RECEIPT_SCHEMA:
        raise StereoGeometryError("MAK operation receipt schema is invalid")
    if receipt.get("available") is not True or receipt.get("read_only") is not True:
        raise StereoGeometryError("MAK operation receipt is not available read-only")
    source = receipt.get("source")
    operation = receipt.get("operation")
    provenance = receipt.get("provenance")
    control = receipt.get("control")
    if not all(isinstance(value, Mapping) for value in (source, operation, provenance, control)):
        raise StereoGeometryError("MAK operation receipt shape is invalid")
    if source.get("kind") != "grammar_lab_q610_artifact" or source.get("ref") != "grammar-lab:Q-610:artifact" or not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")):
        raise StereoGeometryError("MAK operation receipt source is invalid")
    if operation.get("name") != "expand_library_program" or operation.get("dialect") != "super-mario-feature-v1":
        raise StereoGeometryError("MAK operation receipt operation is outside the VIZZ context scope")
    keys = operation.get("expanded_keys")
    if not isinstance(keys, list) or any(not isinstance(key, str) or not key for key in keys) or operation.get("expanded_count") != len(keys):
        raise StereoGeometryError("MAK operation receipt expansion is invalid")
    for field in ("library_source_ref", "evaluation_source_ref"):
        _text(provenance.get(field), f"provenance.{field}")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance.get("package_sha256", "")):
        raise StereoGeometryError("MAK operation receipt package hash is invalid")
    if control != {
        "database_write": False,
        "decision_write": False,
        "selection_effect": "none",
        "promotion": "none",
        "publication": False,
        "semantic_equivalence_authorized": False,
    }:
        raise StereoGeometryError("MAK operation receipt control boundary is invalid")


def adapt_operation_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Accept structural provenance while keeping VIZZ metric authorization closed."""

    _validate_receipt(receipt)
    source = receipt["source"]
    operation = receipt["operation"]
    provenance = receipt["provenance"]
    result = {
        "schema": SCHEMA,
        "status": "CONTEXT_ACCEPTED_STRUCTURAL_ONLY",
        "source": {
            "schema": MAK_RECEIPT_SCHEMA,
            "ref": source["ref"],
            "sha256": source["sha256"],
        },
        "operation": {
            "name": operation["name"],
            "dialect": operation["dialect"],
            "expanded_count": operation["expanded_count"],
            "expanded_keys": list(operation["expanded_keys"]),
        },
        "provenance": {
            "library_source_ref": provenance["library_source_ref"],
            "evaluation_source_ref": provenance["evaluation_source_ref"],
            "package_sha256": provenance["package_sha256"],
        },
        "controls": {
            "metric_depth_authorized": False,
            "calibration_audit_required": True,
            "depth_publication": False,
            "network_contact": False,
            "semantic_equivalence_authorized": False,
        },
    }
    validate_operation_context(result)
    return result


def validate_operation_context(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA or payload.get("status") != "CONTEXT_ACCEPTED_STRUCTURAL_ONLY":
        raise StereoGeometryError("VIZZ operation context header is invalid")
    expected = {"schema", "status", "source", "operation", "provenance", "controls"}
    if set(payload) != expected:
        raise StereoGeometryError("VIZZ operation context fields are invalid")
    source = payload["source"]
    if set(source) != {"schema", "ref", "sha256"} or source["schema"] != MAK_RECEIPT_SCHEMA or source["ref"] != "grammar-lab:Q-610:artifact" or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise StereoGeometryError("VIZZ operation context source is invalid")
    operation = payload["operation"]
    if set(operation) != {"name", "dialect", "expanded_count", "expanded_keys"} or operation["name"] != "expand_library_program" or operation["dialect"] != "super-mario-feature-v1" or not isinstance(operation["expanded_keys"], list) or operation["expanded_count"] != len(operation["expanded_keys"]):
        raise StereoGeometryError("VIZZ operation context operation is invalid")
    provenance = payload["provenance"]
    if set(provenance) != {"library_source_ref", "evaluation_source_ref", "package_sha256"} or not all(isinstance(value, str) and value for value in provenance.values()) or not re.fullmatch(r"[0-9a-f]{64}", provenance["package_sha256"]):
        raise StereoGeometryError("VIZZ operation context provenance is invalid")
    if payload["controls"] != {
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
        "depth_publication": False,
        "network_contact": False,
        "semantic_equivalence_authorized": False,
    }:
        raise StereoGeometryError("VIZZ operation context controls are invalid")
    return True


def adapt_portfolio_direction_context(direction: Mapping[str, Any]) -> dict[str, Any]:
    """Carry MAK direction state into VIZZ without granting metric authority."""

    if not isinstance(direction, Mapping) or direction.get("schema") != MAK_DIRECTION_SCHEMA:
        raise StereoGeometryError("MAK portfolio direction schema is invalid")
    if direction.get("available") is not True or direction.get("read_only") is not True:
        raise StereoGeometryError("MAK portfolio direction is not available read-only")
    frame = direction.get("frame")
    control = direction.get("control")
    provenance = direction.get("provenance")
    if not all(isinstance(value, Mapping) for value in (frame, control, provenance)):
        raise StereoGeometryError("MAK portfolio direction shape is invalid")
    vision = frame.get("vision")
    order = frame.get("order")
    culture = frame.get("culture_computation")
    instrument = frame.get("instrument")
    if not all(isinstance(value, Mapping) for value in (vision, order, culture, instrument)):
        raise StereoGeometryError("MAK portfolio direction frame is invalid")
    if vision.get("semantic_claim_established") is not False or order.get("semantic_equivalence_established") is not False:
        raise StereoGeometryError("MAK portfolio direction carries an unauthorized semantic claim")
    if culture.get("relation_inference") is not False or instrument.get("measurement_claim_allowed") is not False:
        raise StereoGeometryError("MAK portfolio direction boundary is invalid")
    if control != {
        "database_write": False,
        "decision_write": False,
        "state_advance": False,
        "selection_effect": "none",
        "promotion": "none",
        "publication": False,
        "normalize_execution": False,
        "measurement_execution": False,
    }:
        raise StereoGeometryError("MAK portfolio direction controls are invalid")
    if provenance.get("semantic_claim") is not False or provenance.get("semantic_equivalence") is not False or provenance.get("learning_demonstrated") is not False:
        raise StereoGeometryError("MAK portfolio direction provenance boundary is invalid")
    result = {
        "schema": DIRECTION_CONTEXT_SCHEMA,
        "status": "CONTEXT_ACCEPTED_FAIL_CLOSED",
        "source": {
            "schema": MAK_DIRECTION_SCHEMA,
            "purpose": _text(direction.get("purpose"), "direction.purpose"),
            "direction_ids": [item["id"] for item in direction.get("directions", [])],
        },
        "states": {
            "vision": _text(vision.get("state"), "direction.frame.vision.state"),
            "order": _text(order.get("state"), "direction.frame.order.state"),
            "culture_computation": _text(culture.get("state"), "direction.frame.culture_computation.state"),
            "instrument": _text(instrument.get("state"), "direction.frame.instrument.state"),
        },
        "measurement": {
            "status": _text(instrument.get("measurement_status"), "direction.frame.instrument.measurement_status"),
            "unknown": instrument.get("measurement_unknown") is True,
            "claim_allowed": False,
        },
        "controls": {
            "metric_depth_authorized": False,
            "calibration_audit_required": True,
            "depth_publication": False,
            "publication": False,
            "semantic_equivalence_authorized": False,
            "domain_mix_authorized": False,
        },
        "provenance": {
            "mak_schema": MAK_DIRECTION_SCHEMA,
            "deterministic": provenance.get("deterministic") is True,
            "relation_inference": False,
            "semantic_claim": False,
            "semantic_equivalence": False,
            "learning_demonstrated": False,
        },
    }
    validate_portfolio_direction_context(result)
    return result


def validate_portfolio_direction_context(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != DIRECTION_CONTEXT_SCHEMA or payload.get("status") != "CONTEXT_ACCEPTED_FAIL_CLOSED":
        raise StereoGeometryError("VIZZ portfolio direction context header is invalid")
    expected = {"schema", "status", "source", "states", "measurement", "controls", "provenance"}
    if set(payload) != expected:
        raise StereoGeometryError("VIZZ portfolio direction context fields are invalid")
    source = payload["source"]
    if set(source) != {"schema", "purpose", "direction_ids"} or source["schema"] != MAK_DIRECTION_SCHEMA or source["purpose"] != "vision_order_culture_computation_read_only_frame" or source["direction_ids"] != ["vision", "order", "culture_computation"]:
        raise StereoGeometryError("VIZZ portfolio direction source is invalid")
    states = payload["states"]
    if set(states) != {"vision", "order", "culture_computation", "instrument"} or any(not isinstance(value, str) or not value for value in states.values()):
        raise StereoGeometryError("VIZZ portfolio direction states are invalid")
    measurement = payload["measurement"]
    if measurement != {"status": "unknown_measurement_refused", "unknown": True, "claim_allowed": False}:
        raise StereoGeometryError("VIZZ portfolio direction measurement boundary is invalid")
    if payload["controls"] != {
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
        "depth_publication": False,
        "publication": False,
        "semantic_equivalence_authorized": False,
        "domain_mix_authorized": False,
    }:
        raise StereoGeometryError("VIZZ portfolio direction controls are invalid")
    provenance = payload["provenance"]
    if provenance != {
        "mak_schema": MAK_DIRECTION_SCHEMA,
        "deterministic": True,
        "relation_inference": False,
        "semantic_claim": False,
        "semantic_equivalence": False,
        "learning_demonstrated": False,
    }:
        raise StereoGeometryError("VIZZ portfolio direction provenance is invalid")
    return True


def adapt_portfolio_work_preview(preview: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only the VIZZ calibration preview as non-executing context."""
    if not isinstance(preview, Mapping) or preview.get("schema") != MAK_WORK_PREVIEW_SCHEMA:
        raise StereoGeometryError("MAK work preview schema is invalid")
    if preview.get("available") is not True or preview.get("read_only") is not True or preview.get("preview_only") is not True:
        raise StereoGeometryError("MAK work preview is not read-only preview")
    source = preview.get("source")
    task = preview.get("task")
    control = preview.get("control")
    provenance = preview.get("provenance")
    if not all(isinstance(value, Mapping) for value in (source, task, control, provenance)):
        raise StereoGeometryError("MAK work preview shape is invalid")
    if source.get("task_id") != "vizz_calibration" or source.get("relation_status") not in {"unbound", "needs_evidence"}:
        raise StereoGeometryError("MAK work preview is outside the VIZZ calibration scope")
    if task.get("area") != "vizz/measurement" or task.get("layer") != "instrument" or task.get("state") != "vizz_measurement_refused" or task.get("human_gate") != "physical_calibration_evidence" or task.get("execution_allowed") is not False:
        raise StereoGeometryError("MAK VIZZ work preview boundary is invalid")
    if control != {
        "database_write": False,
        "decision_write": False,
        "state_advance": False,
        "selection_effect": "context_only",
        "promotion": "none",
        "publication": False,
        "normalize_execution": False,
        "measurement_execution": False,
    }:
        raise StereoGeometryError("MAK VIZZ work preview controls are invalid")
    if provenance.get("typed_relation_present") is not False or provenance.get("task_execution") is not False or provenance.get("semantic_claim") is not False or provenance.get("learning_demonstrated") is not False:
        raise StereoGeometryError("MAK VIZZ work preview provenance boundary is invalid")
    result = {
        "schema": VIZZ_WORK_PREVIEW_SCHEMA,
        "status": "PREVIEW_ACCEPTED_FAIL_CLOSED",
        "source": {
            "schema": MAK_WORK_PREVIEW_SCHEMA,
            "task_id": source["task_id"],
            "project_id": source["project_id"],
            "relation_status": source["relation_status"],
            "typed_relation_present": provenance["typed_relation_present"],
        },
        "task": {
            "area": task["area"],
            "layer": task["layer"],
            "state": task["state"],
            "human_gate": task["human_gate"],
            "execution_allowed": False,
        },
        "controls": {
            "calibration_evidence_required": True,
            "metric_depth_authorized": False,
            "measurement_execution": False,
            "depth_publication": False,
            "publication": False,
            "semantic_equivalence_authorized": False,
            "domain_mix_authorized": False,
        },
        "provenance": {
            "mak_schema": MAK_WORK_PREVIEW_SCHEMA,
            "deterministic": True,
            "preview_only": True,
            "task_execution": False,
            "semantic_claim": False,
            "learning_demonstrated": False,
        },
    }
    validate_portfolio_work_preview(result)
    return result


def validate_portfolio_work_preview(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != VIZZ_WORK_PREVIEW_SCHEMA or payload.get("status") != "PREVIEW_ACCEPTED_FAIL_CLOSED":
        raise StereoGeometryError("VIZZ work preview header is invalid")
    expected = {"schema", "status", "source", "task", "controls", "provenance"}
    if set(payload) != expected:
        raise StereoGeometryError("VIZZ work preview fields are invalid")
    source = payload["source"]
    if set(source) != {"schema", "task_id", "project_id", "relation_status", "typed_relation_present"} or source["schema"] != MAK_WORK_PREVIEW_SCHEMA or source["task_id"] != "vizz_calibration" or source["relation_status"] not in {"unbound", "needs_evidence"} or source["typed_relation_present"] is not False:
        raise StereoGeometryError("VIZZ work preview source is invalid")
    if source["project_id"] is not None and (not isinstance(source["project_id"], str) or not source["project_id"].strip()):
        raise StereoGeometryError("VIZZ work preview project id is invalid")
    if payload["task"] != {
        "area": "vizz/measurement",
        "layer": "instrument",
        "state": "vizz_measurement_refused",
        "human_gate": "physical_calibration_evidence",
        "execution_allowed": False,
    }:
        raise StereoGeometryError("VIZZ work preview task is invalid")
    if payload["controls"] != {
        "calibration_evidence_required": True,
        "metric_depth_authorized": False,
        "measurement_execution": False,
        "depth_publication": False,
        "publication": False,
        "semantic_equivalence_authorized": False,
        "domain_mix_authorized": False,
    }:
        raise StereoGeometryError("VIZZ work preview controls are invalid")
    if payload["provenance"] != {
        "mak_schema": MAK_WORK_PREVIEW_SCHEMA,
        "deterministic": True,
        "preview_only": True,
        "task_execution": False,
        "semantic_claim": False,
        "learning_demonstrated": False,
    }:
        raise StereoGeometryError("VIZZ work preview provenance is invalid")
    return True


def compose_operation_context_with_calibration(
    context: Mapping[str, Any], calibration_audit: Mapping[str, Any]
) -> dict[str, Any]:
    """Combine MAK context and calibration state without merging authorization."""

    validate_operation_context(context)
    validate_calibration_audit(dict(calibration_audit))
    result = {
        "schema": COMPOSED_SCHEMA,
        "status": "CONTEXT_COMPOSED_FAIL_CLOSED",
        "mak_context": {
            "schema": context["schema"],
            "ref": context["source"]["ref"],
            "sha256": context["source"]["sha256"],
            "operation": context["operation"]["name"],
            "dialect": context["operation"]["dialect"],
            "expanded_count": context["operation"]["expanded_count"],
        },
        "calibration": {
            "schema": calibration_audit["schema"],
            "status": calibration_audit["status"],
            "geometry_status": calibration_audit["geometry_status"],
            "evidence_scope": calibration_audit["evidence"]["scope"],
            "provenance_ref": calibration_audit["evidence"]["provenance_ref"],
            "audit_sha256": calibration_audit_sha256(calibration_audit),
            "calibration_audit_required": calibration_audit["calibration_audit_required"],
        },
        "controls": {
            "metric_depth_authorized": False,
            "calibration_audit_required": True,
            "depth_publication": False,
            "publication": False,
            "semantic_equivalence_authorized": False,
            "domain_mix_authorized": False,
        },
    }
    validate_composed_context(result)
    return result


def validate_composed_context(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != COMPOSED_SCHEMA or payload.get("status") != "CONTEXT_COMPOSED_FAIL_CLOSED":
        raise StereoGeometryError("VIZZ composed context header is invalid")
    expected = {"schema", "status", "mak_context", "calibration", "controls"}
    if set(payload) != expected:
        raise StereoGeometryError("VIZZ composed context fields are invalid")
    mak = payload["mak_context"]
    if set(mak) != {"schema", "ref", "sha256", "operation", "dialect", "expanded_count"} or mak["schema"] != SCHEMA or mak["ref"] != "grammar-lab:Q-610:artifact" or not re.fullmatch(r"[0-9a-f]{64}", mak["sha256"]) or mak["operation"] != "expand_library_program" or mak["dialect"] != "super-mario-feature-v1" or not isinstance(mak["expanded_count"], int) or mak["expanded_count"] < 0:
        raise StereoGeometryError("VIZZ composed MAK context is invalid")
    calibration = payload["calibration"]
    if set(calibration) != {"schema", "status", "geometry_status", "evidence_scope", "provenance_ref", "audit_sha256", "calibration_audit_required"} or calibration["schema"] != "vizz-calibration-audit-v1" or calibration["status"] not in {"CALIBRATION_EVIDENCE_REQUIRED", "CALIBRATION_REQUIRED"} or calibration["geometry_status"] not in {"METRIC_STEREO_READY", "CALIBRATION_REQUIRED"} or calibration["evidence_scope"] not in {"synthetic_only", "physical_calibration_required"} or (calibration["provenance_ref"] is not None and (not isinstance(calibration["provenance_ref"], str) or not calibration["provenance_ref"].strip())) or not re.fullmatch(r"[0-9a-f]{64}", calibration["audit_sha256"]) or calibration["calibration_audit_required"] is not True:
        raise StereoGeometryError("VIZZ composed calibration context is invalid")
    if payload["controls"] != {
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
        "depth_publication": False,
        "publication": False,
        "semantic_equivalence_authorized": False,
        "domain_mix_authorized": False,
    }:
        raise StereoGeometryError("VIZZ composed context controls are invalid")
    return True


__all__ = [
    "COMPOSED_SCHEMA",
    "DIRECTION_CONTEXT_SCHEMA",
    "MAK_WORK_PREVIEW_SCHEMA",
    "VIZZ_WORK_PREVIEW_SCHEMA",
    "MAK_DIRECTION_SCHEMA",
    "MAK_RECEIPT_SCHEMA",
    "SCHEMA",
    "adapt_portfolio_direction_context",
    "adapt_portfolio_work_preview",
    "adapt_operation_receipt",
    "calibration_audit_sha256",
    "compose_operation_context_with_calibration",
    "validate_composed_context",
    "validate_portfolio_direction_context",
    "validate_portfolio_work_preview",
    "validate_operation_context",
]
