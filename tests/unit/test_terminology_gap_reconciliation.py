from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from reconcile_chinese_terminology_release_gaps import (  # noqa: E402
    attach_frozen_candidates,
    select_gap_items,
)


class TerminologyGapReconciliationTests(unittest.TestCase):
    def test_current_outputs_select_only_four_release_blockers(self) -> None:
        governed_path = (
            PROJECT_ROOT
            / "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_governed/"
            "candidate_triples.zh_governed.jsonl"
        )
        governed = [
            json.loads(line)
            for line in governed_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        output_dir = governed_path.parent
        unresolved = json.loads(
            (output_dir / "terminology_unresolved.json").read_text(
                encoding="utf-8"
            )
        )
        coverage = json.loads(
            (output_dir / "coverage_chinese_release.json").read_text(
                encoding="utf-8"
            )
        )

        queue, targets = select_gap_items(
            governed, coverage, unresolved
        )
        candidate_artifact = json.loads(
            (
                PROJECT_ROOT
                / "configs/terminology_release_gap_candidates_v1.json"
            ).read_text(encoding="utf-8")
        )
        attach_frozen_candidates(queue, candidate_artifact)

        self.assertEqual(
            {
                surface
                for item in queue
                for surface in item["source_forms"]
            },
            {
                "Choking or clogging of the pump",
                "Incorrect inlet pressure",
                "Motor may be overloaded",
                "Reduce load.",
            },
        )
        self.assertEqual(
            targets["hydraulic_blockage"]["symptom"]["gap"], 2
        )
        self.assertEqual(
            targets["motor_electrical_drive_failure"][
                "inspection_or_maintenance"
            ]["gap"],
            1,
        )
        self.assertTrue(
            all(item["frozen_reconciliation_candidate_zh"] for item in queue)
        )


if __name__ == "__main__":
    unittest.main()
