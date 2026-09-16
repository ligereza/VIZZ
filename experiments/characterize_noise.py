#!/usr/bin/env python3
"""Bounded synthetic characterization of pixel perturbation and stereo baseline."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import StereoRig, ray_from_pixel, triangulate_rays  # noqa: E402

from synthetic_rig import camera  # noqa: E402

OUTPUT = Path(__file__).parents[1] / "results" / "noise-characterization-v1.json"


def estimate(rig: StereoRig, pixel_a: tuple[float, float], pixel_b: tuple[float, float], truth: np.ndarray) -> dict:
    ray_a = ray_from_pixel(rig.camera_a, pixel_a)
    ray_b = ray_from_pixel(rig.camera_b, pixel_b)
    result = triangulate_rays(ray_a, ray_b)
    point = np.asarray(result["point_world"], dtype=np.float64)
    return {
        "point_world": result["point_world"],
        "point_error_world": float(np.linalg.norm(point - truth)),
        "depth_a": result["depth_a"],
        "ray_residual": result["ray_residual"],
        "ray_angle_deg": result["ray_angle_deg"],
        "ray_condition_number": result["ray_condition_number"],
    }


def characterize() -> dict:
    truth = np.asarray((0.064, 0.0, 1.0), dtype=np.float64)
    baseline = StereoRig(camera("a", 0.0), camera("b", 0.2))
    clean_b = (211.2, 240.0)
    pixel_rows = []
    for delta in (0.0, 0.25, 0.5, 1.0):
        row = estimate(baseline, (371.2, 240.0), (clean_b[0] + delta, clean_b[1]), truth)
        pixel_rows.append({"pixel_delta_b_x": delta, **row})
    vertical_row = estimate(baseline, (371.2, 240.0), (clean_b[0], clean_b[1] + 0.5), truth)

    baseline_rows = []
    for distance in (0.2, 0.1, 0.02):
        rig = StereoRig(camera("a", 0.0), camera("b", distance))
        pixel_b_x = 320.0 - 800.0 * distance
        row = estimate(rig, (320.0, 240.0), (pixel_b_x, 240.0), np.asarray((0.0, 0.0, 1.0)))
        baseline_rows.append({"baseline_world": distance, **row})

    result = {
        "schema": "vizz-noise-characterization-v1",
        "scope": "synthetic_only",
        "truth": {"point_world": truth.tolist(), "intrinsics": "800px focal length, principal point (320,240)"},
        "pixel_perturbation": pixel_rows,
        "orthogonal_pixel_perturbation": {"pixel_delta_b_y": 0.5, **vertical_row},
        "baseline_sweep": baseline_rows,
        "findings": {
            "pixel_perturbation_changes_estimate": pixel_rows[0]["point_world"] != pixel_rows[-1]["point_world"],
            "residual_alone_can_be_small_under_coplanar_pixel_error": pixel_rows[-1]["ray_residual"] < 1e-10,
            "orthogonal_pixel_error_is_visible_in_residual": vertical_row["ray_residual"] > 1e-4,
            "shorter_baseline_increases_condition": baseline_rows[-1]["ray_condition_number"] > baseline_rows[0]["ray_condition_number"],
            "shorter_baseline_angle_decreases": baseline_rows[-1]["ray_angle_deg"] < baseline_rows[0]["ray_angle_deg"],
            "real_camera_calibration_claim": False,
        },
        "limitations": [
            "The sweep uses exact synthetic cameras and a deterministic pixel perturbation; it is not a camera-noise distribution.",
            "Residual can remain near zero for coplanar horizontal pixel error, so residual and condition must be read together.",
            "Threshold selection remains a rig-level policy and is not inferred from this fixture.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(characterize(), ensure_ascii=False, indent=2))
