from __future__ import annotations

import copy
import re
import unittest

from vizz.geometry import StereoGeometryError, StereoRig, CameraModel, calibration_audit
from vizz.measurement_gate import evaluate_measurement_request
from vizz.operation_context import (
    adapt_portfolio_direction_context,
    compose_operation_context_with_calibration,
    validate_composed_context,
    validate_portfolio_direction_context,
    adapt_portfolio_work_preview,
    validate_portfolio_work_preview,
)


def _camera(camera_id: str, center: tuple[float, float, float]) -> CameraModel:
    return CameraModel(
        camera_id,
        ((100.0, 0.0, 320.0), (0.0, 100.0, 240.0), (0.0, 0.0, 1.0)),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        center,
    )


class OperationContextLineageTests(unittest.TestCase):
    def _context(self):
        return {
            "schema": "vizz-operation-context-v1",
            "status": "CONTEXT_ACCEPTED_STRUCTURAL_ONLY",
            "source": {"schema": "mak-operation-receipt-v1", "ref": "grammar-lab:Q-610:artifact", "sha256": "a" * 64},
            "operation": {"name": "expand_library_program", "dialect": "super-mario-feature-v1", "expanded_count": 0, "expanded_keys": []},
            "provenance": {"library_source_ref": "library", "evaluation_source_ref": "evaluation", "package_sha256": "b" * 64},
            "controls": {"metric_depth_authorized": False, "calibration_audit_required": True, "depth_publication": False, "network_contact": False, "semantic_equivalence_authorized": False},
        }

    def test_composed_context_preserves_calibration_lineage_without_authorization(self):
        audit = calibration_audit(StereoRig(_camera("a", (0.0, 0.0, 0.0)), _camera("b", (0.2, 0.0, 0.0))))
        composed = compose_operation_context_with_calibration(self._context(), audit)
        calibration = composed["calibration"]
        self.assertIsNone(calibration["provenance_ref"])
        self.assertRegex(calibration["audit_sha256"], re.compile(r"^[0-9a-f]{64}$"))
        self.assertFalse(composed["controls"]["metric_depth_authorized"])
        self.assertTrue(validate_composed_context(composed))

    def test_tampered_calibration_lineage_hash_is_rejected(self):
        audit = calibration_audit(StereoRig(_camera("a", (0.0, 0.0, 0.0)), _camera("b", (0.2, 0.0, 0.0))))
        composed = compose_operation_context_with_calibration(self._context(), audit)
        tampered = copy.deepcopy(composed)
        tampered["calibration"]["audit_sha256"] = "c" * 64
        with self.assertRaisesRegex(StereoGeometryError, "calibration lineage"):
            evaluate_measurement_request(tampered, audit, {"operation": "binocular_measurement"})

    def _direction_context(self):
        return {
            "schema": "mak-portfolio-direction-context-v1",
            "algorithm_version": "portfolio-direction-context-1",
            "available": True,
            "read_only": True,
            "purpose": "vision_order_culture_computation_read_only_frame",
            "frame": {
                "vision": {"state": "bounded_observation", "semantic_claim_established": False},
                "order": {"state": "structural_order_only", "semantic_equivalence_established": False},
                "culture_computation": {"state": "observed_practice_context", "relation_inference": False},
                "instrument": {"state": "vizz_measurement_refused", "measurement_status": "unknown_measurement_refused", "measurement_unknown": True, "measurement_claim_allowed": False},
            },
            "directions": [
                {"id": "vision", "kind": "orientation", "state": "bounded_observation", "human_gate": "interpretation_and_editorial_context"},
                {"id": "order", "kind": "computation", "state": "structural_order_only", "human_gate": "semantic_reuse_or_equivalence"},
                {"id": "culture_computation", "kind": "practice_context", "state": "observed_not_authored", "human_gate": "typed_relation_and_attribution"},
            ],
            "control": {
                "database_write": False, "decision_write": False, "state_advance": False,
                "selection_effect": "none", "promotion": "none", "publication": False,
                "normalize_execution": False, "measurement_execution": False,
            },
            "provenance": {
                "components": [], "deterministic": True, "relation_inference": False,
                "semantic_claim": False, "semantic_equivalence": False,
                "learning_demonstrated": False, "decisions_require_external_human_actor": True,
            },
        }

    def test_portfolio_direction_is_carried_to_vizz_fail_closed(self):
        adapted = adapt_portfolio_direction_context(self._direction_context())
        self.assertEqual(adapted["schema"], "vizz-portfolio-direction-context-v1")
        self.assertTrue(validate_portfolio_direction_context(adapted))
        self.assertFalse(adapted["controls"]["metric_depth_authorized"])
        self.assertTrue(adapted["measurement"]["unknown"])

    def test_portfolio_direction_semantic_claim_is_rejected(self):
        direction = self._direction_context()
        direction["frame"]["vision"]["semantic_claim_established"] = True
        with self.assertRaisesRegex(StereoGeometryError, "semantic claim"):
            adapt_portfolio_direction_context(direction)

    def _work_preview(self):
        return {
            "schema": "mak-portfolio-work-preview-v1",
            "algorithm_version": "portfolio-work-preview-1",
            "available": True,
            "read_only": True,
            "preview_only": True,
            "source": {
                "schema": "mak-portfolio-work-packet-v1",
                "task_id": "vizz_calibration",
                "task_count": 4,
                "project_id": "project-5047cc3a2269b5031460",
                "relation_status": "needs_evidence",
            },
            "task": {
                "id": "vizz_calibration",
                "area": "vizz/measurement",
                "layer": "instrument",
                "state": "vizz_measurement_refused",
                "evidence": "mak-vizz-measurement-status-v1 + mak-vizz-lineage-status-v1",
                "action": "provide_physical_calibration_evidence_before_metric_measurement",
                "human_gate": "physical_calibration_evidence",
                "execution_allowed": False,
            },
            "next_action": "human_review_selected_work_preview_before_execution",
            "control": {
                "database_write": False, "decision_write": False, "state_advance": False,
                "selection_effect": "context_only", "promotion": "none", "publication": False,
                "normalize_execution": False, "measurement_execution": False,
            },
            "provenance": {
                "packet_schema": "mak-portfolio-work-packet-v1",
                "project_id": "project-5047cc3a2269b5031460",
                "relation_status": "needs_evidence",
                "typed_relation_present": False,
                "deterministic": True, "task_execution": False,
                "semantic_claim": False, "learning_demonstrated": False,
                "decisions_require_external_human_actor": True,
            },
        }

    def test_vizz_calibration_preview_is_context_only(self):
        adapted = adapt_portfolio_work_preview(self._work_preview())
        self.assertTrue(validate_portfolio_work_preview(adapted))
        self.assertEqual(adapted["source"]["project_id"], "project-5047cc3a2269b5031460")
        self.assertFalse(adapted["controls"]["measurement_execution"])
        self.assertFalse(adapted["controls"]["metric_depth_authorized"])
        self.assertFalse(adapted["controls"]["publication"])

    def test_vizz_rejects_non_calibration_preview(self):
        preview = self._work_preview()
        preview["source"]["task_id"] = "structural_order"
        with self.assertRaisesRegex(StereoGeometryError, "outside the VIZZ"):
            adapt_portfolio_work_preview(preview)

    def test_vizz_rejects_publication_enablement_in_preview(self):
        adapted = adapt_portfolio_work_preview(self._work_preview())
        adapted["controls"]["publication"] = True
        with self.assertRaisesRegex(StereoGeometryError, "controls"):
            validate_portfolio_work_preview(adapted)

    def test_portfolio_preview_cannot_enter_measurement_gate_as_composed_context(self):
        adapted = adapt_portfolio_work_preview(self._work_preview())
        with self.assertRaisesRegex(StereoGeometryError, "composed context header"):
            evaluate_measurement_request(
                adapted,
                {},
                {"operation": "binocular_measurement"},
            )


if __name__ == "__main__":
    unittest.main()
