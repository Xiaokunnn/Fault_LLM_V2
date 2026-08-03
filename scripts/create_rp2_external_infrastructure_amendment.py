#!/usr/bin/env python3
"""Create a scoped amendment for external-evaluation plumbing bugs after RP2 method freeze."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "configs/frozen/rp2_v3_frozen_protocol.json"
OUTPUT = ROOT / "configs/frozen/rp2_v3_external_infrastructure_amendment_v1.json"
ALLOWED_FILES = (
    "scripts/prepare_shared_heldout_evaluation.py",
    "scripts/run_automatic_silver_adjudication.py",
    "scripts/build_rp2_dense_index.py",
    "scripts/run_rp2_v3_external_source_heldout_secure.sh",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    allowed = set(ALLOWED_FILES)
    for entry in freeze["artifact_sha256"].values():
        path = str(entry["path"])
        if path in allowed:
            continue
        current = ROOT / path
        if not current.is_file() or _sha(current) != entry["sha256"]:
            raise RuntimeError(f"Frozen core artifact changed; amendment forbidden: {path}")
    amendment = {
        "amendment_id": "rp2_v3_external_infrastructure_amendment_v1",
        "status": "scoped_bugfix_after_method_freeze_before_valid_external_result",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_with_bugfix_code": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "original_freeze_path": str(FREEZE.relative_to(ROOT)).replace("\\", "/"),
        "original_freeze_sha256": _sha(FREEZE),
        "reason": (
            "The primary-graph confidence policy correctly vetoes held_out_test records, "
            "but the external benchmark builder incorrectly required the primary-graph "
            "silver_candidate label, deterministically producing an empty external corpus."
        ),
        "allowed_infrastructure_replacements": {
            path: _sha(ROOT / path) for path in ALLOWED_FILES
        },
        "unchanged_method_claims": {
            "retrieval_parameters_unchanged": True,
            "generation_contract_unchanged": True,
            "models_unchanged": True,
            "development_results_unchanged": True,
            "external_labels_remain_silver_only": True,
            "heldout_records_still_forbidden_from_primary_graph": True,
        },
        "external_result_state_at_bug_discovery": {
            "external_silver_records": 0,
            "rp2_candidates": 0,
            "completed_external_graphrag_results": False,
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    OUTPUT.write_text(json.dumps(amendment, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[RP2 amendment] created: {OUTPUT}")
    print("Commit the amendment before resuming external evaluation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
