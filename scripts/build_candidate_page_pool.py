"""Build and freeze the second-round candidate page pool."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage02_triple_extraction.candidate_pool_builder import (  # noqa: E402
    build_candidate_pool,
)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/corpus_candidate_retrieval_marine_pump_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default="data/interim/candidate_pages/corpus_retrieval_v1",
    )
    args = parser.parse_args()
    config = json.loads(
        (PROJECT_ROOT / args.config).read_text(encoding="utf-8")
    )
    ontology = json.loads(
        (
            PROJECT_ROOT / "configs/fault_ontology_marine_pump_v1.json"
        ).read_text(encoding="utf-8")
    )
    database = (
        PROJECT_ROOT
        / "data/interim/page_index/marine_pump_pages_v1.sqlite"
    )
    if not database.exists():
        raise FileNotFoundError(f"Page index not found: {database}")
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print(
        "[Corpus Stage 3] 开始检索：10类故障 × 症状/原因/检查/维护",
        flush=True,
    )
    pages, excluded, summary = build_candidate_pool(
        database_path=database,
        ontology=ontology,
        config=config,
    )
    summary["retrieval_config_version"] = config["version"]
    summary["ontology_version"] = ontology["version"]
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    _write_jsonl(output_dir / "candidate_pages.jsonl", pages)
    _write_jsonl(output_dir / "excluded_pages.jsonl", excluded)
    csv_path = output_dir / "candidate_pages.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "page_key",
            "doc_id",
            "pdf_page_number",
            "source_family_id",
            "target_fault_classes",
            "target_evidence_roles",
            "max_retrieval_score",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for page in pages:
            writer.writerow(
                {
                    "page_key": page["page_key"],
                    "doc_id": page["doc_id"],
                    "pdf_page_number": page["pdf_page_number"],
                    "source_family_id": page["source_family_id"],
                    "target_fault_classes": ";".join(
                        page["target_fault_classes"]
                    ),
                    "target_evidence_roles": ";".join(
                        page["target_evidence_roles"]
                    ),
                    "max_retrieval_score": max(
                        detail["score"]
                        for detail in page["retrieval_details"]
                    ),
                }
            )
    (output_dir / "retrieval_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Corpus Stage 3] 完成：候选页={len(pages)}，"
        f"排除记录={len(excluded)}，来源={summary['source_family_counts']}，"
        f"耗时={summary['elapsed_seconds']}秒",
        flush=True,
    )


if __name__ == "__main__":
    main()
