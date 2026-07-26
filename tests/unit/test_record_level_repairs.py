from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation.record_level_repair import (  # noqa: E402
    apply_record_level_repair,
)


class RecordLevelRepairTests(unittest.TestCase):
    def test_exact_record_repair_changes_only_declared_type(self) -> None:
        result = apply_record_level_repair(
            {
                "triple_id": "MPT-13cac1eef9648e12e3d4",
                "head": "Too high temperature",
                "head_type": "Symptom",
                "relation": "causes",
                "tail": "fire",
                "tail_type": "Risk",
            },
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(result["head_type"], "OperatingCondition")
        self.assertEqual(result["relation"], "causes")
        self.assertIn(
            "record_audit_high_temperature_as_operating_condition",
            result["normalization_actions"],
        )

    def test_repair_fails_closed_when_expected_fields_change(self) -> None:
        result = apply_record_level_repair(
            {
                "triple_id": "MPT-13cac1eef9648e12e3d4",
                "head_type": "Cause",
                "relation": "causes",
                "tail_type": "Risk",
            },
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(result["head_type"], "Cause")
        self.assertEqual(
            result["record_level_repair_error"], "expected_fields_mismatch"
        )

    def test_direction_repair_swaps_surfaces_and_types(self) -> None:
        result = apply_record_level_repair(
            {
                "triple_id": "MPT-8f13acb30da3989b4310",
                "head": "misalignment",
                "head_surface": "misalignment",
                "head_type": "FaultMode",
                "relation": "indicates",
                "tail": "vibration characteristics",
                "tail_surface": "vibration characteristics",
                "tail_type": "SignalFeature",
            },
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(result["head"], "vibration characteristics")
        self.assertEqual(result["head_type"], "SignalFeature")
        self.assertEqual(result["tail"], "misalignment")
        self.assertEqual(result["tail_type"], "FaultMode")

    def test_troubleshooting_problem_is_retyped_as_symptom(self) -> None:
        result = apply_record_level_repair(
            {
                "triple_id": "MPT-f3de072e9db0b6c6ddf4",
                "head": "Leaking shaft seal",
                "head_type": "FaultMode",
                "relation": "causes",
                "tail": "Running dry",
                "tail_type": "Cause",
            },
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(result["head_type"], "Symptom")
        self.assertIn(
            "record_audit_troubleshooting_problem_as_observable_symptom",
            result["normalization_actions"],
        )


if __name__ == "__main__":
    unittest.main()
