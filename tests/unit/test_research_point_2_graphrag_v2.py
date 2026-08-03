from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import EvidenceCandidate, SilverQuery
from research_point_2.dense_index import DenseEvidenceIndex, evidence_index_text
from research_point_2.generation import (
    build_generation_prompt,
    summarize_generation_rows,
    validate_generated_answer,
)
from research_point_2.graph_rag_v2 import retrieve_dense_graph
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex


def _candidate(eid: str, family: str, label: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=eid,
        claim_id=f"C-{eid}",
        head_entity_id="F-汽蚀",
        tail_entity_id=f"T-{eid}",
        head_label_zh="汽蚀",
        tail_label_zh=label,
        head_type="FaultMode",
        tail_type="Symptom",
        relation="manifests_as",
        role="symptom",
        fault_class_ids=("cavitation",),
        evidence_text=f"汽蚀可导致{label}",
        source_family_id=family,
        doc_id="MP001",
        pdf_page_number=7,
        source_url="https://example.com/manual.pdf",
        final_confidence=0.9,
        evidence_level="E1",
    )


class FakeEncoder:
    def encode(self, texts):
        rows = []
        for text in texts:
            rows.append([1.0, 0.0] if "汽蚀" in text else [0.0, 1.0])
        return np.asarray(rows, dtype="float32")


def _query() -> SilverQuery:
    return SilverQuery("Q1", "汽蚀有什么症状？", "cavitation", "汽蚀", "symptom", ("E1",))


def test_dense_index_preserves_chinese_contract_and_roundtrips(tmp_path: Path) -> None:
    candidates = [_candidate("E1", "A", "噪声"), _candidate("E2", "B", "振动")]
    assert "头实体：汽蚀" in evidence_index_text(candidates[0])
    index = DenseEvidenceIndex.build(candidates, FakeEncoder())
    index.save(tmp_path)
    loaded = DenseEvidenceIndex.load(tmp_path)
    assert loaded.evidence_ids == ("E1", "E2")
    assert loaded.search("汽蚀症状", FakeEncoder(), top_n=1)[0].evidence_id == "E1"


def test_dense_ours_enforces_source_family_cap() -> None:
    candidates = [
        _candidate("E1", "A", "噪声"),
        _candidate("E2", "A", "振动"),
        _candidate("E3", "B", "流量下降"),
    ]
    result = retrieve_dense_graph(
        _query(),
        candidates,
        RetrievalIndex(candidates),
        DenseEvidenceIndex.build(candidates, FakeEncoder()),
        FakeEncoder(),
        method="dense_ours",
        budget=RetrievalBudget(max_scored_candidates=3, max_selected_evidence=3, max_per_source_family=1),
    )
    assert result.selected_evidence == 2
    assert {row.source_family_id for row in result.ranked} == {"A", "B"}


def test_generation_prompt_and_citation_validator() -> None:
    prompt = json.loads(build_generation_prompt(_query(), [_candidate("E1", "A", "噪声")]))
    assert prompt["evidence"][0]["evidence_id"] == "E1"
    assert prompt["evidence"][0]["pdf_page"] == 7
    checked = validate_generated_answer(
        {"status": "answered", "answer_points": [{"text": "有噪声", "evidence_ids": ["E1", "BAD"]}]},
        {"E1"},
    )
    assert checked["valid_citation_count"] == 1
    assert checked["invalid_citation_count"] == 1
    assert checked["contract_valid"] is False


def test_abstention_is_not_counted_as_invalid_citation() -> None:
    checked = validate_generated_answer(
        {
            "status": "insufficient_evidence",
            "answer_points": [],
            "summary": "现有证据不足。",
        },
        set(),
    )
    assert checked["citation_validity_rate"] is None
    assert checked["insufficient_contract_valid"] is True
    assert checked["contract_valid"] is True


def test_dense_ours_performs_auditable_graph_expansion() -> None:
    first = replace(
        _candidate("E1", "A", "噪声"),
        head_entity_id="F-CAV",
        tail_entity_id="X-SHARED",
    )
    second = replace(
        _candidate("E2", "B", "振动"),
        head_entity_id="X-SHARED",
        tail_entity_id="Y-VIBRATION",
    )
    candidates = [first, second]
    dense = DenseEvidenceIndex(["E1", "E2"], [[1.0, 0.0], [0.0, 1.0]])
    graph = RetrievalIndex(candidates)
    ours = retrieve_dense_graph(
        _query(),
        candidates,
        graph,
        dense,
        FakeEncoder(),
        method="dense_ours",
        budget=RetrievalBudget(max_scored_candidates=2, max_selected_evidence=2),
        dense_top_n=1,
        anchor_evidence_count=1,
        ours_graph_hops=1,
    )
    no_graph = retrieve_dense_graph(
        _query(),
        candidates,
        graph,
        dense,
        FakeEncoder(),
        method="dense_ours_no_graph",
        budget=RetrievalBudget(max_scored_candidates=2, max_selected_evidence=2),
        dense_top_n=1,
        anchor_evidence_count=1,
    )
    assert {row.evidence_id for row in ours.ranked} == {"E1", "E2"}
    assert ours.visited_nodes > 0
    assert ours.visited_edges > 0
    assert [row.evidence_id for row in no_graph.ranked] == ["E1"]
    assert no_graph.visited_nodes == 0


def test_generation_summary_separates_abstention_and_cached_model_latency() -> None:
    answerable = _query()
    unanswerable = replace(
        answerable,
        query_id="Q2",
        relevant_evidence_ids=(),
        label_status="unanswerable_in_KG_v1_validated",
    )
    rows = [
        {
            "query_id": "Q1",
            "validation": validate_generated_answer(
                {"status": "answered", "answer_points": [{"text": "噪声", "evidence_ids": ["E1"]}]},
                {"E1"},
            ),
            "relevant_citation_recall": 1.0,
            "retrieval_elapsed_ms": 5.0,
            "generation_request_wall_ms": 1.0,
            "model_metrics": {"elapsed_ms": 100.0, "generated_tokens": 10, "tokens_per_second": 10.0},
            "source": "CACHE",
        },
        {
            "query_id": "Q2",
            "validation": validate_generated_answer(
                {"status": "insufficient_evidence", "answer_points": []}, set()
            ),
            "relevant_citation_recall": None,
            "retrieval_elapsed_ms": 5.0,
            "generation_request_wall_ms": 1.0,
            "model_metrics": {"elapsed_ms": 200.0, "generated_tokens": 10, "tokens_per_second": 10.0},
            "source": "CACHE",
        },
    ]
    summary = summarize_generation_rows(rows, {"Q1": answerable, "Q2": unanswerable})
    assert summary["citation_id_validity_rate"] == 1.0
    assert summary["answerable_answer_rate"] == 1.0
    assert summary["unanswerable_abstention_rate"] == 1.0
    assert summary["generation_model_latency_ms_mean"] == 150.0
    assert summary["generation_request_wall_ms_mean"] == 1.0
