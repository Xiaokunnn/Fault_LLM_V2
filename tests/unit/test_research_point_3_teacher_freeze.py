from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest
import src.research_point_3.teacher_freeze as teacher_freeze_module

from src.research_point_3.artifacts import (
    canonical_json_bytes,
    normalized_text_sha256,
)
from src.research_point_3.contracts import ContractError
from src.research_point_3.teacher_freeze import (
    CANONICAL_GRAPH_ROOT,
    CANONICAL_REQUIRED_MODEL_PATHS,
    CANONICAL_RP2_CONFIG_PATH,
    CANONICAL_RP2_PAPER_FREEZE_PATH,
    CANONICAL_RP2_REPLAY_MANIFEST_PATH,
    CANONICAL_RP2_REPLAY_PATH,
    CANONICAL_TOP32_TRACE_MANIFEST_PATH,
    CANONICAL_TOP32_TRACE_PATH,
    CANONICAL_VECTOR_INDEX_DIR,
    DEFAULT_GRAPH_COUNTS,
    audit_teacher_freeze,
    freeze_teacher_manifest,
)


def _jsonl(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps({"id": index}) + "\n" for index in range(count)),
        encoding="utf-8",
    )


def _at(root: Path, relative: str) -> Path:
    return root / Path(relative)


def _config() -> dict:
    return {
        "schema": "rp3_teacher_graph_freeze_config_v1",
        "teacher_graph_id": "TeacherGraph_RP3_v1",
        "terminology_tier": "strict_208",
        "graph_root": CANONICAL_GRAPH_ROOT,
        "vector_index_dir": CANONICAL_VECTOR_INDEX_DIR,
        "rp2_replay_path": CANONICAL_RP2_REPLAY_PATH,
        "rp2_replay_manifest_path": CANONICAL_RP2_REPLAY_MANIFEST_PATH,
        "rp2_config_path": CANONICAL_RP2_CONFIG_PATH,
        "rp2_paper_freeze_path": CANONICAL_RP2_PAPER_FREEZE_PATH,
        "required_model_paths": list(CANONICAL_REQUIRED_MODEL_PATHS),
        "expected_counts": dict(DEFAULT_GRAPH_COUNTS),
        "required_replay": {
            "query_count": 40,
            "teacher_method": "Ours_v6_k3_equal",
            "total_record_count": 200,
            "method_count": 5,
            "require_exact_replay_identity": True,
        },
        "required_training_bundle": {
            "trace_dir": "data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/training",
            "memory_dir": "data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory/training",
            "trace_count": 40,
            "base_perturbation_id": "original",
            "required_card_roles": [
                "symptom",
                "cause_or_mechanism",
                "inspection",
                "maintenance",
            ],
            "require_route_closure": True,
        },
        "required_teacher_trace": {
            "data_path": CANONICAL_TOP32_TRACE_PATH,
            "manifest_path": CANONICAL_TOP32_TRACE_MANIFEST_PATH,
            "base_query_count": 40,
            "base_perturbation_id": "original",
            "candidates_per_query": 32,
            "candidate_count_policy": "exact",
            "require_complete_top32": True,
            "maximum_selected": 3,
            "teacher_method": "Ours_v6_k3_equal",
            "strict_evidence_count": 208,
            "required_validation_flags": [
                "unique_base_query_ids",
                "base_queries_only",
                "teacher_method_consistent",
                "candidate_width_valid",
                "candidate_ids_unique_within_query",
                "complete_teacher_decisions",
                "strict_evidence_id_closure",
                "query_set_matches_replay",
            ],
        },
        "human_expert_reviewed": False,
    }


def _complete(root: Path) -> None:
    graph_root = _at(root, CANONICAL_GRAPH_ROOT)
    for filename, count in {
        "claims.jsonl": DEFAULT_GRAPH_COUNTS["claims"],
        "entities.jsonl": DEFAULT_GRAPH_COUNTS["entities"],
        "claim_evidence_links.jsonl": DEFAULT_GRAPH_COUNTS["claim_evidence_links"],
        "source_records.jsonl": DEFAULT_GRAPH_COUNTS["source_records"],
    }.items():
        _jsonl(graph_root / filename, count)
    evidence_path = graph_root / "evidence_assertions.jsonl"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        "".join(
            json.dumps({"evidence_id": f"E{index:03d}"}) + "\n"
            for index in range(DEFAULT_GRAPH_COUNTS["evidence_assertions"])
        ),
        encoding="utf-8",
    )
    replay_path = _at(root, CANONICAL_RP2_REPLAY_PATH)
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    methods = (
        "B1_dense_k3_equal",
        "B4_role_k3_equal",
        "A2_role_graph_k3_equal",
        "Ours_v6_k3_equal",
        "B1_dense_k4_secondary",
    )
    replay_path.write_text(
        "".join(
            json.dumps(
                {
                    "query_id": f"Q{query_index:02d}",
                    "method": method,
                    "ranked": [],
                }
            )
            + "\n"
            for method in methods
            for query_index in range(40)
        ),
        encoding="utf-8",
    )
    replay_hash = normalized_text_sha256(replay_path)
    replay_manifest = {
        "replay_artifact": {"sha256": replay_hash},
        "validation": {
            "records": 200,
            "methods": 5,
            "queries_per_method": 40,
            "identical_query_id_sets": True,
            "source_method_mapping_valid": True,
            "candidate_budget_upper_bounds_valid": True,
        },
        "method_mappings": [
            {
                "id": method,
                "query_count": 40,
                "candidate_budget": 4 if method == "B1_dense_k4_secondary" else 3,
            }
            for method in methods
        ],
    }
    replay_manifest_path = _at(root, CANONICAL_RP2_REPLAY_MANIFEST_PATH)
    replay_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    replay_manifest_path.write_text(
        json.dumps(replay_manifest) + "\n", encoding="utf-8"
    )
    rp2_config_path = _at(root, CANONICAL_RP2_CONFIG_PATH)
    rp2_config_path.parent.mkdir(parents=True, exist_ok=True)
    rp2_config_path.write_text(
        json.dumps(
            {
                "protocol_id": "marine_pump_rp2_graphrag_v6_equal_budget",
                "graph_root": CANONICAL_GRAPH_ROOT,
                "frozen_retrieval_results": CANONICAL_RP2_REPLAY_PATH,
                "frozen_retrieval_manifest": CANONICAL_RP2_REPLAY_MANIFEST_PATH,
                "embedding": {
                    "model_path": CANONICAL_REQUIRED_MODEL_PATHS[0],
                    "index_dir": CANONICAL_VECTOR_INDEX_DIR,
                    "normalize_embeddings": True,
                },
                "generator": {"model_path": CANONICAL_REQUIRED_MODEL_PATHS[1]},
                "retrieval": {
                    "dense_top_n": 32,
                    "max_scored_candidates": 32,
                    "ours_graph_hops": 1,
                },
                "generation_contract": {"max_answer_points": 3},
                "cascade": {"decision_policy": "single_run"},
                "replay_preparation": {
                    "expected_query_count": 40,
                    "method_mappings": [
                        {
                            "id": "Ours_v6_k3_equal",
                            "source_method": "Ours_v4_k3",
                            "retrieval_method": "dense_ours_v4",
                            "candidate_budget": 3,
                        }
                    ],
                },
                "primary_comparison": {
                    "evidence_budget": 3,
                    "methods": ["Ours_v6_k3_equal"],
                },
                "anti_leakage": {
                    "frozen_retrieval_reused_without_reranking": True
                },
                "scenarios": [
                    {
                        "id": "Ours_v6_k3_equal",
                        "retrieval_method": "dense_ours_v4",
                        "max_selected_evidence": 3,
                        "components": {
                            "role_filter": True,
                            "graph_expansion": True,
                            "fault_affinity": True,
                            "source_family_novelty": True,
                            "source_family_cap_active_at_k3": False,
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    frozen = {
        "freeze_id": "marine_pump_rp2_v6_paper_evidence_freeze_v1",
        "status": "frozen_for_short_paper_drafting",
        "human_expert_reviewed": False,
        "artifacts": [
            {
                "path": relative,
                "sha256": normalized_text_sha256(_at(root, relative)),
            }
            for relative in (
                CANONICAL_RP2_CONFIG_PATH,
                CANONICAL_RP2_REPLAY_MANIFEST_PATH,
            )
        ]
    }
    paper_freeze_path = _at(root, CANONICAL_RP2_PAPER_FREEZE_PATH)
    paper_freeze_path.parent.mkdir(parents=True, exist_ok=True)
    paper_freeze_path.write_text(
        json.dumps(frozen) + "\n", encoding="utf-8"
    )
    paper_hash = normalized_text_sha256(paper_freeze_path)
    teacher_freeze_module.RP2_PAPER_FREEZE_RAW_SHA256 = hashlib.sha256(paper_freeze_path.read_bytes()).hexdigest()
    teacher_freeze_module.RP2_PAPER_FREEZE_NORMALIZED_SHA256 = paper_hash
    for path in (
        _at(root, CANONICAL_VECTOR_INDEX_DIR) / "index.bin",
        _at(root, CANONICAL_REQUIRED_MODEL_PATHS[0]) / "weights.bin",
        _at(root, CANONICAL_REQUIRED_MODEL_PATHS[1]) / "weights.bin",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    _write_complete_trace(root)


def _write_complete_trace(root: Path) -> None:
    trace_path = _at(root, CANONICAL_TOP32_TRACE_PATH)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "".join(
            json.dumps(
            {
                "query_id": f"Q{query_index:02d}",
                "teacher_method": "Ours_v6_k3_equal",
                "perturbation_id": "original",
                "candidates": [
                    {
                        "evidence_id": f"E{index:03d}",
                        "score": 1.0 - index / 100,
                        "available": True,
                    }
                    for index in range(32)
                ],
                "final_support_by_evidence_id": {
                    "E000": "direct",
                    "E001": "irrelevant",
                },
                "selected_evidence_ids": ["E000"],
                "underfill_reason_codes": ["only_one_direct_support"],
            })
            + "\n"
            for query_index in range(40)
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema": "rp3_teacher_candidate_trace_manifest_v1",
        "trace_schema": "rp3_teacher_candidate_trace_v1",
        "data_artifact": {
            "path": CANONICAL_TOP32_TRACE_PATH,
            "sha256": normalized_text_sha256(trace_path),
        },
        "teacher_graph": {
            "id": "TeacherGraph_RP3_v1",
            "terminology_tier": "strict_208",
            "evidence_count": 208,
            "evidence_assertions_sha256": normalized_text_sha256(
                _at(root, CANONICAL_GRAPH_ROOT) / "evidence_assertions.jsonl"
            ),
        },
        "rp2_replay_sha256": normalized_text_sha256(
            _at(root, CANONICAL_RP2_REPLAY_PATH)
        ),
        "teacher_method": "Ours_v6_k3_equal",
        "base_query_count": 40,
        "candidates_per_query": 32,
        "candidate_count_policy": "exact",
        "maximum_selected": 3,
        "validation": {
            "unique_base_query_ids": True,
            "base_queries_only": True,
            "teacher_method_consistent": True,
            "candidate_width_valid": True,
            "candidate_ids_unique_within_query": True,
            "complete_teacher_decisions": True,
            "strict_evidence_id_closure": True,
            "query_set_matches_replay": True,
        },
    }
    manifest["logical_sha256"] = hashlib.sha256(
        canonical_json_bytes(manifest, newline=False)
    ).hexdigest()
    manifest_path = _at(root, CANONICAL_TOP32_TRACE_MANIFEST_PATH)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(canonical_json_bytes(manifest))


def test_missing_index_blocks_teacher_freeze(tmp_path: Path, monkeypatch) -> None:
    _complete(tmp_path)
    (_at(tmp_path, CANONICAL_VECTOR_INDEX_DIR) / "index.bin").unlink()
    calls = []
    original = teacher_freeze_module._directory_inventory
    monkeypatch.setattr(
        teacher_freeze_module,
        "_directory_inventory",
        lambda *args, **kwargs: calls.append(args) or original(*args, **kwargs),
    )
    audit = audit_teacher_freeze(tmp_path, _config())
    assert audit.ready is False
    assert audit.teacher_system_ready is False
    assert calls == []
    assert audit.manifest["vector_index"]["inventory"]["status"] == (
        "skipped_due_to_failed_teacher_prerequisite"
    )
    with pytest.raises(ContractError, match="not ready"):
        freeze_teacher_manifest(tmp_path / "freeze.json", audit)


def test_teacher_and_candidate_ready_wait_for_final_training_bundle(
    tmp_path: Path,
) -> None:
    _complete(tmp_path)
    audit = audit_teacher_freeze(tmp_path, _config())
    assert audit.ready is False
    assert audit.teacher_system_ready is True
    assert audit.distillation_trace_ready is True
    assert audit.final_training_bundle_ready is False
    assert len(audit.manifest["immutable_graph_logical_sha256"]) == 64
    assert len(audit.manifest["teacher_system_identity_sha256"]) == 64
    assert len(audit.manifest["freeze_manifest_logical_sha256"]) == 64


def test_teacher_system_ready_but_missing_top32_trace_blocks_distillation(
    tmp_path: Path,
) -> None:
    _complete(tmp_path)
    _at(tmp_path, CANONICAL_TOP32_TRACE_PATH).unlink()
    _at(tmp_path, CANONICAL_TOP32_TRACE_MANIFEST_PATH).unlink()
    audit = audit_teacher_freeze(tmp_path, _config())
    assert audit.teacher_system_ready is True
    assert audit.distillation_trace_ready is False
    assert audit.ready is False
    assert audit.manifest["teacher_system_status"] == "ready_to_freeze"
    assert audit.manifest["distillation_trace_status"] == "blocked"
    assert any("full teacher trace data missing" in item for item in audit.blockers)


def test_trace_candidate_outside_strict208_blocks_freeze(tmp_path: Path) -> None:
    _complete(tmp_path)
    trace_path = _at(tmp_path, CANONICAL_TOP32_TRACE_PATH)
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["candidates"][1]["evidence_id"] = "NOT-IN-STRICT-GRAPH"
    rows[0]["final_support_by_evidence_id"] = {
        "E000": "direct",
        "NOT-IN-STRICT-GRAPH": "irrelevant",
    }
    trace_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    manifest_path = _at(tmp_path, CANONICAL_TOP32_TRACE_MANIFEST_PATH)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_artifact"]["sha256"] = normalized_text_sha256(trace_path)
    manifest.pop("logical_sha256")
    manifest["logical_sha256"] = hashlib.sha256(
        canonical_json_bytes(manifest, newline=False)
    ).hexdigest()
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    audit = audit_teacher_freeze(tmp_path, _config())
    assert audit.teacher_system_ready is True
    assert audit.distillation_trace_ready is False
    assert any("outside=1" in item for item in audit.distillation_trace_blockers)


def test_teacher_freeze_rejects_a_different_main_id(tmp_path: Path) -> None:
    config = _config()
    config["teacher_graph_id"] = "TeacherGraph_620"
    with pytest.raises(ContractError, match="immutable"):
        audit_teacher_freeze(tmp_path, config)


def test_teacher_freeze_rejects_fake_exact_rank_claim(tmp_path: Path) -> None:
    config = _config()
    config["required_replay"].pop("require_exact_replay_identity")
    config["required_replay"]["require_exact_rank_match"] = True
    with pytest.raises(ContractError, match="require_exact_rank_match is forbidden"):
        audit_teacher_freeze(tmp_path, config)
