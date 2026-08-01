"""Strict Stage 03 validation API for marine-pump graph evidence."""

from .chinese_canonicalizer import (
    CanonicalEndpoint,
    ChineseCanonicalization,
    contains_han,
    default_terminology_path,
    detect_surface_language,
    load_chinese_terminology,
    normalize_lookup_text,
    validate_chinese_canonicalization,
)
from .confidence_policy import ConfidenceDecision, decide_confidence
from .coverage_gate import (
    CoverageThresholds,
    build_coverage_report,
    is_build_coverage_eligible,
)
from .deduplicator import (
    DeduplicationResult,
    deduplicate_triples,
    enrich_stable_ids,
    normalize_identity_text,
    stable_claim_id,
    stable_entity_id,
    stable_evidence_id,
    stable_triple_id,
)
from .evidence_span_validator import (
    E1,
    E2,
    E3,
    EvidenceSpanValidation,
    SurfaceSpan,
    locate_surface,
    validate_evidence_span,
)
from .fault_class_mapper import (
    FaultClassMapping,
    default_ontology_path,
    load_fault_ontology,
    map_fault_classes,
)
from .graph_constraint_report import (
    GraphPackage,
    generate_graph_constraint_report,
    load_graph_package,
    render_graph_constraint_report_markdown,
    write_graph_constraint_report,
)
from .relation_entailment_validator import (
    RelationEntailmentValidation,
    validate_relation_entailment,
)
from .relation_type_validator import (
    DirectionNormalization,
    RelationTypeValidation,
    load_provenance_schema,
    missing_required_fields,
    normalize_relation_direction,
    validate_relation_type,
)
from .table_alignment_validator import (
    TableAlignmentValidation,
    TableEvidenceUnit,
    validate_table_alignment,
)
from .pipeline import VALIDATOR_VERSION, validate_candidate

__all__ = [
    "ConfidenceDecision",
    "CanonicalEndpoint",
    "ChineseCanonicalization",
    "CoverageThresholds",
    "DeduplicationResult",
    "DirectionNormalization",
    "E1",
    "E2",
    "E3",
    "EvidenceSpanValidation",
    "FaultClassMapping",
    "GraphPackage",
    "RelationEntailmentValidation",
    "RelationTypeValidation",
    "SurfaceSpan",
    "TableAlignmentValidation",
    "TableEvidenceUnit",
    "VALIDATOR_VERSION",
    "build_coverage_report",
    "decide_confidence",
    "deduplicate_triples",
    "contains_han",
    "detect_surface_language",
    "default_terminology_path",
    "default_ontology_path",
    "enrich_stable_ids",
    "generate_graph_constraint_report",
    "is_build_coverage_eligible",
    "load_fault_ontology",
    "load_graph_package",
    "load_chinese_terminology",
    "load_provenance_schema",
    "locate_surface",
    "map_fault_classes",
    "missing_required_fields",
    "normalize_identity_text",
    "normalize_lookup_text",
    "normalize_relation_direction",
    "render_graph_constraint_report_markdown",
    "stable_claim_id",
    "stable_entity_id",
    "stable_evidence_id",
    "stable_triple_id",
    "validate_evidence_span",
    "validate_relation_entailment",
    "validate_relation_type",
    "validate_table_alignment",
    "validate_candidate",
    "validate_chinese_canonicalization",
    "write_graph_constraint_report",
]
