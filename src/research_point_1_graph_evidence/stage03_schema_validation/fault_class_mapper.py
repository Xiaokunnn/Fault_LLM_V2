"""Versioned, claim-scoped marine-pump fault-class mapping."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class FaultClassMapping:
    fault_class_ids: tuple[str, ...]
    mapping_version: str
    matched_rule_ids: dict[str, tuple[str, ...]]
    mapping_evidence: dict[str, tuple[dict[str, object], ...]]
    rejected_requested_ids: tuple[str, ...]
    invalid_requested_ids: tuple[str, ...]
    validation_scope: str = "head_tail_and_validated_evidence"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_ontology_path(project_root: str | Path | None = None) -> Path:
    return (
        Path(project_root or Path.cwd())
        / "configs"
        / "fault_ontology_marine_pump_v1.json"
    )


def load_fault_ontology(
    ontology_path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> dict[str, object]:
    path = Path(ontology_path) if ontology_path else default_ontology_path(project_root)
    if not path.is_file():
        raise FileNotFoundError(
            "Marine-pump fault ontology not found at "
            f"{path}. Create/version configs/fault_ontology_marine_pump_v1.json "
            "before running strict fault mapping."
        )
    try:
        ontology = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid fault ontology JSON: {path}: {exc}") from exc
    if "fault_classes" not in ontology:
        raise ValueError(f"Fault ontology {path} is missing 'fault_classes'")
    return ontology


def _flatten_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        result: list[str] = []
        for nested in value.values():
            result.extend(_flatten_strings(nested))
        return result
    if isinstance(value, Sequence):
        result = []
        for nested in value:
            result.extend(_flatten_strings(nested))
        return result
    return []


def _class_entries(ontology: Mapping[str, object]) -> dict[str, dict[str, object]]:
    raw = ontology.get("fault_classes")
    entries: dict[str, dict[str, object]] = {}
    if isinstance(raw, Mapping):
        for fault_id, value in raw.items():
            item = dict(value) if isinstance(value, Mapping) else {}
            item.setdefault("fault_id", str(fault_id))
            entries[str(fault_id)] = item
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        for value in raw:
            if not isinstance(value, Mapping) or not value.get("fault_id"):
                raise ValueError("Each fault class must contain a non-empty fault_id")
            entries[str(value["fault_id"])] = dict(value)
    else:
        raise ValueError("Fault ontology 'fault_classes' must be an array or object")
    if not entries:
        raise ValueError("Fault ontology contains no fault classes")
    return entries


def _pattern_rules(
    fault_id: str, entry: Mapping[str, object], ontology: Mapping[str, object]
) -> list[tuple[str, str, str]]:
    values: list[tuple[object, str]] = []
    for key in (
        "mapping_patterns",
        "positive_patterns",
        "lexical_patterns",
        "patterns",
    ):
        if key in entry:
            raw = entry[key]
            if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
                values.extend((value, "claim_and_evidence") for value in raw)
            else:
                values.append((raw, "claim_and_evidence"))
    raw_claim_only = entry.get("claim_only_mapping_patterns")
    if raw_claim_only is not None:
        if isinstance(raw_claim_only, Sequence) and not isinstance(
            raw_claim_only, (str, bytes)
        ):
            values.extend((value, "claim_only") for value in raw_claim_only)
        else:
            values.append((raw_claim_only, "claim_only"))
    top_patterns = ontology.get("patterns")
    if isinstance(top_patterns, Mapping) and fault_id in top_patterns:
        raw = top_patterns[fault_id]
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend((value, "claim_and_evidence") for value in raw)
        else:
            values.append((raw, "claim_and_evidence"))

    rules: list[tuple[str, str, str]] = []
    for index, (value, scope) in enumerate(values):
        if isinstance(value, Mapping):
            pattern = str(value.get("pattern", ""))
            rule_id = str(value.get("rule_id") or value.get("id") or f"{fault_id}:p{index}")
        else:
            pattern = str(value or "")
            rule_id = f"{fault_id}:p{index}"
        if pattern:
            rules.append((rule_id, pattern, scope))

    aliases = _flatten_strings(entry.get("aliases"))
    aliases.extend(_flatten_strings(entry.get("synonyms")))
    for index, alias in enumerate(aliases):
        if alias.strip():
            rules.append(
                (
                    f"{fault_id}:alias{index}",
                    rf"(?<!\w){re.escape(alias.strip())}(?!\w)",
                    "claim_and_evidence",
                )
            )
    return rules


def _negative_patterns(entry: Mapping[str, object]) -> list[str]:
    result: list[str] = []
    for key in ("negative_patterns", "exclusion_patterns"):
        result.extend(_flatten_strings(entry.get(key)))
    return result


def map_fault_classes(
    *,
    head_surface: str,
    tail_surface: str,
    evidence_text: str,
    ontology: Mapping[str, object],
    requested_fault_class_ids: Iterable[str] = (),
) -> FaultClassMapping:
    """Map only from claim entities and their already validated evidence."""

    entries = _class_entries(ontology)
    requested = tuple(dict.fromkeys(str(item) for item in requested_fault_class_ids))
    invalid_requested = tuple(item for item in requested if item not in entries)
    claim_only_text = "\n".join(
        value for value in (head_surface, tail_surface) if value
    )
    claim_and_evidence_text = "\n".join(
        value for value in (claim_only_text, evidence_text) if value
    )
    matched: dict[str, tuple[str, ...]] = {}
    mapping_evidence: dict[str, tuple[dict[str, object], ...]] = {}
    for fault_id, entry in entries.items():
        if any(
            re.search(
                pattern,
                claim_and_evidence_text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            for pattern in _negative_patterns(entry)
        ):
            continue
        hits: list[str] = []
        evidence_hits: list[dict[str, object]] = []
        for rule_id, pattern, scope in _pattern_rules(
            fault_id, entry, ontology
        ):
            try:
                match_text = (
                    claim_only_text
                    if scope == "claim_only"
                    else claim_and_evidence_text
                )
                match = re.search(
                    pattern,
                    match_text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if match:
                    hits.append(rule_id)
                    evidence_hits.append(
                        {
                            "rule_id": rule_id,
                            "char_start": match.start(),
                            "char_end": match.end(),
                            "matched_text": match.group(0),
                            "match_scope": scope,
                        }
                    )
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex for fault class {fault_id}, rule {rule_id}: {exc}"
                ) from exc
        if hits:
            matched[fault_id] = tuple(dict.fromkeys(hits))
            mapping_evidence[fault_id] = tuple(evidence_hits)

    rejected_requested = tuple(
        item for item in requested if item in entries and item not in matched
    )
    version = str(
        ontology.get("version")
        or ontology.get("ontology_version")
        or "unversioned_fault_ontology"
    )
    return FaultClassMapping(
        fault_class_ids=tuple(sorted(matched)),
        mapping_version=version,
        matched_rule_ids={key: matched[key] for key in sorted(matched)},
        mapping_evidence={
            key: mapping_evidence[key] for key in sorted(mapping_evidence)
        },
        rejected_requested_ids=rejected_requested,
        invalid_requested_ids=invalid_requested,
    )
