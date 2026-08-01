#!/usr/bin/env python3
"""Run retrieval-only K/source-family/diversity sensitivity for GraphRAG v2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import EvidenceCandidate, SilverQuery, _read_jsonl  # noqa: E402
from research_point_2.dense_index import DenseEvidenceIndex  # noqa: E402
from research_point_2.evaluation import evaluate_results  # noqa: E402
from research_point_2.graph_rag_v2 import retrieve_dense_graph  # noqa: E402
from research_point_2.local_models import BgeM3Encoder  # noqa: E402
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex  # noqa: E402


class _CachingEncoder:
    """Reuse query vectors across parameter settings; index-time latency is out of scope here."""

    def __init__(self, base) -> None:
        self.base = base
        self.cache = {}

    def encode(self, texts):
        import numpy as np

        rows = []
        for text in texts:
            if text not in self.cache:
                self.cache[text] = self.base.encode([text])[0]
            rows.append(self.cache[text])
        return np.asarray(rows, dtype="float32")


def _candidate(row: dict) -> EvidenceCandidate:
    row = dict(row)
    row["fault_class_ids"] = tuple(row.get("fault_class_ids", []))
    return EvidenceCandidate(**row)


def _query(row: dict) -> SilverQuery:
    row = dict(row)
    row["relevant_evidence_ids"] = tuple(row.get("relevant_evidence_ids", []))
    row["candidate_evidence_ids"] = tuple(row.get("candidate_evidence_ids", []))
    return SilverQuery(**row)


def _plot(rows: list[dict], output: Path) -> None:
    import matplotlib.pyplot as plt

    groups = (
        ("K=", "Evidence budget K"),
        ("family_cap=", "Source-family cap"),
        ("source_bonus=", "Source-family bonus"),
        ("redundancy_penalty=", "Redundancy penalty"),
    )
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for axis, (prefix, title) in zip(axes.flat, groups):
        selected = [row for row in rows if row["setting_id"].startswith(prefix)]
        labels = [row["setting_id"].split("=", 1)[1] for row in selected]
        axis.plot(labels, [row["recall_at_budget_macro"] for row in selected], marker="o", label="Recall@K")
        axis.plot(labels, [row["mean_source_family_coverage"] for row in selected], marker="s", label="Family coverage")
        axis.set_title(title)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    figure.suptitle("GraphRAG v2 sensitivity (development Silver)")
    figure.savefig(output / "sensitivity.svg", metadata={"Date": None})
    figure.savefig(output / "sensitivity.png", dpi=180, metadata={"Date": None})
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_graphrag_v2_development.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-generation", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--methods", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    benchmark = ROOT / config["benchmark_dir"]
    candidates = [_candidate(row) for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")]
    queries = [_query(row) for row in _read_jsonl(benchmark / "queries.jsonl")]
    if args.limit:
        queries = queries[: args.limit]
    if any(query.candidate_evidence_ids for query in queries):
        raise RuntimeError("Sensitivity experiment requires full-graph queries")
    embedding = config["embedding"]
    retrieval = config["retrieval"]
    encoder = _CachingEncoder(
        BgeM3Encoder(
            ROOT / embedding["model_path"],
            batch_size=int(embedding["batch_size"]),
            max_length=int(embedding["max_length"]),
        )
    )
    dense = DenseEvidenceIndex.load(ROOT / embedding["index_dir"])
    graph = RetrievalIndex(candidates)
    print(f"[RP2 sensitivity] pre-encoding {len(queries)} development queries", flush=True)
    for query in queries:
        encoder.encode([query.question_zh])
    base = {
        "k": int(retrieval["max_selected_evidence"]),
        "family_cap": int(retrieval["max_per_source_family"]),
        "source_bonus": float(retrieval["source_family_bonus"]),
        "redundancy_penalty": float(retrieval["redundancy_penalty"]),
    }
    settings = []
    for value in (2, 4, 6, 8):
        settings.append((f"K={value}", {**base, "k": value}))
    for value in (1, 2, 3, 4):
        settings.append((f"family_cap={value}", {**base, "family_cap": value}))
    for value in (0.0, 0.06, 0.12, 0.24):
        settings.append((f"source_bonus={value}", {**base, "source_bonus": value}))
    for value in (0.0, 0.16, 0.32, 0.48):
        settings.append((f"redundancy_penalty={value}", {**base, "redundancy_penalty": value}))
    rows = []
    for position, (setting_id, values) in enumerate(settings, start=1):
        budget = RetrievalBudget(
            max_scored_candidates=int(retrieval["max_scored_candidates"]),
            max_selected_evidence=values["k"],
            max_per_source_family=values["family_cap"],
            source_family_bonus=values["source_bonus"],
            redundancy_penalty=values["redundancy_penalty"],
        )
        results = [
            retrieve_dense_graph(
                query,
                candidates,
                graph,
                dense,
                encoder,
                method="dense_ours",
                budget=budget,
                dense_top_n=int(retrieval["dense_top_n"]),
                anchor_evidence_count=int(retrieval["anchor_evidence_count"]),
                fixed_hops=int(retrieval["fixed_hops"]),
            )
            for query in queries
        ]
        metrics = evaluate_results(queries, candidates, results)["methods"]["dense_ours"]
        rows.append({"setting_id": setting_id, **values, **metrics})
        print(
            f"[RP2 sensitivity][{position}/{len(settings)}] {setting_id}: "
            f"recall={metrics['recall_at_budget_macro']:.4f}, "
            f"families={metrics['mean_source_family_coverage']:.3f}, "
            f"latency_p95={metrics['latency_ms_p95']:.3f}ms",
            flush=True,
        )
    output = ROOT / "results/experiments/research_point_2/graphrag_v2_sensitivity"
    output.mkdir(parents=True, exist_ok=True)
    (output / "sensitivity_metrics.json").write_text(
        json.dumps(
            {
                "protocol_id": config["protocol_id"],
                "label_policy": "Silver only; never Gold",
                "human_expert_reviewed": False,
                "query_count": len(queries),
                "full_graph_candidate_count": len(candidates),
                "latency_scope": "retrieval_after_offline_query_embedding_cache",
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _plot(rows, output)
    print(f"[RP2 sensitivity] completed: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
