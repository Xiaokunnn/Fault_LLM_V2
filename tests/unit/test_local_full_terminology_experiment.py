from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_local_full_terminology_experiment.py"
SPEC = importlib.util.spec_from_file_location("local_full_terminology", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _item(*, labels: list[str], confidences: list[float], units: int = 1):
    return {
        "surface_forms": {"low pressure"},
        "labels": MODULE.Counter(labels),
        "confidences": confidences,
        "evidence_units": {("MP001", index + 1) for index in range(units)},
        "record_count": len(confidences),
    }


def test_repeated_exact_label_consensus_is_accepted() -> None:
    accepted, reason, label = MODULE.evaluate_candidate(
        _item(labels=["低压力", "低压力"], confidences=[0.90, 0.95], units=2),
        terminology={"protected_term_patterns": []},
        repeated_min_confidence=0.90,
        singleton_min_confidence=0.95,
    )
    assert accepted is True
    assert reason == "repeated_exact_label_consensus"
    assert label == "低压力"


def test_conflicting_labels_are_rejected() -> None:
    accepted, reason, _ = MODULE.evaluate_candidate(
        _item(labels=["低压力", "压力不足"], confidences=[0.95, 0.95], units=2),
        terminology={"protected_term_patterns": []},
        repeated_min_confidence=0.90,
        singleton_min_confidence=0.95,
    )
    assert accepted is False
    assert reason == "label_missing_or_conflicting"


def test_singleton_requires_higher_confidence() -> None:
    accepted, reason, _ = MODULE.evaluate_candidate(
        _item(labels=["低压力"], confidences=[0.90]),
        terminology={"protected_term_patterns": []},
        repeated_min_confidence=0.90,
        singleton_min_confidence=0.95,
    )
    assert accepted is False
    assert reason == "singleton_below_confidence"


def test_nonrelease_identifiers_are_restored() -> None:
    record = {
        "decision": "rejected",
        "claim_id": "new-claim",
        "evidence_id": "new-evidence",
        "terminology_governance": {
            "previous_ids": {
                "claim_id": "old-claim",
                "evidence_id": "old-evidence",
            }
        },
    }
    MODULE.restore_nonrelease_identifiers([record])
    assert record["claim_id"] == "old-claim"
    assert record["evidence_id"] == "old-evidence"
