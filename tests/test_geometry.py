import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import (  # noqa: E402
    CameraModel,
    StereoGeometryError,
    StereoRig,
    binocular_measurement,
)


def camera(camera_id, center):
    return CameraModel(
        camera_id=camera_id,
        intrinsics=((800.0, 0.0, 320.0), (0.0, 800.0, 240.0), (0.0, 0.0, 1.0)),
        rotation_world_from_camera=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        center_world=tuple(center),
    )


class VIZZGeometryTests(unittest.TestCase):
    def test_triangulates_two_eyes_in_common_world_frame(self):
        rig = StereoRig(camera("webcam", (0.0, 0.0, 0.0)), camera("ir", (0.2, 0.0, 0.0)))
        result = binocular_measurement(
            rig,
            eyes_a={"left": (320.0, 240.0), "right": (371.2, 240.0)},
            eyes_b={"left": (160.0, 240.0), "right": (211.2, 240.0)},
            max_residual=1e-8,
        )
        np.testing.assert_allclose(result["left"]["point_world"], (0.0, 0.0, 1.0), atol=1e-6)
        np.testing.assert_allclose(result["right"]["point_world"], (0.064, 0.0, 1.0), atol=1e-6)
        self.assertAlmostEqual(result["interocular_distance_world"], 0.064, places=6)
        self.assertEqual(result["status"], "BINOCULAR_MEASUREMENT")

    def test_coincident_cameras_are_rejected(self):
        rig = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.0, 0.0, 0.0)))
        with self.assertRaises(StereoGeometryError):
            rig.validate()

    def test_invalid_rotation_is_rejected(self):
        invalid = CameraModel(
            "bad",
            ((800.0, 0.0, 320.0), (0.0, 800.0, 240.0), (0.0, 0.0, 1.0)),
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)),
            (0.0, 0.0, 0.0),
        )
        with self.assertRaises(StereoGeometryError):
            invalid.matrices()


if __name__ == "__main__":
    unittest.main()
