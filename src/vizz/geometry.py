"""Camera-independent metric geometry for a calibrated two-camera rig.

This module deliberately starts after feature detection.  A detector supplies
corresponding image points; this kernel validates the rig, constructs rays,
triangulates points, and reports residuals.  It never treats an IR frame as a
depth map and never infers camera pose from a single image.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np


class StereoGeometryError(ValueError):
    """The rig or an observation cannot support a metric result."""


CALIBRATION_AUDIT_SCHEMA = "vizz-calibration-audit-v1"


def _finite_array(name: str, value: Any, shape: tuple[int, ...]) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise StereoGeometryError(f"{name} must be finite with shape {shape}")
    return array


def _unit(name: str, value: Sequence[float]) -> np.ndarray:
    vector = _finite_array(name, value, (3,))
    length = float(np.linalg.norm(vector))
    if length <= 1e-12:
        raise StereoGeometryError(f"{name} must be non-zero")
    return vector / length


@dataclass(frozen=True)
class CameraModel:
    """Pinhole camera expressed in a common world frame.

    `rotation_world_from_camera` maps camera-frame directions into world
    directions. `center_world` is the optical center in world coordinates.
    Image points must already be undistorted; distortion calibration is kept
    outside this minimal kernel so it cannot be silently ignored.
    """

    camera_id: str
    intrinsics: tuple[tuple[float, ...], ...]
    rotation_world_from_camera: tuple[tuple[float, ...], ...]
    center_world: tuple[float, float, float]

    def matrices(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not self.camera_id.strip():
            raise StereoGeometryError("camera_id is required")
        intrinsic = _finite_array("intrinsics", self.intrinsics, (3, 3))
        rotation = _finite_array("rotation_world_from_camera", self.rotation_world_from_camera, (3, 3))
        center = _finite_array("center_world", self.center_world, (3,))
        if abs(float(np.linalg.det(intrinsic))) <= 1e-12:
            raise StereoGeometryError("intrinsics must be invertible")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6):
            raise StereoGeometryError("rotation must be orthonormal")
        determinant = float(np.linalg.det(rotation))
        if not math.isclose(determinant, 1.0, abs_tol=1e-6):
            raise StereoGeometryError("rotation must preserve orientation")
        return intrinsic, rotation, center


@dataclass(frozen=True)
class StereoRig:
    """Two calibrated cameras with a shared metric coordinate system."""

    camera_a: CameraModel
    camera_b: CameraModel

    def validate(self) -> float:
        _, _, center_a = self.camera_a.matrices()
        _, _, center_b = self.camera_b.matrices()
        baseline = float(np.linalg.norm(center_b - center_a))
        if baseline <= 1e-9:
            raise StereoGeometryError("camera baseline must be positive")
        return baseline


@dataclass(frozen=True)
class ScreenPlane:
    """A flat screen expressed in the same world frame as the rig.

    `right_world` and `up_world` span the visible area from `origin_world`,
    so their lengths carry the screen extent and an intersection can be
    reported as a fraction of each edge. A curved or multi-monitor surface is
    not this: it needs its own model rather than a plane fitted silently.
    """

    screen_id: str
    origin_world: tuple[float, float, float]
    right_world: tuple[float, float, float]
    up_world: tuple[float, float, float]

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if not self.screen_id.strip():
            raise StereoGeometryError("screen_id is required")
        origin = _finite_array("origin_world", self.origin_world, (3,))
        right = _finite_array("right_world", self.right_world, (3,))
        up = _finite_array("up_world", self.up_world, (3,))
        if float(np.linalg.norm(right)) <= 1e-12 or float(np.linalg.norm(up)) <= 1e-12:
            raise StereoGeometryError("screen edges must be non-zero")
        normal = np.cross(right, up)
        if float(np.linalg.norm(normal)) <= 1e-12:
            raise StereoGeometryError("screen edges must not be parallel")
        return origin, right, up, normal / float(np.linalg.norm(normal))


def calibration_state(rig: StereoRig) -> dict[str, Any]:
    """Report whether a rig can support metric stereo, without raising.

    A caller deciding whether to show a distance at all needs this as a
    state, not as an exception: without intrinsics for both cameras and their
    relative pose the correct answer is `CALIBRATION_REQUIRED`, never a
    guessed depth.
    """

    try:
        baseline = rig.validate()
    except StereoGeometryError as exc:
        return {
            "status": "CALIBRATION_REQUIRED",
            "reason": str(exc),
            "camera_baseline_world": None,
            "metric_depth_authorized": False,
            "calibration_audit_required": True,
        }
    return {
        "status": "METRIC_STEREO_READY",
        "reason": None,
        "camera_baseline_world": baseline,
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
    }


def calibration_audit(
    rig: StereoRig,
    *,
    evidence_scope: str = "physical_calibration_required",
    provenance_ref: str | None = None,
) -> dict[str, Any]:
    """Separate valid model geometry from physical calibration evidence.

    A caller can supply numerically valid intrinsics and pose without having
    observed either camera in a calibration procedure. This report refuses to
    turn those parameters into permission to show metric depth. A future
    calibration pipeline may add a separately validated evidence record; this
    kernel has no such record today.

    ``evidence_scope`` is a declaration by the caller, never inferred from
    matrices, camera names or baseline. Synthetic fixtures must identify their
    source with ``provenance_ref``; the default keeps physical calibration
    required. Neither scope authorizes metric depth.
    """

    allowed_scopes = {"synthetic_only", "physical_calibration_required"}
    if evidence_scope not in allowed_scopes:
        raise StereoGeometryError("evidence_scope must be synthetic_only or physical_calibration_required")
    if provenance_ref is not None:
        if not isinstance(provenance_ref, str) or not provenance_ref.strip():
            raise StereoGeometryError("provenance_ref must be a non-empty string or None")
        provenance_ref = provenance_ref.strip()
    if evidence_scope == "synthetic_only" and provenance_ref is None:
        raise StereoGeometryError("synthetic_only requires provenance_ref")
    state = calibration_state(rig)
    geometry_ready = state["status"] == "METRIC_STEREO_READY"
    result = {
        "schema": CALIBRATION_AUDIT_SCHEMA,
        "status": "CALIBRATION_EVIDENCE_REQUIRED" if geometry_ready else "CALIBRATION_REQUIRED",
        "geometry_status": state["status"],
        "reason": (
            "model parameters are valid, but no physical calibration evidence was observed"
            if geometry_ready else state["reason"]
        ),
        "camera_baseline_world": state["camera_baseline_world"],
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
        "evidence": {
            "basis": "caller_supplied_camera_model",
            "scope": evidence_scope,
            "provenance_ref": provenance_ref,
            "physical_intrinsics_observed": False,
            "physical_pose_observed": False,
            "real_camera_calibration_claim": False,
        },
        "controls": {
            "frames_captured": False,
            "frames_stored": False,
            "network_contact": False,
            "depth_publication": False,
        },
    }
    validate_calibration_audit(result)
    return result


def validate_calibration_audit(payload: dict[str, Any]) -> bool:
    """Validate the evidence boundary without reading hardware or files."""

    if not isinstance(payload, dict) or payload.get("schema") != CALIBRATION_AUDIT_SCHEMA:
        raise StereoGeometryError("calibration audit schema is invalid")
    expected = {
        "schema", "status", "geometry_status", "reason", "camera_baseline_world",
        "metric_depth_authorized", "calibration_audit_required", "evidence", "controls",
    }
    if set(payload) != expected:
        raise StereoGeometryError("calibration audit fields are invalid")
    status = payload["status"]
    geometry_status = payload["geometry_status"]
    if geometry_status not in {"METRIC_STEREO_READY", "CALIBRATION_REQUIRED"}:
        raise StereoGeometryError("calibration audit geometry status is invalid")
    if status not in {"CALIBRATION_EVIDENCE_REQUIRED", "CALIBRATION_REQUIRED"}:
        raise StereoGeometryError("calibration audit status is invalid")
    baseline = payload["camera_baseline_world"]
    if geometry_status == "METRIC_STEREO_READY":
        if status != "CALIBRATION_EVIDENCE_REQUIRED" or not isinstance(baseline, (int, float)) or not math.isfinite(float(baseline)) or baseline <= 0:
            raise StereoGeometryError("calibration audit ready geometry is inconsistent")
    elif status != "CALIBRATION_REQUIRED" or baseline is not None:
        raise StereoGeometryError("calibration audit required geometry is inconsistent")
    if payload["metric_depth_authorized"] is not False or payload["calibration_audit_required"] is not True:
        raise StereoGeometryError("calibration audit authorization flags are invalid")
    evidence = payload["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {
        "basis", "scope", "provenance_ref", "physical_intrinsics_observed",
        "physical_pose_observed", "real_camera_calibration_claim",
    }:
        raise StereoGeometryError("calibration audit evidence is invalid")
    if evidence["basis"] != "caller_supplied_camera_model":
        raise StereoGeometryError("calibration audit evidence basis is invalid")
    if evidence["scope"] not in {"synthetic_only", "physical_calibration_required"}:
        raise StereoGeometryError("calibration audit evidence scope is invalid")
    provenance_ref = evidence["provenance_ref"]
    if provenance_ref is not None and (not isinstance(provenance_ref, str) or not provenance_ref.strip()):
        raise StereoGeometryError("calibration audit provenance is invalid")
    if evidence["scope"] == "synthetic_only" and provenance_ref is None:
        raise StereoGeometryError("synthetic_only requires provenance_ref")
    for field in ("physical_intrinsics_observed", "physical_pose_observed", "real_camera_calibration_claim"):
        if evidence[field] is not False:
            raise StereoGeometryError("calibration audit physical evidence is invalid")
    if payload["controls"] != {
        "frames_captured": False,
        "frames_stored": False,
        "network_contact": False,
        "depth_publication": False,
    }:
        raise StereoGeometryError("calibration audit controls are invalid")
    return True


def screen_plane_intersection(
    ray_origin: Sequence[float],
    ray_direction: Sequence[float],
    screen: ScreenPlane,
    *,
    require_inside: bool = False,
) -> dict[str, Any]:
    """Intersect one ray with a screen plane and report where it lands.

    The result carries the world point, the distance travelled along the ray
    and the position as a fraction of each screen edge. A ray parallel to the
    plane, or one whose intersection does not lie ahead of its own origin, is
    refused instead of being projected backwards onto the screen.

    `distance_along_ray` is reported, not constrained: an origin sitting on
    the plane yields a distance near zero rather than an error, because a
    minimum viewing distance is a property of a physical setup and not of
    this scale-free geometry. A caller that needs one should assert it.
    """

    origin = _finite_array("ray_origin", ray_origin, (3,))
    direction = _unit("ray_direction", ray_direction)
    screen_origin, right, up, normal = screen.basis()
    denominator = float(np.dot(direction, normal))
    if abs(denominator) <= 1e-12:
        raise StereoGeometryError("ray is parallel to the screen plane")
    distance = float(np.dot(screen_origin - origin, normal) / denominator)
    if distance <= 0.0:
        raise StereoGeometryError("screen plane does not lie ahead of the ray origin")
    point = origin + distance * direction
    offset = point - screen_origin
    horizontal = float(np.dot(offset, right) / np.dot(right, right))
    vertical = float(np.dot(offset, up) / np.dot(up, up))
    inside = 0.0 <= horizontal <= 1.0 and 0.0 <= vertical <= 1.0
    if require_inside and not inside:
        raise StereoGeometryError("intersection lies outside the screen bounds")
    return {
        "screen_id": screen.screen_id,
        "point_world": [float(value) for value in point],
        "distance_along_ray": distance,
        "screen_fraction": [horizontal, vertical],
        "inside_screen": inside,
        "status": "SCREEN_PLANE_INTERSECTION",
    }


def ray_from_pixel(camera: CameraModel, pixel: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """Return `(origin_world, unit_direction_world)` for an undistorted pixel."""

    if len(pixel) != 2:
        raise StereoGeometryError("pixel must have two coordinates")
    intrinsic, rotation, center = camera.matrices()
    homogeneous = np.array([float(pixel[0]), float(pixel[1]), 1.0], dtype=np.float64)
    if not np.all(np.isfinite(homogeneous)):
        raise StereoGeometryError("pixel must be finite")
    direction_camera = np.linalg.solve(intrinsic, homogeneous)
    direction_world = rotation @ direction_camera
    return center, _unit("ray direction", direction_world)


def triangulate_rays(
    ray_a: tuple[Sequence[float], Sequence[float]],
    ray_b: tuple[Sequence[float], Sequence[float]],
    *,
    max_residual: float | None = None,
    max_condition_number: float | None = None,
) -> dict[str, Any]:
    """Find the closest midpoint between two rays and report geometry quality.

    A small angle between the rays makes depth sensitive to tiny image or pose
    errors.  The condition number exposes that risk and an optional ceiling
    lets a caller refuse a result whose geometry is too poorly conditioned.
    """

    origin_a = _finite_array("ray_a origin", ray_a[0], (3,))
    direction_a = _unit("ray_a direction", ray_a[1])
    origin_b = _finite_array("ray_b origin", ray_b[0], (3,))
    direction_b = _unit("ray_b direction", ray_b[1])
    matrix = np.column_stack((direction_a, -direction_b))
    parameters, _, rank, _ = np.linalg.lstsq(matrix, origin_b - origin_a, rcond=None)
    if rank < 2:
        raise StereoGeometryError("rays are parallel or degenerate")
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    condition_number = float(singular_values[0] / singular_values[-1])
    if max_condition_number is not None:
        if not math.isfinite(max_condition_number) or max_condition_number <= 0.0:
            raise StereoGeometryError("max_condition_number must be finite and positive")
        if condition_number > max_condition_number:
            raise StereoGeometryError("ray condition number exceeds threshold")
    point_a = origin_a + parameters[0] * direction_a
    point_b = origin_b + parameters[1] * direction_b
    midpoint = (point_a + point_b) / 2.0
    residual = float(np.linalg.norm(point_a - point_b))
    if parameters[0] <= 0.0 or parameters[1] <= 0.0:
        raise StereoGeometryError("point lies behind one camera")
    if max_residual is not None and residual > max_residual:
        raise StereoGeometryError("ray residual exceeds threshold")
    angle = math.degrees(math.acos(float(np.clip(np.dot(direction_a, direction_b), -1.0, 1.0))))
    return {
        "point_world": [float(value) for value in midpoint],
        "depth_a": float(parameters[0]),
        "depth_b": float(parameters[1]),
        "ray_residual": residual,
        "ray_angle_deg": angle,
        "ray_condition_number": condition_number,
        "status": "METRIC_STEREO_POINT",
    }


def binocular_measurement(
    rig: StereoRig,
    eyes_a: dict[str, Sequence[float]],
    eyes_b: dict[str, Sequence[float]],
    *,
    max_residual: float | None = None,
    max_condition_number: float | None = None,
) -> dict[str, Any]:
    """Triangulate corresponding left/right eyes and measure 3-D separation."""

    baseline = rig.validate()
    required = {"left", "right"}
    if set(eyes_a) != required or set(eyes_b) != required:
        raise StereoGeometryError("both cameras must provide left and right eye points")
    points: dict[str, dict[str, Any]] = {}
    for eye in sorted(required):
        points[eye] = triangulate_rays(
            ray_from_pixel(rig.camera_a, eyes_a[eye]),
            ray_from_pixel(rig.camera_b, eyes_b[eye]),
            max_residual=max_residual,
            max_condition_number=max_condition_number,
        )
    left = np.asarray(points["left"]["point_world"], dtype=np.float64)
    right = np.asarray(points["right"]["point_world"], dtype=np.float64)
    midpoint = (left + right) / 2.0
    return {
        "left": points["left"],
        "right": points["right"],
        "eye_midpoint_world": [float(value) for value in midpoint],
        "interocular_distance_world": float(np.linalg.norm(right - left)),
        "camera_baseline_world": baseline,
        "metric_depth_authorized": False,
        "calibration_audit_required": True,
        "status": "BINOCULAR_MEASUREMENT",
    }
