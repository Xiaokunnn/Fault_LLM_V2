"""Test diagnostic controls and frozen outputs, not a KG enhancement model."""
import copy
from collections import Counter
from pathlib import Path

import pytest

import investigate as m
from deepen import alias_sensitivity, component_stats
from finalize_data import fraction
from verify_cases import bind_quote


RUN = m.TASK / "runs/20261113_v1"


def test_literal_quote_keeps_actual_whitespace_and_offsets():
    page = {"doc_id": "MP001", "pdf_page_number": 1, "page_text": "A\n  causes B."}
    actual = bind_quote(page, "A causes B.", lambda *_: pytest.fail("Unexpected fallback"))
    assert actual["text"] == "A\n  causes B."
    assert page["page_text"][actual["start"]:actual["end"]] == actual["text"]


def test_missing_quote_fails_instead_of_inventing_source():
    page = {"doc_id": "MP001", "pdf_page_number": 1, "page_text": "actual"}
    with pytest.raises(ValueError, match="not uniquely bound"):
        bind_quote(page, "invented", lambda *_: ([], {}))


def test_component_count_includes_isolates():
    result = component_stats({"a", "b", "c"}, [("a", "b")])
    assert result == dict(nodes=3, weak_components=2, largest_component=2, degree_one=2)


def test_alias_sensitivity_neither_writes_nor_invents_relations():
    graph = {"entities": [{"entity_id": i} for i in ["a", "b", "c", "d"]],
             "claims": [{"head_entity_id": "a", "relation": "causes", "tail_entity_id": "c"},
                        {"head_entity_id": "b", "relation": "causes", "tail_entity_id": "d"}]}
    before = copy.deepcopy(graph)
    result = alias_sensitivity(graph, [{"entity_ids": ["a", "b"]}])
    assert graph == before
    assert result["new_edges_inferred"] == 0 and not result["graph_written"]
    assert result["before"]["relations"] == result["hypothetical_exact_surface_alias_merge"]["relations"] == 2


def test_fraction_has_explicit_denominator_and_handles_empty_frame():
    assert fraction(3, 10, "proxy")["percentage"] == 30
    assert fraction(0, 0, "no frame")["percentage"] is None


def test_all_data_phase_seal_hashes_match():
    seal = m.read(RUN / "verification/data_phase_seal.json")
    assert seal["input_git_commit"] == m.REV
    assert seal["step4_literature_search_not_yet_started"]
    assert m.sha((m.TASK / "problem_register.json").read_bytes()) == seal["problem_register_sha256"]
    for relative, expected in seal["evidence_hashes"].items():
        assert m.sha((RUN / relative).read_bytes()) == expected


def test_only_build_documents_were_investigated():
    pages = m.read(RUN / "inventory/page_frame.jsonl")
    assert len(pages) == 1934 and {r["doc_id"] for r in pages} == m.BUILD
    assert len(m.read(RUN / "source_scan/source_only_probe_sample.jsonl")) == 48


def test_case_counts_do_not_assert_independence_or_gold():
    rows = m.read(RUN / "case_review/cases.jsonl")
    summary = m.read(RUN / "case_review/summary.json")
    assert len(rows) == summary["diagnostic_cases"] == 20
    assert dict(Counter(r["status"] for r in rows)) == summary["case_proposition_status_counts"]
    assert all(r["human_gold"] is False for r in rows)
    assert not summary["independent_reviewer_model_used"]
    assert summary["record_ids_are_not_independent_cases"]


def test_problem_register_has_eight_required_dimensions():
    register = m.read(m.TASK / "problem_register.json")
    required = {"definition", "metric", "evidence", "diagnosis_impact", "data_sufficiency",
                "engineering", "algorithm_research", "evaluation_boundary"}
    assert len(register["problems"]) == 10
    assert all(required <= set(r) for r in register["problems"])
    assert not register["independent_ground_truth"]
    assert register["new_model_calls"] == register["formal_graph_modifications"] == 0


def test_graphml_and_source_pdf_preservation_controls():
    assert all(r["jsonl_topology_consistent"] for r in m.read(RUN / "verification/graphml_consistency.jsonl"))
    rows = m.read(RUN / "verification/source_preservation.jsonl")
    assert len(rows) == 15
    for row in rows:
        assert row["preserved"] and m.sha((m.ROOT / row["path"]).read_bytes()) == row["sha256"]


def test_data_phase_decision_does_not_choose_an_architecture():
    decision = m.read(m.TASK / "decision_before_literature.json")
    assert decision["status"] == "INCONCLUSIVE"
    assert decision["prespecified_B0_B1_B2_B3_cancelled"]
    assert not decision["algorithm_architecture_selected"]
    assert not decision["beyond_simple_rules_demonstrated"]
    assert decision["no_new_algorithm_implemented"]
