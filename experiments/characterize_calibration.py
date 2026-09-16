#!/usr/bin/env python3
"""Bounded synthetic characterization of calibration error in VIZZ."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import CameraModel, ray_from_pixel, triangulate_rays  # noqa: E402

from synthetic_rig import camera, project  # noqa: E402

OUTPUT = Path(__file__).parents[1] / "results" / "calibration-characterization-v1.json"


def estimate(camera_a: CameraModel, camera_b: CameraModel, pixel_a: tuple[float, float], pixel_b: tuple[float, float], truth: np.ndarray) -> dict:
    result = triangulate_rays(ray_from_pixel(camera_a, pixel_a), ray_from_pixel(camera_b, pixel_b))
    point = np.asarray(result["point_world"], dtype=np.float64)
    return {
        "point_world": result["point_world"],
        "point_error_world": float(np.linalg.norm(point - truth)),
        "ray_residual": result["ray_residual"],
        "ray_angle_deg": result["ray_angle_deg"],
        "ray_condition_number": result["ray_condition_number"],
    }


def characterize() -> dict:
    truth = np.asarray((0.064, 0.05, 1.0), dtype=np.float64)
    true_a, true_b = camera("true-a", 0.0), camera("true-b", 0.2)
    pixel_a, pixel_b = project(true_a, truth), project(true_b, truth)
    clean = estimate(true_a, true_b, pixel_a, pixel_b, truth)
    focal_b = camera("estimated-b-focal", 0.2, focal_scale=1.01)
    pose_b = camera("estimated-b-pose", 0.2, yaw_deg=0.5)
    rows = {
        "clean": clean,
        "focal_length_plus_1_percent": estimate(true_a, focal_b, pixel_a, pixel_b, truth),
        "camera_b_yaw_plus_0_5_deg": estimate(true_a, pose_b, pixel_a, pixel_b, truth),
    }
    result = {
        "schema": "vizz-calibration-characterization-v1",
        "scope": "synthetic_only",
        "truth": {"point_world": truth.tolist(), "true_baseline_world": 0.2, "pixel_a": pixel_a, "pixel_b": pixel_b},
        "estimates": rows,
        "findings": {
            "focal_error_changes_point": rows["focal_length_plus_1_percent"]["point_error_world"] > rows["clean"]["point_error_world"] + 1e-4,
            "pose_error_changes_point": rows["camera_b_yaw_plus_0_5_deg"]["point_error_world"] > rows["clean"]["point_error_world"] + 1e-4,
            "clean_residual_is_near_zero": rows["clean"]["ray_residual"] < 1e-10,
            "calibration_error_not_hidden": rows["focal_length_plus_1_percent"]["point_error_world"] > 1e-4 and rows["camera_b_yaw_plus_0_5_deg"]["point_error_world"] > 1e-4,
            "real_camera_calibration_claim": False,
        },
        "limitations": [
            "The true cameras and observations are synthetic; this does not estimate a real rig's calibration uncertainty.",
            "The perturbations are one focal-length and one yaw fixture, not a statistical error model.",
            "Threshold selection remains a rig-level policy and is not inferred from this report.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(characterize(), ensure_ascii=False, indent=2))
