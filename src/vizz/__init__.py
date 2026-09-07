"""Auditable dual-camera geometry primitives."""

from .geometry import (
    CameraModel,
    ScreenPlane,
    StereoRig,
    StereoGeometryError,
    binocular_measurement,
    calibration_state,
    ray_from_pixel,
    screen_plane_intersection,
    triangulate_rays,
)

__all__ = [
    "CameraModel",
    "ScreenPlane",
    "StereoRig",
    "StereoGeometryError",
    "binocular_measurement",
    "calibration_state",
    "ray_from_pixel",
    "screen_plane_intersection",
    "triangulate_rays",
]
