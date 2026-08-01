#!/usr/bin/env python3
"""Summarize completed B0--Ours real-API prompt comparison outputs."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/experiments/research_point_1/api_prompt_comparison_v1"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    rows = []
    for method in ("B0", "B1", "B2", "B3", "Ours"):
        root = BASE / method
        extraction = json.loads((root / "extraction_run_summary.json").read_text(encoding="utf-8"))
        strict = json.loads((root / "strict" / "strict_v2_validation_summary.json").read_text(encoding="utf-8"))
        records = _read_jsonl(root / "strict" / "candidate_triples.strict_v2.jsonl")
        decisions = Counter(str(item.get("decision")) for item in records)
        provenance_fields = (
            "doc_id", "pdf_page_number", "source_url", "document_sha256",
            "page_text_sha256", "evidence_text",
        )
        provenance_complete = sum(
            all(item.get(field) not in (None, "") for field in provenance_fields)
            for item in records
        )
        rows.append({
            "method": method,
            "pages": extraction["pages_selected"],
            "raw_proposals": extraction["raw_proposals"],
            "normalized_candidates": extraction["retained_candidates"],
            "model_contract_rejections": extraction["rejected_proposals"],
            "strict_silver": decisions.get("silver_candidate", 0),
            "needs_review": decisions.get("candidate_needs_review", 0),
            "rejected": decisions.get("rejected", 0),
            "strict_silver_rate_over_normalized": round(
                decisions.get("silver_candidate", 0) / max(1, len(records)), 6
            ),
            "provenance_complete_rate": round(provenance_complete / max(1, len(records)), 6),
            "api_latency_ms_total": sum(
                int(page.get("latency_ms") or 0) for page in extraction.get("page_results", [])
            ),
            "interpretation": "structure_and_grounding_yield_not_fact_accuracy",
        })
    BASE.mkdir(parents=True, exist_ok=True)
    with (BASE / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "experiment": "rp1_fixed_page_real_api_prompt_comparison_v1",
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "page_selection": "stratified_evidence_rich_build_pages_not_corpus_random_sample",
        "rows": rows,
    }
    (BASE / "comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
