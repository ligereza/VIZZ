import copy
import unittest

from vizz import (
    adapt_portfolio_read_only_context,
    evaluate_portfolio_measurement_request,
    validate_portfolio_measurement_gate,
    validate_portfolio_read_only_context,
)
from vizz.geometry import StereoGeometryError
from vizz.measurement_gate import evaluate_measurement_request


def _context():
    return {
        "schema": "mak-vizz-portfolio-read-only-context-v1",
        "available": True,
        "read_only": True,
        "source": {
            "measurement_schema": "mak-vizz-measurement-status-v1",
            "lineage_schema": "mak-vizz-lineage-status-v1",
            "delta_schema": "mak-structural-delta-status-v1",
            "preview_schema": "mak-portfolio-work-preview-v1",
        },
        "measurement": {
            "status": "unknown_measurement_refused",
            "calibration_status": "CALIBRATION_EVIDENCE_REQUIRED",
            "triangulation_attempted": False,
            "depth_result_present": False,
            "claim_allowed": False,
        },
        "lineage": {
            "status": "revision_context_only",
            "current_status": "unknown_measurement_refused",
            "revision_status": "revision_accepted",
            "current_state_replaced": False,
            "current_ref": "grammar-lab:Q-650:artifact",
        },
        "delta": {
            "status": "revision_only_delta",
            "shared_keys": 2,
            "residue_keys": 15,
            "serialized_savings_bytes": -131,
            "learning_demonstrated": False,
        },
        "preview": {
            "task_id": "vizz_calibration",
            "state": "vizz_measurement_refused",
            "human_gate": "physical_calibration_evidence",
            "project_id": "project-1",
            "relation_status": "needs_evidence",
            "preview_only": True,
            "execution_allowed": False,
            "task_execution": False,
        },
        "boundary": {
            "measurement_refused": True,
            "calibration_required": True,
            "lineage_is_not_authorization": True,
            "delta_is_structural_only": True,
            "preview_is_not_execution": True,
            "semantic_claim": False,
            "learning_demonstrated": False,
        },
        "control": {
            "database_write": False,
            "decision_write": False,
            "state_advance": False,
            "selection_effect": "none",
            "promotion": "none",
            "publication": False,
            "measurement_execution": False,
            "metric_depth_authorized": False,
            "network": False,
            "execution": False,
        },
    }


class PortfolioContextTests(unittest.TestCase):
    def test_adapter_accepts_bounded_context(self):
        adapted = adapt_portfolio_read_only_context(_context())

        self.assertTrue(validate_portfolio_read_only_context(adapted))
        self.assertEqual(adapted["schema"], "vizz-portfolio-read-only-context-v1")
        self.assertFalse(adapted["controls"]["metric_depth_authorized"])
        self.assertFalse(adapted["claims"]["measurement_executed"])

    def test_adapter_preserves_signed_structural_delta(self):
        adapted = adapt_portfolio_read_only_context(_context())

        self.assertEqual(adapted["delta"]["serialized_savings_bytes"], -131)
        self.assertFalse(adapted["delta"]["learning_demonstrated"])

    def test_context_cannot_enter_measurement_gate(self):
        adapted = adapt_portfolio_read_only_context(_context())

        with self.assertRaises(StereoGeometryError):
            evaluate_measurement_request(
                adapted, {}, {"operation": "binocular_measurement"}
            )

    def test_measurement_request_returns_typed_refusal(self):
        adapted = adapt_portfolio_read_only_context(_context())
        request = {
            "operation": "binocular_measurement",
            "eyes_a": {"left": (320.0, 240.0)},
            "eyes_b": {"left": (160.0, 240.0)},
        }

        first = evaluate_portfolio_measurement_request(adapted, request)
        second = evaluate_portfolio_measurement_request(adapted, request)

        self.assertTrue(validate_portfolio_measurement_gate(first))
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "MEASUREMENT_REFUSED")
        self.assertFalse(first["execution"]["triangulation_attempted"])
        self.assertIsNone(first["execution"]["depth_result"])
        self.assertFalse(first["controls"]["metric_depth_authorized"])

    def test_refusal_has_no_selection_or_publication_effect(self):
        adapted = adapt_portfolio_read_only_context(_context())
        before = copy.deepcopy(adapted)

        refused = evaluate_portfolio_measurement_request(
            adapted, {"operation": "binocular_measurement"}
        )

        self.assertEqual(adapted, before)
        self.assertEqual(refused["controls"]["selection_effect"], "none")
        self.assertFalse(refused["controls"]["publication"])
        self.assertFalse(refused["controls"]["measurement_execution"])

    def test_adapter_rejects_boundary_tampering(self):
        cases = {
            "measurement": ("triangulation_attempted", True),
            "lineage": ("current_state_replaced", True),
            "preview": ("execution_allowed", True),
            "boundary": ("semantic_claim", True),
            "control": ("publication", True),
        }
        for container, (field, value) in cases.items():
            with self.subTest(container=container, field=field):
                tampered = copy.deepcopy(_context())
                tampered[container][field] = value
                with self.assertRaises(StereoGeometryError):
                    adapt_portfolio_read_only_context(tampered)

    def test_adapter_rejects_authorization_changes_on_new_revision(self):
        fields = [
            ("control", "metric_depth_authorized"),
            ("control", "measurement_execution"),
            ("control", "publication"),
            ("control", "network"),
            ("control", "execution"),
            ("boundary", "semantic_claim"),
            ("boundary", "learning_demonstrated"),
        ]
        for container, field in fields:
            with self.subTest(container=container, field=field):
                tampered = copy.deepcopy(_context())
                tampered[container][field] = True
                with self.assertRaises(StereoGeometryError):
                    adapt_portfolio_read_only_context(tampered)


if __name__ == "__main__":
    unittest.main()
