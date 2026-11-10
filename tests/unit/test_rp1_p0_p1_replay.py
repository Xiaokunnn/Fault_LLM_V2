"""Audit instrumentation and provenance tests; not expert semantic evaluation."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("p0_p1_replay", ROOT/"scripts/audit_rp1_p0_p1_replay.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_immutable_audit_outputs(tmp_path):
    p = tmp_path/"record.json"
    audit.save(p, {"a": 1})
    audit.save(p, {"a": 1})
    with pytest.raises(ValueError, match="overwrite audit record"):
        audit.save(p, {"a": 2})


def test_snapshot_has_no_mutable_alias_to_live_rule_results():
    original = {"payload": {"conditions": ["one"]}, "included": False, "barriers": ["x"]}
    frozen = audit.snapshot(original)
    original["payload"]["conditions"].append("two")
    assert frozen["payload"]["conditions"] == ["one"]


def test_source_roundtrip_uses_real_unit_ids_and_offsets():
    ws = [{"unit_id": "b1", "start": 1, "end": 4, "text": "bcd"}]
    assert audit.addresses_roundtrip(ws, {"b1": "abcde"}, {"page_text": ""}) == [{"unit_id": "b1", "valid": True}]


@pytest.mark.parametrize("w", [
    {"unit_id": "unknown", "start": 0, "end": 2, "text": "ab"},
    {"unit_id": "b1", "start": -1, "end": 2, "text": "ab"},
    {"unit_id": "b1", "start": 0, "end": 20, "text": "ab"},
    {"unit_id": "b1", "start": 0, "end": 2, "text": "xy"},
])
def test_false_native_addresses_cannot_be_certified(w):
    assert not audit.addresses_roundtrip([w], {"b1": "abcde"}, {"page_text": ""})[0]["valid"]


def test_binding_and_schema_flags_are_not_called_learned_entailment():
    result = audit.failure_domains({"included": False,
             "screen_flags": ["schema_type_direction", "unbound_quote", "unknown_native_unit"],
             "barriers": ["alternative_action_not_preserved"]})
    assert result["schema_direction"] == ["schema_type_direction"]
    assert result["quotation_binding"] == ["unbound_quote"]
    assert result["evidence_address"] == ["unknown_native_unit"]
    assert result["bounded_semantic_or_admission_rules"] == ["alternative_action_not_preserved"]
    assert result["learned_relation_entailment"].startswith("not_run")


def fake_modules(*, fail=False, change_B2=False):
    def transform(a, *_args, **_kwargs):
        if fail:
            raise RuntimeError("fixture failure")
        return {"payload": copy.deepcopy(a), "included": False, "screen_flags": ["unbound_quote"], "barriers": []}
    context = SimpleNamespace(transform=transform)
    clause = SimpleNamespace(refine=lambda _a, _p, r, *_args: copy.deepcopy(r))
    layout = SimpleNamespace(refine=lambda _a, _p, r, *_args: {**copy.deepcopy(r), "included": True, "screen_flags": []})
    native = SimpleNamespace(normalize=lambda a: (copy.deepcopy(a), []), batch_repair=lambda *_: (None, "no_proposal"))
    def legacy(a, p, reg, screen):
        a, _ = native.normalize(a)
        r = context.transform(a, p, reg, screen)
        r = clause.refine(a, p, r, screen)
        r = layout.refine(a, p, r, reg, screen)
        native.batch_repair(r, p, reg)
        return r
    native.legacy_rules = legacy
    native.local_select = lambda _c, r, _reg: (not r["included"] if change_B2 else r["included"], "same_legacy_decision")
    return {"native_local_reconstruction_v1": native, "automatic_contract_v4_1": context,
            "clause_binding_v1": clause, "layout_direction_context_v1": layout}


def test_instrumentation_records_actual_calls_and_restores_functions():
    modules = fake_modules()
    before = {n: dict(vars(m)) for n, m in modules.items()}
    original = {"head_surface": "raw"}
    result, trace, b2 = audit.latest_trace(original, {}, {}, SimpleNamespace(filter_flags=lambda *_: []), modules)
    assert [t["stage"] for t in trace] == ["normalize", "context", "clause", "layout", "batch_repair"]
    assert original == {"head_surface": "raw"}
    assert result["included"] and b2["included"]
    assert all(vars(modules[n]) == b for n, b in before.items())


def test_instrumentation_restores_functions_after_failure():
    modules = fake_modules(fail=True)
    before = {n: dict(vars(m)) for n, m in modules.items()}
    with pytest.raises(RuntimeError, match="fixture failure"):
        audit.latest_trace({}, {}, {}, SimpleNamespace(filter_flags=lambda *_: []), modules)
    assert all(vars(modules[n]) == b for n, b in before.items())


def test_B2_cannot_change_fixed_cached_candidate_membership():
    with pytest.raises(ValueError, match="same-input premise"):
        audit.latest_trace({}, {}, {}, SimpleNamespace(filter_flags=lambda *_: []), fake_modules(change_B2=True))


def test_existing_type_normalizer_handles_pressure_reversal_without_a_model():
    path = ROOT/"src/research_point_1_graph_evidence/stage03_schema_validation/relation_type_validator.py"
    spec = importlib.util.spec_from_file_location("existing_rp1_type_normalizer", path)
    normalizer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = normalizer
    spec.loader.exec_module(normalizer)
    result = normalizer.normalize_relation_direction(head="damage to the Impeller", head_type="FaultMode", relation="causes",
        tail="operate above maximum differential pressure", tail_type="OperatingCondition")
    assert result.head_type == "OperatingCondition" and result.tail_type == "FaultMode"
    assert result.actions == ("reoriented_cause_to_effect",)


def test_type_normalization_does_not_solve_condition_action_object_binding():
    normalizer = sys.modules.get("existing_rp1_type_normalizer")
    if normalizer is None:
        test_existing_type_normalizer_handles_pressure_reversal_without_a_model()
        normalizer = sys.modules["existing_rp1_type_normalizer"]
    result = normalizer.normalize_relation_direction(head="temperature changes", head_type="OperatingCondition", relation="causes",
        tail="recheck shaft rotation", tail_type="InspectionAction")
    assert result.actions == ()
    assert result.relation == "causes" and result.tail_type == "InspectionAction"
