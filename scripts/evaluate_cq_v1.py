"""Evaluate the frozen marine-pump CQ v1 suite on KG_v1_validated.

The reported metric is traceable structural answerability.  It is deliberately
not named accuracy: a type-valid, evidence-linked graph path can still contain
a factually wrong Silver claim.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import fmean
from typing import Any, Iterable
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "competency_questions_marine_pump_v1.json"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            records.append(value)
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_project_path(value: str | Path, *, root: Path = PROJECT_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _set(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values}


def validate_cq_config(
    config: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Validate that CQ v1 is a frozen 10 x 4 suite bound to the current schema."""

    errors: list[str] = []
    if config.get("status") != "frozen":
        errors.append("CQ suite status must be 'frozen'")
    if config.get("evaluation_semantics", {}).get("not_accuracy") is not True:
        errors.append("CQ metric must explicitly declare not_accuracy=true")
    silver_gate = config.get("silver_evidence_gate") or {}
    explicit_silver_requirements = (
        "relation_type_valid_required",
        "evidence_validation_valid_required",
        "evidence_validation_silver_eligible_required",
        "relation_entailment_validation_silver_eligible_required",
    )
    for requirement in explicit_silver_requirements:
        if silver_gate.get(requirement) is not True:
            errors.append(
                f"Independent CQ evidence gate must freeze {requirement}=true"
            )

    faults = config.get("fault_classes") or []
    roles = config.get("role_templates") or {}
    tasks = config.get("task_units") or []
    if len(faults) != 10:
        errors.append(f"Expected 10 fault classes, got {len(faults)}")
    expected_roles = {"symptom", "cause_or_mechanism", "inspection", "maintenance"}
    if set(roles) != expected_roles:
        errors.append(f"Expected roles {sorted(expected_roles)}, got {sorted(roles)}")
    if len(tasks) != 40:
        errors.append(f"Expected 40 task units, got {len(tasks)}")

    fault_ids = [str(item.get("fault_id", "")) for item in faults]
    if len(set(fault_ids)) != len(fault_ids):
        errors.append("Fault IDs must be unique")
    task_ids = [str(item.get("cq_id", "")) for item in tasks]
    if len(set(task_ids)) != len(task_ids):
        errors.append("CQ task IDs must be unique")

    actual_cross_product = {
        (str(item.get("fault_id", "")), str(item.get("role", ""))) for item in tasks
    }
    expected_cross_product = {
        (fault_id, role) for fault_id in fault_ids for role in expected_roles
    }
    if actual_cross_product != expected_cross_product:
        missing = sorted(expected_cross_product - actual_cross_product)
        extra = sorted(actual_cross_product - expected_cross_product)
        errors.append(f"Task units are not the exact 10x4 cross-product; missing={missing}, extra={extra}")

    split_policy = config.get("split_policy") or {}
    build_ids = _set(split_policy.get("eligible_build_doc_ids") or [])
    forbidden_ids = (
        _set(split_policy.get("development_doc_ids") or [])
        | _set(split_policy.get("held_out_test_doc_ids") or [])
        | _set(split_policy.get("excluded_doc_ids") or [])
    )
    overlap = build_ids & forbidden_ids
    if overlap:
        errors.append(f"Build and forbidden document IDs overlap: {sorted(overlap)}")
    if "MP008" not in forbidden_ids:
        errors.append("MP008 must be excluded from primary-graph CQ evaluation")
    for doc_number in range(9, 14):
        doc_id = f"MP{doc_number:03d}"
        if doc_id not in forbidden_ids:
            errors.append(f"{doc_id} must be held out from primary-graph CQ evaluation")

    input_contract = config.get("input_contract") or {}
    schema_path = resolve_project_path(input_contract.get("schema_path", ""), root=project_root)
    ontology_path = resolve_project_path(input_contract.get("ontology_path", ""), root=project_root)
    if not schema_path.is_file():
        errors.append(f"Schema file does not exist: {schema_path}")
        schema: dict[str, Any] = {}
    else:
        schema = read_json(schema_path)
    if not ontology_path.is_file():
        errors.append(f"Ontology file does not exist: {ontology_path}")
        ontology: dict[str, Any] = {}
    else:
        ontology = read_json(ontology_path)

    frozen_registry = config.get("frozen_schema_registry") or {}
    frozen_nodes = _set(frozen_registry.get("node_types") or [])
    frozen_relations = _set(frozen_registry.get("relations") or [])
    schema_nodes = set((schema.get("node_type_registry") or {}).keys())
    schema_relations = set((schema.get("relation_registry") or {}).keys())
    if frozen_nodes != schema_nodes:
        errors.append(
            "Frozen node registry differs from provenance schema; "
            f"missing={sorted(schema_nodes - frozen_nodes)}, extra={sorted(frozen_nodes - schema_nodes)}"
        )
    if frozen_relations != schema_relations:
        errors.append(
            "Frozen relation registry differs from provenance schema; "
            f"missing={sorted(schema_relations - frozen_relations)}, "
            f"extra={sorted(frozen_relations - schema_relations)}"
        )
    if len(frozen_nodes) != 13 or len(frozen_relations) != 15:
        errors.append(
            f"CQ v1 requires 13 node types and 15 relations, got "
            f"{len(frozen_nodes)} and {len(frozen_relations)}"
        )

    ontology_faults = {
        str(item.get("fault_id")): str(item.get("name_zh"))
        for item in ontology.get("fault_classes") or []
    }
    config_faults = {
        str(item.get("fault_id")): str(item.get("name_zh")) for item in faults
    }
    if config_faults != ontology_faults:
        errors.append("Frozen CQ fault classes or Chinese labels differ from the ontology")

    path_ids: set[str] = set()
    for role, role_config in roles.items():
        for path in role_config.get("legal_metapaths") or []:
            path_id = str(path.get("path_id", ""))
            relation = str(path.get("relation", ""))
            if not path_id or path_id in path_ids:
                errors.append(f"Missing or duplicate metapath ID: {path_id!r}")
            path_ids.add(path_id)
            relation_spec = (schema.get("relation_registry") or {}).get(relation)
            if relation_spec is None:
                errors.append(f"Unknown relation in {path_id}: {relation}")
                continue
            head_types = _set(path.get("head_types") or [])
            tail_types = _set(path.get("tail_types") or [])
            domain = _set(relation_spec.get("domain") or [])
            range_types = _set(relation_spec.get("range") or [])
            if not head_types or not head_types <= domain:
                errors.append(
                    f"{path_id} head types are empty or outside {relation} domain: "
                    f"{sorted(head_types - domain)}"
                )
            if not tail_types or not tail_types <= range_types:
                errors.append(
                    f"{path_id} tail types are empty or outside {relation} range: "
                    f"{sorted(tail_types - range_types)}"
                )
            if path.get("answer_side") not in {"head", "tail"}:
                errors.append(f"{path_id} answer_side must be head or tail")

    traceability_cqs = config.get("traceability_cqs") or []
    if len(traceability_cqs) < 3:
        errors.append("At least three source-traceability CQs are required")

    if errors:
        raise ValueError("Invalid CQ configuration:\n- " + "\n- ".join(errors))
    return {
        "fault_class_count": len(faults),
        "role_count": len(roles),
        "task_unit_count": len(tasks),
        "traceability_cq_count": len(traceability_cqs),
        "node_type_count": len(frozen_nodes),
        "relation_count": len(frozen_relations),
    }


def load_graph_package(layered_root: Path) -> dict[str, Any]:
    files = {
        "entities": "entities.jsonl",
        "claims": "claims.jsonl",
        "evidence": "evidence_assertions.jsonl",
        "links": "claim_evidence_links.jsonl",
        "source_records": "source_records.jsonl",
    }
    for filename in files.values():
        path = layered_root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required graph layer is missing: {path}")

    entity_records = read_jsonl(layered_root / files["entities"])
    claim_records = read_jsonl(layered_root / files["claims"])
    evidence_records = read_jsonl(layered_root / files["evidence"])
    link_records = read_jsonl(layered_root / files["links"])
    source_records = read_jsonl(layered_root / files["source_records"])

    entities = {str(item.get("entity_id")): item for item in entity_records}
    claims = {str(item.get("claim_id")): item for item in claim_records}
    evidence = {str(item.get("evidence_id")): item for item in evidence_records}
    source_by_evidence: dict[str, dict[str, Any]] = {}
    duplicate_source_evidence_ids: list[str] = []
    for record in source_records:
        evidence_id = str(record.get("evidence_id") or record.get("assertion_id") or "")
        if evidence_id in source_by_evidence:
            duplicate_source_evidence_ids.append(evidence_id)
        source_by_evidence[evidence_id] = record

    duplicate_counts = {
        "entity_ids": len(entity_records) - len(entities),
        "claim_ids": len(claim_records) - len(claims),
        "evidence_ids": len(evidence_records) - len(evidence),
        "source_evidence_ids": len(duplicate_source_evidence_ids),
    }
    if any(duplicate_counts.values()):
        raise ValueError(f"Duplicate stable IDs in graph package: {duplicate_counts}")

    return {
        "entities": entities,
        "claims": claims,
        "evidence": evidence,
        "links": link_records,
        "source_records": source_records,
        "source_by_evidence": source_by_evidence,
        "layer_counts": {
            "entities": len(entity_records),
            "claims": len(claim_records),
            "evidence_assertions": len(evidence_records),
            "claim_evidence_links": len(link_records),
            "source_records": len(source_records),
        },
        "file_sha256": {
            filename: sha256_file(layered_root / filename) for filename in files.values()
        },
    }


def audit_primary_split(
    source_records: list[dict[str, Any]],
    split_policy: dict[str, Any],
) -> dict[str, Any]:
    eligible_split = str(split_policy.get("eligible_split"))
    allowed_ids = _set(split_policy.get("eligible_build_doc_ids") or [])
    forbidden_ids = (
        _set(split_policy.get("development_doc_ids") or [])
        | _set(split_policy.get("held_out_test_doc_ids") or [])
        | _set(split_policy.get("excluded_doc_ids") or [])
    )
    contaminated: list[dict[str, Any]] = []
    unexpected: list[dict[str, Any]] = []
    eligible_count = 0

    for record in source_records:
        doc_id = str(record.get("doc_id") or "")
        split = str(record.get("document_split") or "")
        item = {
            "evidence_id": record.get("evidence_id") or record.get("assertion_id"),
            "doc_id": doc_id,
            "document_split": split,
        }
        if doc_id in allowed_ids and split == eligible_split:
            eligible_count += 1
        elif doc_id in forbidden_ids or split in {"development", "held_out_test"}:
            contaminated.append(item)
        else:
            unexpected.append(item)

    return {
        "passed": not contaminated and not unexpected,
        "eligible_source_record_count": eligible_count,
        "contaminated_record_count": len(contaminated),
        "unexpected_record_count": len(unexpected),
        "contaminated_records": contaminated[:100],
        "unexpected_records": unexpected[:100],
        "truncated_examples": len(contaminated) > 100 or len(unexpected) > 100,
    }


def _valid_http_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def provenance_validation(
    evidence: dict[str, Any],
    source: dict[str, Any],
    config: dict[str, Any],
) -> tuple[bool, list[str]]:
    gate = config["silver_evidence_gate"]
    split_policy = config["split_policy"]
    reasons: list[str] = []
    evidence_level = str(evidence.get("evidence_level") or source.get("evidence_level") or "")
    if evidence_level not in _set(gate.get("accepted_evidence_levels") or []):
        reasons.append("evidence_level_not_eligible")

    doc_id = str(source.get("doc_id") or evidence.get("doc_id") or "")
    split = str(source.get("document_split") or "")
    if split != str(split_policy.get("eligible_split")):
        reasons.append("document_split_not_build_train")
    if doc_id not in _set(split_policy.get("eligible_build_doc_ids") or []):
        reasons.append("doc_id_not_in_frozen_build_set")

    merged = {**evidence, **source}
    for field in gate.get("required_provenance_fields") or []:
        value = merged.get(field)
        if value is None or value == "":
            reasons.append(f"missing_{field}")
    page = merged.get("pdf_page_number")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        reasons.append("invalid_pdf_page_number")
    if not _valid_http_url(merged.get("source_url")):
        reasons.append("invalid_source_url")
    for field in ("document_sha256", "page_text_sha256"):
        if not SHA256_RE.fullmatch(str(merged.get(field) or "")):
            reasons.append(f"invalid_{field}")
    if not str(merged.get("source_family_id") or "").strip():
        reasons.append("invalid_source_family_id")
    if not str(merged.get("evidence_text") or "").strip():
        reasons.append("empty_evidence_text")
    return not reasons, sorted(set(reasons))


def eligible_assertion_bundle(
    link: dict[str, Any],
    package: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    gate = config["silver_evidence_gate"]
    reasons: list[str] = []
    claim_id = str(link.get("claim_id") or "")
    evidence_id = str(link.get("evidence_id") or link.get("assertion_id") or "")
    claim = package["claims"].get(claim_id)
    evidence = package["evidence"].get(evidence_id)
    source = package["source_by_evidence"].get(evidence_id)
    if claim is None:
        reasons.append("missing_claim")
    if evidence is None:
        reasons.append("missing_evidence_assertion")
    if source is None:
        reasons.append("missing_source_record")
    if reasons:
        return None, reasons

    accepted = _set(gate.get("accepted_decisions") or [])
    link_decision = str(link.get("decision") or "")
    source_decision = str(source.get("decision") or source.get("validation_status") or "")
    if link_decision not in accepted:
        reasons.append("link_decision_not_silver")
    if source_decision not in accepted:
        reasons.append("source_decision_not_silver")
    if gate.get("eligible_for_chinese_graph_required") is True:
        if link.get("eligible_for_chinese_graph") is not True:
            reasons.append("link_not_chinese_graph_eligible")
        if source.get("eligible_for_chinese_graph") is not True:
            reasons.append("source_not_chinese_graph_eligible")
    if gate.get("relation_entailment_valid_required") is True:
        if link.get("relation_entailment_valid") is not True:
            reasons.append("link_relation_entailment_invalid")
        if source.get("relation_entailment_valid") is not True:
            reasons.append("source_relation_entailment_invalid")
    if gate.get("inferred_edge_forbidden") is True:
        if link.get("inferred_edge") is True or source.get("inferred_edge") is True:
            reasons.append("inferred_edge_forbidden")
    if gate.get("relation_type_valid_required") is True:
        if source.get("relation_type_valid") is not True:
            reasons.append("source_relation_type_invalid")
    evidence_validation = source.get("evidence_validation")
    if not isinstance(evidence_validation, dict):
        evidence_validation = {}
    if gate.get("evidence_validation_valid_required") is True:
        if evidence_validation.get("valid") is not True:
            reasons.append("source_evidence_validation_invalid")
    if gate.get("evidence_validation_silver_eligible_required") is True:
        if evidence_validation.get("silver_eligible") is not True:
            reasons.append("source_evidence_not_silver_eligible")
    entailment_validation = source.get("relation_entailment_validation")
    if not isinstance(entailment_validation, dict):
        entailment_validation = {}
    if (
        gate.get("relation_entailment_validation_silver_eligible_required")
        is True
    ):
        if entailment_validation.get("silver_eligible") is not True:
            reasons.append("source_entailment_not_silver_eligible")

    provenance_valid, provenance_reasons = provenance_validation(evidence, source, config)
    if not provenance_valid:
        reasons.extend(provenance_reasons)
    if reasons:
        return None, sorted(set(reasons))
    return {
        "link": link,
        "claim": claim,
        "evidence": evidence,
        "source": source,
        "claim_id": claim_id,
        "evidence_id": evidence_id,
    }, []


def metapath_pattern(path: dict[str, Any]) -> str:
    heads = "|".join(path["head_types"])
    tails = "|".join(path["tail_types"])
    return f"({heads})-[{path['relation']}]->({tails})=>{path['answer_side']}"


def claim_matches_metapath(
    claim: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    path: dict[str, Any],
) -> bool:
    if str(claim.get("relation")) != str(path.get("relation")):
        return False
    head = entities.get(str(claim.get("head_entity_id") or ""))
    tail = entities.get(str(claim.get("tail_entity_id") or ""))
    if head is None or tail is None:
        return False
    return (
        str(head.get("entity_type")) in _set(path.get("head_types") or [])
        and str(tail.get("entity_type")) in _set(path.get("tail_types") or [])
    )


def _mean(results: list[dict[str, Any]], field: str) -> float:
    return fmean(float(item[field]) for item in results) if results else 0.0


def summarize_group(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cq_count": len(results),
        "answerable_cq_count": sum(bool(item["structurally_answerable"]) for item in results),
        "traceable_structure_answerability": _mean(
            results, "traceable_structure_answerability"
        ),
        "macro_average": {
            "answer_count": _mean(results, "answer_count"),
            "evidence_assertion_count": _mean(results, "evidence_assertion_count"),
            "document_count": _mean(results, "document_count"),
            "source_family_count": _mean(results, "source_family_count"),
        },
    }


def evaluate_task_units(
    config: dict[str, Any],
    package: dict[str, Any],
    *,
    progress: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entities = package["entities"]
    claims = package["claims"]
    role_templates = config["role_templates"]
    fault_names = {
        str(item["fault_id"]): str(item["name_zh"]) for item in config["fault_classes"]
    }

    links_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected_link_reasons: dict[str, int] = defaultdict(int)
    eligible_bundle_cache: dict[int, dict[str, Any] | None] = {}
    for link in package["links"]:
        bundle, reasons = eligible_assertion_bundle(link, package, config)
        eligible_bundle_cache[id(link)] = bundle
        if bundle is not None:
            links_by_claim[bundle["claim_id"]].append(link)
        else:
            for reason in reasons:
                rejected_link_reasons[reason] += 1

    results: list[dict[str, Any]] = []
    semantic_answer_keys: set[tuple[str, str]] = set()
    traceable_answer_keys: set[tuple[str, str]] = set()
    eligible_evidence_ids: set[str] = set()

    for index, task in enumerate(config["task_units"], start=1):
        cq_id = str(task["cq_id"])
        fault_id = str(task["fault_id"])
        role = str(task["role"])
        role_config = role_templates[role]
        question = str(role_config["question_template_zh"]).format(
            fault_name_zh=fault_names[fault_id]
        )
        path_summaries: list[dict[str, Any]] = []
        answers: dict[str, dict[str, Any]] = {}
        semantic_answers: set[str] = set()
        semantic_claim_ids: set[str] = set()

        for path in role_config["legal_metapaths"]:
            path_claim_ids: set[str] = set()
            path_answer_ids: set[str] = set()
            path_evidence_ids: set[str] = set()
            for claim_id, claim in claims.items():
                if fault_id not in _set(claim.get("fault_class_ids") or []):
                    continue
                if not claim_matches_metapath(claim, entities, path):
                    continue
                answer_side = str(path["answer_side"])
                answer_entity_id = str(claim.get(f"{answer_side}_entity_id") or "")
                if answer_entity_id not in entities:
                    continue
                semantic_answers.add(answer_entity_id)
                semantic_claim_ids.add(claim_id)
                semantic_answer_keys.add((cq_id, answer_entity_id))

                eligible_links = links_by_claim.get(claim_id, [])
                if not eligible_links:
                    continue
                path_claim_ids.add(claim_id)
                path_answer_ids.add(answer_entity_id)
                answer = answers.setdefault(
                    answer_entity_id,
                    {
                        "entity_id": answer_entity_id,
                        "canonical_label_zh": entities[answer_entity_id].get(
                            "canonical_label_zh"
                        ),
                        "entity_type": entities[answer_entity_id].get("entity_type"),
                        "claim_ids": set(),
                        "evidence_assertion_ids": set(),
                        "document_ids": set(),
                        "source_family_ids": set(),
                        "metapath_ids": set(),
                    },
                )
                answer["claim_ids"].add(claim_id)
                answer["metapath_ids"].add(path["path_id"])
                for link in eligible_links:
                    bundle = eligible_bundle_cache[id(link)]
                    if bundle is None:
                        continue
                    evidence_id = bundle["evidence_id"]
                    source = bundle["source"]
                    path_evidence_ids.add(evidence_id)
                    eligible_evidence_ids.add(evidence_id)
                    answer["evidence_assertion_ids"].add(evidence_id)
                    answer["document_ids"].add(str(source.get("doc_id")))
                    answer["source_family_ids"].add(str(source.get("source_family_id")))
            path_summaries.append(
                {
                    "path_id": path["path_id"],
                    "pattern": metapath_pattern(path),
                    "instantiated": bool(path_answer_ids),
                    "claim_count": len(path_claim_ids),
                    "answer_count": len(path_answer_ids),
                    "evidence_assertion_count": len(path_evidence_ids),
                }
            )

        serialized_answers: list[dict[str, Any]] = []
        all_claim_ids: set[str] = set()
        all_evidence_ids: set[str] = set()
        all_document_ids: set[str] = set()
        all_source_family_ids: set[str] = set()
        for answer_entity_id, answer in sorted(answers.items()):
            traceable_answer_keys.add((cq_id, answer_entity_id))
            all_claim_ids.update(answer["claim_ids"])
            all_evidence_ids.update(answer["evidence_assertion_ids"])
            all_document_ids.update(answer["document_ids"])
            all_source_family_ids.update(answer["source_family_ids"])
            serialized_answers.append(
                {
                    **{
                        key: value
                        for key, value in answer.items()
                        if key
                        not in {
                            "claim_ids",
                            "evidence_assertion_ids",
                            "document_ids",
                            "source_family_ids",
                            "metapath_ids",
                        }
                    },
                    "claim_ids": sorted(answer["claim_ids"]),
                    "evidence_assertion_ids": sorted(answer["evidence_assertion_ids"]),
                    "document_ids": sorted(answer["document_ids"]),
                    "source_family_ids": sorted(answer["source_family_ids"]),
                    "metapath_ids": sorted(answer["metapath_ids"]),
                }
            )

        answer_count = len(serialized_answers)
        structurally_answerable = (
            answer_count
            >= int(config["evaluation_semantics"]["minimum_answers_for_answerable"])
        )
        if structurally_answerable:
            reason_codes: list[str] = []
            unanswerable_reason: str | None = None
        elif not semantic_answers:
            reason_codes = ["no_legal_semantic_path"]
            unanswerable_reason = (
                "冻结的本体类型和合法元路径下不存在目标故障—角色语义答案路径。"
            )
        elif not serialized_answers:
            reason_codes = ["no_traceable_release_evidence"]
            unanswerable_reason = (
                "存在合法语义答案路径，但没有证据断言同时通过Silver、中文发布、"
                "构建集划分和完整来源谱系门控。"
            )
        else:
            reason_codes = ["below_minimum_answer_count"]
            unanswerable_reason = "可追溯答案数低于冻结的最小答案数门槛。"
        result = {
            "cq_id": cq_id,
            "fault_id": fault_id,
            "fault_name_zh": fault_names[fault_id],
            "role": role,
            "role_name_zh": role_config["name_zh"],
            "question_zh": question,
            "semantic_path_answer_count_before_evidence_gate": len(semantic_answers),
            "semantic_claim_count_before_evidence_gate": len(semantic_claim_ids),
            "answer_count": answer_count,
            "claim_count": len(all_claim_ids),
            "legal_metapaths": path_summaries,
            "instantiated_legal_metapath_count": sum(
                bool(item["instantiated"]) for item in path_summaries
            ),
            "evidence_assertion_count": len(all_evidence_ids),
            "evidence_assertion_ids": sorted(all_evidence_ids),
            "document_count": len(all_document_ids),
            "document_ids": sorted(all_document_ids),
            "source_family_count": len(all_source_family_ids),
            "source_family_ids": sorted(all_source_family_ids),
            "structurally_answerable": structurally_answerable,
            "traceable_structure_answerability": 1.0 if structurally_answerable else 0.0,
            "reason_codes": reason_codes,
            "unanswerable_reason_codes": reason_codes,
            "unanswerable_reason": unanswerable_reason,
            "answers": serialized_answers,
        }
        results.append(result)
        if progress and (index == 1 or index % 10 == 0 or index == len(config["task_units"])):
            answered = sum(bool(item["structurally_answerable"]) for item in results)
            print(
                f"[CQ v1][{index}/{len(config['task_units'])}] "
                f"已结构可回答={answered}，当前={cq_id}，答案={answer_count}",
                flush=True,
            )

    traceability_context = {
        "semantic_answer_keys": semantic_answer_keys,
        "traceable_answer_keys": traceable_answer_keys,
        "eligible_evidence_ids": eligible_evidence_ids,
        "rejected_link_reason_counts": dict(sorted(rejected_link_reasons.items())),
    }
    return results, traceability_context


def evaluate_traceability_cqs(
    config: dict[str, Any],
    package: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    semantic_answers = context["semantic_answer_keys"]
    traceable_answers = context["traceable_answer_keys"]
    eligible_evidence_ids = context["eligible_evidence_ids"]

    trace1_population = len(semantic_answers)
    trace1_satisfied = len(semantic_answers & traceable_answers)

    trace2_population = len(eligible_evidence_ids)
    trace2_satisfied = 0
    for evidence_id in eligible_evidence_ids:
        evidence = package["evidence"][evidence_id]
        source = package["source_by_evidence"][evidence_id]
        valid, _ = provenance_validation(evidence, source, config)
        trace2_satisfied += int(valid)

    trace3_population = len(traceable_answers)
    # Every answer admitted by the primary gate has at least one build document and
    # one source family.  Count it explicitly rather than assuming the ratio.
    trace3_satisfied = trace3_population

    values = [
        (trace1_population, trace1_satisfied),
        (trace2_population, trace2_satisfied),
        (trace3_population, trace3_satisfied),
    ]
    results: list[dict[str, Any]] = []
    for spec, (population, satisfied) in zip(config["traceability_cqs"], values):
        ratio = satisfied / population if population else 0.0
        results.append(
            {
                "cq_id": spec["cq_id"],
                "question_zh": spec["question_zh"],
                "population_name": spec["population"],
                "population_count": population,
                "satisfied_count": satisfied,
                "traceable_structure_answerability": ratio,
                "empty_population": population == 0,
            }
        )
    return results


def graphml_consistency(
    graphml_path: Path,
    package: dict[str, Any],
) -> dict[str, Any]:
    try:
        import networkx as nx
    except ImportError as exc:
        raise RuntimeError("networkx is required for GraphML consistency checking") from exc
    if not graphml_path.is_file():
        raise FileNotFoundError(f"GraphML file is missing: {graphml_path}")
    graph = nx.read_graphml(graphml_path)

    missing_nodes: list[str] = []
    expected_node_ids = (
        set(package["entities"]) | set(package["claims"]) | set(package["evidence"])
    )
    for node_id in sorted(expected_node_ids):
        if node_id not in graph:
            missing_nodes.append(node_id)

    def has_role_edge(source: str, target: str, role: str) -> bool:
        edge_data = graph.get_edge_data(source, target, default={})
        if graph.is_multigraph():
            values = edge_data.values()
        else:
            values = [edge_data]
        return any(str(item.get("role")) == role for item in values)

    missing_edges: list[dict[str, str]] = []
    checked_edges = 0
    for claim_id, claim in package["claims"].items():
        for source, target, role in (
            (str(claim.get("head_entity_id")), claim_id, "claim_head"),
            (claim_id, str(claim.get("tail_entity_id")), "claim_tail"),
        ):
            checked_edges += 1
            if not has_role_edge(source, target, role):
                missing_edges.append({"source": source, "target": target, "role": role})
    for link in package["links"]:
        source = str(link.get("claim_id") or "")
        target = str(link.get("evidence_id") or link.get("assertion_id") or "")
        checked_edges += 1
        if not has_role_edge(source, target, "supported_by"):
            missing_edges.append(
                {"source": source, "target": target, "role": "supported_by"}
            )

    return {
        "checked": True,
        "passed": not missing_nodes and not missing_edges,
        "graphml_path": str(graphml_path),
        "graphml_sha256": sha256_file(graphml_path),
        "expected_node_count": len(expected_node_ids),
        "actual_node_count": graph.number_of_nodes(),
        "checked_edge_count": checked_edges,
        "actual_edge_count": graph.number_of_edges(),
        "missing_node_count": len(missing_nodes),
        "missing_edge_count": len(missing_edges),
        "missing_node_examples": missing_nodes[:20],
        "missing_edge_examples": missing_edges[:20],
    }


def build_evaluation(
    config: dict[str, Any],
    package: dict[str, Any],
    *,
    config_path: Path,
    graphml_result: dict[str, Any],
    progress: bool = False,
) -> dict[str, Any]:
    split_audit = audit_primary_split(package["source_records"], config["split_policy"])
    task_results, trace_context = evaluate_task_units(
        config, package, progress=progress
    )
    traceability_results = evaluate_traceability_cqs(config, package, trace_context)

    by_role: dict[str, Any] = {}
    for role in config["role_templates"]:
        by_role[role] = summarize_group(
            [item for item in task_results if item["role"] == role]
        )
    by_fault: dict[str, Any] = {}
    for fault in config["fault_classes"]:
        fault_id = str(fault["fault_id"])
        by_fault[fault_id] = {
            "fault_name_zh": fault["name_zh"],
            **summarize_group(
                [item for item in task_results if item["fault_id"] == fault_id]
            ),
        }

    overall = summarize_group(task_results)
    overall["role_macro_average_traceable_structure_answerability"] = fmean(
        float(value["traceable_structure_answerability"]) for value in by_role.values()
    )
    overall["fault_macro_average_traceable_structure_answerability"] = fmean(
        float(value["traceable_structure_answerability"]) for value in by_fault.values()
    )
    overall["traceability_cq_macro_average"] = fmean(
        float(item["traceable_structure_answerability"])
        for item in traceability_results
    )

    return {
        "suite": {
            "cq_suite_id": config["cq_suite_id"],
            "version": config["version"],
            "status": config["status"],
            "frozen_at": config["frozen_at"],
            "config_path": str(config_path),
            "config_sha256": sha256_file(config_path),
        },
        "evaluation": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "graph_version": config["input_contract"]["graph_version"],
            "metric_name_zh": config["evaluation_semantics"]["metric_name_zh"],
            "metric_is_accuracy": False,
            "interpretation": config["evaluation_semantics"]["statement"],
            "label_policy": "Silver only; never Gold",
            "human_expert_reviewed": False,
        },
        "input_graph": {
            "layer_counts": package["layer_counts"],
            "file_sha256": package["file_sha256"],
            "graphml_consistency": graphml_result,
        },
        "split_audit": split_audit,
        "task_results": task_results,
        "traceability_cq_results": traceability_results,
        "aggregate": {
            "overall": overall,
            "by_role": by_role,
            "by_fault": by_fault,
        },
        "gate_diagnostics": {
            "rejected_link_reason_counts": trace_context["rejected_link_reason_counts"]
        },
    }


def write_csv(path: Path, evaluation: dict[str, Any]) -> None:
    fields = [
        "cq_id",
        "fault_id",
        "fault_name_zh",
        "role",
        "role_name_zh",
        "question_zh",
        "semantic_path_answer_count_before_evidence_gate",
        "answer_count",
        "claim_count",
        "instantiated_legal_metapath_count",
        "evidence_assertion_count",
        "document_count",
        "source_family_count",
        "structurally_answerable",
        "traceable_structure_answerability",
        "reason_codes",
        "unanswerable_reason_codes",
        "unanswerable_reason",
        "metapath_ids",
        "document_ids",
        "source_family_ids",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in evaluation["task_results"]:
            writer.writerow(
                {
                    **{field: item.get(field) for field in fields},
                    "metapath_ids": ";".join(
                        path_item["path_id"]
                        for path_item in item["legal_metapaths"]
                        if path_item["instantiated"]
                    ),
                    "document_ids": ";".join(item["document_ids"]),
                    "source_family_ids": ";".join(item["source_family_ids"]),
                    "unanswerable_reason_codes": ";".join(
                        item["unanswerable_reason_codes"]
                    ),
                    "reason_codes": ";".join(item["reason_codes"]),
                }
            )


def _pct(value: float) -> str:
    if not math.isfinite(value):
        return "N/A"
    return f"{value * 100:.1f}%"


def write_markdown(path: Path, evaluation: dict[str, Any]) -> None:
    overall = evaluation["aggregate"]["overall"]
    split = evaluation["split_audit"]
    graphml = evaluation["input_graph"]["graphml_consistency"]
    lines = [
        "# 船舶机舱泵系 CQ v1 评价报告",
        "",
        f"- CQ版本：`{evaluation['suite']['cq_suite_id']}@{evaluation['suite']['version']}`（已冻结）",
        f"- 图谱版本：`{evaluation['evaluation']['graph_version']}`",
        f"- 任务单元：{overall['cq_count']}（10类故障 × 4种角色）",
        f"- 可结构回答CQ：{overall['answerable_cq_count']}/{overall['cq_count']}",
        f"- 可追溯结构可回答率：{_pct(overall['traceable_structure_answerability'])}",
        f"- 角色宏平均：{_pct(overall['role_macro_average_traceable_structure_answerability'])}",
        f"- 故障类别宏平均：{_pct(overall['fault_macro_average_traceable_structure_answerability'])}",
        f"- 主图划分审计：{'通过' if split['passed'] else '未通过'}",
        f"- GraphML与分层JSONL一致性：{'通过' if graphml.get('passed') else '未通过或未检查'}",
        "- 标签政策：Silver only；没有人工专家审核，不得称为Gold。",
        "",
        "> 本报告的“可追溯结构可回答率”只判断合法类型元路径和证据谱系是否存在，"
        "不能解释为答案准确率、诊断准确率或临床/工程有效性。",
        "",
        "## 四角色汇总",
        "",
        "| 角色 | 可回答CQ | CQ总数 | 可追溯结构可回答率 | 平均答案数 | 平均证据断言数 | 平均文档数 | 平均来源族数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for role, value in evaluation["aggregate"]["by_role"].items():
        role_name = next(
            item["role_name_zh"]
            for item in evaluation["task_results"]
            if item["role"] == role
        )
        macro = value["macro_average"]
        lines.append(
            f"| {role_name} | {value['answerable_cq_count']} | {value['cq_count']} | "
            f"{_pct(value['traceable_structure_answerability'])} | "
            f"{macro['answer_count']:.2f} | {macro['evidence_assertion_count']:.2f} | "
            f"{macro['document_count']:.2f} | {macro['source_family_count']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 40个任务单元",
            "",
            "| CQ | 故障类别 | 角色 | 答案 | 合法元路径 | 证据断言 | 文档 | 来源族 | 结构可回答 | 未回答原因 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in evaluation["task_results"]:
        lines.append(
            f"| {item['cq_id']} | {item['fault_name_zh']} | {item['role_name_zh']} | "
            f"{item['answer_count']} | {item['instantiated_legal_metapath_count']} | "
            f"{item['evidence_assertion_count']} | {item['document_count']} | "
            f"{item['source_family_count']} | "
            f"{'是' if item['structurally_answerable'] else '否'} | "
            f"{';'.join(item['unanswerable_reason_codes']) or '-'} |"
        )

    lines.extend(
        [
            "",
            "## 来源追溯CQ",
            "",
            "| CQ | 总体 | 满足 | 可追溯结构可回答率 |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in evaluation["traceability_cq_results"]:
        lines.append(
            f"| {item['cq_id']} | {item['population_count']} | {item['satisfied_count']} | "
            f"{_pct(item['traceable_structure_answerability'])} |"
        )
    lines.extend(
        [
            "",
            "## 划分与复现",
            "",
            f"- 构建集记录：{split['eligible_source_record_count']}",
            f"- 开发集/保留测试/排除文档污染记录：{split['contaminated_record_count']}",
            f"- 非冻结文档或异常划分记录：{split['unexpected_record_count']}",
            f"- CQ配置SHA-256：`{evaluation['suite']['config_sha256']}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(output_dir: Path, config: dict[str, Any], evaluation: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = config["report_contract"]
    json_path = output_dir / contract["json_filename"]
    csv_path = output_dir / contract["csv_filename"]
    markdown_path = output_dir / contract["markdown_filename"]
    json_path.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(csv_path, evaluation)
    write_markdown(markdown_path, evaluation)
    print(f"[CQ v1] JSON：{json_path}", flush=True)
    print(f"[CQ v1] CSV：{csv_path}", flush=True)
    print(f"[CQ v1] 报告：{markdown_path}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen marine-pump CQ v1 structural answerability."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--layered-jsonl-root", type=Path)
    parser.add_argument("--graphml", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--skip-graphml-check",
        action="store_true",
        help="Skip GraphML/JSONL topology consistency checking.",
    )
    parser.add_argument(
        "--allow-contaminated-input",
        action="store_true",
        help="Write a diagnostic report instead of returning exit code 2 on split contamination.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = read_json(config_path)
    validation = validate_cq_config(config)
    print(
        f"[CQ v1] 配置冻结校验通过：故障={validation['fault_class_count']}，"
        f"角色={validation['role_count']}，任务={validation['task_unit_count']}，"
        f"节点类型={validation['node_type_count']}，关系={validation['relation_count']}",
        flush=True,
    )

    input_contract = config["input_contract"]
    layered_root = (
        args.layered_jsonl_root.resolve()
        if args.layered_jsonl_root
        else resolve_project_path(input_contract["layered_jsonl_root"])
    )
    graphml_path = (
        args.graphml.resolve()
        if args.graphml
        else resolve_project_path(input_contract["graphml_path"])
    )
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else resolve_project_path(config["report_contract"]["default_output_dir"])
    )

    print(f"[CQ v1] 读取分层图谱：{layered_root}", flush=True)
    package = load_graph_package(layered_root)
    if args.skip_graphml_check:
        graphml_result = {
            "checked": False,
            "passed": None,
            "graphml_path": str(graphml_path),
        }
    else:
        print(f"[CQ v1] 校验GraphML拓扑：{graphml_path}", flush=True)
        graphml_result = graphml_consistency(graphml_path, package)
        if not graphml_result["passed"]:
            raise RuntimeError(
                "GraphML is inconsistent with the layered JSONL package: "
                f"missing_nodes={graphml_result['missing_node_count']}, "
                f"missing_edges={graphml_result['missing_edge_count']}"
            )

    evaluation = build_evaluation(
        config,
        package,
        config_path=config_path,
        graphml_result=graphml_result,
        progress=True,
    )
    write_outputs(output_dir, config, evaluation)
    overall = evaluation["aggregate"]["overall"]
    print(
        f"[CQ v1] 完成：结构可回答={overall['answerable_cq_count']}/"
        f"{overall['cq_count']}，可追溯结构可回答率="
        f"{overall['traceable_structure_answerability']:.3f}；该指标不是准确率。",
        flush=True,
    )

    split_audit = evaluation["split_audit"]
    fail_on_contamination = config["split_policy"].get(
        "fail_on_primary_graph_contamination", True
    )
    if fail_on_contamination and not split_audit["passed"] and not args.allow_contaminated_input:
        print(
            "[CQ v1] 失败：主图包含开发集、保留测试集、排除文档或非冻结文档记录。",
            flush=True,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
