#!/usr/bin/env python3
"""Deterministic synthetic distribution for VIZZ calibration/noise sensitivity."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import ray_from_pixel, triangulate_rays  # noqa: E402

from synthetic_rig import camera, project  # noqa: E402

OUTPUT = Path(__file__).parents[1] / "results" / "distribution-characterization-v1.json"


def run() -> dict:
    seed = 20260913
    sample_count = 100
    rng = np.random.default_rng(seed)
    truth = np.asarray((0.064, 0.05, 1.0), dtype=np.float64)
    true_a, true_b = camera("true-a", 0.0), camera("true-b", 0.2)
    clean_a, clean_b = project(true_a, truth), project(true_b, truth)
    rows = []
    failures = []
    for index in range(sample_count):
        pixel_noise = rng.normal(0.0, 0.2, size=4)
        focal_scale = 1.0 + float(rng.normal(0.0, 0.002))
        yaw_deg = float(rng.normal(0.0, 0.1))
        estimated_b = camera(f"estimated-b-{index}", 0.2, focal_scale=focal_scale, yaw_deg=yaw_deg)
        pixels_a = (clean_a[0] + float(pixel_noise[0]), clean_a[1] + float(pixel_noise[1]))
        pixels_b = (clean_b[0] + float(pixel_noise[2]), clean_b[1] + float(pixel_noise[3]))
        try:
            result = triangulate_rays((ray_from_pixel(true_a, pixels_a)), (ray_from_pixel(estimated_b, pixels_b)))
        except Exception as exc:  # a failure is a measured fail-closed outcome
            failures.append({"index": index, "error": type(exc).__name__})
            continue
        point = np.asarray(result["point_world"], dtype=np.float64)
        rows.append({
            "index": index,
            "point_error_world": float(np.linalg.norm(point - truth)),
            "ray_residual": result["ray_residual"],
            "ray_condition_number": result["ray_condition_number"],
            "pixel_noise_rms": float(np.linalg.norm(pixel_noise) / 2.0),
            "focal_scale": focal_scale,
            "yaw_deg": yaw_deg,
        })

    def stats(field: str) -> dict:
        values = np.asarray([row[field] for row in rows], dtype=np.float64)
        return {"min": float(np.min(values)), "median": float(np.quantile(values, 0.5)), "p95": float(np.quantile(values, 0.95)), "max": float(np.max(values))}

    result = {
        "schema": "vizz-distribution-characterization-v1",
        "scope": "synthetic_only",
        "sampling": {"seed": seed, "requested": sample_count, "succeeded": len(rows), "failed_closed": len(failures), "pixel_noise_sigma_px": 0.2, "focal_sigma_fraction": 0.002, "yaw_sigma_deg": 0.1},
        "truth": {"point_world": truth.tolist(), "baseline_world": 0.2, "pixel_a": clean_a, "pixel_b": clean_b},
        "statistics": {field: stats(field) for field in ("point_error_world", "ray_residual", "ray_condition_number")},
        "failures": failures,
        "findings": {
            "all_samples_accounted_for": len(rows) + len(failures) == sample_count,
            "finite_statistics": all(math.isfinite(value) for field in ("point_error_world", "ray_residual", "ray_condition_number") for value in stats(field).values()),
            "error_distribution_nonzero": stats("point_error_world")["p95"] > 0.0,
            "condition_distribution_reported": stats("ray_condition_number")["p95"] >= stats("ray_condition_number")["median"],
            "real_camera_calibration_claim": False,
        },
        "limitations": [
            "The distribution is seeded synthetic noise plus calibration perturbation, not a measured camera error distribution.",
            "The p95 values describe this fixture only and are not production thresholds.",
            "No semantic or ophthalmological interpretation is made.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
