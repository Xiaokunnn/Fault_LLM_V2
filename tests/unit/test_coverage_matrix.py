from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_fault_coverage_matrix import evaluate_gate  # noqa: E402


class CoverageMatrixGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = {
            "symptom": 5,
            "cause_or_mechanism": 3,
            "inspection_or_maintenance": 2,
            "independent_documents": 2,
            "independent_source_families": 2,
        }

    def test_all_thresholds_are_required(self) -> None:
        checks, passed = evaluate_gate(
            symptoms=5,
            causes=3,
            actions=2,
            documents=2,
            source_families=1,
            gate=self.gate,
        )
        self.assertFalse(passed)
        self.assertFalse(checks["independent_source_families"])

    def test_exact_thresholds_pass(self) -> None:
        checks, passed = evaluate_gate(
            symptoms=5,
            causes=3,
            actions=2,
            documents=2,
            source_families=2,
            gate=self.gate,
        )
        self.assertTrue(passed)
        self.assertTrue(all(checks.values()))


if __name__ == "__main__":
    unittest.main()
