from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_silver_terminology_governance.py"
SPEC = importlib.util.spec_from_file_location("terminology_governance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _record(
    *,
    decision: str,
    fault_class_ids: list[str],
    head: str,
    tail: str,
) -> dict[str, object]:
    return {
        "decision": decision,
        "fault_class_ids": fault_class_ids,
        "head_surface": head,
        "head_type": "Symptom",
        "head_canonical_zh": f"{head}中文",
        "tail_surface": tail,
        "tail_type": "Cause",
        "tail_canonical_zh": f"{tail}中文",
        "doc_id": "MP001",
        "pdf_page_number": 1,
        "relation": "caused_by",
        "evidence_text": f"{head} is caused by {tail}",
    }


def test_all_eligible_scope_includes_non_fault_qualified_records() -> None:
    records = [
        _record(
            decision="silver_candidate",
            fault_class_ids=["FC001"],
            head="noise",
            tail="cavitation",
        ),
        _record(
            decision="silver_candidate",
            fault_class_ids=[],
            head="high temperature",
            tail="blocked flow",
        ),
        _record(
            decision="rejected",
            fault_class_ids=["FC001"],
            head="leakage",
            tail="seal wear",
        ),
    ]

    fault_core = MODULE.collect_governance_endpoints(records, scope="fault_core")
    all_eligible = MODULE.collect_governance_endpoints(
        records, scope="all_eligible"
    )

    assert len(fault_core) == 2
    assert len(all_eligible) == 4


def test_unknown_scope_fails_closed() -> None:
    try:
        MODULE.collect_governance_endpoints([], scope="unknown")
    except ValueError as exc:
        assert "Unsupported terminology governance scope" in str(exc)
    else:
        raise AssertionError("unknown scope must be rejected")
