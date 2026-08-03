"""Evidence-only prompt contract and automatic Silver generation metrics."""

from __future__ import annotations

import json
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


def build_generation_prompt(query: SilverQuery, evidence: list[EvidenceCandidate]) -> str:
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
        "insufficient_evidence_contract": {
            "status": "insufficient_evidence",
            "answer_points": [],
            "summary": "现有证据不足，无法回答。",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_generated_answer(answer: dict, allowed_evidence_ids: set[str]) -> dict:
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
    contract_valid = status_valid and (
        answered_contract_valid if status == "answered" else insufficient_contract_valid
    )
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
        "contract_valid": contract_valid,
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
    token_rates = [
        float(row.get("model_metrics", {}).get("tokens_per_second", 0.0))
        for row in rows
        if float(row.get("model_metrics", {}).get("tokens_per_second", 0.0)) > 0
    ]
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
        "generation_model_latency_ms_mean": statistics.fmean(model_latencies) if model_latencies else None,
        "generation_request_wall_ms_mean": statistics.fmean(request_latencies),
        "end_to_end_model_latency_ms_mean": statistics.fmean(end_to_end_latencies) if end_to_end_latencies else None,
        "tokens_per_second_mean": statistics.fmean(token_rates) if token_rates else None,
        "generated_tokens_mean": statistics.fmean(
            [float(row.get("model_metrics", {}).get("generated_tokens", 0.0)) for row in rows]
        ),
        "cuda_peak_memory_bytes_max": max(
            (int(row.get("model_metrics", {}).get("cuda_peak_memory_bytes", 0)) for row in rows),
            default=0,
        ),
        "cache_hits": sum(row.get("source") == "CACHE" for row in rows),
        "model_calls": sum(row.get("source") == "MODEL" for row in rows),
        "metric_boundary": "citation ID validity is not semantic entailment or expert factual accuracy",
    }
