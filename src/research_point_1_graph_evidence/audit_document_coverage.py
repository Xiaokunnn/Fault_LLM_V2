"""Lexical source screening for targeted extraction.

This utility never creates triples or Silver labels. By default it scans only
the build split so development and held-out documents cannot fill coverage.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path


def extract_pages(pdf_path: Path) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        check=False,
        capture_output=True,
    )
    text = result.stdout.decode("utf-8", errors="replace")
    if not text.strip():
        warning = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"No text extracted from {pdf_path}: {warning}")
    return text.split("\f")


def _split_assignments(split: dict[str, object]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for key, label in (
        ("build_train_doc_ids", "build_train"),
        ("development_doc_ids", "development"),
        ("held_out_test_doc_ids", "held_out_test"),
    ):
        for doc_id in split.get(key, []):
            if doc_id in assignments:
                raise ValueError(f"{doc_id} appears in multiple splits")
            assignments[str(doc_id)] = label
    return assignments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split",
        default="configs/document_split_marine_pump_v2.json",
    )
    parser.add_argument(
        "--eligible-split",
        default="build_train",
        choices=("build_train", "development", "held_out_test", "all"),
    )
    parser.add_argument(
        "--output-version",
        default="source_coverage_lexical_build_v2",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    manifest_path = project_root / "data/source_docs/marine_pump/source_manifest.csv"
    pdf_dir = project_root / "data/source_docs/marine_pump/raw"
    output_dir = project_root / "data/kg/marine_pump/silver_evidencebench"
    output_dir.mkdir(parents=True, exist_ok=True)
    ontology = json.loads(
        (project_root / "configs/fault_ontology_marine_pump_v1.json").read_text(
            encoding="utf-8"
        )
    )
    split_path = project_root / args.split
    if not split_path.exists():
        split_path = (
            project_root / "configs/document_split_marine_pump_pilot_v1.json"
        )
    split = json.loads(split_path.read_text(encoding="utf-8"))
    assignments = _split_assignments(split)

    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    if args.eligible_split != "all":
        manifest = [
            item
            for item in manifest
            if assignments.get(item["doc_id"]) == args.eligible_split
        ]

    documents: dict[str, list[str]] = {}
    metadata: dict[str, dict[str, str]] = {}
    for item in manifest:
        pdf_path = pdf_dir / item["file_name"]
        if not pdf_path.exists():
            continue
        documents[item["doc_id"]] = extract_pages(pdf_path)
        metadata[item["doc_id"]] = item

    rows: list[dict[str, object]] = []
    for fault in ontology["fault_classes"]:
        compiled = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in fault["selection_patterns"]
        ]
        matched_docs: list[str] = []
        matched_families: set[str] = set()
        page_keys: list[str] = []
        match_count = 0

        for doc_id, pages in documents.items():
            doc_has_match = False
            for page_number, page in enumerate(pages, start=1):
                page_matches = sum(len(pattern.findall(page)) for pattern in compiled)
                if page_matches:
                    doc_has_match = True
                    page_keys.append(f"{doc_id}:{page_number}")
                    match_count += page_matches
            if doc_has_match:
                matched_docs.append(doc_id)
                family = (
                    metadata[doc_id].get("source_family_id")
                    or metadata[doc_id]["publisher"]
                )
                matched_families.add(family)

        rows.append(
            {
                "fault_id": fault["fault_id"],
                "name_zh": fault["name_zh"],
                "eligible_split": args.eligible_split,
                "matched_document_count": len(matched_docs),
                "matched_source_family_count": len(matched_families),
                "matched_page_count": len(page_keys),
                "lexical_match_count": match_count,
                "matched_doc_ids": ";".join(matched_docs),
                "matched_source_family_ids": ";".join(sorted(matched_families)),
                "candidate_page_keys": ";".join(page_keys),
                "screening_status": (
                    "source_diverse_candidates"
                    if len(matched_docs) >= 2 and len(matched_families) >= 2
                    else "targeted_source_gap"
                ),
            }
        )

    csv_path = output_dir / f"{args.output_version}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "version": args.output_version,
        "ontology_version": ontology["version"],
        "split_version": split["version"],
        "eligible_split": args.eligible_split,
        "documents_scanned": len(documents),
        "fault_classes_scanned": len(rows),
        "source_diverse_candidate_classes": sum(
            row["screening_status"] == "source_diverse_candidates" for row in rows
        ),
        "targeted_source_gap_classes": sum(
            row["screening_status"] == "targeted_source_gap" for row in rows
        ),
        "interpretation": (
            "Page-location screening only. Keyword matches are neither triples nor "
            "Silver evidence and cannot authorize graph construction."
        ),
    }
    summary_path = output_dir / f"{args.output_version}_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
