"""Frozen graph and development Silver benchmark adapters for research point 2."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


ROLE_RELATIONS = {
    "symptom": {"manifests_as", "indicates"},
    "cause_or_mechanism": {"causes", "evolves_to", "increases_risk_of"},
    "inspection": {"diagnosed_by", "inspected_by"},
    "maintenance": {"mitigated_by", "prevented_by", "maintained_by"},
}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return [text] if text else []
    return [str(value)]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def relation_role(relation: str) -> str:
    for role, relations in ROLE_RELATIONS.items():
        if relation in relations:
            return role
    return "other"


@dataclass(frozen=True)
class EvidenceCandidate:
    evidence_id: str
    claim_id: str
    head_entity_id: str
    tail_entity_id: str
    head_label_zh: str
    tail_label_zh: str
    head_type: str
    tail_type: str
    relation: str
    role: str
    fault_class_ids: tuple[str, ...]
    evidence_text: str
    source_family_id: str
    doc_id: str
    pdf_page_number: int
    source_url: str
    final_confidence: float
    evidence_level: str

    @property
    def searchable_text(self) -> str:
        return " ".join(
            part
            for part in (
                self.head_label_zh,
                self.relation,
                self.tail_label_zh,
                self.evidence_text,
            )
            if part
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fault_class_ids"] = list(self.fault_class_ids)
        return payload


@dataclass(frozen=True)
class SilverQuery:
    query_id: str
    question_zh: str
    fault_id: str
    fault_name_zh: str
    role: str
    relevant_evidence_ids: tuple[str, ...]
    candidate_evidence_ids: tuple[str, ...] = ()
    label_status: str = "development_silver"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["relevant_evidence_ids"] = list(self.relevant_evidence_ids)
        payload["candidate_evidence_ids"] = list(self.candidate_evidence_ids)
        return payload


def load_evidence_candidates(graph_root: str | Path) -> list[EvidenceCandidate]:
    """Load only the already released Chinese Silver graph records."""

    root = Path(graph_root)
    rows = _read_jsonl(root / "source_records.jsonl")
    candidates: list[EvidenceCandidate] = []
    seen: set[str] = set()
    for row in rows:
        evidence_id = str(row.get("evidence_id") or row.get("assertion_id") or "")
        if not evidence_id or evidence_id in seen:
            continue
        if str(row.get("decision")) not in {"silver_candidate", "accepted_silver"}:
            continue
        if not bool(row.get("eligible_for_chinese_graph")):
            continue
        if bool(row.get("inferred_edge")):
            continue
        relation = str(row.get("relation") or "")
        candidates.append(
            EvidenceCandidate(
                evidence_id=evidence_id,
                claim_id=str(row.get("claim_id") or ""),
                head_entity_id=str(row.get("head_entity_id") or ""),
                tail_entity_id=str(row.get("tail_entity_id") or ""),
                head_label_zh=str(row.get("head_canonical_zh") or row.get("head") or ""),
                tail_label_zh=str(row.get("tail_canonical_zh") or row.get("tail") or ""),
                head_type=str(row.get("head_type") or ""),
                tail_type=str(row.get("tail_type") or ""),
                relation=relation,
                role=relation_role(relation),
                fault_class_ids=tuple(sorted(set(_as_list(row.get("fault_class_ids"))))),
                evidence_text=str(row.get("evidence_text") or ""),
                source_family_id=str(row.get("source_family_id") or ""),
                doc_id=str(row.get("doc_id") or ""),
                pdf_page_number=int(row.get("pdf_page_number") or 0),
                source_url=str(row.get("source_url") or ""),
                final_confidence=float(row.get("final_confidence") or 0.0),
                evidence_level=str(row.get("evidence_level") or ""),
            )
        )
        seen.add(evidence_id)
    return candidates


def load_silver_queries(cq_evaluation_path: str | Path) -> list[SilverQuery]:
    data = json.loads(Path(cq_evaluation_path).read_text(encoding="utf-8"))
    queries: list[SilverQuery] = []
    for item in data.get("task_results", []):
        relevant = tuple(sorted(set(_as_list(item.get("evidence_assertion_ids")))))
        queries.append(
            SilverQuery(
                query_id=str(item["cq_id"]),
                question_zh=str(item["question_zh"]),
                fault_id=str(item["fault_id"]),
                fault_name_zh=str(item["fault_name_zh"]),
                role=str(item["role"]),
                relevant_evidence_ids=relevant,
                label_status=(
                    "development_silver"
                    if relevant
                    else "unanswerable_in_KG_v1_validated"
                ),
            )
        )
    return queries


def _hardness(query: SilverQuery, candidate: EvidenceCandidate) -> tuple[int, int, float, str]:
    fault_match = int(query.fault_id in candidate.fault_class_ids)
    role_match = int(query.role == candidate.role)
    return (fault_match + role_match, role_match, candidate.final_confidence, candidate.evidence_id)


def build_candidate_pools(
    queries: Iterable[SilverQuery],
    candidates: Iterable[EvidenceCandidate],
    *,
    pool_size: int = 64,
    seed: int = 20260801,
) -> list[SilverQuery]:
    """Build deterministic hard-negative pools without changing Silver labels."""

    candidate_list = list(candidates)
    by_id = {item.evidence_id: item for item in candidate_list}
    rng = random.Random(seed)
    output: list[SilverQuery] = []
    for query in queries:
        positives = [eid for eid in query.relevant_evidence_ids if eid in by_id]
        positive_set = set(positives)
        negatives = [item for item in candidate_list if item.evidence_id not in positive_set]
        rng.shuffle(negatives)
        negatives.sort(key=lambda item: _hardness(query, item), reverse=True)
        target_size = max(pool_size, len(positives))
        pool = positives + [item.evidence_id for item in negatives[: max(0, target_size - len(positives))]]
        output.append(
            SilverQuery(
                query_id=query.query_id,
                question_zh=query.question_zh,
                fault_id=query.fault_id,
                fault_name_zh=query.fault_name_zh,
                role=query.role,
                relevant_evidence_ids=query.relevant_evidence_ids,
                candidate_evidence_ids=tuple(pool),
                label_status=query.label_status,
            )
        )
    return output


def write_benchmark(
    queries: Iterable[SilverQuery],
    candidates: Iterable[EvidenceCandidate],
    output_dir: str | Path,
    *,
    manifest_overrides: dict[str, Any] | None = None,
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    query_rows = [query.to_dict() for query in queries]
    candidate_rows = [candidate.to_dict() for candidate in candidates]
    with (output / "queries.jsonl").open("w", encoding="utf-8") as handle:
        for row in query_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "evidence_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in candidate_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "benchmark_id": "marine_pump_rp2_development_silver_v1",
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "query_count": len(query_rows),
        "answerable_query_count": sum(bool(row["relevant_evidence_ids"]) for row in query_rows),
        "unanswerable_query_count": sum(not row["relevant_evidence_ids"] for row in query_rows),
        "candidate_count": len(candidate_rows),
        "scope": "development_only_from_frozen_CQ_v1_and_KG_v1_validated",
        "held_out_test": False,
    }
    manifest.update(manifest_overrides or {})
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
