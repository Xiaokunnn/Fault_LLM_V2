"""Evidence-only prompt contract and automatic Silver generation metrics."""

from __future__ import annotations

import json
from typing import Protocol

from .dataset import EvidenceCandidate, SilverQuery


SYSTEM_PROMPT = """你是船舶机舱泵系故障辅助诊断模型。只能使用给出的证据，不得补入外部常识。
每个结论必须引用证据ID。证据不足时将status设为insufficient_evidence。
输出严格JSON，不输出Markdown。"""


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
    return {
        "answer_point_count": len(points),
        "citation_count": len(citations),
        "valid_citation_count": len(valid),
        "invalid_citation_count": len(citations) - len(valid),
        "citation_validity_rate": len(valid) / len(citations) if citations else 0.0,
        "uncited_answer_point_rate": uncited / len(points) if points else 0.0,
        "status": str(answer.get("status", "")),
    }
