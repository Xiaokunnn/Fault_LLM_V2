"""Chinese semantic-layer canonicalization after source-evidence validation.

Source surfaces and evidence text are never translated in place.  This module
only creates a Chinese canonical projection for graph entities and display
labels after the raw-language assertion has been validated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping, Sequence
import unicodedata


HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class CanonicalEndpoint:
    source_surface: str
    source_language: str
    entity_type: str
    canonical_label_zh: str | None
    terminology_id: str | None
    translation_method: str
    translation_status: str
    protected_terms: tuple[str, ...]
    protected_terms_valid: bool
    graph_ready: bool
    source_forms: tuple[dict[str, str], ...]
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ChineseCanonicalization:
    graph_ready: bool
    graph_display_language: str
    terminology_version: str
    relation_code: str
    relation_label_zh: str | None
    head_type_label_zh: str | None
    tail_type_label_zh: str | None
    head: CanonicalEndpoint
    tail: CanonicalEndpoint
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_terminology_path(project_root: str | Path | None = None) -> Path:
    root = Path(project_root or Path.cwd())
    return root / "configs" / "entity_terminology_zh_marine_pump_v1.json"


def load_chinese_terminology(
    path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> dict[str, object]:
    selected = Path(path) if path is not None else default_terminology_path(project_root)
    try:
        payload = json.loads(selected.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Chinese terminology JSON: {selected}: {exc}") from exc
    required = (
        "version",
        "graph_display_language",
        "policy",
        "node_type_labels_zh",
        "relation_labels_zh",
        "terms",
    )
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise ValueError(
            f"Chinese terminology {selected} is missing fields: {', '.join(missing)}"
        )
    return payload


def normalize_lookup_text(value: object) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(value or "")).casefold().split()
    )


def contains_han(value: object) -> bool:
    return bool(HAN_PATTERN.search(str(value or "")))


def detect_surface_language(value: object) -> str:
    text = str(value or "")
    has_han = bool(HAN_PATTERN.search(text))
    has_latin = bool(LATIN_PATTERN.search(text))
    if has_han and has_latin:
        return "multilingual"
    if has_han:
        return "zh"
    if has_latin:
        return "en"
    return "und"


def _term_index(
    terminology: Mapping[str, object],
) -> dict[tuple[str, str], Mapping[str, object]]:
    result: dict[tuple[str, str], Mapping[str, object]] = {}
    for raw_entry in terminology.get("terms", []):
        if not isinstance(raw_entry, Mapping):
            continue
        entity_type = str(raw_entry.get("entity_type", ""))
        for raw_form in raw_entry.get("source_forms", []):
            if not isinstance(raw_form, Mapping):
                continue
            surface = normalize_lookup_text(raw_form.get("surface", ""))
            if not entity_type or not surface:
                continue
            key = (entity_type, surface)
            if key in result and result[key].get("terminology_id") != raw_entry.get(
                "terminology_id"
            ):
                raise ValueError(
                    "Ambiguous type-scoped terminology surface: "
                    f"{entity_type}:{surface}"
                )
            result[key] = raw_entry
    return result


def _protected_terms(
    surface: str,
    terminology: Mapping[str, object],
) -> tuple[str, ...]:
    found: list[str] = []
    for pattern in terminology.get("protected_term_patterns", []):
        for match in re.finditer(str(pattern), surface, flags=re.IGNORECASE):
            token = match.group(0).strip()
            if token and token.casefold() not in {item.casefold() for item in found}:
                found.append(token)
    return tuple(found)


def _generated_concept_id(entity_type: str, canonical_label_zh: str) -> str:
    identity = f"{entity_type}\u241f{normalize_lookup_text(canonical_label_zh)}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"MPTERM-ZH-{digest}"


def _reviewed_translation_method(status: str) -> str:
    if status == "secondary_ai_verified":
        return "secondary_ai_verified"
    if status == "human_approved":
        return "human_reviewed"
    return "model_proposed"


def _canonicalize_endpoint(
    *,
    surface: str,
    entity_type: str,
    proposed_label_zh: str | None,
    proposed_translation_status: str | None,
    proposed_terminology_id: str | None,
    terminology: Mapping[str, object],
) -> CanonicalEndpoint:
    source_language = detect_surface_language(surface)
    lookup = _term_index(terminology)
    matched = lookup.get((entity_type, normalize_lookup_text(surface)))
    eligible_statuses = {
        str(item)
        for item in (
            terminology.get("policy", {}).get("eligible_translation_statuses", [])
            if isinstance(terminology.get("policy"), Mapping)
            else []
        )
    }
    reasons: list[str] = []

    if matched is not None:
        canonical_label = str(matched["canonical_label_zh"]).strip()
        terminology_id = str(matched["terminology_id"])
        translation_method = "type_scoped_dictionary"
        translation_status = "dictionary_approved"
        if proposed_label_zh and normalize_lookup_text(proposed_label_zh) != normalize_lookup_text(
            canonical_label
        ):
            reasons.append("model_label_overridden_by_dictionary")
        if proposed_terminology_id and proposed_terminology_id != terminology_id:
            reasons.append("model_terminology_id_overridden_by_dictionary")
    elif source_language in {"zh", "multilingual"} and contains_han(surface):
        canonical_label = str(proposed_label_zh or surface).strip()
        if normalize_lookup_text(canonical_label) == normalize_lookup_text(surface):
            translation_method = "source_zh_exact"
            translation_status = "source_zh_exact"
        else:
            translation_status = str(proposed_translation_status or "needs_review")
            translation_method = _reviewed_translation_method(translation_status)
        terminology_id = str(
            proposed_terminology_id
            or _generated_concept_id(entity_type, canonical_label)
        )
    else:
        canonical_label = str(proposed_label_zh or "").strip() or None
        terminology_id = (
            str(proposed_terminology_id).strip()
            if proposed_terminology_id
            else (
                _generated_concept_id(entity_type, canonical_label)
                if canonical_label and contains_han(canonical_label)
                else None
            )
        )
        translation_status = str(proposed_translation_status or "needs_review")
        translation_method = _reviewed_translation_method(translation_status)

    if not canonical_label:
        reasons.append("canonical_zh_missing")
    elif not contains_han(canonical_label):
        reasons.append("canonical_zh_has_no_han_character")

    protected = _protected_terms(surface, terminology)
    protected_valid = bool(canonical_label) and all(
        normalize_lookup_text(token) in normalize_lookup_text(canonical_label)
        for token in protected
    )
    if protected and not protected_valid:
        reasons.append("protected_term_missing_from_canonical_zh")

    if translation_status not in eligible_statuses:
        reasons.append("translation_status_not_graph_eligible")

    graph_ready = (
        bool(canonical_label)
        and contains_han(canonical_label)
        and bool(terminology_id)
        and protected_valid
        and translation_status in eligible_statuses
    )
    forms: list[dict[str, str]] = [
        {"surface": surface, "language": source_language, "role": "source_surface"}
    ]
    if canonical_label and normalize_lookup_text(canonical_label) != normalize_lookup_text(
        surface
    ):
        forms.append(
            {
                "surface": canonical_label,
                "language": "zh",
                "role": "canonical_label",
            }
        )
    return CanonicalEndpoint(
        source_surface=surface,
        source_language=source_language,
        entity_type=entity_type,
        canonical_label_zh=canonical_label,
        terminology_id=terminology_id,
        translation_method=translation_method,
        translation_status=translation_status,
        protected_terms=protected,
        protected_terms_valid=protected_valid,
        graph_ready=graph_ready,
        source_forms=tuple(forms),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def validate_chinese_canonicalization(
    *,
    head_surface: str,
    head_type: str,
    relation: str,
    tail_surface: str,
    tail_type: str,
    candidate: Mapping[str, object] | None = None,
    terminology: Mapping[str, object],
) -> ChineseCanonicalization:
    candidate = candidate or {}
    head = _canonicalize_endpoint(
        surface=head_surface,
        entity_type=head_type,
        proposed_label_zh=(
            str(candidate.get("head_canonical_zh", "")).strip() or None
        ),
        proposed_translation_status=(
            str(candidate.get("head_translation_status", "")).strip() or None
        ),
        proposed_terminology_id=(
            str(candidate.get("head_terminology_id", "")).strip() or None
        ),
        terminology=terminology,
    )
    tail = _canonicalize_endpoint(
        surface=tail_surface,
        entity_type=tail_type,
        proposed_label_zh=(
            str(candidate.get("tail_canonical_zh", "")).strip() or None
        ),
        proposed_translation_status=(
            str(candidate.get("tail_translation_status", "")).strip() or None
        ),
        proposed_terminology_id=(
            str(candidate.get("tail_terminology_id", "")).strip() or None
        ),
        terminology=terminology,
    )
    relation_labels = terminology.get("relation_labels_zh", {})
    type_labels = terminology.get("node_type_labels_zh", {})
    relation_label = (
        str(relation_labels.get(relation, "")).strip()
        if isinstance(relation_labels, Mapping)
        else ""
    ) or None
    head_type_label = (
        str(type_labels.get(head_type, "")).strip()
        if isinstance(type_labels, Mapping)
        else ""
    ) or None
    tail_type_label = (
        str(type_labels.get(tail_type, "")).strip()
        if isinstance(type_labels, Mapping)
        else ""
    ) or None
    reasons = [*head.reasons, *tail.reasons]
    if relation_label is None:
        reasons.append("relation_zh_label_missing")
    if head_type_label is None:
        reasons.append("head_type_zh_label_missing")
    if tail_type_label is None:
        reasons.append("tail_type_zh_label_missing")
    graph_ready = bool(
        head.graph_ready
        and tail.graph_ready
        and relation_label
        and head_type_label
        and tail_type_label
    )
    return ChineseCanonicalization(
        graph_ready=graph_ready,
        graph_display_language=str(
            terminology.get("graph_display_language", "zh-CN")
        ),
        terminology_version=str(terminology.get("version", "")),
        relation_code=relation,
        relation_label_zh=relation_label,
        head_type_label_zh=head_type_label,
        tail_type_label_zh=tail_type_label,
        head=head,
        tail=tail,
        reasons=tuple(dict.fromkeys(reasons)),
    )
