from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_point_2.dataset import EvidenceCandidate, SilverQuery, build_candidate_pools
from research_point_2.retrieval import RetrievalBudget, RetrievalIndex, retrieve


def _candidate(evidence_id: str, family: str, *, relevant: bool = True) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=evidence_id,
        claim_id=f"C-{evidence_id}",
        head_entity_id=f"H-{evidence_id}",
        tail_entity_id=f"T-{evidence_id}",
        head_label_zh="汽蚀" if relevant else "轴承",
        tail_label_zh="噪声",
        head_type="FaultMode",
        tail_type="Symptom",
        relation="manifests_as",
        role="symptom",
        fault_class_ids=("cavitation",) if relevant else ("bearing_or_lubrication_failure",),
        evidence_text="汽蚀表现为噪声" if relevant else "轴承出现噪声",
        source_family_id=family,
        doc_id="MP001",
        pdf_page_number=1,
        source_url="https://example.com/a.pdf",
        final_confidence=0.9,
        evidence_level="E1",
    )


def _query() -> SilverQuery:
    return SilverQuery(
        query_id="Q1",
        question_zh="汽蚀有哪些症状？",
        fault_id="cavitation",
        fault_name_zh="汽蚀",
        role="symptom",
        relevant_evidence_ids=("E1", "E2", "E3"),
    )


def test_candidate_pool_preserves_all_positives() -> None:
    candidates = [_candidate("E1", "A"), _candidate("E2", "A"), _candidate("E3", "B")]
    candidates += [_candidate(f"N{i}", "C", relevant=False) for i in range(10)]
    pooled = build_candidate_pools([_query()], candidates, pool_size=6)
    assert set(pooled[0].relevant_evidence_ids).issubset(pooled[0].candidate_evidence_ids)
    assert len(pooled[0].candidate_evidence_ids) == 6


def test_ours_respects_selection_and_source_family_budgets() -> None:
    candidates = [
        _candidate("E1", "A"),
        _candidate("E2", "A"),
        _candidate("E3", "A"),
        _candidate("E4", "B"),
    ]
    result = retrieve(
        _query(),
        candidates,
        method="ours",
        budget=RetrievalBudget(
            max_scored_candidates=4,
            max_selected_evidence=3,
            max_per_source_family=1,
        ),
    )
    assert result.selected_evidence == 2
    assert len({item.source_family_id for item in result.ranked}) == 2
    assert result.scored_candidates <= 4


def test_unknown_method_is_rejected() -> None:
    try:
        retrieve(_query(), [_candidate("E1", "A")], method="not-a-method")
    except ValueError as exc:
        assert "unknown retrieval method" in str(exc)
    else:
        raise AssertionError("unknown method should fail")


def test_index_does_not_use_hidden_fault_labels() -> None:
    candidates = [_candidate("E1", "A"), _candidate("N1", "B", relevant=False)]
    index = RetrievalIndex(candidates)
    result = retrieve(
        _query(),
        index,
        method="role_topk",
        budget=RetrievalBudget(max_scored_candidates=10, max_selected_evidence=10),
    )
    assert {item.evidence_id for item in result.ranked} == {"E1", "N1"}
