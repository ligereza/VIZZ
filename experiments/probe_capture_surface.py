#!/usr/bin/env python3
"""Record camera-node presence and capabilities without capturing frames."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "results" / "capture-surface-probe-v1.json"


def probe(path: Path) -> dict:
    name_path = Path("/sys/class/video4linux") / path.name / "name"
    try:
        name = name_path.read_text(encoding="utf-8").strip()
    except OSError:
        name = None
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "v4l2", "-list_formats", "all", "-i", str(path)],
            capture_output=True, text=True, timeout=8, check=False,
        )
        output = result.stdout + result.stderr
        formats = [line.strip() for line in output.splitlines() if "Compressed:" in line or "Raw       :" in line]
        return {"path": str(path), "sysfs_name": name, "probe_exit_code": result.returncode, "capabilities_listed": bool(formats), "formats": formats}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"path": str(path), "sysfs_name": name, "probe_error": type(exc).__name__, "capabilities_listed": False, "formats": []}


def run() -> dict:
    nodes = sorted(Path("/dev").glob("video*"))
    result = {
        "schema": "vizz-capture-surface-probe-v1",
        "scope": "capability_listing_only",
        "nodes": [probe(path) for path in nodes if path.is_char_device()],
        "calibration_state": "CALIBRATION_REQUIRED",
        "controls": {"frames_captured": False, "frames_stored": False, "network_contact": False, "intrinsics_observed": False, "pose_observed": False},
        "findings": {
            "video_nodes_present": bool(nodes),
            "capabilities_listed_without_frames": True,
            "calibration_data_available": False,
            "metric_depth_authorized": False,
        },
        "limitations": [
            "Device presence and advertised formats do not provide camera intrinsics or stereo pose.",
            "Both nodes may belong to one physical webcam; node count is not camera count.",
            "No frame was captured or stored by this probe.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
