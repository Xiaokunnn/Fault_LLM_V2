from __future__ import annotations

from scripts.summarize_rp2_v6_verifier_ablation import summarize


def test_verifier_ablation_summary_separates_quality_and_generation_cost() -> None:
    config = {
        "protocol_id": "test",
        "scenarios": [{
            "id": "M", "display_name": "Stage 1", "verification_mode": "stage1_only"
        }],
    }
    queries = [
        {"query_id": "Q1", "relevant_evidence_ids": ["E1"]},
        {"query_id": "Q2", "relevant_evidence_ids": []},
    ]
    rows = [
        {
            "query_id": "Q1", "method": "M", "quality_fusion": "none",
            "canonical_quality_repeat": 0,
            "validation": {"status": "answered", "contract_valid": True},
            "silver_evaluation": {
                "silver_citation_precision": 1.0, "silver_citation_f1": 0.5,
            },
            "model_metrics": {"cascade_model_call_count": 1},
            "latency_breakdown_ms": {"generation_pipeline_ms": 100.0},
        },
        {
            "query_id": "Q2", "method": "M", "quality_fusion": "none",
            "canonical_quality_repeat": 0,
            "validation": {"status": "insufficient_evidence", "contract_valid": True},
            "silver_evaluation": {},
            "model_metrics": {"cascade_model_call_count": 1},
            "latency_breakdown_ms": {"generation_pipeline_ms": 120.0},
        },
    ]
    values = summarize(rows, queries, config)["methods"]["M"]
    assert values["silver_citation_precision_macro_answered"] == 1.0
    assert values["silver_citation_f1_macro_answerable"] == 0.5
    assert values["answerable_answer_rate"] == 1.0
    assert values["unanswerable_abstention_rate"] == 1.0
    assert values["model_calls_mean"] == 1.0
    assert values["generation_pipeline_ms_p95"] == 119.0
