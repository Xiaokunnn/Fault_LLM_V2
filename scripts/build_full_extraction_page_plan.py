"""Build the deterministic all-page plan for the frozen build-train corpus."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAULT_IDS = (
    "cavitation",
    "air_ingress_or_loss_of_prime",
    "hydraulic_blockage",
    "impeller_or_wear_part_damage",
    "mechanical_seal_failure",
    "bearing_or_lubrication_failure",
    "pump_motor_misalignment",
    "motor_electrical_drive_failure",
    "pipe_or_valve_integrity_failure",
    "dry_running_or_maintenance_induced_failure",
)
EVIDENCE_ROLES = (
    "symptom",
    "cause_or_mechanism",
    "inspection",
    "maintenance",
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def structural_exclusion(
    page: dict[str, object],
    *,
    page_count: int,
    seen_hashes: set[str],
) -> str | None:
    """Exclude only deterministic non-content pages, never by fault keywords."""

    text = str(page.get("page_text", ""))
    compact = re.sub(r"\s+", " ", text).strip()
    page_number = int(page["pdf_page_number"])
    page_hash = str(page.get("page_text_sha256") or "")
    if page_hash and page_hash in seen_hashes:
        return "exact_duplicate_page_text"
    if page_hash:
        seen_hashes.add(page_hash)
    if len(compact) < 80 and not (page.get("tables") or []):
        return "blank_or_low_text"
    lowered = compact.casefold()
    if (
        page_number <= 2
        and len(compact) < 700
        and not (page.get("tables") or [])
    ):
        return "cover_or_title_page"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    numbered_lines = sum(
        bool(re.search(r"(?:\.{2,}|\s{3,})\s*\d{1,4}\s*$", line))
        for line in lines
    )
    if (
        page_number <= max(20, int(page_count * 0.08))
        and ("table of contents" in lowered or re.search(r"\bcontents\b", lowered))
        and numbered_lines >= 4
    ):
        return "table_of_contents"
    if (
        page_number >= max(1, int(page_count * 0.9))
        and re.search(r"(?:^|\s)index(?:\s|$)", lowered)
        and numbered_lines >= 6
    ):
        return "index_page"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split",
        default="configs/document_split_marine_pump_v4.json",
    )
    parser.add_argument(
        "--input-dir",
        default="data/interim/parsed_pages/corpus_v2",
    )
    parser.add_argument(
        "--output-dir",
        default="data/interim/candidate_pages/full_extraction_v1",
    )
    args = parser.parse_args()

    split = json.loads((PROJECT_ROOT / args.split).read_text(encoding="utf-8"))
    build_docs = tuple(str(value) for value in split["build_train_doc_ids"])
    input_dir = PROJECT_ROOT / args.input_dir
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    included: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    physical_pages = 0
    reasons: Counter[str] = Counter()
    per_document: dict[str, dict[str, int]] = {}

    for doc_index, doc_id in enumerate(build_docs, start=1):
        path = input_dir / f"{doc_id}.pages.v2.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"Missing parsed build document: {path}")
        pages = read_jsonl(path)
        seen_hashes: set[str] = set()
        doc_included = 0
        doc_excluded = 0
        for page in pages:
            if page.get("document_split") != "build_train":
                raise ValueError(
                    f"{doc_id}:p{page.get('pdf_page_number')} is not build_train"
                )
            physical_pages += 1
            reason = structural_exclusion(
                page,
                page_count=len(pages),
                seen_hashes=seen_hashes,
            )
            item = {
                "doc_id": doc_id,
                "pdf_page_number": int(page["pdf_page_number"]),
                "page_text_sha256": page.get("page_text_sha256"),
                "document_split": "build_train",
                "source_family_id": page.get("source_family_id"),
                "target_fault_classes": list(FAULT_IDS),
                "target_evidence_roles": list(EVIDENCE_ROLES),
                "selection_policy": "all_build_pages_deterministic_exclusion_v1",
            }
            if reason is None:
                included.append(item)
                doc_included += 1
            else:
                item["exclusion_reason"] = reason
                excluded.append(item)
                reasons[reason] += 1
                doc_excluded += 1
        per_document[doc_id] = {
            "physical_pages": len(pages),
            "included_pages": doc_included,
            "excluded_pages": doc_excluded,
        }
        print(
            f"[Full Plan][{doc_index}/{len(build_docs)}] {doc_id}: "
            f"物理页={len(pages)}，抽取页={doc_included}，排除={doc_excluded}",
            flush=True,
        )

    for name, records in (
        ("candidate_pages.jsonl", included),
        ("excluded_pages.jsonl", excluded),
    ):
        with (output_dir / name).open(
            "w", encoding="utf-8", newline="\n"
        ) as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {
        "version": "marine_pump_full_extraction_page_plan_v1",
        "split_version": split["version"],
        "selection_policy": (
            "all build_train physical pages except deterministic blank, cover, "
            "contents, index, and exact-duplicate pages; no fault-retrieval score"
        ),
        "build_documents": list(build_docs),
        "physical_pages": physical_pages,
        "included_pages": len(included),
        "excluded_pages": len(excluded),
        "exclusion_reasons": dict(sorted(reasons.items())),
        "per_document": per_document,
        "development_or_test_pages_included": 0,
    }
    (output_dir / "page_plan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Full Plan] 完成：构建文档={len(build_docs)}，物理页={physical_pages}，"
        f"抽取页={len(included)}，确定性排除={len(excluded)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
