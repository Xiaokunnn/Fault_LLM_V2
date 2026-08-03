"""Evidence-only prompt contract and automatic Silver generation metrics."""

from __future__ import annotations

import json
import math
import statistics
from typing import Protocol

from .dataset import EvidenceCandidate, SilverQuery


SYSTEM_PROMPT = """你是船舶机舱泵系故障辅助诊断模型。只能使用给出的证据，不得补入外部常识。
当证据足以回答时，将status设为answered；每个answer_point必须引用至少一个给定的准确证据ID。
当没有证据或证据不足时，将status设为insufficient_evidence，answer_points必须为空数组，summary只说明证据不足。
禁止编造、改写或使用占位证据ID。输出严格JSON，不输出Markdown。"""


class JsonGenerator(Protocol):
    def generate_json(
        self, system_prompt: str, user_prompt: str, *, max_new_tokens: int = 768
    ) -> dict: ...


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
) -> str:
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
    return json.dumps(payload, ensure_ascii=False, indent=2)


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
    silver_scores = [row.get("silver_evaluation", {}) for row in rows]
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
        "cuda_peak_memory_bytes_max": max(
            (int(row.get("model_metrics", {}).get("cuda_peak_memory_bytes", 0)) for row in rows),
            default=0,
        ),
        "cache_hits": sum(row.get("source") == "CACHE" for row in rows),
        "model_calls": sum(row.get("source") == "MODEL" for row in rows),
        "metric_boundary": "citation ID validity is not semantic entailment or expert factual accuracy",
    }
