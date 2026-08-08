#!/usr/bin/env python3
"""Report the data-model and storage footprint used by the RP2 v6 paper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _tree_bytes(path: Path) -> int:
    return (
        sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        if path.exists()
        else 0
    )


def build_report(config: dict) -> dict:
    graph = ROOT / config["graph_root"]
    benchmark = ROOT / config["benchmark_dir"]
    index = ROOT / config["embedding"]["index_dir"]
    candidates = _read_jsonl(benchmark / "evidence_candidates.jsonl")
    provenance_fields = (
        "evidence_text", "doc_id", "pdf_page_number", "source_url", "source_family_id"
    )
    complete = sum(
        all(row.get(field) not in (None, "", 0) for field in provenance_fields)
        for row in candidates
    )
    graph_files = {
        name: {
            "records": len(_read_jsonl(graph / name)),
            "bytes": (graph / name).stat().st_size if (graph / name).is_file() else 0,
        }
        for name in (
            "entities.jsonl",
            "claims.jsonl",
            "evidence_assertions.jsonl",
            "claim_evidence_links.jsonl",
            "source_records.jsonl",
        )
    }
    index_manifest_path = index / "manifest.json"
    index_manifest = (
        json.loads(index_manifest_path.read_text(encoding="utf-8"))
        if index_manifest_path.is_file()
        else None
    )
    return {
        "protocol_id": config["protocol_id"],
        "data_model": "Entity--Claim--Evidence Assertion--Source Family--Provenance",
        "graph": {
            "path": config["graph_root"],
            "total_bytes": _tree_bytes(graph),
            "files": graph_files,
        },
        "retrieval_corpus": {
            "evidence_assertions": len(candidates),
            "source_documents": len(
                {str(row["doc_id"]) for row in candidates if row.get("doc_id")}
            ),
            "source_families": len(
                {
                    str(row["source_family_id"])
                    for row in candidates
                    if row.get("source_family_id")
                }
            ),
            "provenance_complete_records": complete,
            "provenance_complete_rate": complete / len(candidates) if candidates else None,
            "required_provenance_fields": list(provenance_fields),
        },
        "vector_index": {
            "path": config["embedding"]["index_dir"],
            "exists": index.is_dir(),
            "total_bytes": _tree_bytes(index),
            "manifest": index_manifest,
            "build_time_status": (
                "measured"
                if index_manifest and index_manifest.get("build_elapsed_seconds") is not None
                else "not_recorded_for_existing_index; rebuild once with the updated builder if required"
            ),
        },
        "online_query_interface": {
            "input": "q=(natural-language text x, fault scope f, evidence role r)",
            "natural_language_fault_role_parser_evaluated": False,
        },
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default="configs/rp2_graphrag_v6_equal_budget.json"
    )
    parser.add_argument(
        "--output-dir",
        default="results/experiments/research_point_2/graphrag_v6_equal_budget/paper_summary",
    )
    args = parser.parse_args()
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    report = build_report(config)
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "data_system_footprint.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    corpus = report["retrieval_corpus"]
    vector = report["vector_index"]
    lines = [
        "# RP2 v6 data-system footprint",
        "",
        f"- Evidence assertions: {corpus['evidence_assertions']}",
        f"- Source documents: {corpus['source_documents']}",
        f"- Source families: {corpus['source_families']}",
        f"- Provenance completeness: {corpus['provenance_complete_records']}/{corpus['evidence_assertions']}",
        f"- Graph storage: {report['graph']['total_bytes']} bytes",
        f"- Vector-index storage: {vector['total_bytes']} bytes",
        f"- Vector-index build time: {vector['build_time_status']}",
        "- Labels: Silver only; no human expert review.",
    ]
    (output / "data_system_footprint.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"[RP2 v6 footprint] output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
