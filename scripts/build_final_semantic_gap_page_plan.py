"""Freeze three existing DESMI pages for mechanical-seal symptom repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSED_PATH = (
    PROJECT_ROOT / "data/interim/parsed_pages/corpus_v2/MP005.pages.v2.jsonl"
)
OUTPUT_DIR = (
    PROJECT_ROOT / "data/interim/candidate_pages/final_semantic_gap_v1"
)
PAGE_NUMBERS = (54, 55, 65)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    pages = {
        int(record["pdf_page_number"]): record
        for record in read_jsonl(PARSED_PATH)
    }
    missing = sorted(set(PAGE_NUMBERS) - set(pages))
    if missing:
        raise KeyError(f"Parsed MP005 pages missing: {missing}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    reasons = {
        54: "shaft seal leaks a bit during standstill",
        55: "mechanical seal leaks slightly or invisibly as vapor",
        65: "initial leakage like drops or a small trickle",
    }
    for page_number in PAGE_NUMBERS:
        page = pages[page_number]
        records.append(
            {
                "page_key": f"MP005:{page_number}",
                "doc_id": "MP005",
                "pdf_page_number": page_number,
                "document_split": page["document_split"],
                "source_family_id": page["source_family_id"],
                "publisher": page["publisher"],
                "source_url": page["source_url"],
                "normalized_text_sha256": page["page_text_sha256"],
                "target_fault_classes": ["mechanical_seal_failure"],
                "target_evidence_roles": ["symptom"],
                "retrieval_details": [],
                "selection_reasons": [
                    "existing_corpus_role_typing_repair",
                    reasons[page_number],
                ],
                "has_parser_tables": bool(page.get("tables")),
                "visual_layout_checked": bool(page.get("visual_layout_checked")),
                "table_reparse_required": False,
            }
        )
    output = OUTPUT_DIR / "candidate_pages.jsonl"
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {
        "version": "marine_pump_final_semantic_gap_page_plan_v1",
        "source_doc_ids": ["MP005"],
        "candidate_pages": len(records),
        "physical_pages": list(PAGE_NUMBERS),
        "purpose": "repair mechanical-seal symptom extraction from existing evidence",
        "new_document_added": False,
        "candidate_pool_sha256": hashlib.sha256(output.read_bytes()).hexdigest().upper(),
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    (OUTPUT_DIR / "final_semantic_gap_plan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "[Final Semantic Plan] 完成：文档=MP005，候选页=3，页码=54,55,65",
        flush=True,
    )


if __name__ == "__main__":
    main()
