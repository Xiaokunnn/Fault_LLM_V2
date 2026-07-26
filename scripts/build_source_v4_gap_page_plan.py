"""Freeze the MP022 pages selected to close the final three coverage gaps."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSED_PATH = (
    PROJECT_ROOT / "data/interim/parsed_pages/corpus_v2/MP022.pages.v2.jsonl"
)
OUTPUT_DIR = (
    PROJECT_ROOT / "data/interim/candidate_pages/source_v4_gap_v1"
)

PAGE_TARGETS = {
    10: {
        "faults": ["pipe_or_valve_integrity_failure"],
        "roles": ["inspection", "maintenance"],
        "reason": "check-valve prevention for hazardous backflow",
    },
    11: {
        "faults": ["pipe_or_valve_integrity_failure"],
        "roles": ["inspection", "maintenance"],
        "reason": "pipeline routing, tight connections, and self-support checks",
    },
    13: {
        "faults": ["pipe_or_valve_integrity_failure"],
        "roles": ["inspection", "maintenance", "symptom"],
        "reason": "no gaps or angles at pump-to-pipe connections",
    },
    14: {
        "faults": ["mechanical_seal_failure"],
        "roles": ["symptom", "maintenance"],
        "reason": "shaft-seal leakage manifests as media dripping from adapter slot",
    },
    15: {
        "faults": ["dry_running_or_maintenance_induced_failure"],
        "roles": ["symptom", "maintenance"],
        "reason": "liquid-at-start requirement and maximum air-release running time",
    },
    21: {
        "faults": [
            "dry_running_or_maintenance_induced_failure",
            "mechanical_seal_failure",
        ],
        "roles": ["cause", "maintenance", "inspection"],
        "reason": "shaft seal must not run dry and flushing liquid must be connected",
    },
    22: {
        "faults": [
            "dry_running_or_maintenance_induced_failure",
            "mechanical_seal_failure",
        ],
        "roles": ["symptom", "cause", "maintenance"],
        "reason": "verified same-row troubleshooting evidence",
    },
    26: {
        "faults": [
            "dry_running_or_maintenance_induced_failure",
            "mechanical_seal_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
        "reason": "verified maintenance table and slowly starting leakage symptom",
    },
}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    if not PARSED_PATH.exists():
        raise FileNotFoundError(
            "MP022 has not been parsed. Run run_corpus_ingest.py --doc-ids MP022 first."
        )
    pages = {
        int(record["pdf_page_number"]): record
        for record in read_jsonl(PARSED_PATH)
    }
    missing = sorted(set(PAGE_TARGETS) - set(pages))
    if missing:
        raise KeyError(f"Parsed MP022 pages missing: {missing}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates: list[dict[str, object]] = []
    for page_number, target in PAGE_TARGETS.items():
        page = pages[page_number]
        candidates.append(
            {
                "page_key": f"MP022:{page_number}",
                "doc_id": "MP022",
                "pdf_page_number": page_number,
                "document_split": page["document_split"],
                "source_family_id": page["source_family_id"],
                "publisher": page["publisher"],
                "source_url": page["source_url"],
                "normalized_text_sha256": page["page_text_sha256"],
                "target_fault_classes": target["faults"],
                "target_evidence_roles": target["roles"],
                "retrieval_details": [],
                "selection_reasons": [
                    "post_gap_7_of_10_source_supplement",
                    target["reason"],
                ],
                "has_parser_tables": bool(page.get("tables")),
                "visual_layout_checked": bool(page.get("visual_layout_checked")),
                "table_reparse_required": page_number in {22, 26},
            }
        )

    output_path = OUTPUT_DIR / "candidate_pages.jsonl"
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in candidates:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest().upper()
    summary = {
        "version": "marine_pump_source_v4_gap_page_plan_v1",
        "document_split_version": "marine_pump_document_split_v4",
        "source_doc_ids": ["MP022"],
        "candidate_pages": len(candidates),
        "physical_pages": list(PAGE_TARGETS),
        "failed_classes_before_supplement": [
            "mechanical_seal_failure",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "candidate_pool_sha256": digest,
        "selection_is_post_coverage_audit": True,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    (OUTPUT_DIR / "source_v4_gap_plan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Source v4 Plan] 完成：文档=MP022，候选页={len(candidates)}，"
        f"页码={','.join(str(value) for value in PAGE_TARGETS)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
