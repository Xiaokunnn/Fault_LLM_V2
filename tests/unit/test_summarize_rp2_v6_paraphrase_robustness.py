from __future__ import annotations

from scripts.summarize_rp2_v6_paraphrase_robustness import summarize


def test_paraphrase_summary_checks_labels_and_selection_stability() -> None:
    parent = [{
        "query_id": "Q1", "fault_id": "F1", "fault_name_zh": "汽蚀",
        "role": "symptom", "relevant_evidence_ids": ["E1", "E2"],
    }]
    paraphrases = [
        {**parent[0], "query_id": "Q1-P1", "question_zh": "改写一"},
        {**parent[0], "query_id": "Q1-P2", "question_zh": "改写二"},
    ]
    mapping = [
        {"query_id": "Q1-P1", "parent_query_id": "Q1", "variant": 1},
        {"query_id": "Q1-P2", "parent_query_id": "Q1", "variant": 2},
    ]
    frozen = [{
        "method": "M", "query_id": "Q1",
        "ranked": [{"evidence_id": "E1"}, {"evidence_id": "E3"}],
    }]
    rewritten = [
        {"method": "M", "query_id": "Q1-P1", "ranked": [{"evidence_id": "E1"}]},
        {"method": "M", "query_id": "Q1-P2", "ranked": [{"evidence_id": "E2"}]},
    ]
    report = summarize(
        parent_queries=parent,
        paraphrase_queries=paraphrases,
        mapping_rows=mapping,
        parent_retrievals=frozen,
        paraphrase_retrievals=rewritten,
    )
    method = report["methods"]["M"]
    assert method["recall_macro"] == 0.5
    assert method["top1_agreement_vs_parent_rate"] == 0.5
    assert method["selection_jaccard_vs_parent_mean"] == 0.25


def test_paraphrase_summary_rejects_changed_structured_label() -> None:
    parent = [{
        "query_id": "Q1", "fault_id": "F1", "fault_name_zh": "汽蚀",
        "role": "symptom", "relevant_evidence_ids": ["E1"],
    }]
    paraphrase = [{**parent[0], "query_id": "Q1-P1", "role": "maintenance"}]
    try:
        summarize(
            parent_queries=parent,
            paraphrase_queries=paraphrase,
            mapping_rows=[{"query_id": "Q1-P1", "parent_query_id": "Q1", "variant": 1}],
            parent_retrievals=[{"method": "M", "query_id": "Q1", "ranked": []}],
            paraphrase_retrievals=[{"method": "M", "query_id": "Q1-P1", "ranked": []}],
        )
    except ValueError as exc:
        assert "Structured field changed" in str(exc)
    else:
        raise AssertionError("Changed structured labels must fail closed")
