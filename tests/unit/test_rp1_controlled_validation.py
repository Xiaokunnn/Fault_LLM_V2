"""Pilot bookkeeping and fail-closed boundaries, using synthetic labels only."""
import copy
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_rp1_controlled_validation.py"
spec = importlib.util.spec_from_file_location("controlled_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def annotation_fixture():
    key = "MP001:p0001"
    text = "Low pressure causes cavitation."
    source = dict(page_key=key, target=dict(doc_id="MP001", pdf_page_number=1,
                  text_blocks=[dict(block_id=key+":b0", text=text)], tables=[]), context_pages=[])
    target = dict(reference_id="R1", head="Low pressure", head_type="Condition", relation="causes",
                  tail="cavitation", tail_type="Fault", conditions=[], modality="asserted", polarity="positive",
                  applicability="synthetic fixture", evidence=[dict(unit_id=key+":b0", quote=text)])
    row = dict(page_key=key, reviewer_kind="human", reviewer_id="synthetic-test-actor", coverage_complete=True,
               targets=[target], unresolved_notes=[], zero_target_reason="")
    registry = {"causes": dict(domain=["Condition"], range=["Fault"])}
    return source, row, registry


def test_reference_requires_human_and_complete_page():
    source, row, registry = annotation_fixture()
    assert len(pilot.validate_annotations([source], [row], registry)) == 1
    for change in [dict(reviewer_kind="AI"), dict(reviewer_id=""), dict(coverage_complete=False),
                   dict(unresolved_notes=["ambiguous condition"]), dict(targets=[]),
                   dict(targets=[row["targets"][0], row["targets"][0]])]:
        with pytest.raises(pilot.PilotError):
            pilot.validate_annotations([source], [{**row, **change}], registry)


def test_zero_target_page_has_no_perfect_recall():
    source, row, registry = annotation_fixture()
    row.update(targets=[], zero_target_reason="synthetic control")
    assert pilot.validate_annotations([source], [row], registry) == {}
    metrics, ledger = pilot.compute_metrics([], {}, {})
    assert metrics["stages"]["raw"]["recall"] is None
    assert ledger == []


@pytest.mark.parametrize("field,value", [("head_type", "Fault"), ("relation", "unknown"), ("conditions", None)])
def test_reference_cannot_silently_change_task(field, value):
    source, row, registry = annotation_fixture()
    row["targets"][0][field] = value
    with pytest.raises(pilot.PilotError):
        pilot.validate_annotations([source], [row], registry)


def test_reference_quote_roundtrip_and_context_boundary():
    source, row, registry = annotation_fixture()
    row["targets"][0]["evidence"][0]["quote"] = "invented source"
    with pytest.raises(pilot.PilotError):
        pilot.validate_annotations([source], [row], registry)
    source, row, registry = annotation_fixture()
    context = copy.deepcopy(source["target"])
    context.update(pdf_page_number=2)
    context["text_blocks"][0]["block_id"] = "MP001:p0002:b0"
    source["context_pages"] = [context]
    row["targets"][0]["evidence"][0]["unit_id"] = "MP001:p0002:b0"
    with pytest.raises(pilot.PilotError):
        pilot.validate_annotations([source], [row], registry)


def test_loss_positions_and_nonmonotone_latest_branch():
    targets = {f"R{i}": dict(page_key="P") for i in range(1, 8)}
    candidates, judgments = [], {}
    def add(cid, verdict, rid=None, related=(), kept=False, stage="raw"):
        candidates.append(dict(candidate_id=cid, page_key="P", stage=stage,
                               original_pipeline_kept=kept, latest_pipeline_kept=kept))
        judgments[cid] = dict(verdict=verdict, reference_id=rid, related_reference_ids=list(related))
    add("raw1", "complete", "R1", kept=False)
    add("raw2", "wrong_role", related=["R2"])
    add("raw3", "insufficient_evidence", related=["R3"])
    add("raw4", "partial_conditions", related=["R4"])
    add("raw5", "complete", "R5", kept=True)
    add("raw5duplicate", "complete", "R5", kept=True)
    add("raw7", "unsupported", related=["R7"])
    add("new6", "complete", "R6", kept=True, stage="latest")
    metrics, ledger = pilot.compute_metrics(candidates, targets, judgments)
    by_ref = {r["reference_id"]: r["primary_loss_category"] for r in ledger}
    assert by_ref == dict(R1="validation_rejection", R2="relation_or_role_error", R3="insufficient_evidence",
                          R4="incomplete_conditions_or_scope", R5="retained", R6="not_generated", R7="unsupported_relation")
    assert metrics["stages"]["raw"]["unique_targets_covered"] == 2  # duplicates cannot inflate recall
    assert metrics["original_validation_conditional_recall_loss"] == .5
    assert metrics["latest_gain_over_raw_count"] == 1
    assert metrics["latest_loss_from_raw_count"] == 2


def test_unresolved_is_not_absence_or_a_negative_label():
    candidates = [dict(candidate_id="C", page_key="P", stage="raw", original_pipeline_kept=False)]
    judgments = {"C": dict(verdict="unresolved", reference_id=None, related_reference_ids=[])}
    metrics, ledger = pilot.compute_metrics(candidates, {"R": dict(page_key="P")}, judgments)
    assert ledger[0]["primary_loss_category"] == "unresolved_not_proven_absent"
    assert metrics["stages"]["raw"]["recall"] == 0
    assert metrics["stages"]["raw"]["recall_upper_bound"] == 1


def test_candidate_payload_and_reference_identity_cannot_drift():
    c = dict(candidate_id="C", page_key="P", payload=dict(head="fixed"))
    review = dict(review_id="J", page_key="P", payload=c["payload"], reviewer_kind="human",
                  reviewer_id="test", verdict="complete", reference_id="R", related_reference_ids=[], reason="fixture")
    mapping = [dict(review_id="J", candidate_id="C")]
    targets = {"R": dict(page_key="P")}
    assert pilot.validate_reviews([c], targets, [review], mapping)["C"]["verdict"] == "complete"
    for patch in [dict(payload=dict(head="edited")), dict(reference_id="UNKNOWN"), dict(verdict="wrong_role"),
                  dict(reviewer_kind="AI"), dict(verdict="pending"), dict(reason="")]:
        with pytest.raises(pilot.PilotError):
            pilot.validate_reviews([c], targets, [{**review, **patch}], mapping)
    with pytest.raises(pilot.PilotError):
        pilot.validate_reviews([c], {"R": dict(page_key="OTHER")}, [review], mapping)


def test_generated_record_is_immutable(tmp_path):
    path = tmp_path / "manifest.json"
    pilot.write(path, dict(value=1))
    pilot.write(path, dict(value=1))
    before = path.read_bytes()
    with pytest.raises(pilot.PilotError):
        pilot.write(path, dict(value=2))
    assert path.read_bytes() == before


def test_seal_then_audit_and_reject_reference_drift(tmp_path):
    source, annotation, registry = annotation_fixture()
    key = source["page_key"]
    candidates = [
        dict(candidate_id="RAW-A", page_key=key, stage="raw", payload=dict(head="low pressure"),
             original_pipeline_kept=True),
        dict(candidate_id="LATEST-A", page_key=key, stage="latest", payload=dict(head="changed"),
             latest_pipeline_kept=False),
    ]
    pilot.write(tmp_path / "private/sources.jsonl", [source])
    pilot.write(tmp_path / "private/candidates.jsonl", candidates)
    pilot.write(tmp_path / "private/relation_registry.json", registry)
    pilot.write(tmp_path / "annotations/page_annotations.jsonl", [annotation])
    manifest = dict(config=dict(input_commit="synthetic-test-fixture"),
                    tool_sha256=pilot.sha(SCRIPT.read_bytes()), prepared_payloads={})
    for name in ["private/sources.jsonl", "private/candidates.jsonl", "private/relation_registry.json"]:
        manifest["prepared_payloads"][name] = pilot.sha((tmp_path / name).read_bytes())
    pilot.write(tmp_path / "preparation_manifest.json", manifest)
    assert pilot.seal(tmp_path)["reference_count"] == 1
    reviews = pilot.read(tmp_path / "annotations/candidate_reviews.jsonl")
    with pytest.raises(pilot.PilotError):
        pilot.audit(tmp_path)  # pending judgments cannot produce metrics
    assert not (tmp_path / "audit/metrics.json").exists()
    for row in reviews:
        row.update(reviewer_id="synthetic-test-actor", verdict="complete", reference_id="R1", reason="fixture")
    # This is an editable test annotation, not an immutable research artifact.
    (tmp_path / "annotations/candidate_reviews.jsonl").write_bytes(
        b"".join(pilot.canonical(row) + b"\n" for row in reviews))
    result = pilot.audit(tmp_path)
    assert result["stages"]["raw"]["recall"] == 1
    assert result["stages"]["original_pipeline"]["recall"] == 1
    assert result["stages"]["latest_pipeline"]["recall"] == 0
    assert result["latest_loss_from_raw_count"] == 1
    annotation["targets"][0]["head"] = "edited after seal"
    (tmp_path / "annotations/page_annotations.jsonl").write_bytes(pilot.canonical(annotation) + b"\n")
    with pytest.raises(pilot.PilotError, match="changed after sealing"):
        pilot.audit(tmp_path)
