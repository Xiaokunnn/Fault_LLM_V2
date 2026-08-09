from __future__ import annotations

from scripts.summarize_rp2_equal_budget_v6 import (
    _cluster_bootstrap,
    _paired_cluster_bootstrap,
    _partition_table_specs,
    _query_record,
    summarize,
)


def test_protocol_specific_main_group_is_not_treated_as_cross_budget() -> None:
    specs = [
        {"id": "full", "group": "paired_graph_attribution"},
        {"id": "no_graph", "group": "paired_graph_attribution"},
        {"id": "dense_k4", "group": "cross_budget_secondary"},
    ]
    main, secondary = _partition_table_specs(specs)
    assert [spec["id"] for spec in main] == ["full", "no_graph"]
    assert [spec["id"] for spec in secondary] == ["dense_k4"]


def _generation(query_id: str, *, status: str, citations: list[str]) -> dict:
    return {
        "query_id": query_id,
        "method": "B1_dense_k3_equal",
        "quality_fusion": "none",
        "canonical_quality_repeat": 0,
        "answer": {
            "status": status,
            "answer_points": [
                {"text": "point", "evidence_ids": citations}
            ] if citations else [],
        },
        "validation": {"status": status, "contract_valid": True},
        "measurement_repeats": [
            {
                "repeat": repeat,
                "model_call_count": 1,
                "latency_breakdown_ms": {
                    "retrieval_ms": 10 + repeat,
                    "prompt_build_ms": 2,
                    "stage1_verifier_ms": 100 + 10 * repeat,
                    "stage2_review_ms": 20,
                    "render_ms": 1,
                    "end_to_end_ms": 133 + 11 * repeat,
                },
            }
            for repeat in range(3)
        ],
        "model_metrics": {
            "model_call_count": 1,
            "prompt_tokens": 100,
            "generated_tokens": 5,
        },
    }


def test_query_record_computes_silver_citation_and_median_latency() -> None:
    query = {
        "query_id": "Q-F1-A",
        "fault_id": "F1",
        "role": "symptom",
        "relevant_evidence_ids": ["E1", "E2"],
    }
    retrieval = {
        "query_id": "Q-F1-A",
        "method": "B1_dense_k3_equal",
        "ranked": [{"evidence_id": "E1"}, {"evidence_id": "X"}],
    }
    row = _query_record(
        query,
        retrieval,
        _generation("Q-F1-A", status="answered", citations=["E1", "X"]),
        {0: 10.0, 1: 11.0, 2: 12.0},
    )
    assert row["retrieval_recall"] == 0.5
    assert row["citation_precision"] == 0.5
    assert row["citation_recall"] == 0.5
    assert row["citation_f1"] == 0.5
    assert row["latency_ms"]["stage1_verifier"] == 110.0
    assert row["latency_ms"]["end_to_end"] == 144.0


def test_summary_reports_answer_and_abstention_precision_recall() -> None:
    queries = [
        {"query_id": "Q1", "fault_id": "F1", "relevant_evidence_ids": ["E1"]},
        {"query_id": "Q2", "fault_id": "F1", "relevant_evidence_ids": []},
        {"query_id": "Q3", "fault_id": "F2", "relevant_evidence_ids": ["E3"]},
        {"query_id": "Q4", "fault_id": "F2", "relevant_evidence_ids": []},
    ]
    retrieval = [
        {
            "query_id": query["query_id"],
            "method": "B1_dense_k3_equal",
            "ranked": [{"evidence_id": "E1"}],
        }
        for query in queries
    ]
    generations = [
        _generation("Q1", status="answered", citations=["E1"]),
        _generation("Q2", status="insufficient_evidence", citations=[]),
        _generation("Q3", status="insufficient_evidence", citations=[]),
        _generation("Q4", status="answered", citations=["X"]),
    ]
    report = summarize(
        queries=queries,
        retrieval_rows=retrieval,
        generation_rows=generations,
        retrieval_latency_rows=[
            {
                "repeat": repeat,
                "method": "B1_dense_k3_equal",
                "query_id": query["query_id"],
                "retrieval_ms": 10 + repeat,
                "ranking_matches_immutable_replay": True,
            }
            for query in queries
            for repeat in range(3)
        ],
        bootstrap_replicates=50,
        seed=7,
        confidence=0.95,
    )
    metrics = report["methods"]["B1_dense_k3_equal"]
    assert metrics["answer_precision"] == 0.5
    assert metrics["answer_recall"] == 0.5
    assert metrics["abstention_precision"] == 0.5
    assert metrics["abstention_recall"] == 0.5
    assert metrics["citation_f1_macro"] == 0.5
    assert report["bootstrap"]["intervals"]["B1_dense_k3_equal"]


def test_missing_fresh_retrieval_never_falls_back_to_archived_latency() -> None:
    query = {"query_id": "Q1", "fault_id": "F1", "relevant_evidence_ids": ["E1"]}
    retrieval = {
        "query_id": "Q1",
        "method": "B1_dense_k3_equal",
        "ranked": [{"evidence_id": "E1"}],
        "elapsed_ms": 9999.0,
    }
    generation = _generation("Q1", status="answered", citations=["E1"])
    generation["retrieval_elapsed_ms"] = 9999.0
    report = summarize(
        queries=[query],
        retrieval_rows=[retrieval],
        generation_rows=[generation],
        retrieval_latency_rows=[],
        bootstrap_replicates=0,
        seed=7,
        confidence=0.95,
    )
    metrics = report["methods"]["B1_dense_k3_equal"]
    assert metrics["latency"]["retrieval"]["samples"] == 0
    assert metrics["latency"]["end_to_end"]["samples"] == 0
    assert metrics["latency"]["generation_pipeline"]["samples"] == 1
    assert any("E2E latency pending" in warning for warning in report["warnings"])


def test_cluster_bootstrap_is_deterministic_for_fixed_seed() -> None:
    records = {
        "B1_dense_k3_equal": [
            {
                "fault_id": "F1",
                "answerable": True,
                "valid_answer": True,
                "valid_abstention": False,
                "contract_valid": True,
                "retrieval_recall": 1.0,
                "retrieval_ndcg": 1.0,
                "citation_precision": 1.0,
                "citation_recall": 1.0,
                "citation_f1": 1.0,
                "model_calls": 1.0,
                "prompt_tokens": 10.0,
                "generated_tokens": 1.0,
                "latency_ms": {"end_to_end": 10.0},
            },
            {
                "fault_id": "F2",
                "answerable": True,
                "valid_answer": False,
                "valid_abstention": True,
                "contract_valid": True,
                "retrieval_recall": 0.0,
                "retrieval_ndcg": 0.0,
                "citation_precision": 0.0,
                "citation_recall": 0.0,
                "citation_f1": 0.0,
                "model_calls": 1.0,
                "prompt_tokens": 10.0,
                "generated_tokens": 1.0,
                "latency_ms": {"end_to_end": 20.0},
            },
        ]
    }
    first = _cluster_bootstrap(
        records, replicates=100, seed=20260808, confidence=0.95
    )
    second = _cluster_bootstrap(
        records, replicates=100, seed=20260808, confidence=0.95
    )
    assert first == second


def test_paired_cluster_bootstrap_reports_proposed_minus_reference() -> None:
    def row(fault_id: str, recall: float, latency: float) -> dict:
        return {
            "fault_id": fault_id,
            "answerable": True,
            "valid_answer": True,
            "valid_abstention": False,
            "contract_valid": True,
            "retrieval_recall": recall,
            "retrieval_ndcg": recall,
            "citation_precision": recall,
            "citation_recall": recall,
            "citation_f1": recall,
            "model_calls": 1.0,
            "prompt_tokens": 10.0,
            "generated_tokens": 1.0,
            "latency_ms": {"end_to_end": latency},
        }

    records = {
        "reference": [row("F1", 0.2, 120.0), row("F2", 0.4, 100.0)],
        "proposed": [row("F1", 0.6, 90.0), row("F2", 0.8, 80.0)],
    }
    result = _paired_cluster_bootstrap(
        records,
        comparisons=(("ours", "reference", "proposed"),),
        replicates=100,
        seed=9,
        confidence=0.95,
    )["ours"]["metrics"]
    assert abs(
        result["retrieval_recall_macro"][
            "point_delta_proposed_minus_reference"
        ]
        - 0.4
    ) < 1e-12
    assert result["end_to_end_latency_ms_mean"][
        "point_delta_proposed_minus_reference"
    ] == -25.0
    assert result["retrieval_recall_macro"][
        "bootstrap_favorable_probability"
    ] == 1.0
    assert result["end_to_end_latency_ms_mean"][
        "bootstrap_favorable_probability"
    ] == 1.0
