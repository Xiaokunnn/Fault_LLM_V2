from __future__ import annotations

from scripts.run_rp2_dual_prompt_semantic_judge import _spans_verified, _summarize


def test_multispan_quote_verification_is_bound_to_each_evidence() -> None:
    item = {
        "cited_evidence": [
            {"evidence_id": "E1", "verbatim": "If cavitation occurs, inspect the suction line."},
            {"evidence_id": "E2", "verbatim": "Check | the inlet valve before starting."},
        ]
    }
    vote = {
        "evidence_spans": [
            {"evidence_id": "E1", "quote": "cavitation occurs"},
            {"evidence_id": "E2", "quote": "Check the inlet valve"},
        ]
    }
    verified, audit = _spans_verified(item, vote, minimum_chars=4)
    assert verified is True
    assert all(row["verified"] for row in audit)


def test_multispan_quote_verification_rejects_cross_evidence_splicing() -> None:
    item = {
        "cited_evidence": [
            {"evidence_id": "E1", "verbatim": "Inspect the suction line."},
            {"evidence_id": "E2", "verbatim": "Check the inlet valve."},
        ]
    }
    vote = {
        "evidence_spans": [
            {"evidence_id": "E1", "quote": "suction line Check the inlet"}
        ]
    }
    verified, audit = _spans_verified(item, vote, minimum_chars=4)
    assert verified is False
    assert audit[0]["verified"] is False


def test_v2_summary_separates_atomic_and_full_text_support() -> None:
    evidence = [{"evidence_id": "E1", "verbatim": "Cavitation causes noise."}]
    items = [
        {
            "item_id": "M::Q::point::0",
            "answer_id": "M::Q",
            "method": "M",
            "query_id": "Q",
            "item_kind": "answer_point",
            "cited_evidence": evidence,
        },
        {
            "item_id": "M::Q::summary",
            "answer_id": "M::Q",
            "method": "M",
            "query_id": "Q",
            "item_kind": "summary",
            "cited_evidence": evidence,
        },
    ]
    supported = {
        "verdict": "supported",
        "evidence_spans": [{"evidence_id": "E1", "quote": "Cavitation causes noise"}],
    }
    unsupported = {
        "verdict": "unsupported",
        "evidence_spans": [{"evidence_id": "E1", "quote": "Cavitation causes noise"}],
    }
    votes = {
        "M::Q::point::0": {"A": supported, "B": supported},
        "M::Q::summary": {"A": unsupported, "B": unsupported},
    }
    by_answer = {
        "M::Q": {
            "method": "M",
            "validation": {"status": "answered"},
        }
    }
    summary = _summarize(
        items,
        votes,
        by_answer,
        {
            "protocol_id": "test",
            "model": "test",
            "selected_methods": ["M"],
            "quote_protocol": "multi_span_v2",
            "minimum_quote_chars": 4,
        },
    )["methods"]["M"]
    assert summary["all_atomic_claims_strictly_supported_answer_rate"] == 1.0
    assert summary["all_text_strictly_supported_answer_rate"] == 0.0
