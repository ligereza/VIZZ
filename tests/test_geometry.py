import sys
import copy
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
    calibration_audit,
    calibration_state,
    validate_calibration_audit,
    ray_from_pixel,
    screen_plane_intersection,
    triangulate_rays,
    adapt_operation_receipt,
    compose_operation_context_with_calibration,
    evaluate_measurement_request,
    validate_composed_context,
    validate_measurement_gate,
    validate_operation_context,
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
    def operation_receipt(self):
        return {
            "schema": "mak-operation-receipt-v1",
            "available": True,
            "read_only": True,
            "source": {
                "kind": "grammar_lab_q610_artifact",
                "ref": "grammar-lab:Q-610:artifact",
                "sha256": "a" * 64,
            },
            "operation": {
                "name": "expand_library_program",
                "dialect": "super-mario-feature-v1",
                "expanded_count": 2,
                "expanded_keys": ["enemyOnScreen", "gapBelow"],
                "execution_reason": "declared_operation_executed",
            },
            "provenance": {
                "library_source_ref": "b" * 40 + ":features.py",
                "evaluation_source_ref": "c" * 40 + ":src/features.py",
                "package_sha256": "d" * 64,
            },
            "control": {
                "database_write": False,
                "decision_write": False,
                "selection_effect": "none",
                "promotion": "none",
                "publication": False,
                "semantic_equivalence_authorized": False,
            },
        }

    def test_mak_operation_receipt_becomes_bounded_vizz_context(self):
        context = adapt_operation_receipt(self.operation_receipt())

        self.assertEqual(context["schema"], "vizz-operation-context-v1")
        self.assertEqual(context["operation"]["expanded_count"], 2)
        self.assertTrue(validate_operation_context(context))
        self.assertFalse(context["controls"]["metric_depth_authorized"])
        self.assertTrue(context["controls"]["calibration_audit_required"])
        self.assertFalse(context["controls"]["semantic_equivalence_authorized"])

    def test_vizz_rejects_operation_receipt_with_promotion_enabled(self):
        tampered = copy.deepcopy(self.operation_receipt())
        tampered["control"]["promotion"] = "publish"

        with self.assertRaisesRegex(StereoGeometryError, "control boundary"):
            adapt_operation_receipt(tampered)

    def test_vizz_rejects_operation_receipt_from_another_dialect(self):
        tampered = copy.deepcopy(self.operation_receipt())
        tampered["operation"]["dialect"] = "semantic-icons-v1"

        with self.assertRaisesRegex(StereoGeometryError, "outside the VIZZ context scope"):
            adapt_operation_receipt(tampered)

    def test_vizz_composes_mak_context_with_calibration_without_opening_gates(self):
        context = adapt_operation_receipt(self.operation_receipt())
        audit = calibration_audit(StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0))))

        composed = compose_operation_context_with_calibration(context, audit)

        self.assertEqual(composed["schema"], "vizz-composed-context-v1")
        self.assertEqual(composed["mak_context"]["expanded_count"], 2)
        self.assertEqual(composed["calibration"]["status"], "CALIBRATION_EVIDENCE_REQUIRED")
        self.assertTrue(validate_composed_context(composed))
        self.assertFalse(composed["controls"]["metric_depth_authorized"])
        self.assertFalse(composed["controls"]["publication"])
        self.assertFalse(composed["controls"]["domain_mix_authorized"])

    def test_vizz_composition_rejects_tampered_calibration_authorization(self):
        context = adapt_operation_receipt(self.operation_receipt())
        audit = calibration_audit(StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0))))
        tampered = copy.deepcopy(audit)
        tampered["metric_depth_authorized"] = True

        with self.assertRaisesRegex(StereoGeometryError, "authorization flags"):
            compose_operation_context_with_calibration(context, tampered)

    def test_measurement_gate_refuses_metric_depth_before_triangulation(self):
        context = adapt_operation_receipt(self.operation_receipt())
        audit = calibration_audit(StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0))))
        composed = compose_operation_context_with_calibration(context, audit)

        result = evaluate_measurement_request(
            composed,
            audit,
            {"operation": "binocular_measurement", "eyes_a": {"left": (320.0, 240.0)}, "eyes_b": {"left": (160.0, 240.0)}},
        )

        self.assertEqual(result["status"], "MEASUREMENT_REFUSED")
        self.assertFalse(result["execution"]["triangulation_attempted"])
        self.assertIsNone(result["execution"]["depth_result"])
        self.assertFalse(result["controls"]["metric_depth_authorized"])
        self.assertTrue(validate_measurement_gate(result))

    def test_measurement_gate_rejects_context_that_attempts_metric_authorization(self):
        context = adapt_operation_receipt(self.operation_receipt())
        audit = calibration_audit(StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0))))
        composed = compose_operation_context_with_calibration(context, audit)
        composed["controls"]["metric_depth_authorized"] = True

        with self.assertRaisesRegex(StereoGeometryError, "composed context controls"):
            evaluate_measurement_request(composed, audit, {"operation": "binocular_measurement"})

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
        self.assertGreater(result["left"]["ray_condition_number"], 1.0)

    def test_condition_number_can_refuse_nearly_parallel_rays(self):
        result = triangulate_rays(
            ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            ((0.2, 0.0, 0.0), (-0.000001, 0.0, 1.0)),
        )
        self.assertGreater(result["ray_condition_number"], 1_000.0)
        with self.assertRaisesRegex(StereoGeometryError, "condition number"):
            triangulate_rays(
                ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
                ((0.2, 0.0, 0.0), (-0.000001, 0.0, 1.0)),
                max_condition_number=1_000.0,
            )

    def test_condition_number_threshold_must_be_positive_and_finite(self):
        with self.assertRaisesRegex(StereoGeometryError, "max_condition_number"):
            triangulate_rays(
                ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
                ((0.2, 0.0, 0.0), (0.1, 0.0, 1.0)),
                max_condition_number=0.0,
            )

    def test_pixel_to_screen_composition_is_exact_and_fail_closed(self):
        rig = StereoRig(camera("webcam", (0.0, 0.0, 0.0)), camera("ir", (0.2, 0.0, 0.0)))
        origin_a, direction_a = ray_from_pixel(rig.camera_a, (400.0, 280.0))
        origin_b, direction_b = ray_from_pixel(rig.camera_b, (240.0, 280.0))
        point = triangulate_rays((origin_a, direction_a), (origin_b, direction_b), max_residual=1e-8)
        triangulated_direction = np.asarray(point["point_world"]) - origin_a
        landing = screen_plane_intersection(origin_a, triangulated_direction, screen(), require_inside=True)

        np.testing.assert_allclose(point["point_world"], landing["point_world"], atol=1e-6)
        np.testing.assert_allclose(landing["screen_fraction"], (2.0 / 3.0, 5.0 / 8.0), atol=1e-6)
        self.assertEqual(point["status"], "METRIC_STEREO_POINT")
        self.assertEqual(landing["status"], "SCREEN_PLANE_INTERSECTION")

        with self.assertRaisesRegex(StereoGeometryError, "condition number"):
            triangulate_rays(
                ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
                ((0.2, 0.0, 0.0), (-0.000001, 0.0, 1.0)),
                max_condition_number=1_000.0,
            )
        with self.assertRaisesRegex(StereoGeometryError, "residual"):
            triangulate_rays(
                ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
                ((0.2, 0.2, 0.0), (-0.1, 0.0, 1.0)),
                max_residual=0.05,
            )

    def test_pixel_perturbation_changes_depth_without_being_hidden(self):
        rig = StereoRig(camera("webcam", (0.0, 0.0, 0.0)), camera("ir", (0.2, 0.0, 0.0)))
        origin_a, direction_a = ray_from_pixel(rig.camera_a, (371.2, 240.0))
        depths = []
        residuals = []
        for pixel_x in (211.2, 211.45, 211.7):
            origin_b, direction_b = ray_from_pixel(rig.camera_b, (pixel_x, 240.0))
            result = triangulate_rays((origin_a, direction_a), (origin_b, direction_b))
            depths.append(result["depth_a"])
            residuals.append(result["ray_residual"])

        self.assertAlmostEqual(depths[0], (1.0 + 0.064**2) ** 0.5, places=9)
        self.assertNotEqual(depths[0], depths[1])
        self.assertNotEqual(depths[1], depths[2])
        self.assertTrue(all(residual >= 0.0 for residual in residuals))
        self.assertTrue(all(isinstance(residual, float) for residual in residuals))

    def test_shorter_baseline_exposes_worse_ray_conditioning(self):
        long_baseline = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0)))
        short_baseline = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.02, 0.0, 0.0)))
        long_a = ray_from_pixel(long_baseline.camera_a, (320.0, 240.0))
        long_b = ray_from_pixel(long_baseline.camera_b, (160.0, 240.0))
        short_a = ray_from_pixel(short_baseline.camera_a, (320.0, 240.0))
        short_b = ray_from_pixel(short_baseline.camera_b, (304.0, 240.0))

        long_result = triangulate_rays(long_a, long_b)
        short_result = triangulate_rays(short_a, short_b)

        self.assertGreater(short_result["ray_condition_number"], long_result["ray_condition_number"])
        self.assertGreater(short_result["ray_angle_deg"], 0.0)
        self.assertGreater(long_result["ray_angle_deg"], short_result["ray_angle_deg"])

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
        self.assertFalse(state["metric_depth_authorized"])
        self.assertTrue(state["calibration_audit_required"])

    def test_calibration_audit_does_not_authorize_model_only_depth(self):
        rig = StereoRig(camera("webcam", (0.0, 0.0, 0.0)), camera("ir", (0.2, 0.0, 0.0)))
        audit = calibration_audit(rig)

        self.assertEqual(audit["schema"], "vizz-calibration-audit-v1")
        self.assertEqual(audit["status"], "CALIBRATION_EVIDENCE_REQUIRED")
        self.assertEqual(audit["geometry_status"], "METRIC_STEREO_READY")
        self.assertFalse(audit["metric_depth_authorized"])
        self.assertFalse(audit["evidence"]["real_camera_calibration_claim"])
        self.assertEqual(audit["evidence"]["scope"], "physical_calibration_required")
        self.assertIsNone(audit["evidence"]["provenance_ref"])
        self.assertFalse(audit["controls"]["depth_publication"])

    def test_binocular_measurement_marks_model_values_as_not_authorized_depth(self):
        rig = StereoRig(camera("webcam", (0.0, 0.0, 0.0)), camera("ir", (0.2, 0.0, 0.0)))
        result = binocular_measurement(
            rig,
            eyes_a={"left": (320.0, 240.0), "right": (371.2, 240.0)},
            eyes_b={"left": (160.0, 240.0), "right": (211.2, 240.0)},
        )

        self.assertFalse(result["metric_depth_authorized"])
        self.assertTrue(result["calibration_audit_required"])

    def test_calibration_audit_accepts_explicit_synthetic_scope_without_authorizing_depth(self):
        rig = StereoRig(camera("synthetic-a", (0.0, 0.0, 0.0)), camera("synthetic-b", (0.2, 0.0, 0.0)))

        audit = calibration_audit(
            rig,
            evidence_scope="synthetic_only",
            provenance_ref="tests/test_geometry.py",
        )

        self.assertEqual(audit["evidence"]["scope"], "synthetic_only")
        self.assertEqual(audit["evidence"]["provenance_ref"], "tests/test_geometry.py")
        self.assertFalse(audit["metric_depth_authorized"])

    def test_calibration_audit_rejects_undeclared_or_untraceable_scope(self):
        rig = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0)))

        with self.assertRaisesRegex(StereoGeometryError, "evidence_scope"):
            calibration_audit(rig, evidence_scope="inferred")
        with self.assertRaisesRegex(StereoGeometryError, "requires provenance_ref"):
            calibration_audit(rig, evidence_scope="synthetic_only")

    def test_calibration_audit_validator_rejects_tampered_authorization(self):
        rig = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0)))
        tampered = copy.deepcopy(calibration_audit(rig))
        tampered["metric_depth_authorized"] = True

        with self.assertRaisesRegex(StereoGeometryError, "authorization flags"):
            validate_calibration_audit(tampered)

    def test_calibration_audit_validates_its_own_output(self):
        rig = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.2, 0.0, 0.0)))

        audit = calibration_audit(rig)

        self.assertTrue(validate_calibration_audit(audit))

    def test_calibration_audit_preserves_invalid_geometry_failure(self):
        rig = StereoRig(camera("a", (0.0, 0.0, 0.0)), camera("b", (0.0, 0.0, 0.0)))

        audit = calibration_audit(rig)

        self.assertEqual(audit["status"], "CALIBRATION_REQUIRED")
        self.assertIsNone(audit["camera_baseline_world"])

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
