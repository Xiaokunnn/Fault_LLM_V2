"""Expand Chinese terminology locally without external document transfer.

The experiment never changes evidence qualification.  It promotes an entity
label only when the extraction records provide one normalized Chinese label,
the label preserves protected tokens, and the frozen confidence/occurrence
rule is satisfied.  The resulting status is explicitly weaker than dictionary
or dual-prompt verification and remains machine-generated Silver metadata.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import sys
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
for import_root in (SRC_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    CoverageThresholds,
    build_coverage_report,
    contains_han,
    load_chinese_terminology,
    load_fault_ontology,
    normalize_lookup_text,
)
from run_silver_terminology_governance import (  # noqa: E402
    add_form_to_term,
    protected_tokens,
    read_jsonl,
    recanonicalize_records,
    stable_term_id,
    terminology_indexes,
    token_check,
    write_json,
    write_jsonl,
)


def endpoint_key(entity_type: object, surface: object) -> tuple[str, str]:
    return str(entity_type or ""), normalize_lookup_text(surface)


def collect_candidates(
    records: Iterable[Mapping[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    candidates: dict[tuple[str, str], dict[str, object]] = {}
    for record in records:
        if record.get("decision") != "silver_candidate":
            continue
        for side in ("head", "tail"):
            entity_type = str(record.get(f"{side}_type") or "")
            surface = str(record.get(f"{side}_surface") or record.get(side) or "")
            key = endpoint_key(entity_type, surface)
            item = candidates.setdefault(
                key,
                {
                    "entity_type": entity_type,
                    "surface_forms": set(),
                    "labels": Counter(),
                    "confidences": [],
                    "evidence_units": set(),
                    "record_count": 0,
                },
            )
            item["surface_forms"].add(surface)
            label = str(record.get(f"{side}_canonical_zh") or "").strip()
            if label:
                item["labels"][normalize_lookup_text(label)] += 1
            confidence = record.get(f"{side}_translation_confidence")
            try:
                item["confidences"].append(float(confidence))
            except (TypeError, ValueError):
                item["confidences"].append(0.0)
            item["evidence_units"].add(
                (str(record.get("doc_id") or ""), int(record.get("pdf_page_number") or 0))
            )
            item["record_count"] += 1
    return candidates


def _label_is_well_formed(label: str) -> bool:
    if not label or not contains_han(label) or len(label) > 200:
        return False
    forbidden = ("```", "\ufffd", "<html", "</", "{\"", "\u0000")
    return not any(token in label.casefold() for token in forbidden)


def evaluate_candidate(
    item: Mapping[str, object],
    *,
    terminology: Mapping[str, object],
    repeated_min_confidence: float,
    singleton_min_confidence: float | None,
) -> tuple[bool, str, str]:
    labels = item.get("labels")
    if not isinstance(labels, Counter) or len(labels) != 1:
        return False, "label_missing_or_conflicting", ""
    label = str(next(iter(labels)))
    if not _label_is_well_formed(label):
        return False, "label_not_well_formed_chinese", label
    tokens = protected_tokens(item.get("surface_forms", []), terminology)
    if not token_check(tokens, label):
        return False, "protected_token_not_preserved", label
    confidences = [float(value) for value in item.get("confidences", [])]
    if not confidences:
        return False, "translation_confidence_missing", label
    evidence_units = len(item.get("evidence_units", []))
    minimum = min(confidences)
    if evidence_units >= 2:
        if minimum < repeated_min_confidence:
            return False, "repeated_candidate_below_confidence", label
        return True, "repeated_exact_label_consensus", label
    if singleton_min_confidence is None:
        return False, "singleton_not_eligible", label
    if minimum < singleton_min_confidence:
        return False, "singleton_below_confidence", label
    return True, "singleton_high_confidence", label


def append_local_terms(
    terminology: dict[str, object],
    candidates: Mapping[tuple[str, str], Mapping[str, object]],
    *,
    repeated_min_confidence: float,
    singleton_min_confidence: float | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    exact, morphology = terminology_indexes(terminology)
    approved_by_concept: dict[tuple[str, str], dict[str, object]] = {}
    unresolved: list[dict[str, object]] = []
    for key, item in sorted(candidates.items()):
        entity_type, normalized_surface = key
        if key in exact or (entity_type, normalized_surface) in morphology:
            continue
        approved, reason, label = evaluate_candidate(
            item,
            terminology=terminology,
            repeated_min_confidence=repeated_min_confidence,
            singleton_min_confidence=singleton_min_confidence,
        )
        result = {
            "entity_type": entity_type,
            "source_forms": sorted(item.get("surface_forms", [])),
            "canonical_label_zh": label,
            "record_count": int(item.get("record_count", 0)),
            "distinct_evidence_units": len(item.get("evidence_units", [])),
            "minimum_translation_confidence": min(item.get("confidences", [0.0])),
            "decision_reason": reason,
        }
        if not approved:
            unresolved.append(result)
            continue
        concept_key = (entity_type, normalize_lookup_text(label))
        concept = approved_by_concept.setdefault(
            concept_key,
            {
                **result,
                "source_forms": set(),
                "decision_reasons": Counter(),
            },
        )
        concept["source_forms"].update(item.get("surface_forms", []))
        concept["decision_reasons"][reason] += 1

    terms = list(terminology.get("terms", []) or [])
    existing_concepts = {
        (
            str(term.get("entity_type") or ""),
            normalize_lookup_text(term.get("canonical_label_zh")),
        ): term
        for term in terms
    }
    approved_items: list[dict[str, object]] = []
    for concept_key, item in sorted(approved_by_concept.items()):
        entity_type, normalized_label = concept_key
        label = str(item["canonical_label_zh"])
        term = existing_concepts.get(concept_key)
        if term is None:
            term = {
                "terminology_id": stable_term_id(entity_type, label),
                "entity_type": entity_type,
                "canonical_label_zh": label,
                "source_forms": [],
                "approval_status": "local_consistency_verified",
                "verification": {
                    "version": "local_full_terminology_consistency_v1",
                    "method": "exact_label_consistency_and_local_constraints",
                    "independent_model_verification": False,
                    "human_expert_reviewed": False,
                    "label_policy": "Silver only; never Gold",
                },
            }
            terms.append(term)
            existing_concepts[concept_key] = term
        for surface in sorted(item["source_forms"]):
            add_form_to_term(
                term,
                str(surface),
                language="zh" if contains_han(surface) else "en",
            )
        add_form_to_term(term, label, language="zh")
        approved_items.append(
            {
                **{key: value for key, value in item.items() if key != "source_forms"},
                "source_forms": sorted(item["source_forms"]),
                "decision_reasons": dict(item["decision_reasons"]),
                "approval_status": "local_consistency_verified",
            }
        )
    terminology["terms"] = terms
    return approved_items, unresolved


def graph_counts(records: Iterable[Mapping[str, object]]) -> dict[str, int]:
    selected = [
        record
        for record in records
        if record.get("eligible_for_chinese_graph") is True
        and record.get("decision") == "silver_candidate"
        and record.get("inferred_edge") is not True
    ]
    return {
        "records": len(selected),
        "claims": len({str(record.get("claim_id")) for record in selected}),
        "entities": len(
            {
                str(record.get(f"{side}_entity_id"))
                for record in selected
                for side in ("head", "tail")
            }
        ),
    }


def restore_nonrelease_identifiers(
    records: Iterable[dict[str, object]],
) -> None:
    """Keep the frozen audit identity for records outside the release set.

    Recomputing semantic IDs after terminology projection can collapse
    rejected table rows whose original model labels were reversed. Those rows
    are retained only for audit, so their frozen pre-projection identifiers
    remain the correct identity and prevent unrelated audit records from being
    merged.
    """

    identifier_fields = (
        "head_entity_id",
        "tail_entity_id",
        "claim_id",
        "evidence_id",
        "assertion_id",
        "triple_id",
    )
    for record in records:
        if record.get("decision") == "silver_candidate":
            continue
        governance = record.get("terminology_governance")
        previous = (
            governance.get("previous_ids", {})
            if isinstance(governance, Mapping)
            else {}
        )
        for field in identifier_fields:
            if previous.get(field):
                record[field] = previous[field]


def run_policy(
    records: list[dict[str, object]],
    base_terminology: Mapping[str, object],
    candidates: Mapping[tuple[str, str], Mapping[str, object]],
    *,
    name: str,
    repeated_min_confidence: float,
    singleton_min_confidence: float | None,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    terminology = copy.deepcopy(base_terminology)
    terminology["version"] = f"marine_pump_zh_terminology_v5_{name}"
    terminology["status"] = "local_full_automatic_governance"
    terminology["human_expert_reviewed"] = False
    terminology["label_policy"] = "Silver only; never Gold"
    policy = dict(terminology.get("policy", {}) or {})
    statuses = list(policy.get("eligible_translation_statuses", []) or [])
    if "local_consistency_verified" not in statuses:
        statuses.append("local_consistency_verified")
    policy["eligible_translation_statuses"] = statuses
    policy["local_consistency_is_not_independent_semantic_verification"] = True
    terminology["policy"] = policy
    approved, unresolved = append_local_terms(
        terminology,
        candidates,
        repeated_min_confidence=repeated_min_confidence,
        singleton_min_confidence=singleton_min_confidence,
    )
    governed = recanonicalize_records(records, terminology)
    restore_nonrelease_identifiers(governed)
    summary = {
        "policy": name,
        "repeated_min_confidence": repeated_min_confidence,
        "singleton_min_confidence": singleton_min_confidence,
        "approved_concepts": len(approved),
        "unresolved_endpoint_groups": len(unresolved),
        "graph": graph_counts(governed),
        "approval_reason_counts": dict(
            Counter(
                reason
                for item in approved
                for reason, count in item["decision_reasons"].items()
                for _ in range(int(count))
            )
        ),
        "unresolved_reason_counts": dict(
            Counter(str(item["decision_reason"]) for item in unresolved)
        ),
    }
    artifacts = {"terminology": terminology, "approved": approved, "unresolved": unresolved}
    return summary, artifacts, governed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_evidence_repaired/"
            "candidate_triples.evidence_repaired.jsonl"
        ),
    )
    parser.add_argument(
        "--base-terminology",
        default="configs/entity_terminology_zh_marine_pump_v4_silver.json",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_local_full"
        ),
    )
    parser.add_argument(
        "--terminology-output",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_local_full/"
            "entity_terminology_zh_marine_pump_v5_local_full.json"
        ),
    )
    args = parser.parse_args()

    records = read_jsonl(PROJECT_ROOT / args.input)
    base = load_chinese_terminology(PROJECT_ROOT / args.base_terminology)
    candidates = collect_candidates(records)
    baseline_records = recanonicalize_records(records, base)
    sensitivity: list[dict[str, object]] = [
        {
            "policy": "existing_strict",
            "approved_concepts": 0,
            "unresolved_endpoint_groups": 0,
            "graph": graph_counts(baseline_records),
        }
    ]
    policies = (
        ("repeated_only_090", 0.90, None),
        ("conservative_090_095", 0.90, 0.95),
        ("standard_090", 0.90, 0.90),
    )
    policy_artifacts: dict[str, dict[str, object]] = {}
    policy_records: dict[str, list[dict[str, object]]] = {}
    for name, repeated_threshold, singleton_threshold in policies:
        summary, artifacts, governed = run_policy(
            records,
            base,
            candidates,
            name=name,
            repeated_min_confidence=repeated_threshold,
            singleton_min_confidence=singleton_threshold,
        )
        sensitivity.append(summary)
        policy_artifacts[name] = artifacts
        policy_records[name] = governed
    selected_artifacts = policy_artifacts["standard_090"]
    selected_records = policy_records["standard_090"]
    conservative_artifacts = policy_artifacts["conservative_090_095"]
    conservative_records = policy_records["conservative_090_095"]

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "sensitivity.json", sensitivity)
    write_json(output_dir / "terminology_approved.json", selected_artifacts["approved"])
    write_json(output_dir / "terminology_unresolved.json", selected_artifacts["unresolved"])
    write_jsonl(output_dir / "candidate_triples.zh_local_full.jsonl", selected_records)
    write_json(
        output_dir / "terminology_conservative.json",
        conservative_artifacts["terminology"],
    )
    write_jsonl(
        output_dir / "candidate_triples.zh_local_conservative.jsonl",
        conservative_records,
    )
    terminology_path = PROJECT_ROOT / args.terminology_output
    write_json(terminology_path, selected_artifacts["terminology"])

    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    fault_ids = [str(item["fault_id"]) for item in ontology["fault_classes"]]
    thresholds = CoverageThresholds.from_ontology(ontology)
    coverage = build_coverage_report(
        selected_records,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=True,
    )
    write_json(output_dir / "coverage_chinese_release.json", coverage)
    selected_summary = next(
        item for item in sensitivity if item["policy"] == "standard_090"
    )
    conservative_summary = next(
        item
        for item in sensitivity
        if item["policy"] == "conservative_090_095"
    )
    final_summary = {
        "version": "local_full_terminology_governance_v1",
        "input_records": len(records),
        "evidence_qualified_records": sum(
            record.get("decision") == "silver_candidate" for record in records
        ),
        "endpoint_groups": len(candidates),
        "selected_policy": "standard_090",
        "selected_policy_result": selected_summary,
        "conservative_policy_result": conservative_summary,
        "fault_classes_passing_gate": coverage["fault_classes_passing_gate"],
        "terminology_artifact": terminology_path.relative_to(PROJECT_ROOT).as_posix(),
        "external_api_calls": 0,
        "independent_model_verification": False,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    write_json(output_dir / "experiment_summary.json", final_summary)
    print(json.dumps(final_summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
