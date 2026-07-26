"""Fail-closed, versioned repairs for individually audited extraction records."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_record_level_repair(
    candidate: Mapping[str, object],
    *,
    project_root: str | Path | None,
) -> dict[str, object]:
    result = dict(candidate)
    root = Path(project_root or Path.cwd())
    path = root / "configs" / "record_level_relation_repairs_v1.json"
    if not path.exists():
        return result
    registry = _load(str(path))
    repair = registry.get("repairs", {}).get(str(candidate.get("triple_id", "")))
    if not isinstance(repair, Mapping):
        return result
    expected = repair.get("expected", {})
    if not isinstance(expected, Mapping) or any(
        str(candidate.get(key, "")) != str(value)
        for key, value in expected.items()
    ):
        result["record_level_repair_error"] = "expected_fields_mismatch"
        return result
    if repair.get("swap_head_tail") is True:
        for left, right in (
            ("head", "tail"),
            ("head_surface", "tail_surface"),
            ("head_type", "tail_type"),
            ("head_canonical_zh", "tail_canonical_zh"),
            ("head_translation_status", "tail_translation_status"),
            ("head_translation_confidence", "tail_translation_confidence"),
        ):
            if left in result or right in result:
                result[left], result[right] = result.get(right), result.get(left)
    changes = repair.get("set", {})
    if isinstance(changes, Mapping):
        result.update(changes)
    result["normalization_actions"] = list(
        dict.fromkeys(
            [
                *(candidate.get("normalization_actions", []) or []),
                str(repair.get("action", "record_level_audit_repair")),
            ]
        )
    )
    result["record_level_repair_version"] = registry.get("version")
    return result
