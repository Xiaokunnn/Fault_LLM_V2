#!/usr/bin/env python3
"""Build a deterministic wording-robustness benchmark for the RP2 v6 protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PARAPHRASE_TEMPLATES: dict[str, tuple[str, str]] = {
    "symptom": (
        "当泵系出现“{fault}”时，可由资料原文支持的外在表现、症状或信号有哪些？",
        "请只依据可追溯证据，列出“{fault}”能够观察到的故障征兆。",
    ),
    "cause_or_mechanism": (
        "从资料证据看，哪些原因、运行工况或作用机理会引发或加剧“{fault}”？",
        "请列出与“{fault}”有关且有原文佐证的成因和形成机理。",
    ),
    "inspection": (
        "为了检查或诊断“{fault}”，资料中给出了哪些可追溯的方法？",
        "请只依据原文证据，列出用于确认“{fault}”的检查或诊断措施。",
    ),
    "maintenance": (
        "针对“{fault}”，有哪些得到原文支持的维护、缓解或预防做法？",
        "请列出可追溯资料中用于处理或避免“{fault}”的维护措施。",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_paraphrases(source_queries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return two auditable rewrites per query without changing structured labels."""

    output: list[dict] = []
    mapping: list[dict] = []
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    for source in source_queries:
        role = str(source["role"])
        if role not in PARAPHRASE_TEMPLATES:
            raise ValueError(f"Unsupported RP2 query role: {role!r}")
        fault = str(source["fault_name_zh"]).strip()
        if not fault:
            raise ValueError(f"Missing fault_name_zh for {source.get('query_id')}")
        for variant, template in enumerate(PARAPHRASE_TEMPLATES[role], start=1):
            query_id = f"{source['query_id']}-P{variant}"
            question = template.format(fault=fault)
            if query_id in seen_ids or question in seen_questions:
                raise ValueError(f"Duplicate paraphrase generated: {query_id}")
            row = {
                "query_id": query_id,
                "question_zh": question,
                "fault_id": source["fault_id"],
                "fault_name_zh": source["fault_name_zh"],
                "role": role,
                "relevant_evidence_ids": list(source.get("relevant_evidence_ids", [])),
                "candidate_evidence_ids": [],
                "label_status": source.get("label_status", "development_silver"),
            }
            output.append(row)
            mapping.append(
                {
                    "query_id": query_id,
                    "parent_query_id": source["query_id"],
                    "variant": variant,
                    "template_role": role,
                    "labels_copied_without_change": True,
                }
            )
            seen_ids.add(query_id)
            seen_questions.add(question)
    return output, mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        default="data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2",
    )
    parser.add_argument(
        "--output-dir",
        default="data/kg/marine_pump/silver_evidencebench/rp2_v6_paraphrase_robustness",
    )
    args = parser.parse_args()

    source = ROOT / args.source_dir
    output = ROOT / args.output_dir
    query_path = source / "queries.jsonl"
    evidence_path = source / "evidence_candidates.jsonl"
    manifest_path = source / "manifest.json"
    for required in (query_path, evidence_path, manifest_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    source_queries = _read_jsonl(query_path)
    paraphrases, mapping = build_paraphrases(source_queries)
    if len(paraphrases) != len(source_queries) * 2:
        raise RuntimeError("The robustness benchmark must contain exactly two rewrites per query")
    if any(row["candidate_evidence_ids"] for row in paraphrases):
        raise RuntimeError("Positive-seeded candidate pools are forbidden")

    output.mkdir(parents=True, exist_ok=True)
    with (output / "queries.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in paraphrases:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "paraphrase_map.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for row in mapping:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    shutil.copyfile(evidence_path, output / "evidence_candidates.jsonl")

    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = {
        "benchmark_id": "marine_pump_rp2_v6_paraphrase_robustness",
        "parent_benchmark_id": source_manifest.get("benchmark_id"),
        "scope": "development_wording_robustness_only_not_held_out",
        "structured_input_policy": (
            "question wording changes; fault_id, fault_name_zh, role and Silver labels stay fixed"
        ),
        "generation_policy": "two deterministic role-specific templates per parent query",
        "parent_query_count": len(source_queries),
        "query_count": len(paraphrases),
        "answerable_query_count": sum(bool(row["relevant_evidence_ids"]) for row in paraphrases),
        "unanswerable_query_count": sum(not row["relevant_evidence_ids"] for row in paraphrases),
        "candidate_count": int(source_manifest.get("candidate_count", 0)),
        "positive_seeded_candidate_pool": False,
        "parameters_tuned_on_paraphrases": False,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "source_files": {
            "queries": {
                "path": query_path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(query_path),
            },
            "evidence_candidates": {
                "path": evidence_path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(evidence_path),
            },
            "manifest": {
                "path": manifest_path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(manifest_path),
            },
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[RP2 v6 paraphrase] parents={len(source_queries)}, rewrites={len(paraphrases)}, "
        f"output={output.relative_to(ROOT)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
