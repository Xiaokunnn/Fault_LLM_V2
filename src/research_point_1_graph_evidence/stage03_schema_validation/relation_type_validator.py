"""Provenance-schema loading and relation/type validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RelationTypeValidation:
    valid: bool
    relation_known: bool
    head_type_known: bool
    tail_type_known: bool
    allowed_head_types: tuple[str, ...]
    allowed_tail_types: tuple[str, ...]
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DirectionNormalization:
    head: str
    head_type: str
    relation: str
    tail: str
    tail_type: str
    actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_provenance_schema(
    schema_path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> dict[str, object]:
    """Load an explicit schema or prefer v2 and fall back to v1."""

    if schema_path is not None:
        candidates = [Path(schema_path)]
    else:
        root = Path(project_root or Path.cwd())
        schema_dir = root / "data" / "kg" / "marine_pump" / "schema"
        candidates = [
            schema_dir / "provenance_schema_v2.json",
            schema_dir / "provenance_schema_v1.json",
        ]
    selected = next((path for path in candidates if path.is_file()), None)
    if selected is None:
        attempted = ", ".join(str(path) for path in candidates)
        raise FileNotFoundError(
            "No provenance schema was found. Expected v2 or v1 at: "
            f"{attempted}"
        )
    try:
        schema = json.loads(selected.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid provenance schema JSON: {selected}: {exc}") from exc
    # V2 is a normative graph-package JSON Schema.  Expose a small normalized
    # validation view without mutating the file on disk; v1 already uses this
    # normalized shape directly.
    if "node_types" not in schema:
        registry = schema.get("node_type_registry")
        if isinstance(registry, Mapping):
            schema["node_types"] = list(registry)
        else:
            enum = (
                schema.get("$defs", {})
                .get("SemanticEntityType", {})
                .get("enum", [])
                if isinstance(schema.get("$defs"), Mapping)
                else []
            )
            schema["node_types"] = enum
    if "relations" not in schema:
        registry = schema.get("relation_registry")
        if isinstance(registry, Mapping):
            schema["relations"] = list(registry)
        else:
            enum = (
                schema.get("$defs", {})
                .get("CanonicalRelation", {})
                .get("enum", [])
                if isinstance(schema.get("$defs"), Mapping)
                else []
            )
            schema["relations"] = enum
    if "relation_type_constraints" not in schema:
        registry = schema.get("relation_registry")
        if isinstance(registry, Mapping):
            schema["relation_type_constraints"] = {
                str(relation): {
                    "head_types": list(definition.get("domain", [])),
                    "tail_types": list(definition.get("range", [])),
                }
                for relation, definition in registry.items()
                if isinstance(definition, Mapping)
            }
    for field in ("node_types", "relations", "relation_type_constraints"):
        if not schema.get(field):
            raise ValueError(
                f"Provenance schema {selected} does not define usable '{field}'"
            )
    return schema


def validate_relation_type(
    *,
    relation: str,
    head_type: str,
    tail_type: str,
    schema: Mapping[str, object],
) -> RelationTypeValidation:
    node_types = {str(item) for item in schema.get("node_types", [])}
    relations = {str(item) for item in schema.get("relations", [])}
    constraints = schema.get("relation_type_constraints", {})
    constraint = constraints.get(relation, {}) if isinstance(constraints, Mapping) else {}
    allowed_heads = tuple(str(item) for item in constraint.get("head_types", []))
    allowed_tails = tuple(str(item) for item in constraint.get("tail_types", []))

    relation_known = relation in relations
    head_known = head_type in node_types
    tail_known = tail_type in node_types
    reasons: list[str] = []
    if not relation_known:
        reasons.append("unknown_relation")
    if not head_known:
        reasons.append("unknown_head_type")
    if not tail_known:
        reasons.append("unknown_tail_type")
    if relation_known and head_known and head_type not in allowed_heads:
        reasons.append("head_type_not_allowed_for_relation")
    if relation_known and tail_known and tail_type not in allowed_tails:
        reasons.append("tail_type_not_allowed_for_relation")
    return RelationTypeValidation(
        valid=not reasons,
        relation_known=relation_known,
        head_type_known=head_known,
        tail_type_known=tail_known,
        allowed_head_types=allowed_heads,
        allowed_tail_types=allowed_tails,
        reasons=tuple(reasons),
    )


def normalize_relation_direction(
    *,
    head: str,
    head_type: str,
    relation: str,
    tail: str,
    tail_type: str,
) -> DirectionNormalization:
    """Apply only direction-preserving, explicitly auditable rewrites."""

    actions: list[str] = []
    if (
        relation == "causes"
        and head_type in {"Symptom", "SignalFeature", "Risk", "FaultMode"}
        and tail_type in {"Cause", "FailureMechanism", "OperatingCondition"}
    ):
        head, tail = tail, head
        head_type, tail_type = tail_type, head_type
        actions.append("reoriented_cause_to_effect")
    if (
        relation in {"diagnosed_by", "inspected_by"}
        and head_type in {"InspectionMethod", "InspectionAction"}
        and tail_type not in {"InspectionMethod", "InspectionAction"}
    ):
        head, tail = tail, head
        head_type, tail_type = tail_type, head_type
        actions.append(f"reoriented_{relation}_target_to_method")
    # The extraction model sometimes emits a canonical relation in the
    # inverse surface order. These rewrites are type-unique and preserve the
    # proposition; they do not infer a new engineering fact.
    if (
        relation == "mitigated_by"
        and head_type == "MaintenanceAction"
        and tail_type in {"Cause", "FailureMechanism", "FaultMode", "Risk"}
    ):
        head, tail = tail, head
        head_type, tail_type = tail_type, head_type
        actions.append("reoriented_mitigated_target_to_action")
    if (
        relation == "prevented_by"
        and head_type == "MaintenanceAction"
        and tail_type
        in {
            "Cause",
            "FailureMechanism",
            "FaultMode",
            "OperatingCondition",
            "Risk",
        }
    ):
        head, tail = tail, head
        head_type, tail_type = tail_type, head_type
        actions.append("reoriented_prevented_target_to_action")
    if (
        relation == "inspected_by"
        and head_type in {"Symptom", "SignalFeature"}
        and tail_type in {"InspectionMethod", "InspectionAction"}
    ):
        relation = "diagnosed_by"
        actions.append("normalized_symptom_inspection_to_diagnosis")
    if (
        relation == "indicates"
        and head_type in {"FaultMode", "FailureMechanism"}
        and tail_type in {"Symptom", "SignalFeature"}
    ):
        relation = "manifests_as"
        actions.append("normalized_fault_indication_to_manifestation")
    if (
        relation == "manifests_as"
        and head_type in {"Cause", "OperatingCondition"}
        and tail_type in {"Symptom", "SignalFeature"}
    ):
        relation = "causes"
        actions.append("normalized_causal_manifestation_to_causes")
    if (
        relation == "contains"
        and head_type in {"Equipment", "Component"}
        and tail_type in {"FaultMode", "FailureMechanism"}
    ):
        head, tail = tail, head
        head_type, tail_type = tail_type, head_type
        relation = "occurs_at"
        actions.append("normalized_contained_fault_to_occurs_at")
    if (
        relation == "manifests_as"
        and head_type == "Component"
        and tail_type in {"FaultMode", "FailureMechanism"}
    ):
        head, tail = tail, head
        head_type, tail_type = tail_type, head_type
        relation = "occurs_at"
        actions.append("normalized_component_fault_to_occurs_at")
    if (
        relation == "mitigated_by"
        and head_type in {"Equipment", "Component"}
        and tail_type == "MaintenanceAction"
    ):
        relation = "maintained_by"
        actions.append("normalized_component_mitigation_to_maintenance")
    if (
        relation == "causes"
        and head_type in {"Symptom", "SignalFeature"}
        and tail_type in {"Cause", "FailureMechanism", "FaultMode"}
    ):
        relation = "indicates"
        actions.append("normalized_symptom_causation_to_indication")
    return DirectionNormalization(
        head=head,
        head_type=head_type,
        relation=relation,
        tail=tail,
        tail_type=tail_type,
        actions=tuple(actions),
    )


def missing_required_fields(
    record: Mapping[str, object],
    schema: Mapping[str, object],
    *,
    record_kind: str | None = None,
) -> tuple[str, ...]:
    required: object
    definitions = schema.get("$defs")
    if isinstance(definitions, Mapping):
        kind = record_kind or "EvidenceAssertion"
        definition = definitions.get(kind)
        if not isinstance(definition, Mapping):
            raise ValueError(
                f"Provenance schema does not define record kind '{kind}'"
            )
        required = definition.get("required", [])
    else:
        required = schema.get("required_fields", [])
    if not isinstance(required, Sequence) or isinstance(required, (str, bytes)):
        raise ValueError("Schema required-field declaration must be an array")
    missing = [
        str(field)
        for field in required
        if field not in record or record.get(str(field)) in (None, "")
    ]
    return tuple(missing)
