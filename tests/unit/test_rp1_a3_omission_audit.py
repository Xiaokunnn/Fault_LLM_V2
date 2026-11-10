"""Contract checks for an AI audit, not tests of semantic judgment accuracy."""
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts/audit_rp1_a3_omissions.py"
spec = importlib.util.spec_from_file_location("rp1_a3_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_native_quote_offsets_survive_whitespace_and_casefold():
    page = {"page_text": "A Straße\n  causes noise.", "tables": []}
    hit = audit.evidence_locations(page, "STRASSE causes noise.")[0]
    assert page["page_text"][hit["start"]:hit["end"]] == hit["source_quote"]
    assert hit["source_quote"] == "Straße\n  causes noise."


def test_native_cells_are_addressed_without_inventing_cross_cell_quotes():
    page = {"page_text": "", "tables": [{"rows": [{"cells": [
        {"cell_id": "c1", "text": "wear"}, {"cell_id": "c2", "text": "replace bearing"}
    ]}]}]}
    assert audit.evidence_locations(page, "wear")[0]["unit_id"] == "c1"
    assert not audit.evidence_locations(page, "wear replace bearing")


def test_archive_records_cannot_be_overwritten(tmp_path):
    target = tmp_path / "frozen.json"
    audit.save(target, {"x": 1})
    audit.save(target, {"x": 1})
    with pytest.raises(ValueError, match="overwrite research record"):
        audit.save(target, {"x": 2})


@pytest.fixture
def bundle(tmp_path):
    ref = {"reference_id": "S01R01", "sample_id": "S01", "page_key": "MP021:p0015",
           "quotes": ["Air pockets make priming difficult."], "head": "air pockets",
           "relation": "causes", "tail": "priming difficulty"}
    packet = {"sample_id": "S01", "page_key": ref["page_key"], "batch": "freeform29",
              "records": [{"candidate_id": "c1", "section": "main", "payload": {},
                           "filters": {"historical_filter": False}}],
              "model_input": {"text": ref["quotes"][0]}, "latest_B0": [],
              "completed": {"returned_model": "fixture_not_experimental_model"}}

    def write(category="omitted", matches=None, **changes):
        comp = {"category": category, "matching_candidates": matches or [],
                "all_raw_sections_reviewed": True, "reason": "Fixture judgment only."}
        comp.update(changes)
        audit.save(tmp_path/"reference_specs.json", {"fixture": True})
        audit.save(tmp_path/"references.jsonl", [ref])
        audit.save(tmp_path/"source_only/sources.jsonl", [])
        audit.save(tmp_path/"private/raw_packets.jsonl", [packet])
        audit.save(tmp_path/"comparison_specs.json", {ref["reference_id"]: comp})
        audit.save(tmp_path/"reference_seal.json", {
            "spec_sha256": audit.digest((tmp_path/"reference_specs.json").read_bytes()),
            "reference_sha256": audit.digest((tmp_path/"references.jsonl").read_bytes())})
        audit.save(tmp_path/"input_manifest.json", {
            "source_sha256": audit.digest((tmp_path/"source_only/sources.jsonl").read_bytes()),
            "raw_packets_sha256": audit.digest((tmp_path/"private/raw_packets.jsonl").read_bytes())})
        return tmp_path
    return ref, packet, write


def test_omission_is_descriptive_not_population_recall(bundle):
    _, _, write = bundle
    out = write()
    audit.summarize(out)
    result = audit.load(out/"summary.json")
    assert result["strict_omissions"] == 1
    assert result["human_ground_truth"] is False
    assert result["population_recall_estimated"] is False
    assert result["statistical_significance_claim"] is False
    assert result["new_model_calls"] == 0


def test_menu_failure_cannot_be_called_clean_llm_omission(bundle):
    _, packet, write = bundle
    packet["batch"] = "menu10"
    with pytest.raises(ValueError, match="Menu constraints"):
        audit.summarize(write())


def test_missing_request_quote_cannot_be_called_llm_omission(bundle):
    _, packet, write = bundle
    packet["model_input"] = {"text": "Other source text."}
    with pytest.raises(ValueError, match="missing input"):
        audit.summarize(write())


def test_generated_match_cannot_be_counted_as_complete_omission(bundle):
    _, _, write = bundle
    with pytest.raises(ValueError, match="generated relation"):
        audit.summarize(write(matches=[{"candidate_id": "c1", "judgment": "partial", "reason": "Already generated."}]))


@pytest.mark.parametrize("category", ["present", "relation_error", "validation_rejection", "partial_expression", "auxiliary_or_channel"])
def test_nonmissing_categories_need_an_actual_candidate(bundle, category):
    _, _, write = bundle
    with pytest.raises(ValueError, match="actual generated item"):
        audit.summarize(write(category))


def test_rejecting_wrong_relation_is_not_a_verifier_false_rejection(bundle):
    _, _, write = bundle
    with pytest.raises(ValueError, match="complete raw relation"):
        audit.summarize(write("validation_rejection", [{"candidate_id": "c1", "judgment": "wrong_direction", "reason": "Wrong relation."}]))


def test_correct_relation_must_really_have_been_filtered(bundle):
    _, packet, write = bundle
    packet["records"][0]["filters"] = {"historical_filter": True}
    with pytest.raises(ValueError, match="actually filtered"):
        audit.summarize(write("validation_rejection", [{"candidate_id": "c1", "judgment": "complete", "reason": "Semantically correct fixture."}]))


def test_partial_raw_review_is_not_accepted(bundle):
    _, _, write = bundle
    with pytest.raises(ValueError, match="Incomplete raw review"):
        audit.summarize(write(all_raw_sections_reviewed=False))


def test_reference_mutation_is_detected(bundle):
    _, _, write = bundle
    out = write()
    with (out/"references.jsonl").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="Frozen audit input changed"):
        audit.summarize(out)


def test_candidate_id_must_exist(bundle):
    _, _, write = bundle
    with pytest.raises(ValueError, match="Unknown candidate"):
        audit.summarize(write("present", [{"candidate_id": "invented", "judgment": "complete", "reason": "Invalid fixture."}]))
