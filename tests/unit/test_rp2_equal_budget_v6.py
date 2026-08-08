from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.run_rp2_equal_budget_v6 import (  # noqa: E402
    _canonical_run,
    _checkpoint_key,
    _load_checkpoints,
    _median_measurement_summary,
    _repeat_latency_breakdown,
    _rotated,
    _run_measurement,
    _verification_mode,
)
from research_point_2.dataset import EvidenceCandidate, SilverQuery  # noqa: E402
from research_point_2.retrieval import RankedEvidence, RetrievalResult  # noqa: E402


def _measurement(repeat: int, final_mask: list[int], scale: float) -> dict:
    stage1 = {
        "prompt_build_ms": 1.0 * scale,
        "prompt_tokens": 100,
        "generated_tokens": 3,
        "input_preparation_ms": 2.0 * scale,
        "model_inference_ms": 10.0 * scale,
        "total_inference_ms": 12.0 * scale,
        "cuda_peak_memory_bytes": 20,
        "cuda_allocated_memory_bytes": 10,
        "model_output_valid_json": True,
    }
    stage2 = {
        "review_call_count": 2,
        "prompt_build_ms": 2.0 * scale,
        "prompt_tokens": 60,
        "generated_tokens": 4,
        "input_preparation_ms": 4.0 * scale,
        "model_inference_ms": 20.0 * scale,
        "total_inference_ms": 24.0 * scale,
        "cuda_peak_memory_bytes": 30,
        "cuda_allocated_memory_bytes": 15,
        "all_outputs_valid_json": True,
    }
    latency = _repeat_latency_breakdown(
        archived_retrieval_ms=5.0,
        stage1=stage1,
        stage2=stage2,
        render_ms=3.0 * scale,
    )
    return {
        "repeat": repeat,
        "final_mask": final_mask,
        "stage1": stage1,
        "stage2": stage2,
        "latency_breakdown_ms": latency,
        "model_call_count": 3,
    }


def test_v6_canonical_quality_uses_repeat_zero_without_majority_vote() -> None:
    runs = [
        _measurement(0, [1, 0, 0], 1.0),
        _measurement(1, [0, 1, 1], 2.0),
        _measurement(2, [0, 1, 1], 3.0),
    ]
    assert _canonical_run(runs)["final_mask"] == [1, 0, 0]
    with pytest.raises(RuntimeError):
        _canonical_run(runs[1:])


def test_v6_latency_summary_uses_median_repeats_but_not_quality_masks() -> None:
    runs = [
        _measurement(0, [1, 0, 0], 1.0),
        _measurement(1, [0, 1, 1], 2.0),
        _measurement(2, [1, 1, 1], 3.0),
    ]
    latency, model = _median_measurement_summary(runs)
    assert latency["stage1_ms"] == 24.0
    assert latency["stage2_ms"] == 48.0
    assert latency["generation_pipeline_ms"] == 84.0
    assert latency["end_to_end_inference_ms"] is None
    assert latency["retrieval_ms"] is None
    assert model["prompt_tokens"] == 160
    assert model["generated_tokens"] == 7
    assert model["cascade_model_call_count"] == 3
    assert model["quality_fusion"] == "none"


def test_v6_rotating_schedule_changes_order_without_changing_members() -> None:
    scenarios = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    assert [row["id"] for row in _rotated(scenarios, 0)] == ["A", "B", "C"]
    assert [row["id"] for row in _rotated(scenarios, 1)] == ["B", "C", "A"]
    assert [row["id"] for row in _rotated(scenarios, 2)] == ["C", "A", "B"]


def test_v6_resume_ignores_checkpoints_from_another_protocol(tmp_path: Path) -> None:
    path = tmp_path / "measurement_checkpoints.jsonl"
    rows = [
        {
            "protocol_fingerprint": "current",
            "repeat": 0,
            "method": "A",
            "query_id": "Q1",
        },
        {
            "protocol_fingerprint": "stale",
            "repeat": 1,
            "method": "A",
            "query_id": "Q1",
        },
    ]
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    loaded = _load_checkpoints(path, "current")
    assert list(loaded) == [(0, "A", "Q1")]
    assert _checkpoint_key(rows[0]) == (0, "A", "Q1")


def test_v6_verification_modes_default_to_full_cascade_and_fail_closed() -> None:
    assert _verification_mode({}) == "stage1_plus_review"
    assert _verification_mode({"verification_mode": "direct_render"}) == "direct_render"
    assert _verification_mode({"verification_mode": "stage1_only"}) == "stage1_only"
    with pytest.raises(ValueError):
        _verification_mode({"verification_mode": "majority_vote"})


def test_v6_direct_render_calls_no_model_and_excludes_archived_retrieval_latency(
    tmp_path: Path,
) -> None:
    evidence = EvidenceCandidate(
        evidence_id="E1",
        claim_id="C1",
        head_entity_id="F1",
        tail_entity_id="S1",
        head_label_zh="汽蚀",
        tail_label_zh="异常噪声",
        head_type="FaultMode",
        tail_type="Symptom",
        relation="manifests_as",
        role="symptom",
        fault_class_ids=("cavitation",),
        evidence_text="汽蚀会产生异常噪声。",
        source_family_id="SRC1",
        doc_id="MP001",
        pdf_page_number=7,
        source_url="https://example.com/manual.pdf",
        final_confidence=0.9,
        evidence_level="E1",
    )
    query = SilverQuery(
        "Q1", "汽蚀有哪些症状？", "cavitation", "汽蚀", "symptom", ("E1",)
    )
    retrieval = RetrievalResult(
        query_id="Q1",
        method="DenseK3",
        ranked=(
            RankedEvidence("E1", 0.9, "SRC1", "C1", "symptom", True, True),
        ),
        elapsed_ms=999.0,
        scored_candidates=1,
        selected_evidence=1,
        visited_evidence=1,
        visited_nodes=0,
        visited_edges=0,
        generation_mode="frozen",
        timed_out=False,
        early_stopped=False,
    )
    row = _run_measurement(
        repeat=0,
        method_order=["Direct"],
        scenario={
            "id": "Direct",
            "verification_mode": "direct_render",
            "minimum_visible_fault_affinity": 0.05,
        },
        query=query,
        retrieval=retrieval,
        evidence=[evidence],
        generator=object(),
        contract={
            "max_prompt_tokens": 1536,
            "max_answer_points": 3,
            "max_point_chars": 80,
            "max_summary_chars": 100,
        },
        stage1_system="unused",
        stage1_max_new_tokens=64,
        review_max_new_tokens=48,
        cache_dir=tmp_path,
        model_identity="unused",
        protocol_version="test",
        protocol_fingerprint="fingerprint",
        force_generation=False,
    )
    assert row["answer"]["status"] == "answered"
    assert row["model_call_count"] == 0
    assert row["stage1"]["source"] == "NO_CALL"
    assert row["latency_breakdown_ms"]["retrieval_ms"] is None
    assert row["latency_breakdown_ms"]["archived_retrieval_elapsed_ms"] == 999.0
    assert row["latency_breakdown_ms"]["end_to_end_inference_ms"] is None
