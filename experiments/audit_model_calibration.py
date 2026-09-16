"""Emit a bounded audit for a caller-supplied synthetic camera model."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import StereoRig, calibration_audit, validate_calibration_audit  # noqa: E402

from synthetic_rig import camera  # noqa: E402


def main() -> None:
    rig = StereoRig(
        camera("synthetic-a", 0.0),
        camera("synthetic-b", 0.2),
    )
    result = calibration_audit(
        rig,
        evidence_scope="synthetic_only",
        provenance_ref="experiments/audit_model_calibration.py",
    )
    destination = Path(__file__).parents[1] / "results" / "calibration-audit-v1.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    validate_calibration_audit(json.loads(destination.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
