#!/usr/bin/env python3
"""Freeze the RP2 v6 paper evidence chain with SHA-256 hashes.

The manifest fixes the result files cited by the short-paper draft.  Rerunning
this command verifies an existing manifest and fails closed on any drift.
All benchmark labels remain Silver and have not been expert reviewed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "configs/frozen/rp2_v6_paper_evidence_freeze.json"

ARTIFACTS = (
    "configs/rp2_graphrag_v6_equal_budget.json",
    "configs/rp2_graphrag_v6_1_no_graph_control.json",
    "results/experiments/research_point_2/evidence_integrity_v1/evidence_integrity_report.json",
    "results/experiments/research_point_2/graphrag_v6_equal_budget/paper_summary/metrics.json",
    "results/experiments/research_point_2/graphrag_v6_equal_budget/retrieval_replay_manifest.json",
    "results/experiments/research_point_2/graphrag_v6_equal_budget/retrieval_latency/retrieval_latency_summary.json",
    "results/experiments/research_point_2/graphrag_v6_1_no_graph_control/paper_summary/metrics.json",
    "results/experiments/research_point_2/graphrag_v6_1_no_graph_control/retrieval_replay_manifest.json",
    "results/experiments/research_point_2/graphrag_v6_1_no_graph_control/retrieval_latency/retrieval_latency_summary.json",
    "results/experiments/research_point_2/graphrag_v6_verifier_ablation/paper_summary/metrics.json",
    "results/experiments/research_point_2/graphrag_v6_paraphrase_robustness/paraphrase_robustness_summary.json",
    "results/experiments/research_point_2/rp2_v6_same_model_dual_prompt_audit/semantic_judge_summary.json",
    "results/experiments/research_point_2/graphrag_v3_external_source_heldout/metrics.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _current_artifacts() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for relative in ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"Cannot freeze RP2 paper evidence; missing: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return rows


def main() -> int:
    current = _current_artifacts()
    if OUTPUT.exists():
        frozen = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if frozen.get("artifacts") != current:
            raise RuntimeError(
                "RP2 v6 paper evidence has drifted from the frozen manifest. "
                "Use a new protocol/version instead of overwriting reported results."
            )
        print(
            f"[RP2 paper freeze] PASS: {len(current)} artifacts match {OUTPUT.relative_to(ROOT)}"
        )
        return 0

    payload = {
        "freeze_id": "marine_pump_rp2_v6_paper_evidence_freeze_v1",
        "status": "frozen_for_short_paper_drafting",
        "source_commit_before_freeze": _git_head(),
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "claim_boundary": (
            "The manifest freezes reported experimental artifacts. It does not "
            "convert Silver labels into expert-confirmed factual truth."
        ),
        "artifacts": current,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[RP2 paper freeze] created: {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
