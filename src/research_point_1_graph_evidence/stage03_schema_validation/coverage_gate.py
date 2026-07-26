"""Build-only fault-category coverage calculation for strict Silver evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

from .deduplicator import normalize_identity_text, stable_evidence_id


@dataclass(frozen=True)
class CoverageThresholds:
    symptom: int = 5
    cause_or_mechanism: int = 3
    inspection_or_maintenance: int = 2
    independent_documents: int = 2
    source_families: int = 2
    minimum_silver_confidence: float = 0.8

    @classmethod
    def from_ontology(
        cls, ontology: Mapping[str, object]
    ) -> "CoverageThresholds":
        gate = ontology.get("coverage_gate", {})
        if not isinstance(gate, Mapping):
            raise ValueError("Fault ontology 'coverage_gate' must be an object")
        return cls(
            symptom=int(gate.get("symptom", cls.symptom)),
            cause_or_mechanism=int(
                gate.get("cause_or_mechanism", cls.cause_or_mechanism)
            ),
            inspection_or_maintenance=int(
                gate.get(
                    "inspection_or_maintenance",
                    cls.inspection_or_maintenance,
                )
            ),
            independent_documents=int(
                gate.get(
                    "independent_documents", cls.independent_documents
                )
            ),
            source_families=int(
                gate.get(
                    "independent_source_families",
                    gate.get("source_families", cls.source_families),
                )
            ),
            minimum_silver_confidence=float(
                gate.get(
                    "minimum_silver_confidence",
                    cls.minimum_silver_confidence,
                )
            ),
        )


SYMPTOM_TYPES = {"Symptom"}
CAUSE_TYPES = {"Cause", "FailureMechanism"}
INSPECTION_MAINTENANCE_TYPES = {
    "InspectionMethod",
    "InspectionAction",
    "MaintenanceAction",
}


def _decision(record: Mapping[str, object]) -> str:
    return str(record.get("decision") or record.get("validation_status") or "")


def _confidence(record: Mapping[str, object]) -> float:
    try:
        return float(
            record.get("final_confidence", record.get("triple_confidence", 0))
            or 0
        )
    except (TypeError, ValueError):
        return 0.0


def _evidence_level(record: Mapping[str, object]) -> str:
    explicit = record.get("evidence_level")
    if explicit:
        return str(explicit)
    votes = record.get("validation_votes")
    if isinstance(votes, Mapping):
        method = str(votes.get("evidence_match_method", ""))
        return "E3" if "reconstructed" in method else "E1"
    return ""


def _entailment_valid(record: Mapping[str, object]) -> bool:
    if "relation_entailment_valid" in record:
        return record.get("relation_entailment_valid") is True
    votes = record.get("validation_votes")
    return (
        isinstance(votes, Mapping)
        and votes.get("relation_entailment_valid") is True
    )


def is_build_coverage_eligible(
    record: Mapping[str, object],
    thresholds: CoverageThresholds = CoverageThresholds(),
    *,
    require_chinese_graph_ready: bool = False,
) -> bool:
    return (
        _decision(record) in {"silver_candidate", "accepted_silver"}
        and _confidence(record) >= thresholds.minimum_silver_confidence
        and record.get("document_split") == "build_train"
        and bool(record.get("source_family_id"))
        and not bool(record.get("inferred_edge", False))
        and _evidence_level(record) in {"E1", "E2"}
        and _entailment_valid(record)
        and (
            not require_chinese_graph_ready
            or record.get("eligible_for_chinese_graph") is True
        )
    )


def _evidence_id(record: Mapping[str, object]) -> str:
    return str(
        record.get("assertion_id")
        or record.get("evidence_id")
        or stable_evidence_id(record)
    )


def _typed_units(
    records: Sequence[Mapping[str, object]],
    node_types: set[str],
    fallback_role: str,
) -> set[str]:
    units: set[str] = set()
    for record in records:
        evidence_id = _evidence_id(record)
        doc_page = (
            f"{record.get('doc_id', '')}|{record.get('pdf_page_number', '')}"
        )
        typed = False
        for side in ("head", "tail"):
            node_type = str(record.get(f"{side}_type", ""))
            if node_type in node_types:
                typed = True
                entity_id = str(
                    record.get(f"{side}_entity_id")
                    or normalize_identity_text(record.get(side, ""))
                )
                units.add(
                    f"{doc_page}|{evidence_id}|{node_type}|{entity_id}"
                )
        if not typed and record.get("evidence_role") == fallback_role:
            units.add(f"{doc_page}|{evidence_id}|fallback")
    return units


def build_coverage_report(
    records: Iterable[Mapping[str, object]],
    *,
    fault_ids: Iterable[str] | None = None,
    thresholds: CoverageThresholds = CoverageThresholds(),
    require_chinese_graph_ready: bool = False,
) -> dict[str, object]:
    all_records = [dict(record) for record in records]
    eligible = [
        record
        for record in all_records
        if is_build_coverage_eligible(
            record,
            thresholds,
            require_chinese_graph_ready=require_chinese_graph_ready,
        )
    ]
    if fault_ids is None:
        fault_ids = sorted(
            {
                str(fault_id)
                for record in all_records
                for fault_id in (record.get("fault_class_ids") or [])
            }
        )

    coverage: dict[str, object] = {}
    for fault_id in fault_ids:
        relevant = [
            record
            for record in eligible
            if fault_id in (record.get("fault_class_ids") or [])
        ]
        symptom = len(_typed_units(relevant, SYMPTOM_TYPES, "symptom"))
        cause = len(
            _typed_units(
                relevant, CAUSE_TYPES, "cause_or_mechanism"
            )
        )
        inspection = len(
            _typed_units(
                relevant,
                INSPECTION_MAINTENANCE_TYPES,
                "inspection_or_maintenance",
            )
        )
        documents = sorted({str(item.get("doc_id", "")) for item in relevant})
        source_families = sorted(
            {
                str(item.get("source_family_id") or "")
                for item in relevant
                if item.get("source_family_id")
            }
        )
        checks = {
            "symptom_at_least_5": symptom >= thresholds.symptom,
            "cause_or_mechanism_at_least_3": (
                cause >= thresholds.cause_or_mechanism
            ),
            "inspection_or_maintenance_at_least_2": (
                inspection >= thresholds.inspection_or_maintenance
            ),
            "independent_documents_at_least_2": (
                len(documents) >= thresholds.independent_documents
            ),
            "source_families_at_least_2": (
                len(source_families) >= thresholds.source_families
            ),
        }
        coverage[str(fault_id)] = {
            "eligible_triples": len(relevant),
            "unique_evidence_units": len(
                {_evidence_id(record) for record in relevant}
            ),
            "symptom_evidence": symptom,
            "cause_or_mechanism_evidence": cause,
            "inspection_or_maintenance_evidence": inspection,
            "document_ids": documents,
            "source_families": source_families,
            "gate_checks": checks,
            "gate_passed": all(checks.values()),
        }

    return {
        "report_version": "marine_pump_strict_coverage_v2",
        "eligibility_policy": (
            "build_train + stable source_family_id + silver_candidate + confidence threshold + "
            "E1/E2 + relation entailment + non-inferred"
            + (
                " + Chinese canonical graph readiness"
                if require_chinese_graph_ready
                else ""
            )
        ),
        "require_chinese_graph_ready": require_chinese_graph_ready,
        "thresholds": asdict(thresholds),
        "input_records": len(all_records),
        "eligible_build_silver_records": len(eligible),
        "fault_coverage": coverage,
        "fault_classes_passing_gate": sum(
            bool(item["gate_passed"]) for item in coverage.values()
        ),
    }
