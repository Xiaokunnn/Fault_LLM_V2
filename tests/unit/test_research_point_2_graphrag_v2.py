from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from research_point_2.dataset import EvidenceCandidate, SilverQuery
from research_point_2.dense_index import DenseEvidenceIndex, evidence_index_text
from research_point_2.generation import build_generation_prompt, validate_generated_answer
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
