"""Auditable dual-camera geometry primitives."""

from .geometry import (
    CameraModel,
    StereoRig,
    StereoGeometryError,
    binocular_measurement,
    ray_from_pixel,
    triangulate_rays,
)

__all__ = [
    "CameraModel",
    "StereoRig",
    "StereoGeometryError",
    "binocular_measurement",
    "ray_from_pixel",
    "triangulate_rays",
]
