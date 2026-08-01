#!/usr/bin/env python3
"""Build the first-use deterministic page plan for MP010--MP013 after protocol freeze."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_full_extraction_page_plan import EVIDENCE_ROLES, FAULT_IDS, read_jsonl, structural_exclusion  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="data/interim/parsed_pages/heldout_external_v1")
    parser.add_argument("--output-dir", default="data/interim/candidate_pages/heldout_external_v1")
    parser.add_argument("--doc-ids", default="MP010,MP011,MP012,MP013")
    args = parser.parse_args()
    doc_ids = tuple(value.strip() for value in args.doc_ids.split(",") if value.strip())
    if set(doc_ids) != {"MP010", "MP011", "MP012", "MP013"}:
        raise ValueError("Strict external plan v1 must contain exactly MP010--MP013")
    input_dir = ROOT / args.input_dir
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    included, excluded = [], []
    reasons: Counter[str] = Counter()
    physical = 0
    for position, doc_id in enumerate(doc_ids, start=1):
        pages = read_jsonl(input_dir / f"{doc_id}.pages.v2.jsonl")
        seen_hashes: set[str] = set()
        kept = 0
        for page in pages:
            if page.get("document_split") != "held_out_test":
                raise ValueError(f"{doc_id} is not held_out_test")
            physical += 1
            reason = structural_exclusion(page, page_count=len(pages), seen_hashes=seen_hashes)
            item = {
                "doc_id": doc_id,
                "pdf_page_number": int(page["pdf_page_number"]),
                "page_text_sha256": page.get("page_text_sha256"),
                "document_split": "held_out_test",
                "source_family_id": page.get("source_family_id"),
                "target_fault_classes": list(FAULT_IDS),
                "target_evidence_roles": list(EVIDENCE_ROLES),
                "selection_policy": "strict_external_all_pages_deterministic_exclusion_v1",
            }
            if reason is None:
                included.append(item)
                kept += 1
            else:
                item["exclusion_reason"] = reason
                excluded.append(item)
                reasons[reason] += 1
        print(f"[Heldout plan][{position}/4] {doc_id}: physical={len(pages)}, included={kept}", flush=True)
    for name, rows in (("candidate_pages.jsonl", included), ("excluded_pages.jsonl", excluded)):
        with (output_dir / name).open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "version": "marine_pump_heldout_external_page_plan_v1",
        "created_after_rp2_protocol_freeze": True,
        "rp2_protocol": "marine_pump_rp2_budget_retrieval_v1@1.0.0",
        "documents": list(doc_ids),
        "physical_pages": physical,
        "included_pages": len(included),
        "excluded_pages": len(excluded),
        "exclusion_reasons": dict(reasons),
        "anti_leakage": "May evaluate frozen RP1/RP2 only; must not enter primary graph or tune any method.",
    }
    (output_dir / "page_plan_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[Heldout plan] complete: physical={physical}, included={len(included)}, excluded={len(excluded)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
