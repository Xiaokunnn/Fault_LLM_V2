#!/usr/bin/env python3
"""Compare v6 paraphrase retrievals with their frozen parent-query rankings."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _ndcg(ranked: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    hits = [int(evidence_id in relevant) for evidence_id in ranked]
    dcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(hits, start=1))
    ideal = min(len(relevant), len(ranked))
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal + 1))
    return dcg / idcg if idcg else 0.0


def _jaccard(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    return len(left_set & right_set) / len(left_set | right_set)


def summarize(
    *,
    parent_queries: list[dict],
    paraphrase_queries: list[dict],
    mapping_rows: list[dict],
    parent_retrievals: list[dict],
    paraphrase_retrievals: list[dict],
) -> dict:
    parent_by_id = {str(row["query_id"]): row for row in parent_queries}
    paraphrase_by_id = {str(row["query_id"]): row for row in paraphrase_queries}
    mapping = {str(row["query_id"]): row for row in mapping_rows}
    parent_rankings = {
        (str(row["method"]), str(row["query_id"])): [
            str(item["evidence_id"]) for item in row.get("ranked", [])
        ]
        for row in parent_retrievals
    }
    paraphrase_rankings = {
        (str(row["method"]), str(row["query_id"])): [
            str(item["evidence_id"]) for item in row.get("ranked", [])
        ]
        for row in paraphrase_retrievals
    }
    if set(paraphrase_by_id) != set(mapping):
        raise ValueError("Paraphrase queries and paraphrase_map query IDs differ")

    records: list[dict] = []
    for (method, query_id), ranked in sorted(paraphrase_rankings.items()):
        if query_id not in mapping or query_id not in paraphrase_by_id:
            raise KeyError(f"Unmapped paraphrase retrieval: {method}:{query_id}")
        map_row = mapping[query_id]
        parent_id = str(map_row["parent_query_id"])
        if parent_id not in parent_by_id:
            raise KeyError(f"Unknown parent query: {parent_id}")
        parent = parent_by_id[parent_id]
        paraphrase = paraphrase_by_id[query_id]
        for field in ("fault_id", "fault_name_zh", "role", "relevant_evidence_ids"):
            if paraphrase.get(field) != parent.get(field):
                raise ValueError(f"Structured field changed for {query_id}: {field}")
        parent_ranked = parent_rankings.get((method, parent_id))
        if parent_ranked is None:
            raise KeyError(f"Missing frozen parent ranking: {method}:{parent_id}")
        relevant = set(str(value) for value in parent.get("relevant_evidence_ids", []))
        records.append(
            {
                "method": method,
                "query_id": query_id,
                "parent_query_id": parent_id,
                "variant": int(map_row["variant"]),
                "fault_id": parent["fault_id"],
                "role": parent["role"],
                "answerable": bool(relevant),
                "recall": len(set(ranked) & relevant) / len(relevant) if relevant else None,
                "ndcg": _ndcg(ranked, relevant) if relevant else None,
                "selection_jaccard_vs_parent": _jaccard(ranked, parent_ranked),
                "top1_agreement_vs_parent": bool(
                    ranked and parent_ranked and ranked[0] == parent_ranked[0]
                ),
            }
        )

    by_method: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        by_method[row["method"]].append(row)
    methods = {}
    for method, rows in sorted(by_method.items()):
        answerable = [row for row in rows if row["answerable"]]
        methods[method] = {
            "queries": len(rows),
            "parent_queries": len({row["parent_query_id"] for row in rows}),
            "fault_classes": len({row["fault_id"] for row in rows}),
            "answerable_queries": len(answerable),
            "recall_macro": statistics.fmean(row["recall"] for row in answerable),
            "ndcg_macro": statistics.fmean(row["ndcg"] for row in answerable),
            "selection_jaccard_vs_parent_mean": statistics.fmean(
                row["selection_jaccard_vs_parent"] for row in rows
            ),
            "top1_agreement_vs_parent_rate": statistics.fmean(
                float(row["top1_agreement_vs_parent"]) for row in rows
            ),
            "by_variant": {
                str(variant): {
                    "queries": len(variant_rows),
                    "recall_macro": statistics.fmean(
                        row["recall"] for row in variant_rows if row["answerable"]
                    ),
                    "ndcg_macro": statistics.fmean(
                        row["ndcg"] for row in variant_rows if row["answerable"]
                    ),
                    "selection_jaccard_vs_parent_mean": statistics.fmean(
                        row["selection_jaccard_vs_parent"] for row in variant_rows
                    ),
                }
                for variant in sorted({row["variant"] for row in rows})
                for variant_rows in [[row for row in rows if row["variant"] == variant]]
            },
        }
    return {
        "protocol_id": "marine_pump_rp2_v6_paraphrase_robustness_summary",
        "structured_fields_held_fixed": True,
        "parameters_tuned_on_paraphrases": False,
        "methods": methods,
        "records": records,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "metric_boundary": "Development wording robustness, not held-out domain generalization",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parent-benchmark",
        default="data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2",
    )
    parser.add_argument(
        "--paraphrase-benchmark",
        default="data/kg/marine_pump/silver_evidencebench/rp2_v6_paraphrase_robustness",
    )
    parser.add_argument(
        "--parent-retrieval",
        default="results/experiments/research_point_2/graphrag_v6_equal_budget/retrieval_replay.jsonl",
    )
    parser.add_argument(
        "--paraphrase-retrieval",
        default="results/experiments/research_point_2/graphrag_v6_paraphrase_robustness/retrieval_results.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="results/experiments/research_point_2/graphrag_v6_paraphrase_robustness",
    )
    args = parser.parse_args()

    parent = ROOT / args.parent_benchmark
    paraphrase = ROOT / args.paraphrase_benchmark
    report = summarize(
        parent_queries=_read_jsonl(parent / "queries.jsonl"),
        paraphrase_queries=_read_jsonl(paraphrase / "queries.jsonl"),
        mapping_rows=_read_jsonl(paraphrase / "paraphrase_map.jsonl"),
        parent_retrievals=_read_jsonl(ROOT / args.parent_retrieval),
        paraphrase_retrievals=_read_jsonl(ROOT / args.paraphrase_retrieval),
    )
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "paraphrase_robustness_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = [dict(method=method, **values) for method, values in report["methods"].items()]
    with (output / "paraphrase_robustness_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = [
            "method", "queries", "parent_queries", "fault_classes", "answerable_queries",
            "recall_macro", "ndcg_macro", "selection_jaccard_vs_parent_mean",
            "top1_agreement_vs_parent_rate",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[RP2 v6 paraphrase] summary={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
