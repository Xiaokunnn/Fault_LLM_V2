"""Offline B0--Ours comparison and ablation for research point 1.

The experiment operates on one frozen candidate universe.  It measures the
structural effect of cumulative governance and release gates; it does not
rerun extraction prompts, estimate factual accuracy, or create Gold labels.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from typing import Callable, Iterable, Mapping, Sequence

from research_point_1_graph_evidence.stage04_graph_build.source_family_support import (
    heuristic_assertion_score,
)


EXPERIMENT_VERSION = "marine_pump_rp1_b0_ours_ablation_v1"
STAGE_ORDER = ("B0", "B1", "B2", "B3", "Ours")
STAGE_NAMES_ZH = {
    "B0": "固定候选扁平接受",
    "B1": "Schema约束",
    "B2": "结构证据门控",
    "B3": "可追溯Silver治理",
    "Ours": "来源族与中文双门控",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"Expected JSON object at {path}:{line_number}"
                )
            records.append(value)
    return records


def relation_schema_gate(record: Mapping[str, object]) -> bool:
    validation = record.get("relation_type_validation")
    return (
        record.get("relation_type_valid") is True
        and isinstance(validation, Mapping)
        and validation.get("valid") is True
    )


def evidence_grounding_gate(record: Mapping[str, object]) -> bool:
    validation = record.get("evidence_validation")
    return (
        isinstance(validation, Mapping)
        and validation.get("valid") is True
        and validation.get("silver_eligible") is True
        and record.get("evidence_level") in {"E1", "E2"}
        and bool(str(record.get("evidence_text") or "").strip())
    )


def relation_entailment_gate(record: Mapping[str, object]) -> bool:
    validation = record.get("relation_entailment_validation")
    return (
        record.get("relation_entailment_valid") is True
        and isinstance(validation, Mapping)
        and validation.get("valid") is True
        and validation.get("silver_eligible") is True
        and validation.get("status") == "entailed"
    )


def provenance_and_split_gate(
    record: Mapping[str, object],
    *,
    build_doc_ids: frozenset[str],
) -> bool:
    required = (
        "source_family_id",
        "pdf_page_number",
        "source_url",
        "document_sha256",
        "page_text_sha256",
    )
    return (
        record.get("document_split") == "build_train"
        and str(record.get("doc_id") or "") in build_doc_ids
        and record.get("inferred_edge") is not True
        and all(record.get(field) not in (None, "") for field in required)
    )


def score_gate(
    record: Mapping[str, object],
    *,
    threshold: float,
) -> bool:
    return heuristic_assertion_score(record) >= threshold


def chinese_release_gate(record: Mapping[str, object]) -> bool:
    return (
        record.get("eligible_for_chinese_graph") is True
        and record.get("graph_release_status") == "core_silver_ready"
        and bool(str(record.get("head_terminology_id") or "").strip())
        and bool(str(record.get("tail_terminology_id") or "").strip())
        and bool(str(record.get("head_canonical_zh") or "").strip())
        and bool(str(record.get("tail_canonical_zh") or "").strip())
    )


def stage_predicates(
    *,
    build_doc_ids: frozenset[str],
    score_threshold: float,
) -> dict[str, Callable[[Mapping[str, object]], bool]]:
    relation = relation_schema_gate
    evidence = evidence_grounding_gate
    entailment = relation_entailment_gate

    def provenance(record: Mapping[str, object]) -> bool:
        return provenance_and_split_gate(
            record,
            build_doc_ids=build_doc_ids,
        )

    def score(record: Mapping[str, object]) -> bool:
        return score_gate(record, threshold=score_threshold)

    return {
        "B0": lambda record: True,
        "B1": relation,
        "B2": lambda record: relation(record) and evidence(record),
        "B3": lambda record: (
            relation(record)
            and evidence(record)
            and entailment(record)
            and provenance(record)
            and score(record)
        ),
        "Ours": lambda record: (
            relation(record)
            and evidence(record)
            and entailment(record)
            and provenance(record)
            and score(record)
            and chinese_release_gate(record)
        ),
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _entity_ids(records: Sequence[Mapping[str, object]]) -> set[str]:
    result: set[str] = set()
    for record in records:
        for field in ("head_entity_id", "tail_entity_id"):
            value = str(record.get(field) or "").strip()
            if value:
                result.add(value)
    return result


def _fault_ids(records: Sequence[Mapping[str, object]]) -> set[str]:
    return {
        str(fault_id)
        for record in records
        for fault_id in (record.get("fault_class_ids") or [])
        if str(fault_id)
    }


def _gate_rates(
    records: Sequence[Mapping[str, object]],
    *,
    build_doc_ids: frozenset[str],
    score_threshold: float,
) -> dict[str, float]:
    predicates: list[tuple[str, Callable[[Mapping[str, object]], bool]]] = [
        ("schema_pass_rate", relation_schema_gate),
        ("evidence_grounding_pass_rate", evidence_grounding_gate),
        ("entailment_pass_rate", relation_entailment_gate),
        (
            "provenance_split_pass_rate",
            lambda record: provenance_and_split_gate(
                record,
                build_doc_ids=build_doc_ids,
            ),
        ),
        (
            "score_pass_rate",
            lambda record: score_gate(
                record,
                threshold=score_threshold,
            ),
        ),
        ("chinese_release_pass_rate", chinese_release_gate),
    ]
    return {
        name: _safe_rate(sum(predicate(record) for record in records), len(records))
        for name, predicate in predicates
    }


def compute_stage_rows(
    records: Sequence[Mapping[str, object]],
    *,
    build_doc_ids: Iterable[str],
    score_threshold: float = 0.8,
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    build_ids = frozenset(str(value) for value in build_doc_ids)
    predicates = stage_predicates(
        build_doc_ids=build_ids,
        score_threshold=score_threshold,
    )
    selected: dict[str, list[dict[str, object]]] = {}
    rows: list[dict[str, object]] = []
    denominator = len(records)
    for stage_id in STAGE_ORDER:
        stage_records = [
            dict(record)
            for record in records
            if predicates[stage_id](record)
        ]
        selected[stage_id] = stage_records
        row: dict[str, object] = {
            "method_id": stage_id,
            "method_name_zh": STAGE_NAMES_ZH[stage_id],
            "assertion_count": len(stage_records),
            "retention_from_b0": _safe_rate(
                len(stage_records),
                denominator,
            ),
            "claim_count": len(
                {
                    str(record.get("claim_id") or "")
                    for record in stage_records
                    if str(record.get("claim_id") or "")
                }
            ),
            "entity_count": len(_entity_ids(stage_records)),
            "document_count": len(
                {
                    str(record.get("doc_id") or "")
                    for record in stage_records
                    if str(record.get("doc_id") or "")
                }
            ),
            "source_family_count": len(
                {
                    str(record.get("source_family_id") or "")
                    for record in stage_records
                    if str(record.get("source_family_id") or "")
                }
            ),
            "fault_class_count": len(_fault_ids(stage_records)),
        }
        row.update(
            _gate_rates(
                stage_records,
                build_doc_ids=build_ids,
                score_threshold=score_threshold,
            )
        )
        rows.append(row)
    return rows, selected


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


def cluster_bootstrap_stage_retention(
    records: Sequence[Mapping[str, object]],
    *,
    build_doc_ids: Iterable[str],
    score_threshold: float,
    replicates: int,
    seed: int,
    confidence_level: float,
) -> list[dict[str, object]]:
    if replicates < 1:
        raise ValueError("replicates must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")
    build_ids = frozenset(str(value) for value in build_doc_ids)
    predicates = stage_predicates(
        build_doc_ids=build_ids,
        score_threshold=score_threshold,
    )
    by_doc: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        by_doc[str(record.get("doc_id") or "")].append(record)
    documents = sorted(by_doc)
    if not documents:
        return []
    doc_sizes = {
        doc_id: len(doc_records)
        for doc_id, doc_records in by_doc.items()
    }
    doc_stage_counts = {
        doc_id: {
            stage_id: sum(
                predicates[stage_id](record)
                for record in doc_records
            )
            for stage_id in STAGE_ORDER
        }
        for doc_id, doc_records in by_doc.items()
    }

    rng = random.Random(seed)
    samples: dict[str, list[float]] = {
        stage_id: [] for stage_id in STAGE_ORDER
    }
    for _ in range(replicates):
        sampled_docs = [
            rng.choice(documents) for _ in range(len(documents))
        ]
        denominator = sum(doc_sizes[doc_id] for doc_id in sampled_docs)
        for stage_id in STAGE_ORDER:
            numerator = sum(
                doc_stage_counts[doc_id][stage_id]
                for doc_id in sampled_docs
            )
            samples[stage_id].append(
                numerator / denominator if denominator else 0.0
            )

    alpha = (1.0 - confidence_level) / 2.0
    point_rows, _ = compute_stage_rows(
        records,
        build_doc_ids=build_ids,
        score_threshold=score_threshold,
    )
    point_by_stage = {
        str(row["method_id"]): float(row["retention_from_b0"])
        for row in point_rows
    }
    return [
        {
            "metric": "retention_from_b0",
            "cluster_unit": "document",
            "method_id": stage_id,
            "estimate": point_by_stage[stage_id],
            "ci_lower": round(
                percentile(samples[stage_id], alpha),
                6,
            ),
            "ci_upper": round(
                percentile(samples[stage_id], 1.0 - alpha),
                6,
            ),
            "confidence_level": confidence_level,
            "replicates": replicates,
            "seed": seed,
        }
        for stage_id in STAGE_ORDER
    ]


def _incremental_gate_rows(
    records: Sequence[Mapping[str, object]],
    *,
    selected: Mapping[str, Sequence[Mapping[str, object]]],
    build_doc_ids: frozenset[str],
    score_threshold: float,
) -> list[dict[str, object]]:
    b2 = list(selected["B2"])
    entailed = [record for record in b2 if relation_entailment_gate(record)]
    provenance = [
        record
        for record in entailed
        if provenance_and_split_gate(
            record,
            build_doc_ids=build_doc_ids,
        )
    ]
    scored = [
        record
        for record in provenance
        if score_gate(record, threshold=score_threshold)
    ]
    stages: list[tuple[str, str, Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]]] = [
        (
            "relation_schema",
            "关系Schema与Domain/Range",
            records,
            selected["B1"],
        ),
        (
            "evidence_grounding",
            "E1/E2原文与表格对齐",
            selected["B1"],
            selected["B2"],
        ),
        (
            "relation_entailment",
            "关系语义蕴含",
            b2,
            entailed,
        ),
        (
            "provenance_and_split",
            "溯源与文档划分",
            entailed,
            provenance,
        ),
        (
            "heuristic_score",
            "启发式分数阈值",
            provenance,
            scored,
        ),
        (
            "chinese_release",
            "中文术语发布门控",
            scored,
            selected["Ours"],
        ),
    ]
    return [
        {
            "module": module,
            "module_name_zh": label,
            "input_count": len(before),
            "output_count": len(after),
            "removed_count": len(before) - len(after),
            "removed_rate": _safe_rate(
                len(before) - len(after),
                len(before),
            ),
        }
        for module, label, before, after in stages
    ]


def _specific_ablation_rows(
    records: Sequence[Mapping[str, object]],
    *,
    selected: Mapping[str, Sequence[Mapping[str, object]]],
    source_summary: Mapping[str, object],
    cq_report: Mapping[str, object],
) -> list[dict[str, object]]:
    silver = list(selected["B3"])
    claim_counts = Counter(
        str(record.get("claim_id") or "") for record in silver
    )
    e3_excluded = sum(
        record.get("evidence_level") == "E3"
        and isinstance(record.get("evidence_validation"), Mapping)
        and record["evidence_validation"].get("valid") is True
        and record["evidence_validation"].get("silver_eligible") is not True
        for record in records
    )
    replication = dict(
        source_summary["replication_invariance_experiment"]
    )
    cq_overall = dict(cq_report["aggregate"]["overall"])
    missing_cq = (
        int(cq_overall["cq_count"])
        - int(cq_overall["answerable_cq_count"])
    )
    return [
        {
            "ablation": "release_e3",
            "name_zh": "将E3并入自动发布",
            "effect_value": e3_excluded,
            "effect_unit": "条E3重建证据失去人工隔离",
            "interpretation": "这些记录不应被自动等同于E1/E2。",
        },
        {
            "ablation": "flatten_claim_evidence",
            "name_zh": "扁平化Claim与Evidence",
            "effect_value": sum(
                count - 1 for count in claim_counts.values()
            ),
            "effect_unit": "条额外来源断言被覆盖",
            "interpretation": (
                f"{sum(count > 1 for count in claim_counts.values())}"
                "个多证据Claim受到影响。"
            ),
        },
        {
            "ablation": "document_count_as_independence",
            "name_zh": "以文档数代替来源族",
            "effect_value": round(
                int(replication["sum_claim_doc_counts_after"])
                / int(replication["sum_claim_doc_counts_before"])
                - 1.0,
                6,
            ),
            "effect_unit": "文档计数相对放大率",
            "interpretation": (
                "同族复制后文档计数翻倍，但来源族封顶指数变化为0。"
            ),
        },
        {
            "ablation": "remove_chinese_gate",
            "name_zh": "去除中文术语发布门控",
            "effect_value": len(silver) - len(selected["Ours"]),
            "effect_unit": "条非中文发布就绪记录会混入",
            "interpretation": "证据Silver不等于中文规范实体发布就绪。",
        },
        {
            "ablation": "remove_cq",
            "name_zh": "去除CQ功能评价",
            "effect_value": missing_cq,
            "effect_unit": "个功能缺口将不可见",
            "interpretation": "图谱规模不能替代可回答问题覆盖。",
        },
    ]


def compute_score_sensitivity(
    records: Sequence[Mapping[str, object]],
    *,
    build_doc_ids: Iterable[str],
    thresholds: Iterable[float],
) -> list[dict[str, object]]:
    build_ids = frozenset(str(value) for value in build_doc_ids)
    hard_gate_records = [
        record
        for record in records
        if relation_schema_gate(record)
        and evidence_grounding_gate(record)
        and relation_entailment_gate(record)
        and provenance_and_split_gate(
            record,
            build_doc_ids=build_ids,
        )
    ]
    rows: list[dict[str, object]] = []
    for threshold in thresholds:
        selected = [
            record
            for record in hard_gate_records
            if score_gate(record, threshold=float(threshold))
        ]
        rows.append(
            {
                "threshold": float(threshold),
                "assertion_count": len(selected),
                "claim_count": len(
                    {
                        str(record.get("claim_id") or "")
                        for record in selected
                    }
                ),
                "fault_class_count": len(_fault_ids(selected)),
                "retention_from_hard_gate": _safe_rate(
                    len(selected),
                    len(hard_gate_records),
                ),
            }
        )
    return rows


def compute_cq_sensitivity(
    task_results: Sequence[Mapping[str, object]],
    *,
    minimum_answers: Iterable[int],
    minimum_source_families: Iterable[int],
) -> dict[str, list[dict[str, object]]]:
    answer_rows = [
        {
            "minimum_answers": int(threshold),
            "answerable_task_count": sum(
                int(task.get("answer_count") or 0) >= int(threshold)
                for task in task_results
            ),
            "task_count": len(task_results),
            "answerable_rate": _safe_rate(
                sum(
                    int(task.get("answer_count") or 0) >= int(threshold)
                    for task in task_results
                ),
                len(task_results),
            ),
        }
        for threshold in minimum_answers
    ]
    family_rows = [
        {
            "minimum_source_families": int(threshold),
            "answerable_task_count": sum(
                int(task.get("answer_count") or 0) >= 1
                and int(task.get("source_family_count") or 0)
                >= int(threshold)
                for task in task_results
            ),
            "task_count": len(task_results),
            "answerable_rate": _safe_rate(
                sum(
                    int(task.get("answer_count") or 0) >= 1
                    and int(task.get("source_family_count") or 0)
                    >= int(threshold)
                    for task in task_results
                ),
                len(task_results),
            ),
        }
        for threshold in minimum_source_families
    ]
    return {
        "minimum_answers": answer_rows,
        "minimum_source_families": family_rows,
    }


def bootstrap_cq_answerability(
    task_results: Sequence[Mapping[str, object]],
    *,
    replicates: int,
    seed: int,
    confidence_level: float,
) -> dict[str, object]:
    by_fault: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for task in task_results:
        by_fault[str(task.get("fault_id") or "")].append(task)
    faults = sorted(by_fault)
    if not faults:
        return {
            "estimate": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "replicates": replicates,
            "seed": seed,
        }
    estimate = statistics.fmean(
        bool(task.get("structurally_answerable"))
        for task in task_results
    )
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(replicates):
        sampled_faults = [
            rng.choice(faults) for _ in range(len(faults))
        ]
        values = [
            bool(task.get("structurally_answerable"))
            for fault in sampled_faults
            for task in by_fault[fault]
        ]
        samples.append(statistics.fmean(values))
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "metric": "traceable_structure_answerability",
        "cluster_unit": "fault_class",
        "estimate": round(estimate, 6),
        "ci_lower": round(percentile(samples, alpha), 6),
        "ci_upper": round(
            percentile(samples, 1.0 - alpha),
            6,
        ),
        "confidence_level": confidence_level,
        "replicates": replicates,
        "seed": seed,
    }


def compute_experiment(
    records: Sequence[Mapping[str, object]],
    *,
    config: Mapping[str, object],
    cq_report: Mapping[str, object],
    source_summary: Mapping[str, object],
    constraint_report: Mapping[str, object],
) -> dict[str, object]:
    split_policy = dict(config["split_policy"])
    parameters = dict(config["parameters"])
    bootstrap = dict(parameters["bootstrap"])
    sensitivity = dict(parameters["sensitivity"])
    build_doc_ids = frozenset(split_policy["eligible_build_doc_ids"])
    score_threshold = float(parameters["silver_score_threshold"])

    stage_rows, selected = compute_stage_rows(
        records,
        build_doc_ids=build_doc_ids,
        score_threshold=score_threshold,
    )
    incremental = _incremental_gate_rows(
        records,
        selected=selected,
        build_doc_ids=build_doc_ids,
        score_threshold=score_threshold,
    )
    specific = _specific_ablation_rows(
        records,
        selected=selected,
        source_summary=source_summary,
        cq_report=cq_report,
    )
    score_sensitivity = compute_score_sensitivity(
        records,
        build_doc_ids=build_doc_ids,
        thresholds=sensitivity["silver_score_thresholds"],
    )
    cq_sensitivity = compute_cq_sensitivity(
        list(cq_report["task_results"]),
        minimum_answers=sensitivity["cq_minimum_answers"],
        minimum_source_families=(
            sensitivity["cq_minimum_source_families"]
        ),
    )
    stage_bootstrap = cluster_bootstrap_stage_retention(
        records,
        build_doc_ids=build_doc_ids,
        score_threshold=score_threshold,
        replicates=int(bootstrap["replicates"]),
        seed=int(bootstrap["seed"]),
        confidence_level=float(bootstrap["confidence_level"]),
    )
    cq_bootstrap = bootstrap_cq_answerability(
        list(cq_report["task_results"]),
        replicates=int(bootstrap["replicates"]),
        seed=int(bootstrap["seed"]) + 1,
        confidence_level=float(bootstrap["confidence_level"]),
    )
    constraint_summary = dict(constraint_report["summary"])
    source_claim_summary = dict(source_summary["claim_summary"])
    replication = dict(
        source_summary["replication_invariance_experiment"]
    )
    multi_doc = dict(
        source_summary["multi_document_same_family_audit"]
    )
    source_budget_sensitivity = list(
        source_summary["budget_sensitivity"]
    )
    cq_overall = dict(cq_report["aggregate"]["overall"])

    decision_counts = Counter(
        str(record.get("decision") or "") for record in records
    )
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "execution_semantics": config["execution_semantics"],
        "candidate_universe": {
            "record_count": len(records),
            "document_count": len(
                {
                    str(record.get("doc_id") or "")
                    for record in records
                }
            ),
            "decision_counts": dict(sorted(decision_counts.items())),
            "human_expert_reviewed": False,
            "label_policy": "Silver only; never Gold",
        },
        "b0_ours_comparison": stage_rows,
        "incremental_gate_ablation": incremental,
        "specific_module_ablation": specific,
        "sensitivity": {
            "silver_score_threshold": score_sensitivity,
            "source_family_budget": source_budget_sensitivity,
            "cq": cq_sensitivity,
        },
        "bootstrap": {
            "stage_retention": stage_bootstrap,
            "cq_answerability": cq_bootstrap,
        },
        "source_family_result": {
            "eligible_assertion_count": int(
                source_claim_summary["eligible_assertion_count"]
            ),
            "claim_count": int(source_claim_summary["claim_count"]),
            "claims_with_at_least_two_families": int(
                source_claim_summary[
                    "claims_with_at_least_two_families"
                ]
            ),
            "observed_multi_document_claims": int(
                multi_doc["multiple_document_claim_count"]
            ),
            "observed_multi_document_single_family_claims": int(
                multi_doc[
                    "multiple_document_single_family_claim_count"
                ]
            ),
            "replication_invariance_passed": bool(
                replication["invariance_passed"]
            ),
            "replication_doc_count_amplification": round(
                int(replication["sum_claim_doc_counts_after"])
                / int(replication["sum_claim_doc_counts_before"]),
                6,
            ),
            "replication_maximum_index_delta": float(
                replication["maximum_absolute_index_delta"]
            ),
        },
        "cq_result": {
            "task_count": int(cq_overall["cq_count"]),
            "answerable_task_count": int(
                cq_overall["answerable_cq_count"]
            ),
            "traceable_structure_answerability": float(
                cq_overall["traceable_structure_answerability"]
            ),
            "metric_is_accuracy": False,
        },
        "constraint_result": {
            "check_count": int(constraint_summary["checks"]),
            "release_blocking_check_count": int(
                constraint_summary["release_blocking_checks"]
            ),
            "release_blocked": bool(
                constraint_summary["release_blocked"]
            ),
            "is_shacl_or_rdf_validation": False,
        },
        "conclusion_boundaries": {
            "fixed_candidate_offline_ablation": True,
            "prompt_level_extraction_comparison": False,
            "factual_accuracy_measured": False,
            "natural_cross_family_discriminative_validity_observed": (
                int(
                    source_claim_summary[
                        "claims_with_at_least_two_families"
                    ]
                )
                > 0
            ),
            "research_point_1_complete": False,
        },
    }
