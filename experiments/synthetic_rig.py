"""Shared synthetic camera fixture for bounded VIZZ experiments.

The experiments measure different questions, but they must not silently drift
to different camera conventions.  This helper owns the common rig constants,
camera construction and projection math; each experiment still owns its
sampling and interpretation.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import CameraModel  # noqa: E402


IDENTITY = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)
INTRINSICS = (
    (800.0, 0.0, 320.0),
    (0.0, 800.0, 240.0),
    (0.0, 0.0, 1.0),
)


def camera(
    camera_id: str,
    center_x: float,
    *,
    intrinsics=INTRINSICS,
    rotation=IDENTITY,
    focal_scale: float = 1.0,
    yaw_deg: float = 0.0,
) -> CameraModel:
    """Build the common axis-aligned camera, optionally with known perturbations."""

    if focal_scale != 1.0:
        focal = 800.0 * focal_scale
        intrinsics = (
            (focal, 0.0, 320.0),
            (0.0, focal, 240.0),
            (0.0, 0.0, 1.0),
        )
    if yaw_deg:
        angle = math.radians(yaw_deg)
        rotation = (
            (math.cos(angle), 0.0, math.sin(angle)),
            (0.0, 1.0, 0.0),
            (-math.sin(angle), 0.0, math.cos(angle)),
        )
    return CameraModel(camera_id, intrinsics, rotation, (center_x, 0.0, 0.0))


def project(camera_model: CameraModel, point: np.ndarray) -> tuple[float, float]:
    """Project one world point using the same convention as the kernel."""

    intrinsics, rotation, center = camera_model.matrices()
    camera_point = rotation.T @ (point - center)
    homogeneous = intrinsics @ camera_point
    return float(homogeneous[0] / homogeneous[2]), float(homogeneous[1] / homogeneous[2])
