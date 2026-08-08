from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.prepare_rp2_v6_equal_budget_replay import (
    _verify_immutable,
    _write_immutable,
    build_replay,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _row(query_id: str, method: str, count: int) -> dict:
    ranked = [
        {
            "evidence_id": f"{method}-{query_id}-{index}",
            "score": 1.0 - index / 10,
            "source_family_id": "S",
            "claim_id": f"C-{index}",
            "role": "symptom",
            "fault_match": True,
            "role_match": True,
        }
        for index in range(count)
    ]
    return {
        "query_id": query_id,
        "method": method,
        "ranked": ranked,
        "elapsed_ms": 12.5,
        "selected_evidence": len(ranked),
    }


def _config(root: Path) -> tuple[dict, Path]:
    queries = root / "benchmark/queries.jsonl"
    _write_jsonl(queries, [{"query_id": "Q1"}, {"query_id": "Q2"}])
    source = root / "source.jsonl"
    _write_jsonl(source, [_row("Q1", "old", 3), _row("Q2", "old", 2)])
    config = {
        "protocol_id": "test-v6",
        "benchmark_dir": "benchmark",
        "frozen_retrieval_results": "out/replay.jsonl",
        "scenarios": [
            {
                "id": "new",
                "source_retrieval_method": "new",
                "retrieval_method": "dense_metapath",
                "max_selected_evidence": 3,
            }
        ],
        "replay_preparation": {
            "expected_query_count": 2,
            "method_mappings": [
                {
                    "id": "new",
                    "display_name": "Role K3",
                    "comparison_tier": "primary_equal_budget",
                    "source_file": "source.jsonl",
                    "source_method": "old",
                    "retrieval_method": "dense_metapath",
                    "candidate_budget": 3,
                }
            ],
        },
    }
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config, config_path


def test_build_replay_maps_methods_and_binds_sources(tmp_path: Path) -> None:
    config, config_path = _config(tmp_path)
    replay_bytes, manifest = build_replay(tmp_path, config, config_path)
    rows = [json.loads(line) for line in replay_bytes.decode("utf-8").splitlines()]

    assert [(row["query_id"], row["method"]) for row in rows] == [
        ("Q1", "new"),
        ("Q2", "new"),
    ]
    assert all(row["source_method"] == "old" for row in rows)
    assert all(row["replay_provenance"]["formal_v6_latency_eligible"] is False for row in rows)
    assert manifest["validation"]["identical_query_id_sets"] is True
    assert manifest["method_mappings"][0]["underfilled_query_count"] == 1
    assert manifest["replay_artifact"]["sha256"] == hashlib.sha256(replay_bytes).hexdigest()
    assert manifest["latency_policy"]["archived_elapsed_ms_formal_v6_eligible"] is False


def test_build_replay_rejects_budget_overflow(tmp_path: Path) -> None:
    config, config_path = _config(tmp_path)
    source = tmp_path / "source.jsonl"
    _write_jsonl(source, [_row("Q1", "old", 4), _row("Q2", "old", 2)])

    with pytest.raises(ValueError, match="budget=3"):
        build_replay(tmp_path, config, config_path)


def test_build_replay_rejects_query_set_mismatch(tmp_path: Path) -> None:
    config, config_path = _config(tmp_path)
    source = tmp_path / "source.jsonl"
    _write_jsonl(source, [_row("Q1", "old", 3), _row("Q3", "old", 2)])

    with pytest.raises(ValueError, match="query set mismatch"):
        build_replay(tmp_path, config, config_path)


def test_replay_identity_ignores_only_lf_crlf_materialization(tmp_path: Path) -> None:
    artifact = tmp_path / "replay.jsonl"
    artifact.write_bytes(b'{"query_id":"Q1"}\r\n{"query_id":"Q2"}\r\n')
    expected = b'{"query_id":"Q1"}\n{"query_id":"Q2"}\n'

    assert _write_immutable(artifact, expected) == "VERIFIED_EOL_NORMALIZED"
    assert _verify_immutable(artifact, expected) == "VERIFIED_EOL_NORMALIZED"


def test_replay_identity_still_rejects_real_content_change(tmp_path: Path) -> None:
    artifact = tmp_path / "replay.jsonl"
    artifact.write_bytes(b'{"query_id":"Q1"}\r\n')

    with pytest.raises(RuntimeError, match="first_difference=record 1") as error:
        _write_immutable(artifact, b'{"query_id":"Q9"}\n')
    assert "real content/provenance difference" in str(error.value)


def test_build_replay_is_identical_for_lf_and_crlf_inputs(tmp_path: Path) -> None:
    config, config_path = _config(tmp_path)
    queries = tmp_path / "benchmark/queries.jsonl"
    source = tmp_path / "source.jsonl"
    query_lf = queries.read_bytes().replace(b"\r\n", b"\n")
    source_lf = source.read_bytes().replace(b"\r\n", b"\n")
    config_lf = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    queries.write_bytes(query_lf.replace(b"\n", b"\r\n"))
    source.write_bytes(source_lf.replace(b"\n", b"\r\n"))
    config_path.write_bytes(config_lf.replace(b"\n", b"\r\n"))
    crlf_replay, crlf_manifest = build_replay(tmp_path, config, config_path)

    queries.write_bytes(query_lf)
    source.write_bytes(source_lf)
    config_path.write_bytes(config_lf)
    lf_replay, lf_manifest = build_replay(tmp_path, config, config_path)

    assert crlf_replay == lf_replay
    assert crlf_manifest == lf_manifest
