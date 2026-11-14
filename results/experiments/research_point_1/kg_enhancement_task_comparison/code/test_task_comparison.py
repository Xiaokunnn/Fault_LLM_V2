"""Research-contract tests: one base KG, traceability, units and honest limits."""
import copy
import json
from pathlib import Path

import pytest

import inputs as i
from evaluate_review import EVAL, prove_query
from run_baselines import OUT, read, cue_spans, morphology, sample_strata
from run_controls import clause_proposals, normalized_clause_proposals
from run_control_policies import cell_body, policy


def test_inputs_allow_only_the_declared_graph():
    graph_paths=[p for p in i.ALLOWED if "/versions/" in p or "/triples/" in p or "/graph_versions/" in p]
    assert graph_paths and all(p.startswith(i.GRAPH) for p in graph_paths)


def test_unknown_graph_input_is_blocked_before_git(monkeypatch):
    monkeypatch.setattr(i.subprocess,"check_output",lambda *a,**k:pytest.fail("Forbidden input reached Git"))
    with pytest.raises(ValueError,match="not permitted"):
        i.Inputs().raw("data/kg/marine_pump/unapproved_graph/claims.jsonl")


def test_only_build_source_pages_are_allowed():
    assert len(i.BUILD)==15 and len(i.PAGES)==15
    assert not ({"MP008","MP009","MP010","MP011","MP012","MP013","MP014"}&i.BUILD)


def test_normalization_does_not_remove_models_units_or_negation():
    assert i.norm(" ＬＫＨ 40 must NOT run at 20 Nm ")=="lkh 40 must not run at 20 nm"
    assert i.norm("may run")!=i.norm("must not run")


def test_same_core_is_not_same_condition():
    base=dict(head_type="Component",head_canonical_zh="轴承",relation="maintained_by",tail_type="MaintenanceAction",tail_canonical_zh="更换",conditions=["ATEX"])
    assert i.core_tuple(base)==i.core_tuple({**base,"conditions":["normal"]})
    assert i.source_identity({**base,"evidence_text":"A"})!=i.source_identity({**base,"evidence_text":"B"})


def test_lineage_retains_declared_parent_ids():
    row=dict(triple_id="new",legacy_triple_id="raw",expansion_parent_triple_id="audit",terminology_governance={"previous_ids":{"triple_id":"prior"}})
    assert set(i.record_ids(row))=={"new","raw","audit","prior"}
    links=i.IdLinks();links.add(i.record_ids(row))
    assert len({links.find(k) for k in i.record_ids(row)})==1


def test_source_fields_and_existing_bbox_are_not_rewritten():
    source=dict(triple_id="x",doc_id="MP001",pdf_page_number=1,evidence_text="do NOT",evidence_units=[{"cell_id":"c","bbox":[1,2,3,4]}])
    before=copy.deepcopy(source);pointer=i.source_pointer(source)
    assert source==before and pointer["evidence_units"]==source["evidence_units"]


def test_offsets_only_prove_location_not_entailment():
    row={"evidence_text":"A causes B","evidence_start":0,"evidence_end":10,"document_sha256":"d","page_text_sha256":"p"}
    page={"page_text":"A causes B","document_sha256":"d","page_text_sha256":"p"}
    result=i.address_check(row,page)
    assert result["exact_contiguous_offset"] and result["metadata_hashes_match"]
    assert not result["semantic_entailment_established"]


def test_bad_or_invented_address_is_not_repaired():
    result=i.address_check({"evidence_text":"missing","evidence_start":0,"evidence_end":7},{"page_text":"actual"})
    assert not result["exact_contiguous_offset"] and not result["all_provided_cells_match"]


def test_immutable_outputs_and_directory_guard(tmp_path,monkeypatch):
    monkeypatch.setattr(i,"TASK",tmp_path)
    path=tmp_path/"ok.json";i.save(path,{"a":1});i.save(path,{"a":1})
    with pytest.raises(ValueError,match="Immutable"):i.save(path,{"a":2})
    with pytest.raises(ValueError,match="escaped"):i.save(tmp_path.parent/"outside.json",{})


def test_morphology_is_a_probe_not_chinese_semantic_merging():
    assert morphology("pump and motor shafts")==morphology("pump and motor shaft")
    assert morphology("安全阀动作")!=morphology("溢流阀动作")


def test_prohibition_cue_does_not_erase_original_negation():
    text="Do not operate without liquid."
    spans=cue_spans(text)
    assert any(s["kind"]=="prohibition" for s in spans)
    assert all(text[s["start"]:s["end"]]==s["text"] for s in spans)


def test_strong_clauses_fix_layout_breaks_without_losing_offsets():
    text="Use shims when the\n     installation is secured."
    assert clause_proposals(text)[0]["text"]=="when the"
    strong=normalized_clause_proposals(text)[0]
    assert strong["normalized_text"]=="when the installation is secured"
    assert strong["source_roundtrip"] and text[strong["original_start"]:strong["original_end"]]==strong["original_text"]


def test_strong_clauses_keep_decimal_and_section_reference():
    text="It must be reassembled 10 times and then tested under 4-6-2/5.9.2(e).i."
    assert "4-6-2/5.9.2(e).i" in normalized_clause_proposals(text)[0]["normalized_text"]


def test_header_is_not_relation_verb_or_part_of_endpoint():
    field={"text":"CAUSES\nPump not properly primed","column_name":"CAUSES"}
    assert cell_body(field)=="pump not properly primed"
    assert field["text"].startswith("CAUSES")


def test_native_quote_proof_retains_available_geometry_only():
    page={"doc_id":"MP001","pdf_page_number":1,"page_text":"","text_blocks":[{"block_id":"b","text":"may run","bbox":[1,2,3,4]}]}
    result=prove_query(page,"may run")
    assert result["witnesses"][0]["unit_id"]=="b"
    assert result["witnesses"][0]["bbox"]==[1,2,3,4]


def test_unlocatable_quote_fails_closed():
    with pytest.raises(ValueError,match="No source witness"):
        prove_query({"doc_id":"MP001","pdf_page_number":1,"page_text":"actual"},"invented")


def test_primary_samples_stayed_fixed():
    assert all(len(read(OUT/f"review/{t}_sample.jsonl"))==12 for t in "ABCDE")
    manifest=read(OUT/"baselines/input_manifest.json")
    assert manifest["sampling_seed"]=="rp1-task-comparison-v1-20261113" and manifest["no_other_graph_loaded"]


def test_occurrence_counts_are_not_deduplicated_fact_counts():
    summary=read(OUT/"mapping/summary.json")
    assert summary["raw_candidate_occurrences"]==8007 and summary["unique_raw_record_ids"]==8004
    assert sum(summary["raw_occurrence_categories"].values())==8007
    assert summary["normalized_candidate_core_groups"]==7588
    assert summary["source_semantically_supported_fact_count"] is None


def test_orphan_cache_entries_are_exposed_not_synthesized():
    rows=read(OUT/"mapping/audit_only_orphans.jsonl")
    assert len(rows)==12 and sum(bool(r["current_assertion_ids"]) for r in rows)==11
    assert all(r["count_as_extra_raw_occurrence"] is False for r in rows)


def test_primary_and_supplementary_overlap_is_not_counted_twice():
    rows=read(EVAL/"cases.jsonl")
    assert len(rows)==67 and len({r["id"] for r in rows})==66
    b=[r for r in rows if r["task"].startswith("B")]
    assert len(b)==15 and len({r["id"] for r in b})==14
    assert len({r["id"] for r in rows if r["task"].startswith("D")})==16


def test_four_status_counts_have_explicit_denominators():
    summary=read(EVAL/"summary.json")
    for task,stats in summary["task_statistics"].items():
        assert sum(stats["support_status_counts"].values())==stats["checked_task_items"]
        assert sum(stats["baseline_outcome_counts"].values())==stats["checked_task_items"]
        assert stats["counts_are_not_accuracy_or_prevalence"]


def test_source_first_selection_did_not_filter_by_graph_absence():
    selected=read(OUT/"source_first/selected_units.jsonl")
    assert len(selected)==30 and len({(r["doc_id"],r["pdf_page_number"]) for r in selected})==30
    assert {r["doc_id"] for r in selected}==i.BUILD
    assert any(r["current_assertion_ids_on_page"] for r in selected)


def test_source_omission_frames_keep_existing_knowledge_controls():
    rows=read(EVAL/"source_propositions.jsonl")
    assert len(rows)==10 and sum(not r["raw_frame_found"] for r in rows)==8
    assert any(r["raw_frame_found"] and r["current_frame_found"] for r in rows)
    assert all(r["bounded_review_not_global_absence_proof"] and not r["human_gold"] for r in rows)
    assert all(r["source_proofs"] for r in rows)


def test_heterogeneous_E_opportunities_are_not_called_facts():
    row=read(EVAL/"population_units.json")["E"]
    assert row["unified_core_groups"]==6762 and row["unique_source_first_probe_units"]==30
    assert row["heterogeneous_total_is_not_fact_count"]


def test_D_rules_preserve_uncertainty_and_do_not_reverse_normative_causes():
    rows=read(OUT/"controls/bounded_action_proposals_v2.jsonl")
    byid={r["opportunity_id"]:r["proposal"] for r in rows}
    assert byid["D-EXA-26ad2e25ba5d1b68e46c28b6"]["do_not_infer_opposite_physical_cause"]
    assert byid["D-EXA-3c06f91ad198d5f65d435522"]["action"]=="retain_native_role_direction"
    assert byid["D-EXA-0e3a98f3dbe8dd694efd4244"]["action"]=="retain_literal_negation_no_reversal"
    assert byid["D-EXA-fa8e9475fd494ec2e55ec00d"]["action"]=="defer_transferability"


def test_no_automatic_formal_graph_writes_or_unqualified_restoration():
    for row in read(OUT/"controls/bounded_action_proposals_v2.jsonl"):
        assert not row["proposal"]["automatic_graph_write"]
        assert row["proposal"].get("restore_as_qualified_fact") is not True


def test_AI_review_does_not_become_independent_gold():
    rows=read(EVAL/"cases.jsonl")
    assert all(not r["human_gold"] and not r["independent_review"] for r in rows)


def test_apparent_conflict_is_not_promoted_to_true_contradiction():
    row=read(EVAL/"supplementary_conflict_probe.json")
    assert row["result"]=="apparent_conflict_different_applicability"
    assert row["support"]=="insufficient_evidence"


def test_pinned_input_manifest_graph_scope():
    for relative in ["mapping/input_manifest.json","baselines/input_manifest.json","review/preparation_manifest.json","controls/manifest_v2.json","evaluation_v2/manifest.json"]:
        manifest=read(OUT/relative)
        assert manifest["input_git_commit"]==i.REV
        assert set(manifest["input_sha256"])<=i.ALLOWED


def test_original_pdf_hashes_preserved():
    rows=read(EVAL/"source_pdf_preservation.jsonl")
    assert len(rows)==15
    assert all(i.digest((i.ROOT/r["path"]).read_bytes())==r["sha256"] for r in rows)


def test_final_graph_only_id_check_passed():
    summary=read(EVAL/"summary.json")
    assert summary["sole_base_graph"]=="expanded1456" and summary["current_graph_ID_and_GraphML_consistency"]
    assert summary["model_calls"]==summary["formal_graph_modifications"]==0


def test_separate_raw_pool_screens_and_semantic_judgments():
    assert read(EVAL/"summary.json")["full_initial_pool_semantically_supported_fact_count"] is None
    rows=read(OUT/"mapping/raw_occurrence_mapping.jsonl")
    assert len(rows)==8007 and all(r["semantic_source_review_status"]=="not_reviewed_in_this_phase" for r in rows)


def test_dictionary_does_not_turn_language_repetition_into_independence():
    summary=read(OUT/"controls/dictionary_summary.json")
    assert summary["sole_base_graph"]=="expanded1456"
    assert summary["multi_evidence_claims"]==38 and summary["multi_source_family_claims"]==0
    assert summary["independent_truth_support_count"] is None
    assert all(not row["semantic_equivalence_certified"] for row in read(OUT/"controls/typed_dictionary.jsonl"))
