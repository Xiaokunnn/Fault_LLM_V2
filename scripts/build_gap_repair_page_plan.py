"""Freeze one gap-repair page pool for the six classes that failed source-v3."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COVERAGE = (
    "data/interim/candidate_triples/"
    "qwen3_7_max_corpus_retrieval_v3_source_supplement_"
    "strict_v4_auto_adjudicated/"
    "auto_adjudicated_coverage_evidence_only.json"
)
DEFAULT_RECORDS = (
    "data/interim/candidate_triples/"
    "qwen3_7_max_corpus_retrieval_v3_source_supplement_"
    "strict_v4_auto_adjudicated/"
    "candidate_triples.auto_adjudicated_silver.jsonl"
)
DEFAULT_POOL = (
    "data/interim/candidate_pages/"
    "corpus_retrieval_v3_source_supplement/candidate_pages.jsonl"
)
DEFAULT_PARSED = "data/interim/parsed_pages/corpus_v2"
DEFAULT_OUTPUT = "data/interim/candidate_pages/gap_repair_v1"

FAULT_LABELS = {
    "cavitation": "汽蚀",
    "air_ingress_or_loss_of_prime": "空气侵入或失去自吸",
    "mechanical_seal_failure": "机械密封失效",
    "motor_electrical_drive_failure": "电机电气驱动故障",
    "pipe_or_valve_integrity_failure": "管路或阀件完整性故障",
    "dry_running_or_maintenance_induced_failure": "干运转或维护引入故障",
}

# These pages were already admitted through the versioned AI visual-layout
# review or were identified in the rejection audit as containing an explicit
# missing-role statement. They prevent the lexical retrieval score from
# excluding a known correction/troubleshooting table.
CURATED_PAGES: dict[tuple[str, int], dict[str, list[str]]] = {
    ("MP017", 13): {
        "classes": ["air_ingress_or_loss_of_prime", "pipe_or_valve_integrity_failure"],
        "roles": ["inspection", "maintenance"],
    },
    ("MP017", 14): {
        "classes": ["air_ingress_or_loss_of_prime", "pipe_or_valve_integrity_failure"],
        "roles": ["inspection", "maintenance"],
    },
    ("MP017", 15): {
        "classes": ["motor_electrical_drive_failure"],
        "roles": ["inspection", "maintenance"],
    },
    ("MP017", 17): {
        "classes": [
            "air_ingress_or_loss_of_prime",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP017", 18): {
        "classes": ["air_ingress_or_loss_of_prime"],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP018", 24): {
        "classes": ["mechanical_seal_failure", "pipe_or_valve_integrity_failure"],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP018", 25): {
        "classes": ["mechanical_seal_failure", "pipe_or_valve_integrity_failure"],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP018", 26): {
        "classes": [
            "mechanical_seal_failure",
            "motor_electrical_drive_failure",
            "pipe_or_valve_integrity_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP018", 27): {
        "classes": [
            "cavitation",
            "air_ingress_or_loss_of_prime",
            "mechanical_seal_failure",
            "motor_electrical_drive_failure",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP019", 19): {
        "classes": ["motor_electrical_drive_failure"],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP019", 20): {
        "classes": ["motor_electrical_drive_failure"],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP020", 20): {
        "classes": [
            "air_ingress_or_loss_of_prime",
            "motor_electrical_drive_failure",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP020", 21): {
        "classes": [
            "cavitation",
            "air_ingress_or_loss_of_prime",
            "mechanical_seal_failure",
            "pipe_or_valve_integrity_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP020", 22): {
        "classes": [
            "cavitation",
            "air_ingress_or_loss_of_prime",
            "mechanical_seal_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP020", 26): {
        "classes": [
            "cavitation",
            "air_ingress_or_loss_of_prime",
            "mechanical_seal_failure",
            "motor_electrical_drive_failure",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP021", 5): {
        "classes": [
            "mechanical_seal_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP021", 16): {
        "classes": [
            "air_ingress_or_loss_of_prime",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
    ("MP021", 17): {
        "classes": [
            "cavitation",
            "air_ingress_or_loss_of_prime",
            "pipe_or_valve_integrity_failure",
            "dry_running_or_maintenance_induced_failure",
        ],
        "roles": ["symptom", "inspection", "maintenance"],
    },
}


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_page_lookup(parsed_dir: Path) -> dict[tuple[str, int], dict[str, object]]:
    result: dict[tuple[str, int], dict[str, object]] = {}
    for path in parsed_dir.glob("*.pages.v2.jsonl"):
        for page in read_jsonl(path):
            result[(str(page["doc_id"]), int(page["pdf_page_number"]))] = page
    return result


def missing_roles(coverage: dict[str, object]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    fault_coverage = coverage.get("fault_coverage", {})
    if not isinstance(fault_coverage, dict):
        return result
    for fault_id in FAULT_LABELS:
        entry = fault_coverage.get(fault_id, {})
        if not isinstance(entry, dict) or entry.get("gate_passed") is True:
            continue
        checks = entry.get("gate_checks", {})
        roles: set[str] = set()
        if isinstance(checks, dict):
            if checks.get("symptom_at_least_5") is not True:
                roles.add("symptom")
            if checks.get("cause_or_mechanism_at_least_3") is not True:
                roles.add("cause_or_mechanism")
            if checks.get("inspection_or_maintenance_at_least_2") is not True:
                roles.update(("inspection", "maintenance"))
        result[fault_id] = roles
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE)
    parser.add_argument("--records", default=DEFAULT_RECORDS)
    parser.add_argument("--pool", default=DEFAULT_POOL)
    parser.add_argument("--parsed-dir", default=DEFAULT_PARSED)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    coverage_path = PROJECT_ROOT / args.coverage
    records_path = PROJECT_ROOT / args.records
    pool_path = PROJECT_ROOT / args.pool
    parsed_dir = PROJECT_ROOT / args.parsed_dir
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    records = read_jsonl(records_path)
    pool = read_jsonl(pool_path)
    page_lookup = load_page_lookup(parsed_dir)
    gaps = missing_roles(coverage)
    if set(gaps) != set(FAULT_LABELS):
        raise ValueError(
            "Frozen gap-repair v1 expects exactly the six source-v3 failed classes; "
            f"found {sorted(gaps)}"
        )

    selected: dict[tuple[str, int], dict[str, object]] = {}

    def admit(
        key: tuple[str, int],
        *,
        fault_id: str,
        role: str,
        reason: str,
        detail: dict[str, object] | None = None,
    ) -> None:
        if fault_id not in gaps or role not in gaps[fault_id]:
            return
        item = selected.setdefault(
            key,
            {
                "faults": set(),
                "roles": set(),
                "reasons": set(),
                "details": [],
            },
        )
        item["faults"].add(fault_id)
        item["roles"].add(role)
        item["reasons"].add(reason)
        if detail is not None:
            item["details"].append(detail)

    for item in pool:
        key = (str(item["doc_id"]), int(item["pdf_page_number"]))
        for raw_detail in item.get("retrieval_details", []) or []:
            detail = dict(raw_detail)
            fault_id = str(detail.get("fault_id", ""))
            role = str(detail.get("evidence_role", ""))
            admit(
                key,
                fault_id=fault_id,
                role=role,
                reason="wide_recall_missing_role_hit",
                detail=detail,
            )

    for record in records:
        if record.get("decision") == "silver_candidate":
            continue
        role = str(record.get("evidence_role", ""))
        key = (str(record["doc_id"]), int(record["pdf_page_number"]))
        for fault_id in record.get("fault_class_ids", []) or []:
            admit(
                key,
                fault_id=str(fault_id),
                role=role,
                reason="existing_non_silver_missing_role_candidate",
            )

    for key, scope in CURATED_PAGES.items():
        for fault_id in scope["classes"]:
            for role in scope["roles"]:
                admit(
                    key,
                    fault_id=fault_id,
                    role=role,
                    reason="curated_explicit_gap_evidence_page",
                )

    output_records: list[dict[str, object]] = []
    table_reparse_pages: list[str] = []
    for key in sorted(selected):
        if key not in page_lookup:
            raise KeyError(f"Parsed page not found: {key[0]}:{key[1]}")
        page = page_lookup[key]
        selection = selected[key]
        has_tables = bool(page.get("tables"))
        visual_checked = page.get("visual_layout_checked") is True
        table_reparse = has_tables and visual_checked
        if table_reparse:
            table_reparse_pages.append(f"{key[0]}:{key[1]}")
        output_records.append(
            {
                "page_key": f"{key[0]}:{key[1]}",
                "doc_id": key[0],
                "pdf_page_number": key[1],
                "document_split": page.get("document_split"),
                "source_family_id": page.get("source_family_id"),
                "publisher": page.get("publisher"),
                "source_url": page.get("source_url"),
                "normalized_text_sha256": page.get("page_text_sha256"),
                "target_fault_classes": sorted(selection["faults"]),
                "target_evidence_roles": sorted(selection["roles"]),
                "retrieval_details": selection["details"],
                "selection_reasons": sorted(selection["reasons"]),
                "has_parser_tables": has_tables,
                "visual_layout_checked": visual_checked,
                "table_reparse_required": table_reparse,
            }
        )

    write_jsonl(output_dir / "candidate_pages.jsonl", output_records)
    per_fault = {
        fault_id: sum(
            fault_id in item["target_fault_classes"] for item in output_records
        )
        for fault_id in FAULT_LABELS
    }
    summary = {
        "version": "marine_pump_gap_repair_page_plan_v1",
        "frozen_from_coverage_sha256": sha256_file(coverage_path),
        "frozen_from_records_sha256": sha256_file(records_path),
        "frozen_from_pool_sha256": sha256_file(pool_path),
        "failed_fault_classes": list(FAULT_LABELS),
        "missing_roles": {key: sorted(value) for key, value in gaps.items()},
        "candidate_pages": len(output_records),
        "pages_by_document": dict(
            sorted(Counter(item["doc_id"] for item in output_records).items())
        ),
        "pages_by_fault_class": per_fault,
        "table_reparse_pages": table_reparse_pages,
        "table_reparse_page_count": len(table_reparse_pages),
        "selection_policy": [
            "all wide-recall pages matching a failed role",
            "all non-Silver candidates already mapped to a failed role",
            "curated explicit troubleshooting/correction pages from source intake",
            "no pages from the four already-passing classes solely for their passed roles",
        ],
        "label_policy": "Silver only; never Gold",
    }
    (output_dir / "gap_repair_plan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config_path = PROJECT_ROOT / "configs/gap_repair_plan_marine_pump_v1.json"
    config_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_doc: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in output_records:
        by_doc[str(item["doc_id"])].append(item)
    lines = [
        "# 六类故障一次性缺口页面清单 v1",
        "",
        "本清单由source-v3最终覆盖矩阵、非Silver记录和已核验代表页一次性冻结。",
        "它只服务于缺失证据角色修复，不用于改变门槛或补做全量抽取。",
        "",
        f"- 页面数：{len(output_records)}",
        f"- 明确表格重解析页：{len(table_reparse_pages)}",
        "- 标签政策：仅Silver，绝不称Gold",
        "",
        "## 缺口",
        "",
    ]
    for fault_id, roles in gaps.items():
        lines.append(
            f"- {FAULT_LABELS[fault_id]}：{', '.join(sorted(roles))}；"
            f"页面={per_fault[fault_id]}"
        )
    lines.extend(["", "## 页面", ""])
    for doc_id in sorted(by_doc):
        pages = by_doc[doc_id]
        lines.append(f"### {doc_id}")
        lines.append("")
        for item in pages:
            classes = "、".join(
                FAULT_LABELS[value]
                for value in item["target_fault_classes"]
            )
            roles = "、".join(item["target_evidence_roles"])
            table_flag = "；同行/同行组表格重解析" if item["table_reparse_required"] else ""
            lines.append(
                f"- 物理页{item['pdf_page_number']}：{classes}；{roles}{table_flag}"
            )
        lines.append("")
    report_path = PROJECT_ROOT / "docs/research/gap_repair_page_plan_v1.md"
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(
        f"[Gap Plan] 完成：缺口类别={len(gaps)}，页面={len(output_records)}，"
        f"表格重解析页={len(table_reparse_pages)}",
        flush=True,
    )
    for fault_id, roles in gaps.items():
        print(
            f"[Gap Plan] {FAULT_LABELS[fault_id]}："
            f"角色={','.join(sorted(roles))}，页面={per_fault[fault_id]}",
            flush=True,
        )


if __name__ == "__main__":
    main()
