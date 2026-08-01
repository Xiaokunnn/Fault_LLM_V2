"""Claim-level source-family-capped corroboration analysis.

The implementation follows equations (11)--(12) in the research-point-1
method specification:

    s_f(c) = max q_i, for assertions i from source family f
    S_fam^B(c) = (1 / B) * sum of the top min(B, |F_c|) family scores

The denominator always remains B, so absent families contribute zero.  This
module deliberately computes a corroboration/ranking index.  It neither
estimates a probability nor proves statistical independence, and it never
changes an assertion's existing Silver decision.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import statistics
from typing import Iterable, Mapping, Sequence


SOURCE_FAMILY_SUPPORT_VERSION = "marine_pump_source_family_support_v1"
DEFAULT_BUDGET = 2
DEFAULT_MINIMUM_SCORE = 0.8
ELIGIBLE_SILVER_DECISIONS = frozenset(
    {"silver_candidate", "accepted_silver"}
)
FROZEN_BUILD_DOC_IDS = frozenset(
    {
        *(f"MP{index:03d}" for index in range(1, 8)),
        *(f"MP{index:03d}" for index in range(15, 23)),
    }
)

EVIDENCE_WEIGHTS = {"E1": 1.0, "E2": 0.95, "E3": 0.75}
ENTAILMENT_WEIGHTS = {
    "entailed": 1.0,
    "undetermined": 0.75,
    "not_entailed": 0.0,
}


@dataclass(frozen=True)
class EligibilityResult:
    """Eligible evidence assertions plus a reproducible exclusion audit."""

    records: tuple[dict[str, object], ...]
    input_record_count: int
    exclusion_counts: dict[str, int]


def file_sha256(path: Path) -> str:
    """Return the uppercase SHA-256 binding for an immutable input artifact."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _bounded(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))


def _nested(
    record: Mapping[str, object],
    container: str,
    field: str,
    default: object = None,
) -> object:
    value = record.get(container)
    if isinstance(value, Mapping):
        return value.get(field, default)
    return default


def _entailment_status(record: Mapping[str, object]) -> str:
    status = str(
        _nested(
            record,
            "relation_entailment_validation",
            "status",
            "",
        )
        or ""
    )
    if status:
        return status
    if record.get("relation_entailment_valid") is True:
        return "entailed"
    if record.get("relation_entailment_valid") is False:
        return "undetermined"
    return ""


def heuristic_assertion_score(record: Mapping[str, object]) -> float:
    """Return q_i from equations (6)--(8), without probability semantics."""

    model_score = _bounded(record.get("model_confidence"))
    evidence_weight = EVIDENCE_WEIGHTS.get(
        str(record.get("evidence_level") or ""),
        0.0,
    )
    entailment_weight = ENTAILMENT_WEIGHTS.get(
        _entailment_status(record),
        0.0,
    )
    return round(model_score * evidence_weight * entailment_weight, 6)


def _eligibility_reasons(
    record: Mapping[str, object],
    *,
    minimum_score: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if str(record.get("decision") or "") not in ELIGIBLE_SILVER_DECISIONS:
        reasons.append("decision_not_silver")
    if str(record.get("document_split") or "") != "build_train":
        reasons.append("document_split_not_build_train")
    if str(record.get("doc_id") or "") not in FROZEN_BUILD_DOC_IDS:
        reasons.append("doc_id_not_frozen_build_set")
    if str(record.get("evidence_level") or "") not in {"E1", "E2"}:
        reasons.append("evidence_level_not_e1_e2")
    if record.get("inferred_edge") is True:
        reasons.append("inferred_edge")
    if not str(record.get("claim_id") or "").strip():
        reasons.append("missing_claim_id")
    if not str(record.get("doc_id") or "").strip():
        reasons.append("missing_doc_id")
    if not str(record.get("source_family_id") or "").strip():
        reasons.append("missing_source_family_id")
    if record.get("relation_type_valid") is not True:
        reasons.append("relation_type_invalid")
    if _entailment_status(record) != "entailed":
        reasons.append("relation_entailment_not_entailed")
    if _nested(record, "evidence_validation", "valid", False) is not True:
        reasons.append("evidence_invalid")
    if (
        _nested(
            record,
            "evidence_validation",
            "silver_eligible",
            False,
        )
        is not True
    ):
        reasons.append("evidence_not_silver_eligible")
    if (
        _nested(
            record,
            "relation_entailment_validation",
            "silver_eligible",
            False,
        )
        is not True
    ):
        reasons.append("entailment_not_silver_eligible")
    if heuristic_assertion_score(record) < minimum_score:
        reasons.append("heuristic_score_below_minimum")
    return tuple(dict.fromkeys(reasons))


def filter_eligible_assertions(
    records: Iterable[Mapping[str, object]],
    *,
    minimum_score: float = DEFAULT_MINIMUM_SCORE,
) -> EligibilityResult:
    """Select only build-set, grounded, non-inferred E1/E2 Silver records."""

    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError("minimum_score must be between 0 and 1")

    eligible: list[dict[str, object]] = []
    exclusions: Counter[str] = Counter()
    input_count = 0
    for source in records:
        input_count += 1
        reasons = _eligibility_reasons(source, minimum_score=minimum_score)
        if reasons:
            exclusions.update(reasons)
            continue
        eligible.append(dict(source))
    return EligibilityResult(
        records=tuple(eligible),
        input_record_count=input_count,
        exclusion_counts=dict(sorted(exclusions.items())),
    )


def _stable_assertion_key(
    record: Mapping[str, object],
) -> tuple[str, str, str, str]:
    return (
        str(record.get("assertion_id") or ""),
        str(record.get("evidence_id") or ""),
        str(record.get("doc_id") or ""),
        str(record.get("pdf_page_number") or ""),
    )


def _best_family_assertion(
    records: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    return min(
        records,
        key=lambda item: (
            -heuristic_assertion_score(item),
            *_stable_assertion_key(item),
        ),
    )


def aggregate_claim_support(
    eligible_records: Iterable[Mapping[str, object]],
    *,
    budget: int = DEFAULT_BUDGET,
) -> list[dict[str, object]]:
    """Aggregate eligible assertions using family max and top-B mean."""

    if budget < 1:
        raise ValueError("budget must be a positive integer")

    by_claim: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in eligible_records:
        claim = str(record.get("claim_id") or "").strip()
        family = str(record.get("source_family_id") or "").strip()
        if not claim or not family:
            raise ValueError(
                "aggregate_claim_support requires prefiltered records with "
                "claim_id and source_family_id"
            )
        by_claim[claim].append(record)

    rows: list[dict[str, object]] = []
    for claim_id in sorted(by_claim):
        claim_records = by_claim[claim_id]
        by_family: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for record in claim_records:
            by_family[str(record["source_family_id"])].append(record)

        family_rows: list[dict[str, object]] = []
        for family_id, family_records in by_family.items():
            best = _best_family_assertion(family_records)
            family_doc_ids = sorted(
                {
                    str(item.get("doc_id") or "")
                    for item in family_records
                }
            )
            family_rows.append(
                {
                    "source_family_id": family_id,
                    "max_q": heuristic_assertion_score(best),
                    "assertion_count": len(family_records),
                    "doc_count": len(family_doc_ids),
                    "doc_ids": family_doc_ids,
                    "top_assertion_id": best.get("assertion_id"),
                    "top_evidence_id": best.get("evidence_id"),
                    "top_doc_id": best.get("doc_id"),
                    "top_pdf_page_number": best.get("pdf_page_number"),
                }
            )
        family_rows.sort(
            key=lambda item: (
                -float(item["max_q"]),
                str(item["source_family_id"]),
            )
        )

        top_scores = [
            float(item["max_q"]) for item in family_rows[:budget]
        ]
        padded_scores = top_scores + [0.0] * (budget - len(top_scores))
        index = round(sum(top_scores) / budget, 6)
        representative = _best_family_assertion(claim_records)
        claim_doc_ids = sorted(
            {
                str(item.get("doc_id") or "")
                for item in claim_records
            }
        )

        def distinct_values(*field_names: str) -> list[str]:
            return sorted(
                {
                    str(item.get(field) or "").strip()
                    for item in claim_records
                    for field in field_names
                    if str(item.get(field) or "").strip()
                }
            )

        chinese_release_count = sum(
            item.get("eligible_for_chinese_graph") is True
            for item in claim_records
        )
        rows.append(
            {
                "analysis_version": SOURCE_FAMILY_SUPPORT_VERSION,
                "claim_id": claim_id,
                "endpoint_semantics": (
                    "canonical_zh_candidates_are_governance_candidates;"
                    "only assertions counted in chinese_release are eligible "
                    "for the Chinese release graph"
                ),
                "head_endpoint": {
                    "source_surfaces": distinct_values(
                        "head_surface",
                        "head",
                    ),
                    "canonical_zh_candidates": distinct_values(
                        "head_canonical_zh"
                    ),
                    "terminology_ids": distinct_values(
                        "head_terminology_id"
                    ),
                    "translation_statuses": distinct_values(
                        "head_translation_status"
                    ),
                },
                "head_type": representative.get("head_type"),
                "relation": representative.get("relation"),
                "relation_label_zh": representative.get("relation_label_zh"),
                "tail_endpoint": {
                    "source_surfaces": distinct_values(
                        "tail_surface",
                        "tail",
                    ),
                    "canonical_zh_candidates": distinct_values(
                        "tail_canonical_zh"
                    ),
                    "terminology_ids": distinct_values(
                        "tail_terminology_id"
                    ),
                    "translation_statuses": distinct_values(
                        "tail_translation_status"
                    ),
                },
                "tail_type": representative.get("tail_type"),
                "chinese_release": {
                    "eligible_assertion_count": chinese_release_count,
                    "total_silver_assertion_count": len(claim_records),
                    "has_eligible_assertion": chinese_release_count > 0,
                    "all_assertions_eligible": (
                        chinese_release_count == len(claim_records)
                    ),
                    "representative_assertion_eligible": (
                        representative.get("eligible_for_chinese_graph")
                        is True
                    ),
                    "representative_graph_release_status": (
                        representative.get("graph_release_status")
                    ),
                },
                "fault_class_ids": sorted(
                    {
                        str(fault_id)
                        for item in claim_records
                        for fault_id in (item.get("fault_class_ids") or [])
                        if str(fault_id)
                    }
                ),
                "assertion_count": len(claim_records),
                "doc_count": len(claim_doc_ids),
                "doc_ids": claim_doc_ids,
                "family_count": len(family_rows),
                "source_family_budget": budget,
                "family_scores": family_rows,
                "top_family_scores": top_scores,
                "padded_top_family_scores": padded_scores,
                "source_family_support_index": index,
                "metric_semantics": (
                    "heuristic_corroboration_index_not_probability"
                ),
                "changes_existing_silver_labels": False,
            }
        )
    return rows


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(
        ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction
    )


def summarize_claim_rows(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    scores = [
        float(item.get("source_family_support_index") or 0.0)
        for item in rows
    ]
    family_counts = [int(item.get("family_count") or 0) for item in rows]
    doc_counts = [int(item.get("doc_count") or 0) for item in rows]
    assertion_counts = [
        int(item.get("assertion_count") or 0) for item in rows
    ]
    return {
        "claim_count": len(rows),
        "eligible_assertion_count": sum(assertion_counts),
        "claims_with_at_least_two_families": sum(
            count >= 2 for count in family_counts
        ),
        "claims_with_multiple_documents": sum(
            count >= 2 for count in doc_counts
        ),
        "mean_family_count": round(statistics.fmean(family_counts), 6)
        if family_counts
        else 0.0,
        "mean_doc_count": round(statistics.fmean(doc_counts), 6)
        if doc_counts
        else 0.0,
        "support_index": {
            "minimum": round(min(scores), 6) if scores else 0.0,
            "p25": round(_quantile(scores, 0.25), 6),
            "median": round(statistics.median(scores), 6)
            if scores
            else 0.0,
            "mean": round(statistics.fmean(scores), 6)
            if scores
            else 0.0,
            "p75": round(_quantile(scores, 0.75), 6),
            "maximum": round(max(scores), 6) if scores else 0.0,
            "count_ge_0_5": sum(score >= 0.5 for score in scores),
            "count_ge_0_8": sum(score >= 0.8 for score in scores),
        },
    }


def multi_document_same_family_audit(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Audit observed multi-document Claims without semantic re-clustering."""

    multiple_document = [
        item for item in rows if int(item.get("doc_count") or 0) >= 2
    ]
    single_family = [
        item
        for item in multiple_document
        if int(item.get("family_count") or 0) == 1
    ]
    multiple_family = [
        item
        for item in multiple_document
        if int(item.get("family_count") or 0) >= 2
    ]
    details = []
    for item in multiple_document:
        family_rows = list(item.get("family_scores") or [])
        details.append(
            {
                "claim_id": item.get("claim_id"),
                "doc_count": item.get("doc_count"),
                "doc_ids": list(item.get("doc_ids") or []),
                "family_count": item.get("family_count"),
                "source_family_ids": [
                    family.get("source_family_id")
                    for family in family_rows
                    if isinstance(family, Mapping)
                ],
                "source_family_support_index": item.get(
                    "source_family_support_index"
                ),
            }
        )
    return {
        "multiple_document_claim_count": len(multiple_document),
        "multiple_document_single_family_claim_count": len(single_family),
        "multiple_document_multiple_family_claim_count": len(multiple_family),
        "all_observed_multiple_document_claims_are_single_family": (
            bool(multiple_document)
            and len(single_family) == len(multiple_document)
        ),
        "claims": details,
        "interpretation": (
            "This is an exact-Claim audit. It does not merge semantically "
            "similar Claims and does not imply class-level source coverage."
        ),
    }


def budget_sensitivity(
    eligible_records: Sequence[Mapping[str, object]],
    *,
    budgets: Iterable[int] = (1, 2, 3, 4),
) -> list[dict[str, object]]:
    """Evaluate equation (12) under predeclared family budgets."""

    normalized_budgets = sorted({int(value) for value in budgets})
    if not normalized_budgets or normalized_budgets[0] < 1:
        raise ValueError("budgets must contain positive integers")
    result: list[dict[str, object]] = []
    for budget in normalized_budgets:
        rows = aggregate_claim_support(eligible_records, budget=budget)
        item = summarize_claim_rows(rows)
        item["budget"] = budget
        result.append(item)
    return result


def _synthetic_same_family_replicas(
    eligible_records: Sequence[Mapping[str, object]],
    *,
    copies: int,
) -> list[dict[str, object]]:
    result = [dict(item) for item in eligible_records]
    for copy_index in range(1, copies + 1):
        suffix = f"::SAME_FAMILY_REPLICA_{copy_index}"
        for source in eligible_records:
            replica = dict(source)
            replica["doc_id"] = f"{source.get('doc_id')}{suffix}"
            for field in (
                "assertion_id",
                "evidence_id",
                "triple_id",
                "legacy_triple_id",
            ):
                if source.get(field):
                    replica[field] = f"{source[field]}{suffix}"
            replica["synthetic_replication_injection"] = True
            result.append(replica)
    return result


def replication_invariance_experiment(
    eligible_records: Sequence[Mapping[str, object]],
    *,
    budget: int = DEFAULT_BUDGET,
    copies: int = 1,
    tolerance: float = 1e-12,
) -> dict[str, object]:
    """Verify that same-family replicas grow doc counts but not the index."""

    if copies < 1:
        raise ValueError("copies must be a positive integer")
    baseline = {
        str(item["claim_id"]): item
        for item in aggregate_claim_support(
            eligible_records,
            budget=budget,
        )
    }
    injected_records = _synthetic_same_family_replicas(
        eligible_records,
        copies=copies,
    )
    injected = {
        str(item["claim_id"]): item
        for item in aggregate_claim_support(
            injected_records,
            budget=budget,
        )
    }

    index_changed = 0
    family_count_changed = 0
    doc_count_increased = 0
    maximum_delta = 0.0
    for claim_id, before in baseline.items():
        after = injected[claim_id]
        delta = abs(
            float(after["source_family_support_index"])
            - float(before["source_family_support_index"])
        )
        maximum_delta = max(maximum_delta, delta)
        if delta > tolerance:
            index_changed += 1
        if int(after["family_count"]) != int(before["family_count"]):
            family_count_changed += 1
        if int(after["doc_count"]) > int(before["doc_count"]):
            doc_count_increased += 1

    claims_tested = len(baseline)
    return {
        "experiment": "same_source_family_replication_invariance",
        "budget": budget,
        "synthetic_copies_per_assertion": copies,
        "claims_tested": claims_tested,
        "eligible_assertions_before": len(eligible_records),
        "eligible_assertions_after": len(injected_records),
        "sum_claim_doc_counts_before": sum(
            int(item["doc_count"]) for item in baseline.values()
        ),
        "sum_claim_doc_counts_after": sum(
            int(item["doc_count"]) for item in injected.values()
        ),
        "claims_with_increased_doc_count": doc_count_increased,
        "claims_with_changed_family_count": family_count_changed,
        "claims_with_changed_support_index": index_changed,
        "maximum_absolute_index_delta": round(maximum_delta, 12),
        "invariance_passed": (
            claims_tested > 0
            and doc_count_increased == claims_tested
            and family_count_changed == 0
            and index_changed == 0
        ),
        "interpretation": (
            "Synthetic documents retain the original source_family_id. "
            "Document counts must rise while family-capped scores remain "
            "unchanged."
        ),
    }


def aggregate_document_naive_support(
    eligible_records: Iterable[Mapping[str, object]],
    *,
    budget: int = DEFAULT_BUDGET,
) -> dict[str, float]:
    """Return a deliberately naive document-level corroboration baseline.

    Each document is treated as independent even when documents share a
    publisher/source family.  This baseline exists only for the replication
    stress test and must not be used to relabel Silver assertions.
    """

    if budget < 1:
        raise ValueError("budget must be a positive integer")
    by_claim_doc: dict[str, dict[str, float]] = defaultdict(dict)
    for record in eligible_records:
        claim_id = str(record.get("claim_id") or "")
        doc_id = str(record.get("doc_id") or "")
        if not claim_id or not doc_id:
            raise ValueError("document baseline requires claim_id and doc_id")
        score = heuristic_assertion_score(record)
        by_claim_doc[claim_id][doc_id] = max(
            score,
            by_claim_doc[claim_id].get(doc_id, 0.0),
        )
    return {
        claim_id: round(
            sum(sorted(doc_scores.values(), reverse=True)[:budget]) / budget,
            6,
        )
        for claim_id, doc_scores in by_claim_doc.items()
    }


def replication_pressure_experiment(
    eligible_records: Sequence[Mapping[str, object]],
    *,
    multipliers: Iterable[int] = (1, 2, 4, 8),
    budget: int = DEFAULT_BUDGET,
    decision_threshold: float = 0.8,
) -> dict[str, object]:
    """Compare naive document support with family-capped support under copies."""

    normalized = sorted({int(value) for value in multipliers})
    if not normalized or normalized[0] < 1:
        raise ValueError("multipliers must contain positive integers")
    if not 0.0 <= decision_threshold <= 1.0:
        raise ValueError("decision_threshold must be between 0 and 1")

    baseline_family = {
        str(row["claim_id"]): float(row["source_family_support_index"])
        for row in aggregate_claim_support(eligible_records, budget=budget)
    }
    baseline_doc = aggregate_document_naive_support(
        eligible_records,
        budget=budget,
    )
    rows: list[dict[str, object]] = []
    for multiplier in normalized:
        injected = (
            [dict(item) for item in eligible_records]
            if multiplier == 1
            else _synthetic_same_family_replicas(
                eligible_records,
                copies=multiplier - 1,
            )
        )
        family = {
            str(row["claim_id"]): float(row["source_family_support_index"])
            for row in aggregate_claim_support(injected, budget=budget)
        }
        document = aggregate_document_naive_support(injected, budget=budget)
        family_deltas = [
            abs(family[claim_id] - baseline_family[claim_id])
            for claim_id in baseline_family
        ]
        document_deltas = [
            abs(document[claim_id] - baseline_doc[claim_id])
            for claim_id in baseline_doc
        ]
        rows.append(
            {
                "replication_multiplier": multiplier,
                "eligible_assertion_count": len(injected),
                "family_support_mean": round(
                    statistics.fmean(family.values()), 6
                ),
                "document_naive_support_mean": round(
                    statistics.fmean(document.values()), 6
                ),
                "family_decisions_ge_threshold": sum(
                    value >= decision_threshold for value in family.values()
                ),
                "document_naive_decisions_ge_threshold": sum(
                    value >= decision_threshold for value in document.values()
                ),
                "family_claims_changed_from_x1": sum(delta > 1e-12 for delta in family_deltas),
                "document_claims_changed_from_x1": sum(delta > 1e-12 for delta in document_deltas),
                "family_max_absolute_delta_from_x1": max(family_deltas, default=0.0),
                "document_max_absolute_delta_from_x1": max(document_deltas, default=0.0),
            }
        )
    return {
        "experiment": "same_source_family_replication_pressure",
        "multipliers": normalized,
        "budget": budget,
        "decision_threshold": decision_threshold,
        "claim_count": len(baseline_family),
        "rows": rows,
        "family_invariance_passed": all(
            int(row["family_claims_changed_from_x1"]) == 0 for row in rows
        ),
        "document_baseline_exhibits_replication_inflation": any(
            int(row["document_claims_changed_from_x1"]) > 0 for row in rows[1:]
        ),
        "changes_existing_silver_labels": False,
        "interpretation": (
            "Synthetic replicas retain source_family_id. The naive document "
            "baseline treats replicas as independent; the family-capped index "
            "must remain invariant."
        ),
    }


def _source_family_distribution(
    eligible_records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    assertions: Counter[str] = Counter()
    documents: dict[str, set[str]] = defaultdict(set)
    claims: dict[str, set[str]] = defaultdict(set)
    for item in eligible_records:
        family = str(item.get("source_family_id") or "")
        assertions[family] += 1
        documents[family].add(str(item.get("doc_id") or ""))
        claims[family].add(str(item.get("claim_id") or ""))
    return [
        {
            "source_family_id": family,
            "eligible_assertion_count": assertions[family],
            "document_count": len(documents[family]),
            "claim_count": len(claims[family]),
        }
        for family in sorted(
            assertions,
            key=lambda value: (-assertions[value], value),
        )
    ]


def analyze_source_family_support(
    records: Iterable[Mapping[str, object]],
    *,
    budget: int = DEFAULT_BUDGET,
    sensitivity_budgets: Iterable[int] = (1, 2, 3, 4),
    minimum_score: float = DEFAULT_MINIMUM_SCORE,
    replication_copies: int = 1,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Run the complete non-mutating source-family support analysis."""

    eligibility = filter_eligible_assertions(
        records,
        minimum_score=minimum_score,
    )
    eligible = eligibility.records
    claim_rows = aggregate_claim_support(eligible, budget=budget)
    summary = {
        "analysis_version": SOURCE_FAMILY_SUPPORT_VERSION,
        "formula": {
            "family_cap": "s_f(c)=max_{a_i in A_f(c)} q_i",
            "claim_index": (
                "S_fam^B(c)=(1/B)*sum_{j=1}^{min(B,|F_c|)} s_(j)(c)"
            ),
            "q": (
                "q_i=model_confidence*w_E(evidence_level)"
                "*w_R(entailment_status)"
            ),
            "missing_family_slots": "zero",
        },
        "budget": budget,
        "minimum_heuristic_score": minimum_score,
        "metric_semantics": (
            "heuristic_corroboration_index_not_probability_or_"
            "independence_proof"
        ),
        "changes_existing_silver_labels": False,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "eligibility_audit": {
            "input_record_count": eligibility.input_record_count,
            "eligible_assertion_count": len(eligible),
            "excluded_record_count": (
                eligibility.input_record_count - len(eligible)
            ),
            "exclusion_reason_counts_nonexclusive": (
                eligibility.exclusion_counts
            ),
            "required": [
                "decision in {silver_candidate, accepted_silver}",
                "document_split == build_train",
                "doc_id in frozen build set MP001-MP007, MP015-MP022",
                "evidence_level in {E1, E2}",
                "inferred_edge != true",
                "stable claim_id, doc_id and source_family_id",
                "relation type valid",
                "relation entailment valid and Silver-eligible",
                "evidence valid and Silver-eligible",
                f"q_i >= {minimum_score}",
            ],
            "frozen_build_doc_ids": sorted(FROZEN_BUILD_DOC_IDS),
            "eligible_doc_ids": sorted(
                {
                    str(item.get("doc_id") or "")
                    for item in eligible
                }
            ),
        },
        "claim_summary": summarize_claim_rows(claim_rows),
        "multi_document_same_family_audit": (
            multi_document_same_family_audit(claim_rows)
        ),
        "source_family_distribution": _source_family_distribution(eligible),
        "budget_sensitivity": budget_sensitivity(
            eligible,
            budgets=sensitivity_budgets,
        ),
        "replication_invariance_experiment": (
            replication_invariance_experiment(
                eligible,
                budget=budget,
                copies=replication_copies,
            )
        ),
    }
    return claim_rows, summary
