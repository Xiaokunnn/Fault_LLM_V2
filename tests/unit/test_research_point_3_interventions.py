from __future__ import annotations

from dataclasses import replace

import pytest

from src.research_point_3.contracts import ContractError, DataSplit
from src.research_point_3.interventions import (
    mask_for_teacher_replay,
    remove_evidence,
    student_rollout_for_teacher_correction,
)
from tests.unit.test_research_point_3_data_contracts import _trace


def test_removing_selected_evidence_requires_teacher_replay() -> None:
    trace = replace(_trace(), split=DataSplit.TRAIN)
    with pytest.raises(ContractError, match="rerun the frozen teacher"):
        remove_evidence(trace, ["E1"])
    request = mask_for_teacher_replay(trace, ["E1"])
    assert request["availability_mask"] == [False, True]
    assert request["teacher_replay_required"] is True
    assert request["synthetic_label_allowed"] is False


def test_nonselected_removal_preserves_teacher_target() -> None:
    trace = replace(_trace(), split=DataSplit.TRAIN)
    changed = remove_evidence(trace, ["E2"])
    assert changed.availability_mask == (True, False)
    assert changed.selected_evidence_ids == trace.selected_evidence_ids


def test_student_rollout_exports_only_pending_teacher_correction_request() -> None:
    trace = replace(_trace(), split=DataSplit.TRAIN)
    request = student_rollout_for_teacher_correction(
        trace,
        selected_evidence_ids=["E2"],
        support_by_evidence_id={"E1": "irrelevant", "E2": "direct"},
        field_plan=[{"role": "symptom", "state": "supported", "cardinality": 1}],
        proposed_route="answer",
        controller_version="lec-checkpoint-v1",
    )
    assert request["teacher_replay_required"] is True
    assert request["synthetic_label_allowed"] is False
    assert request["correction_status"] == "pending_teacher_replay"
