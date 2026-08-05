"""Evidence-only prompt contract and automatic Silver generation metrics."""

from __future__ import annotations

import json
import math
import statistics
import time
from typing import Protocol

from .dataset import EvidenceCandidate, SilverQuery
from .retrieval import lexical_similarity


SYSTEM_PROMPT = """你是船舶机舱泵系故障辅助诊断模型。只能使用给出的证据，不得补入外部常识。
当证据足以回答时，将status设为answered；每个answer_point必须引用至少一个给定的准确证据ID。
当没有证据或证据不足时，将status设为insufficient_evidence，answer_points必须为空数组，summary只说明证据不足。
禁止编造、改写或使用占位证据ID。输出严格JSON，不输出Markdown。"""

CONSTRAINED_SYSTEM_PROMPT = """你是船舶机舱泵系的证据选择器。你的任务不是补充常识，而是从给定证据中选出直接回答问题的最小证据集。
每个answer_point只引用一个证据ID；该证据必须同时匹配问题中的故障对象和required_role。
不得删除原证据的否定、条件、可能性、范围和方向；不得将不同证据拼成一个新事实。
证据不足时必须返回insufficient_evidence。输出严格JSON，不输出Markdown。"""

COVERAGE_SYSTEM_PROMPT = """你是船舶机舱泵系的逐证据支持裁决器。必须独立审查每个候选，不得只选最小证据集。
对每个evidence_id必须输出且只输出一个verdict：direct、indirect或irrelevant。
direct要求证据同时匹配问题的故障对象、required_role和关系方向，并可直接支持一个回答点；indirect表示仅背景相关或需要额外推断；irrelevant表示对象或角色不匹配。
若有2至3条互补的direct证据，必须分别引用它们生成2至3个原子回答点；不得因为已有一条可回答证据而停止审查其余候选。
不得删除否定、条件、可能性、范围和方向；不得拼接跨证据新事实。没有direct证据时返回insufficient_evidence。
输出严格JSON，不输出Markdown。"""

COMPACT_MASK_SYSTEM_PROMPT = """你是船舶机舱泵系证据的逐候选二分类器。按输入顺序判断每条候选能否直接回答问题。
只有候选本身同时匹配故障对象、required_role和关系方向时标1；背景相关、需要推断、对象不符或角色不符均标0。问题中的故障名称可能是并列组合类别；候选若明确描述其中一个列举成员、部件或子类型，应视为故障对象匹配。规范化claim是主要语义，verbatim用于核对其有原文依据。每条候选独立判断，不得因已有一个1而停止或压缩其余有效证据。
必须检查全部候选。只输出一个JSON对象：{\"direct\":[0或1,...]}。数组长度必须等于候选数；禁止输出证据ID、解释、回答文本、Markdown或其他字段。"""

GENERATION_STRATEGIES = {
    "freeform_v1",
    "evidence_constrained_v1",
    "evidence_coverage_v2",
    "evidence_mask_v3",
}
FAITHFULNESS_GUARD_VERSION = "rp2_faithfulness_guard_v1"
COVERAGE_GUARD_VERSION = "rp2_evidence_coverage_guard_v2"


def system_prompt_for_strategy(strategy: str) -> str:
    if strategy not in GENERATION_STRATEGIES:
        raise ValueError(f"unknown generation strategy: {strategy}")
    if strategy == "evidence_constrained_v1":
        return CONSTRAINED_SYSTEM_PROMPT
    if strategy == "evidence_coverage_v2":
        return COVERAGE_SYSTEM_PROMPT
    if strategy == "evidence_mask_v3":
        return COMPACT_MASK_SYSTEM_PROMPT
    return SYSTEM_PROMPT


class JsonGenerator(Protocol):
    def generate_json(
        self, system_prompt: str, user_prompt: str, *, max_new_tokens: int = 768
    ) -> dict: ...


class TokenCountingGenerator(JsonGenerator, Protocol):
    def count_chat_tokens(self, system_prompt: str, user_prompt: str) -> int: ...


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def build_generation_prompt(
    query: SilverQuery,
    evidence: list[EvidenceCandidate],
    *,
    max_answer_points: int = 2,
    max_point_chars: int = 80,
    max_summary_chars: int = 100,
    strategy: str = "freeform_v1",
) -> str:
    if strategy not in GENERATION_STRATEGIES:
        raise ValueError(f"unknown generation strategy: {strategy}")
    if strategy == "evidence_mask_v3":
        return json.dumps(
            {
                "question": query.question_zh,
                "required_role": query.role,
                "candidates": [
                    {
                        "candidate": index,
                        "role": item.role,
                        "claim": (
                            f"{item.head_label_zh} --{item.relation}--> "
                            f"{item.tail_label_zh}"
                        ),
                        "verbatim": item.evidence_text,
                    }
                    for index, item in enumerate(evidence, start=1)
                ],
                "output": {
                    "direct": [
                        "按候选顺序输出0或1；长度必须与candidates相同"
                    ]
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    payload = {
        "question": query.question_zh,
        "required_role": query.role,
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "claim": f"{item.head_label_zh} --{item.relation}--> {item.tail_label_zh}",
                "verbatim": item.evidence_text,
                "doc_id": item.doc_id,
                "pdf_page": item.pdf_page_number,
                "source_url": item.source_url,
            }
            for item in evidence
        ],
        "output_schema": {
            "status": "answered|insufficient_evidence",
            "answer_points": [{"text": "中文结论", "evidence_ids": ["证据ID"]}],
            "summary": "简短中文回答",
        },
        "output_budget": {
            "max_answer_points": max_answer_points,
            "max_chinese_chars_per_point": max_point_chars,
            "max_summary_chars": max_summary_chars,
            "instruction": "优先给出直接回答问题且有证据支持的结论，不重复证据原文。",
        },
        "insufficient_evidence_contract": {
            "status": "insufficient_evidence",
            "answer_points": [],
            "summary": "现有证据不足，无法回答。",
        },
    }
    if strategy == "evidence_constrained_v1":
        payload["selection_contract"] = {
            "one_primary_evidence_per_point": True,
            "must_match_required_role": True,
            "must_directly_match_fault_object": True,
            "do_not_merge_evidence_into_new_fact": True,
            "answer_text_is_a_draft_and_will_be_checked_against_the_canonical_claim": True,
        }
    elif strategy == "evidence_coverage_v2":
        for row, item in zip(payload["evidence"], evidence):
            row["evidence_role"] = item.role
        payload["output_schema"] = {
            "evidence_assessments": [
                {
                    "evidence_id": "候选证据ID",
                    "verdict": "direct|indirect|irrelevant",
                    "aspect": "该证据直接支持的简短方面，非direct时为空字符串",
                }
            ],
            "status": "answered|insufficient_evidence",
            "answer_points": [
                {"text": "中文原子结论", "evidence_ids": ["唯一的direct证据ID"]}
            ],
            "summary": "只概括answer_points的简短中文回答",
        }
        payload["coverage_contract"] = {
            "assessment_count_must_equal_candidate_count": len(evidence),
            "assess_every_candidate_once": True,
            "allowed_verdicts": ["direct", "indirect", "irrelevant"],
            "one_primary_evidence_per_point": True,
            "use_all_complementary_direct_evidence_up_to_budget": max_answer_points,
            "do_not_stop_after_first_direct_evidence": True,
            "do_not_use_external_knowledge": True,
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def fit_prompt_budget(
    query: SilverQuery,
    evidence: list[EvidenceCandidate],
    generator: TokenCountingGenerator,
    contract: dict,
    *,
    strategy: str = "freeform_v1",
    system_prompt: str | None = None,
) -> tuple[str, list[EvidenceCandidate], int, int]:
    """Drop lowest-ranked evidence until the exact model prompt fits the shared budget."""

    kept = list(evidence)
    dropped = 0
    max_prompt_tokens = int(contract["max_prompt_tokens"])
    while True:
        prompt = build_generation_prompt(
            query,
            kept,
            max_answer_points=int(contract["max_answer_points"]),
            max_point_chars=int(contract["max_point_chars"]),
            max_summary_chars=int(contract["max_summary_chars"]),
            strategy=strategy,
        )
        active_system_prompt = system_prompt or system_prompt_for_strategy(strategy)
        token_count = generator.count_chat_tokens(active_system_prompt, prompt)
        if token_count <= max_prompt_tokens:
            return prompt, kept, dropped, token_count
        if not kept:
            raise RuntimeError(
                f"Prompt contract alone exceeds max_prompt_tokens={max_prompt_tokens}"
            )
        kept.pop()
        dropped += 1


_RELATION_RENDERERS = {
    "manifests_as": lambda h, t: f"{h}表现为{t}。",
    "indicates": lambda h, t: f"{h}提示{t}。",
    "causes": lambda h, t: f"{h}可能导致{t}。",
    "evolves_to": lambda h, t: f"{h}可能发展为{t}。",
    "increases_risk_of": lambda h, t: f"{h}可能增加{t}的风险。",
    "diagnosed_by": lambda h, t: f"可通过{t}诊断{h}。",
    "inspected_by": lambda h, t: f"可通过{t}检查{h}。",
    "mitigated_by": lambda h, t: f"可采用{t}缓解{h}。",
    "prevented_by": lambda h, t: f"可采用{t}预防{h}。",
    "maintained_by": lambda h, t: f"可采用{t}对{h}进行维护。",
}


def visible_fault_affinity(query: SilverQuery, evidence: EvidenceCandidate) -> float:
    """Visible semantic affinity only; frozen Silver fault labels are never read."""

    return max(
        lexical_similarity(query.fault_name_zh, evidence.head_label_zh),
        lexical_similarity(query.fault_name_zh, evidence.tail_label_zh),
    )


def _fit_complete_text(text: str, max_chars: int) -> str:
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1].rstrip("，,;；。 ") + "。"


def render_canonical_claim(evidence: EvidenceCandidate, *, max_chars: int) -> str:
    renderer = _RELATION_RENDERERS.get(evidence.relation)
    if renderer is None:
        text = f"{evidence.head_label_zh}与{evidence.tail_label_zh}存在{evidence.relation}关系。"
    else:
        text = renderer(evidence.head_label_zh, evidence.tail_label_zh)
    return _fit_complete_text(text, max_chars)


def validate_candidate_assessment_contract(
    answer: dict, allowed_evidence_ids: set[str]
) -> bool:
    assessments = answer.get("evidence_assessments", [])
    if not isinstance(assessments, list) or len(assessments) != len(allowed_evidence_ids):
        return False
    seen: set[str] = set()
    for assessment in assessments:
        if not isinstance(assessment, dict):
            return False
        evidence_id = str(assessment.get("evidence_id", ""))
        verdict = str(assessment.get("verdict", "")).lower()
        if (
            evidence_id not in allowed_evidence_ids
            or evidence_id in seen
            or verdict not in {"direct", "indirect", "irrelevant"}
        ):
            return False
        seen.add(evidence_id)
    return seen == allowed_evidence_ids


def expand_compact_evidence_mask(
    answer: dict, evidence: list[EvidenceCandidate]
) -> tuple[dict, dict]:
    """Map a short ordered 0/1 mask back to immutable evidence IDs.

    The model never has to reproduce long IDs. Invalid or incomplete masks fail
    closed and are never repaired with Silver relevance labels.
    """

    values = answer.get("direct", []) if isinstance(answer, dict) else []
    normalized: list[int] = []
    issues: list[str] = []
    if not isinstance(values, list):
        issues.append("direct_is_not_a_list")
        values = []
    for value in values:
        if value in (0, False, "0"):
            normalized.append(0)
        elif value in (1, True, "1"):
            normalized.append(1)
        else:
            issues.append("non_binary_value")
    if len(normalized) != len(evidence):
        issues.append("mask_length_mismatch")
    contract_valid = not issues
    assessments = []
    if contract_valid:
        assessments = [
            {
                "evidence_id": item.evidence_id,
                "verdict": "direct" if verdict else "irrelevant",
                "aspect": "",
            }
            for item, verdict in zip(evidence, normalized)
        ]
    expanded = {
        "evidence_assessments": assessments,
        "status": (
            "answered"
            if contract_valid and any(normalized)
            else "insufficient_evidence"
            if contract_valid
            else "invalid_model_output"
        ),
        "answer_points": [],
        "summary": "",
    }
    audit = {
        "version": "rp2_compact_evidence_mask_v3",
        "candidate_count": len(evidence),
        "raw_mask_length": len(values),
        "normalized_mask": normalized if contract_valid else None,
        "mask_contract_valid": contract_valid,
        "issues": issues,
        "used_hidden_fault_labels": False,
        "used_relevance_labels": False,
    }
    return expanded, audit


def apply_faithfulness_guard(
    answer: dict,
    query: SilverQuery,
    evidence: list[EvidenceCandidate],
    contract: dict,
    *,
    minimum_fault_affinity: float = 0.0,
) -> tuple[dict, dict]:
    """Conservatively render model-selected, role-matched canonical claims.

    This adds no model call and never reads ``fault_class_ids`` or relevance labels.
    Source-language evidence, page, URL and hashes remain untouched in the graph.
    """

    started = time.perf_counter_ns()
    by_id = {item.evidence_id: item for item in evidence}
    proposed_points = answer.get("answer_points", [])
    if not isinstance(proposed_points, list):
        proposed_points = []
    kept: list[dict] = []
    dropped: list[dict] = []
    used_evidence: set[str] = set()
    max_points = int(contract["max_answer_points"])
    max_point_chars = int(contract["max_point_chars"])

    if str(answer.get("status")) == "answered":
        for point_index, point in enumerate(proposed_points):
            if len(kept) >= max_points:
                dropped.append({"point_index": point_index, "reason": "point_budget_exceeded"})
                continue
            ids = point.get("evidence_ids", []) if isinstance(point, dict) else []
            valid = [str(value) for value in ids if str(value) in by_id]
            if not valid:
                dropped.append({"point_index": point_index, "reason": "missing_allowed_evidence"})
                continue
            primary = by_id[valid[0]]
            if primary.role != query.role:
                dropped.append({"point_index": point_index, "reason": "required_role_mismatch"})
                continue
            affinity = visible_fault_affinity(query, primary)
            if affinity < minimum_fault_affinity:
                dropped.append({
                    "point_index": point_index,
                    "reason": "visible_fault_affinity_below_floor",
                    "visible_fault_affinity": affinity,
                })
                continue
            if primary.evidence_id in used_evidence:
                dropped.append({"point_index": point_index, "reason": "duplicate_primary_evidence"})
                continue
            used_evidence.add(primary.evidence_id)
            kept.append({
                "text": render_canonical_claim(primary, max_chars=max_point_chars),
                "evidence_ids": [primary.evidence_id],
            })

    if kept:
        summary_parts: list[str] = []
        summary_limit = int(contract["max_summary_chars"])
        for point in kept:
            candidate = "".join(summary_parts) + point["text"]
            if len(candidate) <= summary_limit:
                summary_parts.append(point["text"])
        if not summary_parts:
            summary_parts = [_fit_complete_text(kept[0]["text"], summary_limit)]
        guarded = {"status": "answered", "answer_points": kept, "summary": "".join(summary_parts)}
    else:
        guarded = {
            "status": "insufficient_evidence",
            "answer_points": [],
            "summary": "现有证据不足，无法回答。",
        }
    audit = {
        "version": FAITHFULNESS_GUARD_VERSION,
        "model_status": str(answer.get("status", "")),
        "proposed_point_count": len(proposed_points),
        "kept_point_count": len(kept),
        "dropped_point_count": len(dropped),
        "dropped_points": dropped,
        "minimum_visible_fault_affinity": minimum_fault_affinity,
        "used_hidden_fault_labels": False,
        "used_relevance_labels": False,
        "summary_policy": "concatenate_guarded_atomic_points_without_new_facts",
        "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000,
    }
    return guarded, audit


def apply_evidence_coverage_guard(
    answer: dict,
    query: SilverQuery,
    evidence: list[EvidenceCandidate],
    contract: dict,
    *,
    minimum_fault_affinity: float = 0.0,
) -> tuple[dict, dict]:
    """Render every model-adjudicated direct candidate up to the evidence budget.

    Candidate assessment is performed by the same local 7B generation call. The
    deterministic guard never reads Silver relevance labels or fault-class IDs.
    """

    started = time.perf_counter_ns()
    by_id = {item.evidence_id: item for item in evidence}
    assessments = answer.get("evidence_assessments", [])
    if not isinstance(assessments, list):
        assessments = []
    assessment_by_id: dict[str, dict] = {}
    assessment_issues: list[dict] = []
    for index, assessment in enumerate(assessments):
        if not isinstance(assessment, dict):
            assessment_issues.append({"assessment_index": index, "reason": "not_an_object"})
            continue
        evidence_id = str(assessment.get("evidence_id", ""))
        verdict = str(assessment.get("verdict", "")).lower()
        if evidence_id not in by_id:
            assessment_issues.append({
                "assessment_index": index,
                "evidence_id": evidence_id,
                "reason": "unknown_evidence_id",
            })
            continue
        if evidence_id in assessment_by_id:
            assessment_issues.append({
                "assessment_index": index,
                "evidence_id": evidence_id,
                "reason": "duplicate_assessment",
            })
            continue
        if verdict not in {"direct", "indirect", "irrelevant"}:
            assessment_issues.append({
                "assessment_index": index,
                "evidence_id": evidence_id,
                "reason": "invalid_verdict",
            })
            continue
        assessment_by_id[evidence_id] = dict(assessment, verdict=verdict)

    direct_ids = {
        evidence_id
        for evidence_id, assessment in assessment_by_id.items()
        if assessment["verdict"] == "direct"
    }
    proposed_points = answer.get("answer_points", [])
    if not isinstance(proposed_points, list):
        proposed_points = []
    kept: list[dict] = []
    dropped: list[dict] = []
    seen_claims: set[str] = set()
    max_points = int(contract["max_answer_points"])
    max_point_chars = int(contract["max_point_chars"])
    for item in evidence:
        if item.evidence_id not in direct_ids:
            continue
        if len(kept) >= max_points:
            dropped.append({"evidence_id": item.evidence_id, "reason": "point_budget_exceeded"})
            continue
        if item.role != query.role:
            dropped.append({"evidence_id": item.evidence_id, "reason": "required_role_mismatch"})
            continue
        affinity = visible_fault_affinity(query, item)
        if affinity < minimum_fault_affinity:
            dropped.append({
                "evidence_id": item.evidence_id,
                "reason": "visible_fault_affinity_below_floor",
                "visible_fault_affinity": affinity,
            })
            continue
        if item.claim_id and item.claim_id in seen_claims:
            dropped.append({"evidence_id": item.evidence_id, "reason": "duplicate_claim"})
            continue
        if item.claim_id:
            seen_claims.add(item.claim_id)
        kept.append({
            "text": render_canonical_claim(item, max_chars=max_point_chars),
            "evidence_ids": [item.evidence_id],
        })

    if kept:
        summary_limit = int(contract["max_summary_chars"])
        summary_parts: list[str] = []
        for point in kept:
            candidate = "".join(summary_parts) + point["text"]
            if len(candidate) <= summary_limit:
                summary_parts.append(point["text"])
        if not summary_parts:
            summary_parts = [_fit_complete_text(kept[0]["text"], summary_limit)]
        guarded = {"status": "answered", "answer_points": kept, "summary": "".join(summary_parts)}
    else:
        guarded = {
            "status": "insufficient_evidence",
            "answer_points": [],
            "summary": "现有证据不足，无法回答。",
        }
    missing_assessments = [
        item.evidence_id for item in evidence if item.evidence_id not in assessment_by_id
    ]
    audit = {
        "version": COVERAGE_GUARD_VERSION,
        "model_status": str(answer.get("status", "")),
        "candidate_count": len(evidence),
        "valid_assessment_count": len(assessment_by_id),
        "assessment_contract_valid": (
            len(assessment_by_id) == len(evidence) and not assessment_issues
        ),
        "missing_assessment_ids": missing_assessments,
        "assessment_issues": assessment_issues,
        "verdict_counts": {
            verdict: sum(row["verdict"] == verdict for row in assessment_by_id.values())
            for verdict in ("direct", "indirect", "irrelevant")
        },
        "proposed_point_count": len(proposed_points),
        "kept_point_count": len(kept),
        "dropped_point_count": len(dropped),
        "dropped_points": dropped,
        "minimum_visible_fault_affinity": minimum_fault_affinity,
        "used_hidden_fault_labels": False,
        "used_relevance_labels": False,
        "summary_policy": "concatenate_guarded_atomic_points_without_new_facts",
        "elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000,
    }
    return guarded, audit


def validate_generated_answer(
    answer: dict,
    allowed_evidence_ids: set[str],
    *,
    max_answer_points: int | None = None,
    max_point_chars: int | None = None,
    max_summary_chars: int | None = None,
) -> dict:
    points = answer.get("answer_points", [])
    if not isinstance(points, list):
        points = []
    citations: list[str] = []
    uncited = 0
    for point in points:
        ids = point.get("evidence_ids", []) if isinstance(point, dict) else []
        if not ids:
            uncited += 1
        citations.extend(str(value) for value in ids)
    valid = [value for value in citations if value in allowed_evidence_ids]
    status = str(answer.get("status", ""))
    status_valid = status in {"answered", "insufficient_evidence"}
    answered_contract_valid = bool(points) and uncited == 0 and len(valid) == len(citations)
    insufficient_contract_valid = not points and not citations
    point_budget_valid = max_answer_points is None or len(points) <= max_answer_points
    point_length_valid = max_point_chars is None or all(
        len(str(point.get("text", ""))) <= max_point_chars
        for point in points
        if isinstance(point, dict)
    )
    summary_length_valid = (
        max_summary_chars is None
        or len(str(answer.get("summary", ""))) <= max_summary_chars
    )
    contract_valid = status_valid and (
        answered_contract_valid if status == "answered" else insufficient_contract_valid
    ) and point_budget_valid and point_length_valid and summary_length_valid
    return {
        "answer_point_count": len(points),
        "citation_count": len(citations),
        "valid_citation_count": len(valid),
        "invalid_citation_count": len(citations) - len(valid),
        "citation_validity_rate": len(valid) / len(citations) if citations else None,
        "uncited_answer_point_rate": uncited / len(points) if points else 0.0,
        "status": status,
        "status_valid": status_valid,
        "answered_contract_valid": answered_contract_valid,
        "insufficient_contract_valid": insufficient_contract_valid,
        "point_budget_valid": point_budget_valid,
        "point_length_valid": point_length_valid,
        "summary_length_valid": summary_length_valid,
        "contract_valid": contract_valid,
    }


def score_silver_response(
    answer: dict,
    validation: dict,
    relevant_evidence_ids: set[str],
) -> dict:
    """Score final-answer behavior against frozen Silver evidence labels.

    This is a conservative automatic proxy, not expert factual correctness. A
    cited but unlabeled assertion may still be valid, so the metric must remain
    explicitly named Silver in reports.
    """

    cited = {
        str(evidence_id)
        for point in answer.get("answer_points", [])
        if isinstance(point, dict)
        for evidence_id in point.get("evidence_ids", [])
    }
    matched = cited & relevant_evidence_ids
    precision = len(matched) / len(cited) if cited else 0.0
    recall = len(matched) / len(relevant_evidence_ids) if relevant_evidence_ids else None
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if recall is not None and precision + recall > 0
        else 0.0
    )
    answerable = bool(relevant_evidence_ids)
    if answerable:
        utility = f1 if validation.get("status") == "answered" and validation.get("contract_valid") else 0.0
    else:
        utility = float(
            validation.get("status") == "insufficient_evidence"
            and validation.get("contract_valid")
        )
    return {
        "silver_relevant_citation_count": len(matched),
        "silver_citation_precision": precision if cited else None,
        "silver_citation_recall": recall,
        "silver_citation_f1": f1 if answerable else None,
        "answer_supported_by_silver_evidence": bool(matched) if answerable else None,
        "correct_silver_abstention": (
            validation.get("status") == "insufficient_evidence"
            and validation.get("contract_valid")
        ) if not answerable else None,
        "silver_response_utility": utility,
        "metric_boundary": "Silver evidence-label agreement; not human expert factual accuracy",
    }


def summarize_generation_rows(rows: list[dict], query_by_id: dict[str, SilverQuery]) -> dict:
    """Aggregate generation metrics without conflating abstention and citation validity."""

    if not rows:
        return {
            "samples": 0,
            "citation_id_validity_rate": None,
            "answerable_answer_rate": None,
            "unanswerable_abstention_rate": None,
        }
    total_citations = sum(int(row["validation"].get("citation_count", 0)) for row in rows)
    valid_citations = sum(int(row["validation"].get("valid_citation_count", 0)) for row in rows)
    answer_points = sum(int(row["validation"].get("answer_point_count", 0)) for row in rows)
    uncited_points = sum(
        int(round(float(row["validation"].get("uncited_answer_point_rate", 0.0)) * int(row["validation"].get("answer_point_count", 0))))
        for row in rows
    )
    answerable = [row for row in rows if query_by_id[row["query_id"]].relevant_evidence_ids]
    unanswerable = [row for row in rows if not query_by_id[row["query_id"]].relevant_evidence_ids]
    answered = [row for row in rows if row["validation"].get("status") == "answered"]
    answered_citation_counts = [
        int(row["validation"].get("citation_count", 0)) for row in answered
    ]
    relevant_recalls = [
        float(row["relevant_citation_recall"])
        for row in rows
        if row.get("relevant_citation_recall") is not None
    ]
    model_latencies = [
        float(row.get("model_metrics", {}).get("elapsed_ms", 0.0))
        for row in rows
        if float(row.get("model_metrics", {}).get("elapsed_ms", 0.0)) > 0
    ]
    request_latencies = [float(row.get("generation_request_wall_ms", 0.0)) for row in rows]
    end_to_end_latencies = [
        float(row.get("retrieval_elapsed_ms", 0.0))
        + float(row.get("model_metrics", {}).get("elapsed_ms", 0.0))
        for row in rows
        if float(row.get("model_metrics", {}).get("elapsed_ms", 0.0)) > 0
    ]
    end_to_end_wall_latencies = [
        float(row.get("retrieval_elapsed_ms", 0.0))
        + float(row.get("generation_request_wall_ms", 0.0))
        for row in rows
        if float(row.get("generation_request_wall_ms", 0.0)) > 0
    ]
    end_to_end_inference_latencies = [
        float(row.get("end_to_end_inference_elapsed_ms", 0.0))
        for row in rows
        if float(row.get("end_to_end_inference_elapsed_ms", 0.0)) > 0
    ]
    token_rates = [
        float(row.get("model_metrics", {}).get("tokens_per_second", 0.0))
        for row in rows
        if float(row.get("model_metrics", {}).get("tokens_per_second", 0.0)) > 0
    ]
    prompt_tokens = [
        float(row.get("model_metrics", {}).get("prompt_tokens", 0.0))
        for row in rows
        if float(row.get("model_metrics", {}).get("prompt_tokens", 0.0)) > 0
    ]
    generated_tokens = [
        float(row.get("model_metrics", {}).get("generated_tokens", 0.0))
        for row in rows
    ]
    json_parse_flags = [
        bool(row.get("model_metrics", {}).get("model_output_valid_json", True))
        for row in rows
    ]
    silver_scores = [row.get("silver_evaluation", {}) for row in rows]
    guard_rows = [row["faithfulness_guard"] for row in rows if row.get("faithfulness_guard")]
    silver_precisions = [
        float(score["silver_citation_precision"])
        for score in silver_scores
        if score.get("silver_citation_precision") is not None
    ]
    silver_f1 = [
        float(score["silver_citation_f1"])
        for score in silver_scores
        if score.get("silver_citation_f1") is not None
    ]
    silver_utilities = [float(score.get("silver_response_utility", 0.0)) for score in silver_scores]
    return {
        "samples": len(rows),
        "answered_queries": len(answered),
        "citations_per_answered_query_mean": (
            statistics.fmean(answered_citation_counts)
            if answered_citation_counts else None
        ),
        "answered_query_citation_count_distribution": {
            str(count): answered_citation_counts.count(count)
            for count in sorted(set(answered_citation_counts))
        },
        "multi_citation_answer_rate": (
            sum(count >= 2 for count in answered_citation_counts)
            / len(answered_citation_counts)
            if answered_citation_counts else None
        ),
        "insufficient_evidence_queries": sum(
            row["validation"].get("status") == "insufficient_evidence" for row in rows
        ),
        "answerable_queries": len(answerable),
        "answerable_answer_rate": (
            sum(row["validation"].get("status") == "answered" for row in answerable) / len(answerable)
            if answerable else None
        ),
        "unanswerable_queries": len(unanswerable),
        "unanswerable_abstention_rate": (
            sum(row["validation"].get("status") == "insufficient_evidence" for row in unanswerable)
            / len(unanswerable)
            if unanswerable else None
        ),
        "citation_count": total_citations,
        "valid_citation_count": valid_citations,
        "invalid_citation_count": total_citations - valid_citations,
        "citation_id_validity_rate": valid_citations / total_citations if total_citations else None,
        "answer_point_count": answer_points,
        "uncited_answer_point_rate": uncited_points / answer_points if answer_points else 0.0,
        "strict_contract_rate": statistics.fmean(
            [float(bool(row["validation"].get("contract_valid"))) for row in rows]
        ),
        "strict_grounded_answer_rate": (
            sum(bool(row["validation"].get("answered_contract_valid")) for row in answered)
            / len(answered)
            if answered else None
        ),
        "relevant_citation_recall": statistics.fmean(relevant_recalls) if relevant_recalls else None,
        "silver_citation_precision_macro": statistics.fmean(silver_precisions) if silver_precisions else None,
        "silver_citation_f1_macro_answerable": statistics.fmean(silver_f1) if silver_f1 else None,
        "silver_response_utility_macro": statistics.fmean(silver_utilities) if silver_utilities else None,
        "silver_supported_answer_rate": (
            sum(bool(score.get("answer_supported_by_silver_evidence")) for score in silver_scores if score.get("answer_supported_by_silver_evidence") is not None)
            / sum(score.get("answer_supported_by_silver_evidence") is not None for score in silver_scores)
            if any(score.get("answer_supported_by_silver_evidence") is not None for score in silver_scores)
            else None
        ),
        "generation_model_latency_ms_mean": statistics.fmean(model_latencies) if model_latencies else None,
        "generation_model_latency_ms_p50": _percentile(model_latencies, 0.50),
        "generation_model_latency_ms_p95": _percentile(model_latencies, 0.95),
        "generation_request_wall_ms_mean": statistics.fmean(request_latencies),
        "end_to_end_model_latency_ms_mean": statistics.fmean(end_to_end_latencies) if end_to_end_latencies else None,
        "end_to_end_model_latency_ms_p50": _percentile(end_to_end_latencies, 0.50),
        "end_to_end_model_latency_ms_p95": _percentile(end_to_end_latencies, 0.95),
        "end_to_end_wall_latency_ms_p50": _percentile(end_to_end_wall_latencies, 0.50),
        "end_to_end_wall_latency_ms_p95": _percentile(end_to_end_wall_latencies, 0.95),
        "end_to_end_inference_latency_ms_mean": statistics.fmean(end_to_end_inference_latencies) if end_to_end_inference_latencies else None,
        "end_to_end_inference_latency_ms_p50": _percentile(end_to_end_inference_latencies, 0.50),
        "end_to_end_inference_latency_ms_p95": _percentile(end_to_end_inference_latencies, 0.95),
        "tokens_per_second_mean": statistics.fmean(token_rates) if token_rates else None,
        "prompt_tokens_mean": statistics.fmean(prompt_tokens) if prompt_tokens else None,
        "prompt_tokens_p95": _percentile(prompt_tokens, 0.95),
        "generated_tokens_mean": statistics.fmean(generated_tokens),
        "generated_tokens_p95": _percentile(generated_tokens, 0.95),
        "model_output_valid_json_rate": statistics.fmean(
            [float(value) for value in json_parse_flags]
        ),
        "model_output_json_failure_count": sum(not value for value in json_parse_flags),
        "faithfulness_guard_applied_rate": len(guard_rows) / len(rows),
        "faithfulness_guard_latency_ms_mean": (
            statistics.fmean(float(row.get("elapsed_ms", 0.0)) for row in guard_rows)
            if guard_rows else None
        ),
        "faithfulness_guard_dropped_point_count": sum(
            int(row.get("dropped_point_count", 0)) for row in guard_rows
        ),
        "candidate_assessment_contract_rate": (
            statistics.fmean(
                float(bool(row["validation"].get("candidate_assessment_contract_valid")))
                for row in rows
                if "candidate_assessment_contract_valid" in row["validation"]
            )
            if any(
                "candidate_assessment_contract_valid" in row["validation"]
                for row in rows
            )
            else None
        ),
        "cuda_peak_memory_bytes_max": max(
            (int(row.get("model_metrics", {}).get("cuda_peak_memory_bytes", 0)) for row in rows),
            default=0,
        ),
        "cache_hits": sum(row.get("source") == "CACHE" for row in rows),
        "model_calls": sum(row.get("source") == "MODEL" for row in rows),
        "deterministic_empty_short_circuits": sum(
            row.get("source") == "DETERMINISTIC_EMPTY" for row in rows
        ),
        "metric_boundary": "citation ID validity is not semantic entailment or expert factual accuracy",
    }
