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
) -> dict[str, Any]:
    """Find the closest midpoint between two rays and report geometry quality."""

    origin_a = _finite_array("ray_a origin", ray_a[0], (3,))
    direction_a = _unit("ray_a direction", ray_a[1])
    origin_b = _finite_array("ray_b origin", ray_b[0], (3,))
    direction_b = _unit("ray_b direction", ray_b[1])
    matrix = np.column_stack((direction_a, -direction_b))
    parameters, _, rank, _ = np.linalg.lstsq(matrix, origin_b - origin_a, rcond=None)
    if rank < 2:
        raise StereoGeometryError("rays are parallel or degenerate")
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
        "status": "METRIC_STEREO_POINT",
    }


def binocular_measurement(
    rig: StereoRig,
    eyes_a: dict[str, Sequence[float]],
    eyes_b: dict[str, Sequence[float]],
    *,
    max_residual: float | None = None,
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
        "status": "BINOCULAR_MEASUREMENT",
    }
