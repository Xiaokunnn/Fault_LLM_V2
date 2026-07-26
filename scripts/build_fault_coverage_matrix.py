"""Build the auditable fault-class coverage and targeted-extraction matrix."""

from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_gate(
    *,
    symptoms: int,
    causes: int,
    actions: int,
    documents: int,
    source_families: int,
    gate: dict[str, int],
) -> tuple[dict[str, bool], bool]:
    checks = {
        "symptom": symptoms >= gate["symptom"],
        "cause_or_mechanism": causes >= gate["cause_or_mechanism"],
        "inspection_or_maintenance": (
            actions >= gate["inspection_or_maintenance"]
        ),
        "independent_documents": documents >= gate["independent_documents"],
        "independent_source_families": (
            source_families >= gate["independent_source_families"]
        ),
    }
    return checks, all(checks.values())


def main() -> None:
    ontology = json.loads(
        (PROJECT_ROOT / "configs/fault_ontology_marine_pump_v1.json").read_text(
            encoding="utf-8"
        )
    )
    pilot = json.loads(
        (
            PROJECT_ROOT
            / "results/benchmarks/qwen3_7_max_triple_pilot_v1"
            / "pilot_coverage_report.json"
        ).read_text(encoding="utf-8")
    )
    strict_path = (
        PROJECT_ROOT
        / "data/interim/candidate_triples/qwen3_7_max_triple_pilot_strict_v2"
        / "strict_v2_coverage_report.json"
    )
    strict = (
        json.loads(strict_path.read_text(encoding="utf-8"))
        if strict_path.exists()
        else None
    )
    lexical_path = (
        PROJECT_ROOT
        / "data/kg/marine_pump/silver_evidencebench"
        / "source_coverage_lexical_build_v2.csv"
    )
    lexical = {row["fault_id"]: row for row in read_csv(lexical_path)}
    gate = ontology["coverage_gate"]
    rows: list[dict[str, object]] = []

    for fault in ontology["fault_classes"]:
        fault_id = fault["fault_id"]
        pilot_current = pilot["fault_coverage"].get(fault_id, {})
        current = (
            strict["fault_coverage"].get(fault_id, {})
            if strict is not None
            else pilot_current
        )
        source = lexical.get(fault_id, {})
        symptoms = int(current.get("symptom_evidence", 0))
        causes = int(current.get("cause_or_mechanism_evidence", 0))
        actions = int(current.get("inspection_or_maintenance_evidence", 0))
        docs = list(current.get("document_ids", []))
        families = list(current.get("source_families", []))
        gate_checks, gate_passed = evaluate_gate(
            symptoms=symptoms,
            causes=causes,
            actions=actions,
            documents=len(docs),
            source_families=len(families),
            gate=gate,
        )
        rows.append(
            {
                "fault_id": fault_id,
                "name_zh": fault["name_zh"],
                "strict_v2_symptom": symptoms,
                "target_symptom": gate["symptom"],
                "symptom_gap": max(0, gate["symptom"] - symptoms),
                "strict_v2_cause_or_mechanism": causes,
                "target_cause_or_mechanism": gate["cause_or_mechanism"],
                "cause_or_mechanism_gap": max(
                    0, gate["cause_or_mechanism"] - causes
                ),
                "strict_v2_inspection_or_maintenance": actions,
                "target_inspection_or_maintenance": gate[
                    "inspection_or_maintenance"
                ],
                "inspection_or_maintenance_gap": max(
                    0, gate["inspection_or_maintenance"] - actions
                ),
                "strict_v2_document_count": len(docs),
                "target_document_count": gate["independent_documents"],
                "document_gap": max(0, gate["independent_documents"] - len(docs)),
                "strict_v2_source_family_count": len(families),
                "target_source_family_count": gate["independent_source_families"],
                "source_family_gap": max(
                    0, gate["independent_source_families"] - len(families)
                ),
                "strict_v2_document_ids": ";".join(docs),
                "strict_v2_source_families": ";".join(families),
                "pilot_v1_reported_symptom": int(
                    pilot_current.get("symptom_evidence", 0)
                ),
                "pilot_v1_reported_cause_or_mechanism": int(
                    pilot_current.get("cause_or_mechanism_evidence", 0)
                ),
                "pilot_v1_reported_inspection_or_maintenance": int(
                    pilot_current.get("inspection_or_maintenance_evidence", 0)
                ),
                "candidate_build_document_ids": source.get("matched_doc_ids", ""),
                "candidate_build_source_families": source.get(
                    "matched_source_family_ids", ""
                ),
                "candidate_page_keys": source.get("candidate_page_keys", ""),
                "lexical_screening_status": source.get(
                    "screening_status", "not_run"
                ),
                "gate_checks": json.dumps(
                    gate_checks,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "gate_passed": gate_passed,
                "strict_v2_status": (
                    (
                        "formal_gate_passed"
                        if gate_passed
                        else "revalidated_targeted_extraction_required"
                    )
                    if strict is not None
                    else "pending_revalidation_and_targeted_extraction"
                ),
                "class_graph_eligible": gate_passed,
            }
        )

    passing_classes = sum(bool(row["gate_passed"]) for row in rows)
    bulk_graph_authorized = bool(rows) and passing_classes == len(rows)
    output_dir = (
        PROJECT_ROOT / "data/kg/marine_pump/silver_evidencebench"
    )
    csv_path = output_dir / "fault_category_coverage_matrix_v2.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "version": "marine_pump_fault_category_coverage_matrix_v2",
        "ontology_version": ontology["version"],
        "pilot_report_version": pilot["report_version"],
        "current_counts_are": (
            "strict-v2 locally revalidated Silver candidates"
            if strict is not None
            else "legacy pilot-v1 reported Silver candidates"
        ),
        "strict_v2_interpretation": (
            "Strict-v2 applies relation-entailment, entity-anchor, source-family, "
            "split and E1/E2 gates. Lexical page candidates guide extraction only."
        ),
        "classes_passing_formal_gate": passing_classes,
        "total_fault_classes": len(rows),
        "bulk_graph_authorized": bulk_graph_authorized,
        "rows": rows,
    }
    json_path = output_dir / "fault_category_coverage_matrix_v2.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown = [
        "# 船舶机舱泵系故障类别覆盖矩阵 v2",
        "",
        "当前数量来自严格v2本地复验；词法候选页只用于选页，不是三元组或Silver证据。"
        "旧试抽取结果仍作为历史对照保留。",
        "",
        "| 故障类别 | 症状 当前/目标 | 原因 当前/目标 | 检查维护 当前/目标 | 文档 当前/目标 | 来源族 当前/目标 | 状态 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        status = (
            "严格门槛通过"
            if row["gate_passed"]
            else "已严格复验，待定向补抽"
        )
        markdown.append(
            "| {name_zh} | {strict_v2_symptom}/{target_symptom} | "
            "{strict_v2_cause_or_mechanism}/{target_cause_or_mechanism} | "
            "{strict_v2_inspection_or_maintenance}/{target_inspection_or_maintenance} | "
            "{strict_v2_document_count}/{target_document_count} | "
            "{strict_v2_source_family_count}/{target_source_family_count} | "
            f"{status} |".format(**row)
        )
    markdown.extend(
        [
            "",
            (
                "结论：所有类别均已达到硬门槛，可以进入批量构图。"
                if bulk_graph_authorized
                else (
                    f"结论：当前{passing_classes}/{len(rows)}类通过硬门槛，"
                    "尚未获得批量构图授权。"
                )
            ),
            "",
        ]
    )
    (output_dir / "fault_category_coverage_matrix_v2.md").write_text(
        "\n".join(markdown),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "output": str(csv_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
