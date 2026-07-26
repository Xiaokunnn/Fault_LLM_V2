"""Produce a decision-oriented corpus sufficiency report after large-pool extraction."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pool", required=True)
    parser.add_argument("--strict-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    ontology = json.loads(
        (PROJECT_ROOT / "configs/fault_ontology_marine_pump_v1.json").read_text(
            encoding="utf-8"
        )
    )
    thresholds = ontology["coverage_gate"]
    pages = read_jsonl(PROJECT_ROOT / args.candidate_pool)
    strict_dir = PROJECT_ROOT / args.strict_dir
    strict = json.loads(
        (strict_dir / "strict_v2_coverage_evidence_only_audit.json").read_text(
            encoding="utf-8"
        )
    )

    direct_pages: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    documents: dict[str, set[str]] = defaultdict(set)
    families: dict[str, set[str]] = defaultdict(set)
    for page in pages:
        for detail in page.get("retrieval_details", []) or []:
            if detail.get("retrieval_mode") == "adjacent_context":
                continue
            fault_id = str(detail["fault_id"])
            role = str(detail["evidence_role"])
            direct_pages[fault_id][role].add(str(page["page_key"]))
            documents[fault_id].add(str(page["doc_id"]))
            families[fault_id].add(str(page["source_family_id"]))

    results: list[dict[str, object]] = []
    for fault in ontology["fault_classes"]:
        fault_id = str(fault["fault_id"])
        coverage = strict["fault_coverage"][fault_id]
        potential_checks = {
            "symptom_candidate_pages_at_least_5": len(
                direct_pages[fault_id]["symptom"]
            )
            >= int(thresholds["symptom"]),
            "cause_candidate_pages_at_least_3": len(
                direct_pages[fault_id]["cause_or_mechanism"]
            )
            >= int(thresholds["cause_or_mechanism"]),
            "action_candidate_pages_at_least_2": (
                len(direct_pages[fault_id]["inspection"])
                + len(direct_pages[fault_id]["maintenance"])
            )
            >= int(thresholds["inspection_or_maintenance"]),
            "documents_at_least_2": len(documents[fault_id])
            >= int(thresholds["independent_documents"]),
            "source_families_at_least_2": len(families[fault_id])
            >= int(thresholds["independent_source_families"]),
        }
        strict_passed = bool(coverage["gate_passed"])
        lexical_potential = all(potential_checks.values())
        if strict_passed:
            decision = "current_documents_sufficient"
            next_action = "eligible_for_full_extraction"
        elif lexical_potential:
            decision = "not_proven_sufficient"
            next_action = "inspect_extraction_or_validation_gap_before_new_sources"
        else:
            decision = "current_documents_insufficient_at_candidate_evidence_level"
            next_action = "add_independent_documents_for_missing_roles_or_sources"
        results.append(
            {
                "fault_id": fault_id,
                "name_zh": fault["name_zh"],
                "decision": decision,
                "next_action": next_action,
                "strict_coverage": coverage,
                "direct_candidate_page_counts": {
                    role: len(direct_pages[fault_id][role])
                    for role in (
                        "symptom",
                        "cause_or_mechanism",
                        "inspection",
                        "maintenance",
                    )
                },
                "candidate_documents": sorted(documents[fault_id]),
                "candidate_source_families": sorted(families[fault_id]),
                "candidate_potential_checks": potential_checks,
            }
        )

    passed = sum(
        item["decision"] == "current_documents_sufficient" for item in results
    )
    insufficient = sum(
        item["decision"]
        == "current_documents_insufficient_at_candidate_evidence_level"
        for item in results
    )
    report = {
        "version": "marine_pump_large_candidate_corpus_sufficiency_v1",
        "candidate_pages": len(pages),
        "strict_classes_passing": passed,
        "classes_with_candidate_level_source_or_role_gap": insufficient,
        "global_decision": (
            "proceed_to_full_extraction"
            if passed == len(results)
            else "do_not_start_full_extraction"
        ),
        "fault_classes": results,
    }
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "corpus_sufficiency_decision.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# 现有文档故障覆盖能力判定",
        "",
        f"- 大候选池：{len(pages)}页",
        f"- 严格覆盖通过：{passed}/10类",
        f"- 候选层仍缺角色或来源：{insufficient}/10类",
        f"- 总体决策：`{report['global_decision']}`",
        "",
        "| 故障类别 | 严格判定 | 症状候选页 | 原因候选页 | 检查候选页 | 维护候选页 | 来源族 | 下一步 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        counts = item["direct_candidate_page_counts"]
        lines.append(
            f"| {item['name_zh']} | {item['decision']} | "
            f"{counts['symptom']} | {counts['cause_or_mechanism']} | "
            f"{counts['inspection']} | {counts['maintenance']} | "
            f"{len(item['candidate_source_families'])} | {item['next_action']} |"
        )
    (output_dir / "corpus_sufficiency_decision.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(
        f"[Coverage Decision] 完成：严格通过={passed}/10，"
        f"候选层明确缺口={insufficient}/10，"
        f"总体={report['global_decision']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
