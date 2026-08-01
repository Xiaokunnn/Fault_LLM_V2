#!/usr/bin/env python3
"""Run the x1/x2/x4/x8 same-source-family replication pressure test."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib.pyplot as plt  # noqa: E402

from research_point_1_graph_evidence.stage04_graph_build import (  # noqa: E402
    filter_eligible_assertions,
    replication_pressure_experiment,
)


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> int:
    source = ROOT / "data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl"
    output = ROOT / "results/experiments/research_point_1/source_family_replication_pressure_v1"
    output.mkdir(parents=True, exist_ok=True)
    print(f"[RP1 replication] loading {source}", flush=True)
    eligible = filter_eligible_assertions(_load_jsonl(source)).records
    result = replication_pressure_experiment(
        eligible,
        multipliers=(1, 2, 4, 8),
        budget=2,
        decision_threshold=0.8,
    )
    rows = result["rows"]
    (output / "replication_pressure.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "replication_pressure.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    multipliers = [row["replication_multiplier"] for row in rows]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    axes[0].plot(
        multipliers,
        [row["document_naive_support_mean"] for row in rows],
        marker="o",
        label="Naive document count",
        color="#b45309",
    )
    axes[0].plot(
        multipliers,
        [row["family_support_mean"] for row in rows],
        marker="o",
        label="Source-family capped",
        color="#0f766e",
    )
    axes[0].set_xlabel("Same-family replication multiplier")
    axes[0].set_ylabel("Mean corroboration index")
    axes[0].grid(alpha=0.25)
    axes[0].legend(frameon=False)
    axes[1].plot(
        multipliers,
        [row["document_naive_decisions_ge_threshold"] for row in rows],
        marker="o",
        label="Naive document count",
        color="#b45309",
    )
    axes[1].plot(
        multipliers,
        [row["family_decisions_ge_threshold"] for row in rows],
        marker="o",
        label="Source-family capped",
        color="#0f766e",
    )
    axes[1].set_xlabel("Same-family replication multiplier")
    axes[1].set_ylabel("Claims above threshold 0.8")
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False)
    fig.suptitle("RP1 same-source-family replication pressure")
    fig.tight_layout()
    fig.savefig(output / "replication_pressure.png", dpi=200, bbox_inches="tight")
    fig.savefig(output / "replication_pressure.svg", bbox_inches="tight")
    plt.close(fig)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print(f"[RP1 replication] outputs={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
