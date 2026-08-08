from __future__ import annotations

from scripts.build_rp2_v6_paraphrase_benchmark import build_paraphrases


def _query(query_id: str, role: str) -> dict:
    return {
        "query_id": query_id,
        "question_zh": "原始问法",
        "fault_id": "cavitation",
        "fault_name_zh": "汽蚀",
        "role": role,
        "relevant_evidence_ids": ["E1", "E2"],
        "candidate_evidence_ids": [],
        "label_status": "development_silver",
    }


def test_paraphrase_benchmark_changes_only_wording_and_query_id() -> None:
    source = [
        _query("Q-SYM", "symptom"),
        _query("Q-CAUSE", "cause_or_mechanism"),
        _query("Q-INS", "inspection"),
        _query("Q-MAINT", "maintenance"),
    ]
    output, mapping = build_paraphrases(source)

    assert len(output) == 8
    assert len(mapping) == 8
    assert {row["query_id"] for row in output} == {
        f"{row['query_id']}-P{variant}" for row in source for variant in (1, 2)
    }
    assert all(row["question_zh"] != "原始问法" for row in output)
    assert all(row["relevant_evidence_ids"] == ["E1", "E2"] for row in output)
    assert all(row["candidate_evidence_ids"] == [] for row in output)
    assert all(row["fault_id"] == "cavitation" for row in output)
    assert all(row["fault_name_zh"] == "汽蚀" for row in output)
    assert all(row["labels_copied_without_change"] for row in mapping)


def test_paraphrase_benchmark_rejects_unknown_role() -> None:
    try:
        build_paraphrases([_query("Q-BAD", "unknown")])
    except ValueError as exc:
        assert "Unsupported RP2 query role" in str(exc)
    else:
        raise AssertionError("Unknown roles must fail closed")
