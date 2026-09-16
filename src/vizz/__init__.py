"""Auditable dual-camera geometry primitives."""

from .geometry import (
    CameraModel,
    ScreenPlane,
    StereoRig,
    StereoGeometryError,
    binocular_measurement,
    calibration_audit,
    calibration_state,
    validate_calibration_audit,
    ray_from_pixel,
    screen_plane_intersection,
    triangulate_rays,
)
from .operation_context import (
    adapt_portfolio_direction_context,
    adapt_operation_receipt,
    adapt_portfolio_work_preview,
    calibration_audit_sha256,
    compose_operation_context_with_calibration,
    validate_composed_context,
    validate_operation_context,
    validate_portfolio_direction_context,
    validate_portfolio_work_preview,
)
from .measurement_gate import evaluate_measurement_request, validate_measurement_gate
from .portfolio_context import (
    adapt_portfolio_read_only_context,
    evaluate_portfolio_measurement_request,
    validate_portfolio_measurement_gate,
    validate_portfolio_read_only_context,
)

__all__ = [
    "CameraModel",
    "ScreenPlane",
    "StereoRig",
    "StereoGeometryError",
    "binocular_measurement",
    "calibration_audit",
    "calibration_state",
    "validate_calibration_audit",
    "ray_from_pixel",
    "screen_plane_intersection",
    "triangulate_rays",
    "adapt_portfolio_direction_context",
    "adapt_operation_receipt",
    "adapt_portfolio_work_preview",
    "calibration_audit_sha256",
    "compose_operation_context_with_calibration",
    "validate_composed_context",
    "validate_operation_context",
    "validate_portfolio_direction_context",
    "validate_portfolio_work_preview",
    "evaluate_measurement_request",
    "validate_measurement_gate",
    "adapt_portfolio_read_only_context",
    "evaluate_portfolio_measurement_request",
    "validate_portfolio_measurement_gate",
    "validate_portfolio_read_only_context",
]
