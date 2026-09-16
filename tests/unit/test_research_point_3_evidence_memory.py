from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research_point_3.contracts import ContractError
from src.research_point_3.evidence_memory import compile_evidence_memory


def _row(evidence_id: str = "E1") -> dict:
    return {
        "evidence_id": evidence_id,
        "claim_id": f"C-{evidence_id}",
        "head_canonical_zh": "汽蚀",
        "relation": "manifests_as",
        "tail_canonical_zh": "振动",
        "evidence_role": "symptom",
        "fault_class_ids": ["cavitation"],
        "evidence_text": "泵出现振动。",
        "doc_id": "MP001",
        "pdf_page_number": 2,
        "source_family_id": "SF1",
        "source_url": "https://example.invalid/manual.pdf",
        "decision": "silver_candidate",
        "eligible_for_chinese_graph": True,
        "inferred_edge": False,
        "final_confidence": 0.9,
    }


def _write(root: Path, rows: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "source_records.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_compile_memory_is_id_addressed_and_bucketed(tmp_path: Path) -> None:
    _write(tmp_path, [_row("E1"), _row("E2")])
    records, report = compile_evidence_memory(
        tmp_path, feature_vectors={"E1": [0.1, 0.2], "E2": [0.3, 0.4]}
    )
    assert [row.memory_index for row in records] == [0, 1]
    assert report.record_count == 2
    assert report.maximum_bucket_size == 2
    assert report.vector_dimension == 2


def test_compile_memory_rejects_non_build_or_unreleased_rows(tmp_path: Path) -> None:
    row = _row()
    row["doc_id"] = "MP009"
    _write(tmp_path, [row])
    with pytest.raises(ContractError, match="non-build"):
        compile_evidence_memory(tmp_path)


def test_compile_memory_requires_exact_vector_id_coverage(tmp_path: Path) -> None:
    _write(tmp_path, [_row()])
    with pytest.raises(ContractError, match="feature-vector IDs disagree"):
        compile_evidence_memory(tmp_path, feature_vectors={"UNKNOWN": [0.1]})


def test_compile_memory_preserves_non_card_context_without_mislabeling(
    tmp_path: Path,
) -> None:
    row = _row()
    row["evidence_role"] = "standard"
    row["relation"] = "specified_by"
    _write(tmp_path, [row])
    records, report = compile_evidence_memory(tmp_path)
    assert records[0].role.value == "context"
    assert records[0].metadata["card_selectable"] is False
    assert report.record_count == 1


def test_compile_memory_preserves_unscoped_rows_as_nonselectable(
    tmp_path: Path,
) -> None:
    row = _row()
    row["fault_class_ids"] = []
    _write(tmp_path, [row])
    records, _ = compile_evidence_memory(tmp_path)
    assert records[0].fault_class_ids == ("__unscoped_nonselectable__",)
    assert records[0].metadata["card_selectable"] is False


def test_compile_memory_rejects_string_booleans(tmp_path: Path) -> None:
    row = _row()
    row["eligible_for_chinese_graph"] = "true"
    _write(tmp_path, [row])
    with pytest.raises(ContractError, match="released"):
        compile_evidence_memory(tmp_path)
