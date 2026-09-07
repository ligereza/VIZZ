import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from vizz import (  # noqa: E402
    CameraModel,
    ScreenPlane,
    StereoGeometryError,
    StereoRig,
    binocular_measurement,
    calibration_state,
    screen_plane_intersection,
)


def screen():
    return ScreenPlane(
        screen_id="monitor",
        origin_world=(-0.3, -0.2, 1.0),
        right_world=(0.6, 0.0, 0.0),
        up_world=(0.0, 0.4, 0.0),
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

    def test_uncalibrated_rig_reports_calibration_required(self):
        coincident = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.0, 0.0, 0.0)))
        state = calibration_state(coincident)
        self.assertEqual(state["status"], "CALIBRATION_REQUIRED")
        self.assertIsNone(state["camera_baseline_world"])

    def test_calibrated_rig_reports_metric_ready_with_baseline(self):
        rig = StereoRig(camera("webcam", (0.0, 0.0, 0.0)), camera("ir", (0.2, 0.0, 0.0)))
        state = calibration_state(rig)
        self.assertEqual(state["status"], "METRIC_STEREO_READY")
        self.assertAlmostEqual(state["camera_baseline_world"], 0.2, places=9)

    def test_ray_meets_screen_centre(self):
        result = screen_plane_intersection((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), screen())
        np.testing.assert_allclose(result["point_world"], (0.0, 0.0, 1.0), atol=1e-9)
        self.assertAlmostEqual(result["distance_along_ray"], 1.0, places=9)
        np.testing.assert_allclose(result["screen_fraction"], (0.5, 0.5), atol=1e-9)
        self.assertTrue(result["inside_screen"])
        self.assertEqual(result["status"], "SCREEN_PLANE_INTERSECTION")

    def test_ray_past_the_edge_is_located_but_not_inside(self):
        result = screen_plane_intersection((0.0, 0.0, 0.0), (0.5, 0.0, 1.0), screen())
        self.assertGreater(result["screen_fraction"][0], 1.0)
        self.assertFalse(result["inside_screen"])
        with self.assertRaises(StereoGeometryError):
            screen_plane_intersection((0.0, 0.0, 0.0), (0.5, 0.0, 1.0), screen(), require_inside=True)

    def test_parallel_and_backward_rays_are_refused(self):
        with self.assertRaises(StereoGeometryError):
            screen_plane_intersection((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), screen())
        with self.assertRaises(StereoGeometryError):
            screen_plane_intersection((0.0, 0.0, 0.0), (0.0, 0.0, -1.0), screen())

    def test_origin_on_the_plane_is_refused_not_projected(self):
        with self.assertRaises(StereoGeometryError):
            screen_plane_intersection((0.0, 0.0, 1.0), (0.0, 0.0, 1.0), screen())

    def test_degenerate_screen_is_refused(self):
        collapsed = ScreenPlane("flat", (0.0, 0.0, 1.0), (0.6, 0.0, 0.0), (0.6, 0.0, 0.0))
        with self.assertRaises(StereoGeometryError):
            screen_plane_intersection((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), collapsed)


if __name__ == "__main__":
    unittest.main()
