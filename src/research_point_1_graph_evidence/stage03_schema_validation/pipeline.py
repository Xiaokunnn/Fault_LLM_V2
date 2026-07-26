"""End-to-end strict validation of extracted evidence candidates."""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Mapping, Sequence

from .chinese_canonicalizer import (
    load_chinese_terminology,
    validate_chinese_canonicalization,
)
from .confidence_policy import decide_confidence
from .deduplicator import enrich_stable_ids
from .evidence_span_validator import E3, validate_evidence_span
from .fault_class_mapper import load_fault_ontology, map_fault_classes
from .relation_entailment_validator import validate_relation_entailment
from .record_level_repair import apply_record_level_repair
from .relation_type_validator import (
    load_provenance_schema,
    normalize_relation_direction,
    validate_relation_type,
)
from .table_alignment_validator import validate_table_alignment


VALIDATOR_VERSION = "marine_pump_strict_validation_v2_1"


def validate_candidate(
    candidate: Mapping[str, object],
    *,
    page_text: str,
    project_root: str | Path | None = None,
    schema: Mapping[str, object] | None = None,
    ontology: Mapping[str, object] | None = None,
    terminology: Mapping[str, object] | None = None,
    table_evidence_units: Sequence[Mapping[str, object]] | None = None,
    structured_relation: str | None = None,
    visual_layout_checked: bool = False,
) -> dict[str, object]:
    """Validate one candidate without calling an external model.

    Table evidence is accepted only when the caller supplies parser-generated
    units and an independently verified structured relation. The function
    never infers a table relation merely because two cells are near each other.
    """

    schema = schema or load_provenance_schema(project_root=project_root)
    ontology = ontology or load_fault_ontology(project_root=project_root)
    terminology = terminology or load_chinese_terminology(
        project_root=project_root
    )
    candidate = apply_record_level_repair(
        candidate,
        project_root=project_root,
    )
    normalized = normalize_relation_direction(
        head=str(candidate.get("head", "")),
        head_type=str(candidate.get("head_type", "")),
        relation=str(candidate.get("relation", "")),
        tail=str(candidate.get("tail", "")),
        tail_type=str(candidate.get("tail_type", "")),
    )
    relation_type = validate_relation_type(
        relation=normalized.relation,
        head_type=normalized.head_type,
        tail_type=normalized.tail_type,
        schema=schema,
    )

    if table_evidence_units:
        evidence = validate_table_alignment(
            page_text=page_text,
            evidence_units=table_evidence_units,
            head_surface=normalized.head,
            tail_surface=normalized.tail,
            visual_layout_checked=visual_layout_checked,
        )
        evidence_text = "\n--- CELL ---\n".join(
            str(unit.get("text", "")) for unit in table_evidence_units
        )
        evidence_level = evidence.evidence_level
    else:
        evidence = validate_evidence_span(
            page_text=page_text,
            evidence_text=str(candidate.get("evidence_text", "")),
            head_surface=normalized.head,
            tail_surface=normalized.tail,
        )
        legacy_method = str(
            (
                candidate.get("validation_votes", {})
                if isinstance(candidate.get("validation_votes"), Mapping)
                else {}
            ).get("evidence_match_method", "")
        )
        if legacy_method == "head_tail_context_reconstructed" and evidence.valid:
            evidence = replace(
                evidence,
                evidence_level=E3,
                silver_eligible=False,
                silver_veto_reasons=tuple(
                    dict.fromkeys(
                        [
                            *evidence.silver_veto_reasons,
                            "legacy_reconstructed_evidence_cannot_be_promoted",
                        ]
                    )
                ),
                review_reasons=tuple(
                    dict.fromkeys(
                        [
                            *evidence.review_reasons,
                            "reconstructed_evidence_requires_review",
                        ]
                    )
                ),
            )
        evidence_text = evidence.evidence_text
        evidence_level = evidence.evidence_level or ""

    entailment = validate_relation_entailment(
        relation=normalized.relation,
        evidence_text=evidence_text,
        head_surface=normalized.head,
        tail_surface=normalized.tail,
        evidence_level=evidence_level,
        structured_relation=structured_relation,
    )
    confidence = decide_confidence(
        model_confidence=float(
            candidate.get(
                "model_confidence",
                candidate.get("triple_confidence", 0.0),
            )
            or 0.0
        ),
        evidence_validation=evidence,
        relation_type_validation=relation_type,
        relation_entailment_validation=entailment,
        schema_valid=True,
        source_tier=str(candidate.get("source_tier", "")),
        inferred_edge=bool(candidate.get("inferred_edge", False)),
        document_split=str(candidate.get("document_split", "unassigned")),
    )
    mapping = map_fault_classes(
        head_surface=normalized.head,
        tail_surface=normalized.tail,
        evidence_text=evidence_text if bool(getattr(evidence, "valid", False)) else "",
        ontology=ontology,
        requested_fault_class_ids=candidate.get("fault_class_ids", ()) or (),
    )
    chinese_candidate = dict(candidate)
    if any(
        action.startswith("reoriented_") for action in normalized.actions
    ):
        for suffix in (
            "canonical_zh",
            "terminology_id",
            "source_language",
            "translation_method",
            "translation_status",
            "translation_confidence",
        ):
            head_key = f"head_{suffix}"
            tail_key = f"tail_{suffix}"
            head_value = chinese_candidate.get(head_key)
            tail_value = chinese_candidate.get(tail_key)
            if head_key in chinese_candidate or tail_key in chinese_candidate:
                chinese_candidate[head_key] = tail_value
                chinese_candidate[tail_key] = head_value
    chinese = validate_chinese_canonicalization(
        head_surface=normalized.head,
        head_type=normalized.head_type,
        relation=normalized.relation,
        tail_surface=normalized.tail,
        tail_type=normalized.tail_type,
        candidate=chinese_candidate,
        terminology=terminology,
    )
    eligible_for_chinese_graph = bool(
        confidence.decision == "silver_candidate" and chinese.graph_ready
    )

    result = dict(candidate)
    result.update(
        {
            "legacy_triple_id": candidate.get("triple_id"),
            "head": normalized.head,
            "head_surface": normalized.head,
            "head_type": normalized.head_type,
            "relation": normalized.relation,
            "tail": normalized.tail,
            "tail_surface": normalized.tail,
            "tail_type": normalized.tail_type,
            "evidence_text": evidence_text,
            "evidence_level": evidence_level or None,
            "evidence_start": getattr(evidence, "evidence_start", None),
            "evidence_end": getattr(evidence, "evidence_end", None),
            "evidence_validation": asdict(evidence),
            "relation_type_validation": asdict(relation_type),
            "relation_entailment_validation": asdict(entailment),
            "relation_type_valid": relation_type.valid,
            "relation_entailment_valid": entailment.valid,
            "fault_class_ids": list(mapping.fault_class_ids),
            "fault_class_mapping_version": mapping.mapping_version,
            "fault_class_mapping_rule_ids": {
                key: list(value) for key, value in mapping.matched_rule_ids.items()
            },
            "fault_class_mapping_evidence": {
                key: list(value) for key, value in mapping.mapping_evidence.items()
            },
            "head_canonical_zh": chinese.head.canonical_label_zh,
            "head_terminology_id": chinese.head.terminology_id,
            "head_source_language": chinese.head.source_language,
            "head_translation_method": chinese.head.translation_method,
            "head_translation_status": chinese.head.translation_status,
            "head_type_label_zh": chinese.head_type_label_zh,
            "tail_canonical_zh": chinese.tail.canonical_label_zh,
            "tail_terminology_id": chinese.tail.terminology_id,
            "tail_source_language": chinese.tail.source_language,
            "tail_translation_method": chinese.tail.translation_method,
            "tail_translation_status": chinese.tail.translation_status,
            "tail_type_label_zh": chinese.tail_type_label_zh,
            "relation_label_zh": chinese.relation_label_zh,
            "graph_display_language": chinese.graph_display_language,
            "terminology_version": chinese.terminology_version,
            "chinese_canonicalization": chinese.to_dict(),
            "chinese_canonicalization_reasons": list(chinese.reasons),
            "eligible_for_chinese_graph": eligible_for_chinese_graph,
            "graph_release_status": (
                "core_silver_ready"
                if eligible_for_chinese_graph
                else (
                    "candidate_needs_chinese_normalization"
                    if confidence.decision == "silver_candidate"
                    else "not_silver_evidence"
                )
            ),
            "decision": confidence.decision,
            "validation_status": confidence.decision,
            "final_confidence": confidence.final_confidence,
            "confidence_components": asdict(confidence),
            "review_reasons": list(confidence.review_reasons),
            "rejection_reasons": list(confidence.rejection_reasons),
            "normalization_actions": list(
                dict.fromkeys(
                    [
                        *(candidate.get("normalization_actions", []) or []),
                        *normalized.actions,
                    ]
                )
            ),
            "validator": f"local:{VALIDATOR_VERSION}",
        }
    )
    if table_evidence_units:
        result["evidence_units"] = [dict(unit) for unit in table_evidence_units]
    return enrich_stable_ids(result)
