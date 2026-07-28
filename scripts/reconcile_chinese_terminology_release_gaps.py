"""Reconcile only terminology endpoints that block frozen release gates.

This stage does not relax the first-pass terminology threshold and does not
promote all unresolved concepts. It identifies the minimum Silver records
needed by failed Chinese coverage roles, asks two new conservative prompt
roles to independently verify their blocked endpoints, and keeps every
remaining concept quarantined.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
for import_root in (SRC_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from research_point_1_graph_evidence.stage02_triple_extraction.bailian_client import (  # noqa: E402
    call_chat_completion,
)
from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    CoverageThresholds,
    build_coverage_report,
    contains_han,
    is_build_coverage_eligible,
    load_chinese_terminology,
    load_fault_ontology,
    normalize_lookup_text,
)
from run_silver_terminology_governance import (  # noqa: E402
    add_form_to_term,
    normalized_label,
    read_jsonl,
    recanonicalize_records,
    stable_term_id,
    token_check,
    write_json,
    write_jsonl,
)


SYSTEM_C = """你是船舶机舱泵系术语的逐词语义核验员。输入项已经在首轮保守审核中未达一致，只能根据source_forms、entity_type和原文上下文重新判断，首轮投票仅用于指出争议，不能视为批准。
中文规范名必须逐项保留原词的部件范围、动作、否定、可能性、程度、并列或选择结构。实体类型可以是故障、症状、原因，也可以是检查或维护动作；不能仅因它是动作短语而拒绝。候选译名有语义漂移时可以给出更忠实的中文名。
本轮只核验frozen_reconciliation_candidate_zh：严格等价则原样批准；不等价则拒绝或不确定，可在canonical_label_zh给出建议，但建议本轮不会自动发布。输出严格JSON：
{"judgments":[{"id":"...","verdict":"approved|rejected|uncertain","canonical_label_zh":"...","confidence":0到1,"reason_code":"..."}]}。"""


SYSTEM_D = """你是独立的中英泵系术语反向翻译审计员。对每项先把frozen_reconciliation_candidate_zh在内部回译，再与source_forms及原文证据比较。特别检查may/might等可能性、incorrect等限定、reduce等动作方向、or等并列结构、设备或部件范围是否完整。
首轮结果不具约束力。允许纠正候选名，但不得加入外部机理、把不确定条件改成确定事实、把原文较窄概念扩成泛化概念。检查/维护动作是合法的规范端点，不得以“不是名词术语”为由拒绝。
只有冻结候选名严格等价且置信度至少0.9时才原样批准；否则拒绝或不确定，修订建议不会在本轮自动发布。输出严格JSON：
{"judgments":[{"id":"...","verdict":"approved|rejected|uncertain","canonical_label_zh":"...","confidence":0到1,"reason_code":"..."}]}。"""


ROLE_SPECS = {
    "symptom": {
        "check": "symptom_at_least_5",
        "count": "symptom_evidence",
        "threshold": "symptom",
        "types": {"Symptom"},
    },
    "cause_or_mechanism": {
        "check": "cause_or_mechanism_at_least_3",
        "count": "cause_or_mechanism_evidence",
        "threshold": "cause_or_mechanism",
        "types": {"Cause", "FailureMechanism"},
    },
    "inspection_or_maintenance": {
        "check": "inspection_or_maintenance_at_least_2",
        "count": "inspection_or_maintenance_evidence",
        "threshold": "inspection_or_maintenance",
        "types": {
            "InspectionMethod",
            "InspectionAction",
            "MaintenanceAction",
        },
    },
}


def endpoint_key(entity_type: object, surface: object) -> tuple[str, str]:
    return str(entity_type or ""), normalize_lookup_text(surface)


def unresolved_index(
    unresolved: Iterable[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    index: dict[tuple[str, str], Mapping[str, object]] = {}
    for item in unresolved:
        entity_type = str(item.get("entity_type") or "")
        for surface in item.get("source_forms", []) or []:
            index[endpoint_key(entity_type, surface)] = item
    return index


def blocked_endpoint_ids(
    record: Mapping[str, object],
    unresolved_by_endpoint: Mapping[
        tuple[str, str], Mapping[str, object]
    ],
) -> tuple[str, ...] | None:
    chinese = record.get("chinese_canonicalization")
    if not isinstance(chinese, Mapping):
        return None
    blockers: set[str] = set()
    for side in ("head", "tail"):
        endpoint = chinese.get(side)
        if isinstance(endpoint, Mapping) and endpoint.get("graph_ready") is True:
            continue
        key = endpoint_key(
            record.get(f"{side}_type"), record.get(f"{side}_surface")
        )
        unresolved = unresolved_by_endpoint.get(key)
        if unresolved is None:
            return None
        blockers.add(str(unresolved["id"]))
    return tuple(sorted(blockers))


def record_identity(record: Mapping[str, object]) -> str:
    return str(
        record.get("assertion_id")
        or record.get("evidence_id")
        or record.get("triple_id")
        or (
            f"{record.get('doc_id')}:{record.get('pdf_page_number')}:"
            f"{record.get('relation')}:{record.get('head_surface')}:"
            f"{record.get('tail_surface')}"
        )
    )


def select_gap_items(
    governed_records: list[dict[str, object]],
    chinese_coverage: Mapping[str, object],
    unresolved: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Select the smallest release-blocking endpoint set by failed role."""

    by_endpoint = unresolved_index(unresolved)
    unresolved_by_id = {str(item["id"]): item for item in unresolved}
    threshold_values = chinese_coverage.get("thresholds", {})
    fault_coverage = chinese_coverage.get("fault_coverage", {})
    selected_ids: set[str] = set()
    target_report: dict[str, object] = {}

    for fault_id, fault_result in fault_coverage.items():
        checks = fault_result.get("gate_checks", {})
        failed_roles = [
            (role, spec)
            for role, spec in ROLE_SPECS.items()
            if checks.get(spec["check"]) is False
        ]
        if not failed_roles:
            continue
        role_report: dict[str, object] = {}
        for role, spec in failed_roles:
            current = int(fault_result.get(spec["count"], 0))
            required = int(threshold_values.get(spec["threshold"], 0))
            gap = max(0, required - current)
            candidates: list[tuple[int, str, dict[str, object], tuple[str, ...]]] = []
            for record in governed_records:
                if (
                    fault_id not in (record.get("fault_class_ids") or [])
                    or record.get("eligible_for_chinese_graph") is True
                    or not is_build_coverage_eligible(
                        record, require_chinese_graph_ready=False
                    )
                    or not any(
                        str(record.get(f"{side}_type") or "") in spec["types"]
                        for side in ("head", "tail")
                    )
                ):
                    continue
                blockers = blocked_endpoint_ids(record, by_endpoint)
                if not blockers:
                    continue
                identity = record_identity(record)
                candidates.append((len(blockers), identity, record, blockers))
            candidates.sort(key=lambda item: (item[0], item[1]))

            selected_records: list[dict[str, object]] = []
            seen_units: set[str] = set()
            for _, identity, record, blockers in candidates:
                typed_sides = [
                    side
                    for side in ("head", "tail")
                    if str(record.get(f"{side}_type") or "") in spec["types"]
                ]
                new_units = {
                    f"{identity}:{side}:{record.get(f'{side}_type')}:"
                    f"{record.get(f'{side}_entity_id')}"
                    for side in typed_sides
                } - seen_units
                if not new_units:
                    continue
                selected_records.append(
                    {
                        "record_id": identity,
                        "doc_id": record.get("doc_id"),
                        "pdf_page_number": record.get("pdf_page_number"),
                        "relation": record.get("relation"),
                        "blocked_term_ids": list(blockers),
                        "evidence_text": record.get("evidence_text"),
                    }
                )
                seen_units.update(new_units)
                selected_ids.update(blockers)
                if len(seen_units) >= gap:
                    break
            if len(seen_units) < gap:
                raise RuntimeError(
                    f"No sufficient quarantined terminology candidates for "
                    f"{fault_id}:{role}; need {gap}, found {len(seen_units)}."
                )
            role_report[role] = {
                "current": current,
                "required": required,
                "gap": gap,
                "selected_records": selected_records,
            }
        target_report[str(fault_id)] = role_report

    queue: list[dict[str, object]] = []
    for item_id in sorted(selected_ids):
        source = unresolved_by_id[item_id]
        queue.append(
            {
                "id": item_id,
                "entity_type": source["entity_type"],
                "source_forms": source["source_forms"],
                "proposed_canonical_zh": source.get(
                    "proposed_canonical_zh", ""
                ),
                "alternative_proposals": source.get(
                    "alternative_proposals", []
                ),
                "protected_tokens": source.get("protected_tokens", []),
                "contexts": source.get("contexts", []),
                "first_pass_votes": source.get("votes", []),
                "first_pass_local_checks": source.get("local_checks", {}),
            }
        )
    return queue, target_report


def attach_frozen_candidates(
    queue: list[dict[str, object]],
    candidate_artifact: Mapping[str, object],
) -> None:
    """Attach versioned machine candidates; never treat them as approvals."""

    candidate_index = {
        endpoint_key(item.get("entity_type"), item.get("source_surface")): item
        for item in candidate_artifact.get("candidates", []) or []
    }
    for item in queue:
        matches = {
            str(candidate_index[endpoint_key(item["entity_type"], surface)][
                "candidate_label_zh"
            ])
            for surface in item["source_forms"]
            if endpoint_key(item["entity_type"], surface) in candidate_index
        }
        if len(matches) != 1:
            raise RuntimeError(
                f"Release-gap item {item['id']} must have exactly one frozen "
                "machine candidate before independent verification."
            )
        item["frozen_reconciliation_candidate_zh"] = matches.pop()
        item["candidate_artifact_version"] = str(
            candidate_artifact.get("version") or ""
        )


def verify_reconciliation_queue(
    queue: list[dict[str, object]],
    *,
    config: Mapping[str, object],
    output_dir: Path,
    dry_run: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    cache_dir = output_dir / "verification_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not queue:
        return [], []
    if not dry_run and not os.environ.get("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY is required and is never stored.")

    prompt = json.dumps(
        {"release_gap_terminology_candidates": queue}, ensure_ascii=False
    )
    votes: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    started = time.perf_counter()
    print(
        f"[Terminology Reconcile] 缺口端点={len(queue)}，独立复核调用=2，"
        f"dry_run={dry_run}",
        flush=True,
    )
    for judge, system in (("C", SYSTEM_C), ("D", SYSTEM_D)):
        digest = hashlib.sha256(
            (system + "\n" + prompt).encode("utf-8")
        ).hexdigest()
        cache_path = cache_dir / f"{digest}.json"
        if dry_run:
            continue
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            source = "CACHE"
        else:
            response = call_chat_completion(
                api_key=str(os.environ["DASHSCOPE_API_KEY"]),
                base_url=str(config["base_url"]),
                model=str(config["model"]),
                system_prompt=system,
                user_prompt=prompt,
                temperature=0,
                enable_thinking=False,
                response_format={"type": "json_object"},
                timeout_seconds=int(config["timeout_seconds"]),
                max_retries=int(config["max_retries"]),
                retry_callback=lambda attempt, maximum, reason, wait: print(
                    f"[Terminology Reconcile][{judge}] 失败 "
                    f"{attempt}/{maximum}，{wait:.0f}s后重试：{reason}",
                    flush=True,
                ),
            )
            payload = {
                "model": response.model,
                "request_id": response.request_id,
                "latency_ms": response.latency_ms,
                "prompt_sha256": digest,
                "response_json": response.content,
            }
            write_json(cache_path, payload)
            source = "API"
        judgments = payload.get("response_json", {}).get("judgments", [])
        if not isinstance(judgments, list):
            raise ValueError("Reconciliation judgments must be an array")
        for vote in judgments:
            votes[str(vote.get("id", ""))][judge] = dict(vote)
        print(
            f"[Terminology Reconcile][{judge}] {source}，"
            f"累计={time.perf_counter()-started:.1f}s",
            flush=True,
        )

    if dry_run:
        return [], []

    approved: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    for item in queue:
        pair = votes.get(str(item["id"]), {})
        c, d = pair.get("C"), pair.get("D")
        labels = [
            normalized_label((vote or {}).get("canonical_label_zh"))
            for vote in (c, d)
        ]
        confidences = [
            float((vote or {}).get("confidence", 0) or 0)
            for vote in (c, d)
        ]
        verdicts = [
            str((vote or {}).get("verdict", "")) for vote in (c, d)
        ]
        checks = {
            "two_new_votes_present": c is not None and d is not None,
            "unanimous_approved": verdicts == ["approved", "approved"],
            "minimum_confidence_0_9": (
                len(confidences) == 2 and min(confidences) >= 0.9
            ),
            "same_nonempty_chinese_label": (
                len(labels) == 2
                and bool(labels[0])
                and labels[0] == labels[1]
                and contains_han(labels[0])
            ),
            "matches_frozen_reconciliation_candidate": (
                len(labels) == 2
                and labels[0]
                == normalized_label(
                    item["frozen_reconciliation_candidate_zh"]
                )
                and labels[1]
                == normalized_label(
                    item["frozen_reconciliation_candidate_zh"]
                )
            ),
            "protected_tokens_preserved": (
                len(labels) == 2
                and token_check(item["protected_tokens"], labels[0])
            ),
        }
        result = {
            **item,
            "reconciliation_votes": [
                vote for vote in (c, d) if vote is not None
            ],
            "reconciliation_checks": checks,
        }
        if all(checks.values()):
            result["canonical_label_zh"] = labels[0]
            result["approval_status"] = "secondary_ai_verified"
            approved.append(result)
        else:
            unresolved.append(result)
    return approved, unresolved


def append_reconciled_terms(
    terminology: dict[str, object],
    approved: list[dict[str, object]],
) -> None:
    terms = list(terminology.get("terms", []) or [])
    concept_index = {
        (
            str(term.get("entity_type") or ""),
            normalize_lookup_text(term.get("canonical_label_zh")),
        ): term
        for term in terms
    }
    for item in approved:
        entity_type = str(item["entity_type"])
        label = str(item["canonical_label_zh"])
        concept_key = (entity_type, normalize_lookup_text(label))
        term = concept_index.get(concept_key)
        if term is None:
            term = {
                "terminology_id": stable_term_id(entity_type, label),
                "entity_type": entity_type,
                "canonical_label_zh": label,
                "source_forms": [],
                "approval_status": "secondary_ai_verified",
                "verification": {
                    "version": "release_gap_dual_pass_qwen_v2",
                    "model": "qwen3.7-max",
                    "independent_prompt_roles": 2,
                    "first_pass_was_not_accepted": True,
                    "human_expert_reviewed": False,
                    "label_policy": "Silver only; never Gold",
                },
            }
            terms.append(term)
            concept_index[concept_key] = term
        for surface in item["source_forms"]:
            add_form_to_term(
                term,
                str(surface),
                language="zh" if contains_han(surface) else "en",
            )
        add_form_to_term(term, label, language="zh")
    terminology["terms"] = terms


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--records",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_evidence_repaired/"
            "candidate_triples.evidence_repaired.jsonl"
        ),
    )
    parser.add_argument(
        "--governed-input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_governed/"
            "candidate_triples.zh_governed.jsonl"
        ),
    )
    parser.add_argument(
        "--unresolved-input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_governed/"
            "terminology_unresolved.json"
        ),
    )
    parser.add_argument(
        "--coverage-input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_governed/"
            "coverage_chinese_release.json"
        ),
    )
    parser.add_argument(
        "--base-terminology",
        default="configs/entity_terminology_zh_marine_pump_v3_silver.json",
    )
    parser.add_argument(
        "--config",
        default="configs/triple_extraction_qwen3_7_max_full_corpus_v1.json",
    )
    parser.add_argument(
        "--candidate-artifact",
        default="configs/terminology_release_gap_candidates_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_reconciled"
        ),
    )
    parser.add_argument(
        "--terminology-output",
        default="configs/entity_terminology_zh_marine_pump_v4_silver.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = read_jsonl(PROJECT_ROOT / args.records)
    governed_records = read_jsonl(PROJECT_ROOT / args.governed_input)
    unresolved = json.loads(
        (PROJECT_ROOT / args.unresolved_input).read_text(encoding="utf-8")
    )
    chinese_coverage = json.loads(
        (PROJECT_ROOT / args.coverage_input).read_text(encoding="utf-8")
    )
    queue, targets = select_gap_items(
        governed_records, chinese_coverage, unresolved
    )
    candidate_artifact = json.loads(
        (PROJECT_ROOT / args.candidate_artifact).read_text(encoding="utf-8")
    )
    attach_frozen_candidates(queue, candidate_artifact)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "release_gap_targets.json", targets)
    write_json(output_dir / "reconciliation_queue.json", queue)

    config = json.loads(
        (PROJECT_ROOT / args.config).read_text(encoding="utf-8")
    )
    approved, still_unresolved = verify_reconciliation_queue(
        queue,
        config=config,
        output_dir=output_dir,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        summary = {
            "version": "marine_pump_zh_release_gap_reconciliation_v1",
            "dry_run": True,
            "target_concepts": len(queue),
            "estimated_api_calls": 2 if queue else 0,
            "human_expert_reviewed": False,
            "label_policy": "Silver only; never Gold",
        }
        write_json(output_dir / "reconciliation_summary.json", summary)
        print(
            f"[Terminology Reconcile] dry-run完成：缺口端点={len(queue)}，"
            f"预计调用={summary['estimated_api_calls']}",
            flush=True,
        )
        return

    terminology = copy.deepcopy(
        load_chinese_terminology(PROJECT_ROOT / args.base_terminology)
    )
    terminology["version"] = "marine_pump_zh_terminology_v4_0_silver"
    terminology["status"] = (
        "secondary_ai_verified_fault_core_gap_reconciled"
    )
    terminology["human_expert_reviewed"] = False
    terminology["label_policy"] = "Silver only; never Gold"
    append_reconciled_terms(terminology, approved)
    terminology_path = PROJECT_ROOT / args.terminology_output
    write_json(terminology_path, terminology)

    reconciled_records = recanonicalize_records(records, terminology)
    records_path = output_dir / "candidate_triples.zh_reconciled.jsonl"
    write_jsonl(records_path, reconciled_records)
    write_json(output_dir / "reconciliation_approved.json", approved)
    write_json(
        output_dir / "reconciliation_still_unresolved.json",
        still_unresolved,
    )

    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    fault_ids = [
        str(item["fault_id"]) for item in ontology["fault_classes"]
    ]
    thresholds = CoverageThresholds.from_ontology(ontology)
    evidence_coverage = build_coverage_report(
        reconciled_records,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=False,
    )
    release_coverage = build_coverage_report(
        reconciled_records,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=True,
    )
    write_json(output_dir / "coverage_evidence_only.json", evidence_coverage)
    write_json(output_dir / "coverage_chinese_release.json", release_coverage)
    decisions = Counter(
        str(record.get("decision") or "") for record in reconciled_records
    )
    summary = {
        "version": "marine_pump_zh_release_gap_reconciliation_v1",
        "dry_run": False,
        "input_records": len(records),
        "target_concepts": len(queue),
        "approved_concepts": len(approved),
        "still_unresolved_concepts": len(still_unresolved),
        "records_eligible_for_chinese_graph": sum(
            record.get("eligible_for_chinese_graph") is True
            for record in reconciled_records
        ),
        "decisions": dict(sorted(decisions.items())),
        "evidence_only_classes_passing": evidence_coverage[
            "fault_classes_passing_gate"
        ],
        "chinese_release_classes_passing": release_coverage[
            "fault_classes_passing_gate"
        ],
        "terminology_artifact": terminology_path.relative_to(
            PROJECT_ROOT
        ).as_posix(),
        "candidate_artifact": args.candidate_artifact,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    write_json(output_dir / "reconciliation_summary.json", summary)
    print(
        f"[Terminology Reconcile] 批准={len(approved)}/{len(queue)}，"
        f"仍隔离={len(still_unresolved)}，"
        f"中文图谱记录={summary['records_eligible_for_chinese_graph']}，"
        f"中文覆盖={summary['chinese_release_classes_passing']}/"
        f"{len(fault_ids)}",
        flush=True,
    )
    if summary["chinese_release_classes_passing"] != len(fault_ids):
        raise RuntimeError(
            "Chinese release coverage remains below 10/10 after targeted "
            "reconciliation; unresolved concepts remain quarantined."
        )


if __name__ == "__main__":
    main()
