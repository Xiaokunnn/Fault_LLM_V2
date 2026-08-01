"""Executable constraint audit for versioned marine-pump graph packages.

This module deliberately implements a project-specific Python validation
profile.  It reuses the relation registry and Chinese terminology rules that
already govern the extraction pipeline, but it is neither a complete JSON
Schema validator nor an RDF/SHACL validator.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse

from .chinese_canonicalizer import (
    contains_han,
    load_chinese_terminology,
    validate_chinese_canonicalization,
)
from .deduplicator import (
    stable_claim_id,
    stable_entity_id,
    stable_evidence_id,
    stable_triple_id,
)
from .relation_type_validator import (
    load_provenance_schema,
    validate_relation_type,
)


REPORT_VERSION = "marine_pump_graph_constraint_report_v1"
VALIDATOR_KIND = "custom_python_graph_constraint_profile"
PRIMARY_GRAPH_VERSIONS = ("KG_v1_raw", "KG_v1_validated")
SILVER_DECISIONS = {"silver_candidate", "accepted_silver"}
ALLOWED_DECISIONS = {
    *SILVER_DECISIONS,
    "candidate_needs_review",
    "context_only_reviewed",
    "rejected",
}
ALLOWED_EVIDENCE_LEVELS = {"E1", "E2"}
CORE_PROVENANCE_FIELDS = (
    "doc_id",
    "document_split",
    "publisher",
    "source_family_id",
    "source_url",
    "document_sha256",
    "page_text_sha256",
    "pdf_page_number",
    "evidence_text",
    "evidence_level",
    "source_language",
)
IMMUTABLE_SOURCE_FIELDS = (
    "head_surface",
    "tail_surface",
    "relation",
    "evidence_text",
    "doc_id",
    "pdf_page_number",
    "source_url",
    "document_sha256",
    "page_text_sha256",
)
HASH_PATTERN = re.compile(r"^[0-9A-Fa-f]{64}$")


@dataclass(frozen=True)
class GraphPackage:
    """The five JSONL layers emitted by the current graph builder."""

    version: str
    directory: Path
    source_records: tuple[dict[str, object], ...]
    entities: tuple[dict[str, object], ...]
    claims: tuple[dict[str, object], ...]
    evidence_assertions: tuple[dict[str, object], ...]
    claim_evidence_links: tuple[dict[str, object], ...]
    file_metadata: dict[str, dict[str, object]]
    missing_files: tuple[str, ...] = ()


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at {path}:{line_number}: {error}"
                ) from error
            if not isinstance(value, dict):
                raise ValueError(
                    f"JSONL record at {path}:{line_number} must be an object"
                )
            records.append(value)
    return tuple(records)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_graph_package(graph_root: Path, version: str) -> GraphPackage:
    """Load a graph package without silently inventing a missing layer."""

    triple_dir = graph_root / "triples" / version
    layer_names = {
        "source_records": "source_records.jsonl",
        "entities": "entities.jsonl",
        "claims": "claims.jsonl",
        "evidence_assertions": "evidence_assertions.jsonl",
        "claim_evidence_links": "claim_evidence_links.jsonl",
    }
    layers: dict[str, tuple[dict[str, object], ...]] = {}
    metadata: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    for key, file_name in layer_names.items():
        path = triple_dir / file_name
        if not path.is_file():
            layers[key] = ()
            missing.append(path.as_posix())
            continue
        layers[key] = _read_jsonl(path)
        metadata[key] = {
            "path": path.as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "records": len(layers[key]),
        }
    return GraphPackage(
        version=version,
        directory=triple_dir,
        source_records=layers["source_records"],
        entities=layers["entities"],
        claims=layers["claims"],
        evidence_assertions=layers["evidence_assertions"],
        claim_evidence_links=layers["claim_evidence_links"],
        file_metadata=metadata,
        missing_files=tuple(missing),
    )


def _record_ref(record: Mapping[str, object]) -> str:
    return str(
        record.get("triple_id")
        or record.get("assertion_id")
        or record.get("evidence_id")
        or record.get("claim_id")
        or record.get("entity_id")
        or f"{record.get('doc_id', '?')}:p{record.get('pdf_page_number', '?')}"
    )


def _is_http_url(value: object) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _index_unique(
    records: Sequence[Mapping[str, object]],
    field: str,
) -> tuple[dict[str, Mapping[str, object]], list[dict[str, object]]]:
    index: dict[str, Mapping[str, object]] = {}
    violations: list[dict[str, object]] = []
    for record in records:
        value = str(record.get(field) or "")
        if not value:
            violations.append(
                {"record": _record_ref(record), "reason": f"missing_{field}"}
            )
            continue
        if value in index:
            violations.append(
                {"record": value, "reason": f"duplicate_{field}"}
            )
            continue
        index[value] = record
    return index, violations


def _source_pair(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        str(record.get("claim_id") or ""),
        str(record.get("evidence_id") or record.get("assertion_id") or ""),
    )


class _ReportBuilder:
    def __init__(self) -> None:
        self.checks: list[dict[str, object]] = []

    def add(
        self,
        *,
        rule_id: str,
        title: str,
        scope: str,
        description: str,
        evaluated: int,
        violations: Iterable[Mapping[str, object] | str],
        failure_severity: str = "error",
        release_blocking: bool = True,
        example_limit: int = 8,
    ) -> None:
        values = list(violations)
        failed = bool(values)
        self.checks.append(
            {
                "rule_id": rule_id,
                "title": title,
                "scope": scope,
                "description": description,
                "status": "fail" if failed else "pass",
                "severity": failure_severity if failed else "info",
                "failure_severity": failure_severity,
                "evaluated": evaluated,
                "violation_count": len(values),
                "release_blocking": bool(
                    failed
                    and release_blocking
                    and failure_severity == "error"
                ),
                "examples": values[:example_limit],
            }
        )

    def note(
        self,
        *,
        rule_id: str,
        title: str,
        scope: str,
        description: str,
        count: int = 0,
        examples: Iterable[Mapping[str, object] | str] = (),
    ) -> None:
        self.checks.append(
            {
                "rule_id": rule_id,
                "title": title,
                "scope": scope,
                "description": description,
                "status": "info",
                "severity": "info",
                "failure_severity": "info",
                "evaluated": count,
                "violation_count": 0,
                "release_blocking": False,
                "examples": list(examples)[:8],
            }
        )


def _records_requiring_release_integrity(
    package: GraphPackage,
) -> tuple[dict[str, object], ...]:
    if package.version == "KG_v1_validated":
        return package.source_records
    return tuple(
        record
        for record in package.source_records
        if str(record.get("decision") or record.get("validation_status") or "")
        in SILVER_DECISIONS
    )


def _check_package_structure(
    package: GraphPackage,
    builder: _ReportBuilder,
) -> dict[str, dict[str, Mapping[str, object]]]:
    scope = package.version
    builder.add(
        rule_id="PKG001_REQUIRED_LAYER_FILES",
        title="五个分层JSONL文件均存在",
        scope=scope,
        description=(
            "检查source_records、entities、claims、evidence_assertions和"
            "claim_evidence_links；这是当前项目图谱包结构检查。"
        ),
        evaluated=5,
        violations=package.missing_files,
    )

    entity_index, entity_duplicates = _index_unique(package.entities, "entity_id")
    claim_index, claim_duplicates = _index_unique(package.claims, "claim_id")
    evidence_index, evidence_duplicates = _index_unique(
        package.evidence_assertions, "evidence_id"
    )
    source_index, source_duplicates = _index_unique(
        package.source_records, "triple_id"
    )
    duplicate_violations = [
        *entity_duplicates,
        *claim_duplicates,
        *evidence_duplicates,
        *source_duplicates,
    ]
    builder.add(
        rule_id="PKG002_UNIQUE_STABLE_IDENTIFIERS",
        title="分层记录ID唯一且非空",
        scope=scope,
        description="检查实体、Claim、Evidence和源记录的稳定ID唯一性。",
        evaluated=(
            len(package.entities)
            + len(package.claims)
            + len(package.evidence_assertions)
            + len(package.source_records)
        ),
        violations=duplicate_violations,
    )

    links_by_claim: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    link_pairs: set[tuple[str, str]] = set()
    link_violations: list[dict[str, object]] = []
    duplicate_pairs: set[tuple[str, str]] = set()
    for link in package.claim_evidence_links:
        claim = str(link.get("claim_id") or "")
        evidence = str(link.get("evidence_id") or "")
        pair = (claim, evidence)
        if not claim or claim not in claim_index:
            link_violations.append(
                {"record": _record_ref(link), "reason": "link_claim_missing"}
            )
        if not evidence or evidence not in evidence_index:
            link_violations.append(
                {"record": _record_ref(link), "reason": "link_evidence_missing"}
            )
        if pair in link_pairs:
            duplicate_pairs.add(pair)
        link_pairs.add(pair)
        links_by_claim[claim].append(link)
    link_violations.extend(
        {
            "record": f"{claim}|{evidence}",
            "reason": "duplicate_claim_evidence_link",
        }
        for claim, evidence in sorted(duplicate_pairs)
    )
    builder.add(
        rule_id="PKG003_LINK_TARGETS_AND_UNIQUENESS",
        title="Claim—Evidence链接稳定且目标存在",
        scope=scope,
        description=(
            "每条链接必须引用存在的Claim和Evidence，同一二元链接不得重复。"
        ),
        evaluated=len(package.claim_evidence_links),
        violations=link_violations,
    )

    unsupported_claims = [
        {"record": claim_id, "reason": "claim_has_no_evidence_link"}
        for claim_id in claim_index
        if not links_by_claim.get(claim_id)
    ]
    builder.add(
        rule_id="PKG004_CLAIM_HAS_EVIDENCE",
        title="每个Claim至少关联一条Evidence",
        scope=scope,
        description="Claim本身不是证据，发布和审计Claim均须保留断言链接。",
        evaluated=len(package.claims),
        violations=unsupported_claims,
    )

    orphan_evidence = [
        {"record": evidence_id, "reason": "evidence_has_no_claim_link"}
        for evidence_id in evidence_index
        if not any(pair[1] == evidence_id for pair in link_pairs)
    ]
    builder.add(
        rule_id="PKG005_EVIDENCE_HAS_CLAIM_LINK",
        title="每条Evidence至少被一个Claim引用",
        scope=scope,
        description="检测分层输出中的孤立证据记录。",
        evaluated=len(package.evidence_assertions),
        violations=orphan_evidence,
    )

    source_link_violations: list[dict[str, object]] = []
    for record in package.source_records:
        pair = _source_pair(record)
        if pair not in link_pairs:
            source_link_violations.append(
                {
                    "record": _record_ref(record),
                    "reason": "source_record_link_pair_missing",
                    "claim_id": pair[0],
                    "evidence_id": pair[1],
                }
            )
    link_source_pairs = {_source_pair(record) for record in package.source_records}
    for pair in link_pairs:
        if pair not in link_source_pairs:
            source_link_violations.append(
                {
                    "record": f"{pair[0]}|{pair[1]}",
                    "reason": "link_has_no_source_record",
                }
            )
    builder.add(
        rule_id="PKG006_SOURCE_RECORD_LINK_COVERAGE",
        title="源记录与Claim—Evidence链接双向覆盖",
        scope=scope,
        description="源记录中的Claim/Evidence对必须与链接层一一对应。",
        evaluated=len(package.source_records) + len(package.claim_evidence_links),
        violations=source_link_violations,
    )

    return {
        "entities": entity_index,
        "claims": claim_index,
        "evidence": evidence_index,
        "sources": source_index,
    }


def _check_status_split_and_leakage(
    package: GraphPackage,
    *,
    build_doc_ids: set[str],
    forbidden_doc_ids: set[str],
    builder: _ReportBuilder,
) -> None:
    scope = package.version
    invalid_status = [
        {
            "record": _record_ref(record),
            "decision": record.get("decision"),
            "reason": "unknown_decision",
        }
        for record in package.source_records
        if str(record.get("decision") or record.get("validation_status") or "")
        not in ALLOWED_DECISIONS
    ]
    builder.add(
        rule_id="GOV001_ALLOWED_GOVERNANCE_STATUS",
        title="治理状态属于冻结枚举",
        scope=scope,
        description=(
            "允许Silver、待复核/隔离、背景复核和拒绝状态；本检查兼容"
            "silver_candidate与accepted_silver两个历史码。"
        ),
        evaluated=len(package.source_records),
        violations=invalid_status,
    )

    leakage: list[dict[str, object]] = []
    for record in package.source_records:
        doc_id = str(record.get("doc_id") or "")
        split = str(record.get("document_split") or "")
        if (
            doc_id in forbidden_doc_ids
            or doc_id not in build_doc_ids
            or split != "build_train"
        ):
            leakage.append(
                {
                    "record": _record_ref(record),
                    "doc_id": doc_id,
                    "document_split": split,
                    "reason": "primary_graph_split_leakage",
                }
            )
    builder.add(
        rule_id="SPLIT001_PRIMARY_GRAPH_BUILD_ONLY",
        title="主图谱不含开发集或保留测试集",
        scope=scope,
        description=(
            "KG_v1_raw与KG_v1_validated都是主图谱资产，只允许冻结的"
            "build_train文档。"
        ),
        evaluated=len(package.source_records),
        violations=leakage,
    )

    if package.version == "KG_v1_validated":
        non_silver = [
            {
                "record": _record_ref(record),
                "decision": record.get("decision"),
                "reason": "validated_record_not_silver",
            }
            for record in package.source_records
            if str(record.get("decision") or record.get("validation_status") or "")
            not in SILVER_DECISIONS
        ]
        builder.add(
            rule_id="GOV002_VALIDATED_ONLY_SILVER",
            title="发布图只包含Silver记录",
            scope=scope,
            description="待复核和拒绝记录只能保留在审计图。",
            evaluated=len(package.source_records),
            violations=non_silver,
        )
    else:
        builder.note(
            rule_id="GOV003_RAW_STATUS_DISTRIBUTION",
            title="审计图治理状态分布",
            scope=scope,
            description="审计图保留全部状态，此项仅报告分布，不作为发布错误。",
            count=len(package.source_records),
            examples=[
                {
                    "decision_counts": dict(
                        Counter(
                            str(
                                record.get("decision")
                                or record.get("validation_status")
                                or ""
                            )
                            for record in package.source_records
                        )
                    )
                }
            ],
        )


def _check_provenance(
    package: GraphPackage,
    builder: _ReportBuilder,
) -> None:
    scope = package.version
    release_records = _records_requiring_release_integrity(package)
    missing: list[dict[str, object]] = []
    malformed: list[dict[str, object]] = []
    for record in release_records:
        missing_fields = [
            field
            for field in CORE_PROVENANCE_FIELDS
            if record.get(field) in (None, "")
        ]
        if missing_fields:
            missing.append(
                {
                    "record": _record_ref(record),
                    "reason": "missing_core_provenance",
                    "fields": missing_fields,
                }
            )
        page = record.get("pdf_page_number")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            malformed.append(
                {
                    "record": _record_ref(record),
                    "reason": "invalid_physical_pdf_page",
                    "value": page,
                }
            )
        if not _is_http_url(record.get("source_url")):
            malformed.append(
                {
                    "record": _record_ref(record),
                    "reason": "invalid_source_url",
                    "value": record.get("source_url"),
                }
            )
        for field in ("document_sha256", "page_text_sha256"):
            if not HASH_PATTERN.fullmatch(str(record.get(field) or "")):
                malformed.append(
                    {
                        "record": _record_ref(record),
                        "reason": f"invalid_{field}",
                        "value": record.get(field),
                    }
                )
    builder.add(
        rule_id="PROV001_CORE_FIELDS_PRESENT",
        title="Silver/发布记录具有核心溯源字段",
        scope=scope,
        description=(
            "检查文档、划分、发布者、来源族、URL、文档/页面哈希、"
            "物理页、原文、证据等级和来源语言。"
        ),
        evaluated=len(release_records),
        violations=missing,
    )
    builder.add(
        rule_id="PROV002_PAGE_URL_HASH_FORMAT",
        title="物理页、URL和哈希格式有效",
        scope=scope,
        description="物理页必须为正整数，URL必须为HTTP(S)，哈希为64位十六进制。",
        evaluated=len(release_records),
        violations=malformed,
    )

    nonrelease_missing = [
        {
            "record": _record_ref(record),
            "reason": "nonrelease_record_missing_evidence_text",
        }
        for record in package.source_records
        if record not in release_records
        and record.get("evidence_text") in (None, "")
    ]
    builder.add(
        rule_id="PROV003_NONRELEASE_EVIDENCE_GAPS",
        title="非发布记录的原文缺失审计",
        scope=scope,
        description=(
            "拒绝项允许因证据缺失而存在于审计图；此项作为warning记录，"
            "不阻止已经合格的发布子集。"
        ),
        evaluated=len(package.source_records) - len(release_records),
        violations=nonrelease_missing,
        failure_severity="warning",
        release_blocking=False,
    )


def _check_evidence_and_relation(
    package: GraphPackage,
    *,
    schema: Mapping[str, object],
    builder: _ReportBuilder,
) -> None:
    scope = package.version
    release_records = _records_requiring_release_integrity(package)
    evidence_violations: list[dict[str, object]] = []
    relation_violations: list[dict[str, object]] = []
    stable_id_violations: list[dict[str, object]] = []

    for record in release_records:
        reference = _record_ref(record)
        level = str(record.get("evidence_level") or "")
        if level not in ALLOWED_EVIDENCE_LEVELS:
            evidence_violations.append(
                {
                    "record": reference,
                    "reason": "release_evidence_not_e1_or_e2",
                    "value": level,
                }
            )
        if record.get("inferred_edge") is True:
            evidence_violations.append(
                {"record": reference, "reason": "release_record_is_inferred"}
            )
        if record.get("relation_entailment_valid") is not True:
            evidence_violations.append(
                {
                    "record": reference,
                    "reason": "relation_entailment_not_valid",
                }
            )
        validation = record.get("evidence_validation")
        if not isinstance(validation, Mapping) or validation.get("valid") is not True:
            evidence_violations.append(
                {"record": reference, "reason": "evidence_validation_not_valid"}
            )
        if level == "E1":
            start, end = record.get("evidence_start"), record.get("evidence_end")
            if (
                not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or start < 0
                or end <= start
            ):
                evidence_violations.append(
                    {
                        "record": reference,
                        "reason": "e1_offsets_invalid",
                        "start": start,
                        "end": end,
                    }
                )
        elif level == "E2":
            units = record.get("evidence_units")
            if not isinstance(units, list) or not units:
                evidence_violations.append(
                    {"record": reference, "reason": "e2_units_missing"}
                )
            else:
                for unit in units:
                    if not isinstance(unit, Mapping):
                        evidence_violations.append(
                            {
                                "record": reference,
                                "reason": "e2_unit_not_object",
                            }
                        )
                        continue
                    bbox = unit.get("bbox")
                    if (
                        not unit.get("table_id")
                        or not unit.get("row_id")
                        or not str(unit.get("text") or "").strip()
                        or not isinstance(bbox, list)
                        or len(bbox) != 4
                    ):
                        evidence_violations.append(
                            {
                                "record": reference,
                                "reason": "e2_unit_geometry_or_identity_invalid",
                                "unit": unit.get("cell_id"),
                            }
                        )

        relation_result = validate_relation_type(
            relation=str(record.get("relation") or ""),
            head_type=str(record.get("head_type") or ""),
            tail_type=str(record.get("tail_type") or ""),
            schema=schema,
        )
        if not relation_result.valid or record.get("relation_type_valid") is not True:
            relation_violations.append(
                {
                    "record": reference,
                    "reason": "relation_registry_or_domain_range_invalid",
                    "details": list(relation_result.reasons),
                }
            )

        expected_head = stable_entity_id(
            str(record.get("head_canonical_zh") or record.get("head") or ""),
            str(record.get("head_type") or ""),
            terminology_id=(
                str(record.get("head_terminology_id"))
                if record.get("head_terminology_id")
                else None
            ),
        )
        expected_tail = stable_entity_id(
            str(record.get("tail_canonical_zh") or record.get("tail") or ""),
            str(record.get("tail_type") or ""),
            terminology_id=(
                str(record.get("tail_terminology_id"))
                if record.get("tail_terminology_id")
                else None
            ),
        )
        expected_claim = stable_claim_id(
            expected_head,
            str(record.get("relation") or ""),
            expected_tail,
        )
        expected_evidence = stable_evidence_id(record, claim_id=expected_claim)
        expected_triple = stable_triple_id(expected_claim, expected_evidence)
        expected_values = {
            "head_entity_id": expected_head,
            "tail_entity_id": expected_tail,
            "claim_id": expected_claim,
            "evidence_id": expected_evidence,
            "assertion_id": expected_evidence,
            "triple_id": expected_triple,
        }
        mismatches = {
            field: {"actual": record.get(field), "expected": value}
            for field, value in expected_values.items()
            if str(record.get(field) or "") != value
        }
        if mismatches:
            stable_id_violations.append(
                {
                    "record": reference,
                    "reason": "stable_identifier_mismatch",
                    "fields": mismatches,
                }
            )

    builder.add(
        rule_id="EVID001_RELEASE_E1_E2_NONINFERRED_ENTAILED",
        title="Silver/发布记录为有效E1/E2且非推断",
        scope=scope,
        description=(
            "检查证据等级、位置、E2单元格结构、证据验证状态、蕴含状态"
            "和inferred_edge。"
        ),
        evaluated=len(release_records),
        violations=evidence_violations,
    )
    builder.add(
        rule_id="REL001_REGISTRY_DOMAIN_RANGE",
        title="Silver/发布关系符合注册表与Domain/Range",
        scope=scope,
        description="复用provenance_schema_v3关系注册表和本地类型校验器。",
        evaluated=len(release_records),
        violations=relation_violations,
    )
    builder.add(
        rule_id="ID001_STABLE_SOURCE_IDENTIFIERS",
        title="Silver/发布源记录稳定ID可重算",
        scope=scope,
        description=(
            "按当前实体、Claim、Evidence和Triple确定性身份函数重算并比对。"
        ),
        evaluated=len(release_records),
        violations=stable_id_violations,
    )

    nonrelease_invalid = []
    if package.version == "KG_v1_raw":
        for record in package.source_records:
            if record in release_records:
                continue
            result = validate_relation_type(
                relation=str(record.get("relation") or ""),
                head_type=str(record.get("head_type") or ""),
                tail_type=str(record.get("tail_type") or ""),
                schema=schema,
            )
            if not result.valid:
                nonrelease_invalid.append(
                    {
                        "record": _record_ref(record),
                        "decision": record.get("decision"),
                        "reasons": list(result.reasons),
                    }
                )
        builder.note(
            rule_id="REL002_RAW_NONRELEASE_INVALID_RELATIONS",
            title="审计图非发布记录中的关系违规分布",
            scope=scope,
            description=(
                "Raw图按设计保留待审和拒绝记录；这些违规只作误差分析，"
                "不表示它们可进入发布图。"
            ),
            count=len(nonrelease_invalid),
            examples=nonrelease_invalid,
        )


def _check_layer_semantics(
    package: GraphPackage,
    indexes: Mapping[str, Mapping[str, Mapping[str, object]]],
    builder: _ReportBuilder,
) -> None:
    scope = package.version
    entities = indexes["entities"]
    claims = indexes["claims"]
    evidence = indexes["evidence"]
    violations: list[dict[str, object]] = []
    for record in package.source_records:
        reference = _record_ref(record)
        head_id = str(record.get("head_entity_id") or "")
        tail_id = str(record.get("tail_entity_id") or "")
        claim_id = str(record.get("claim_id") or "")
        evidence_id = str(record.get("evidence_id") or "")
        head = entities.get(head_id)
        tail = entities.get(tail_id)
        claim = claims.get(claim_id)
        assertion = evidence.get(evidence_id)
        if head is None or tail is None or claim is None or assertion is None:
            violations.append(
                {
                    "record": reference,
                    "reason": "source_record_layer_object_missing",
                }
            )
            continue
        if (
            str(claim.get("head_entity_id") or "") != head_id
            or str(claim.get("tail_entity_id") or "") != tail_id
            or str(claim.get("relation") or "")
            != str(record.get("relation") or "")
        ):
            violations.append(
                {"record": reference, "reason": "claim_projection_mismatch"}
            )
        if (
            str(assertion.get("doc_id") or "") != str(record.get("doc_id") or "")
            or assertion.get("pdf_page_number") != record.get("pdf_page_number")
            or str(assertion.get("evidence_text") or "")
            != str(record.get("evidence_text") or "")
            or str(assertion.get("source_url") or "")
            != str(record.get("source_url") or "")
        ):
            violations.append(
                {"record": reference, "reason": "evidence_projection_mismatch"}
            )
    builder.add(
        rule_id="PKG007_LAYER_PROJECTION_CONSISTENCY",
        title="源记录与实体/Claim/Evidence投影一致",
        scope=scope,
        description="检查分层JSONL没有改变源记录的语义和证据主字段。",
        evaluated=len(package.source_records),
        violations=violations,
    )


def _check_chinese_release(
    package: GraphPackage,
    *,
    terminology: Mapping[str, object],
    builder: _ReportBuilder,
) -> None:
    if package.version != "KG_v1_validated":
        return
    violations: list[dict[str, object]] = []
    eligible_statuses = {
        str(value)
        for value in (
            terminology.get("policy", {}).get("eligible_translation_statuses", [])
            if isinstance(terminology.get("policy"), Mapping)
            else []
        )
    }
    relation_labels = terminology.get("relation_labels_zh", {})
    type_labels = terminology.get("node_type_labels_zh", {})
    for record in package.source_records:
        reference = _record_ref(record)
        canonical = validate_chinese_canonicalization(
            head_surface=str(
                record.get("head_surface") or record.get("head") or ""
            ),
            head_type=str(record.get("head_type") or ""),
            relation=str(record.get("relation") or ""),
            tail_surface=str(
                record.get("tail_surface") or record.get("tail") or ""
            ),
            tail_type=str(record.get("tail_type") or ""),
            candidate=record,
            terminology=terminology,
        )
        reasons: list[str] = []
        if record.get("eligible_for_chinese_graph") is not True:
            reasons.append("record_not_marked_chinese_graph_eligible")
        if not canonical.graph_ready:
            reasons.extend(canonical.reasons or ("canonicalization_not_ready",))
        for side, endpoint in (("head", canonical.head), ("tail", canonical.tail)):
            if not contains_han(endpoint.canonical_label_zh):
                reasons.append(f"{side}_canonical_label_has_no_han")
            if not endpoint.terminology_id:
                reasons.append(f"{side}_terminology_id_missing")
            if endpoint.translation_status not in eligible_statuses:
                reasons.append(f"{side}_translation_status_not_eligible")
            if not endpoint.protected_terms_valid:
                reasons.append(f"{side}_protected_terms_not_preserved")
        relation = str(record.get("relation") or "")
        head_type = str(record.get("head_type") or "")
        tail_type = str(record.get("tail_type") or "")
        if (
            not isinstance(relation_labels, Mapping)
            or not contains_han(relation_labels.get(relation))
        ):
            reasons.append("relation_chinese_label_missing")
        if (
            not isinstance(type_labels, Mapping)
            or not contains_han(type_labels.get(head_type))
            or not contains_han(type_labels.get(tail_type))
        ):
            reasons.append("entity_type_chinese_label_missing")
        if reasons:
            violations.append(
                {
                    "record": reference,
                    "reason": "chinese_release_endpoint_invalid",
                    "details": list(dict.fromkeys(reasons)),
                }
            )
    entity_violations = [
        {
            "record": _record_ref(entity),
            "reason": "validated_entity_chinese_or_terminology_missing",
        }
        for entity in package.entities
        if not contains_han(entity.get("canonical_label_zh"))
        or not entity.get("terminology_id")
        or entity.get("graph_display_language") != "zh-CN"
    ]
    builder.add(
        rule_id="ZH001_RELEASE_ENDPOINT_GOVERNANCE",
        title="发布端点满足中文术语门控",
        scope=package.version,
        description=(
            "检查中文规范名、术语ID、允许的翻译状态、受保护词以及"
            "关系/类型中文显示名。"
        ),
        evaluated=len(package.source_records),
        violations=violations,
    )
    builder.add(
        rule_id="ZH002_RELEASE_ENTITY_PROJECTION",
        title="发布实体具有中文规范名和术语ID",
        scope=package.version,
        description="检查Validated实体投影，不以英文surface冒充中文实体。",
        evaluated=len(package.entities),
        violations=entity_violations,
    )


def _check_release_projection(
    raw: GraphPackage,
    validated: GraphPackage,
    builder: _ReportBuilder,
) -> None:
    raw_by_triple = {
        str(record.get("triple_id") or ""): record
        for record in raw.source_records
        if record.get("triple_id")
    }
    violations: list[dict[str, object]] = []
    for record in validated.source_records:
        triple_id = str(record.get("triple_id") or "")
        source = raw_by_triple.get(triple_id)
        if source is None:
            violations.append(
                {
                    "record": _record_ref(record),
                    "reason": "validated_record_not_in_raw_audit_graph",
                }
            )
            continue
        changed = [
            field
            for field in IMMUTABLE_SOURCE_FIELDS
            if source.get(field) != record.get(field)
        ]
        if changed:
            violations.append(
                {
                    "record": _record_ref(record),
                    "reason": "immutable_source_field_changed",
                    "fields": changed,
                }
            )
    builder.add(
        rule_id="RELEASE001_VALIDATED_SUBSET_WITH_IMMUTABLE_EVIDENCE",
        title="发布记录可回溯到Raw且原文溯源未变",
        scope="KG_v1_raw -> KG_v1_validated",
        description=(
            "Validated记录必须存在于Raw审计图，原文surface、证据、页码、"
            "URL及文档/页面哈希保持不变。"
        ),
        evaluated=len(validated.source_records),
        violations=violations,
    )


def generate_graph_constraint_report(
    *,
    project_root: Path,
    graph_root: Path,
    schema_path: Path,
    terminology_path: Path,
    split_path: Path,
    raw_version: str = PRIMARY_GRAPH_VERSIONS[0],
    validated_version: str = PRIMARY_GRAPH_VERSIONS[1],
) -> dict[str, object]:
    """Generate the machine-readable report without mutating graph artifacts."""

    schema = load_provenance_schema(schema_path, project_root=project_root)
    terminology = load_chinese_terminology(
        terminology_path,
        project_root=project_root,
    )
    split = json.loads(split_path.read_text(encoding="utf-8"))
    build_doc_ids = {str(value) for value in split.get("build_train_doc_ids", [])}
    forbidden_doc_ids = {
        str(value)
        for key in ("development_doc_ids", "held_out_test_doc_ids")
        for value in split.get(key, [])
    }
    raw = load_graph_package(graph_root, raw_version)
    validated = load_graph_package(graph_root, validated_version)
    builder = _ReportBuilder()
    package_summaries: dict[str, object] = {}

    for package in (raw, validated):
        indexes = _check_package_structure(package, builder)
        _check_status_split_and_leakage(
            package,
            build_doc_ids=build_doc_ids,
            forbidden_doc_ids=forbidden_doc_ids,
            builder=builder,
        )
        _check_provenance(package, builder)
        _check_evidence_and_relation(package, schema=schema, builder=builder)
        _check_layer_semantics(package, indexes, builder)
        _check_chinese_release(
            package,
            terminology=terminology,
            builder=builder,
        )
        package_summaries[package.version] = {
            "directory": package.directory.as_posix(),
            "records": {
                "source_records": len(package.source_records),
                "entities": len(package.entities),
                "claims": len(package.claims),
                "evidence_assertions": len(package.evidence_assertions),
                "claim_evidence_links": len(package.claim_evidence_links),
            },
            "decision_counts": dict(
                Counter(
                    str(
                        record.get("decision")
                        or record.get("validation_status")
                        or ""
                    )
                    for record in package.source_records
                )
            ),
            "document_splits": dict(
                Counter(
                    str(record.get("document_split") or "")
                    for record in package.source_records
                )
            ),
            "evidence_levels": dict(
                Counter(
                    str(record.get("evidence_level") or "MISSING")
                    for record in package.source_records
                )
            ),
            "input_files": package.file_metadata,
        }

    _check_release_projection(raw, validated, builder)
    severity_counts = dict(
        Counter(str(check["severity"]) for check in builder.checks)
    )
    status_counts = dict(
        Counter(str(check["status"]) for check in builder.checks)
    )
    release_blocked = any(
        check.get("release_blocking") is True for check in builder.checks
    )
    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validator_kind": VALIDATOR_KIND,
        "validation_scope": {
            "description": (
                "Project-specific executable checks over current layered JSONL "
                "graph packages and source records."
            ),
            "reuses": [
                "provenance_schema_v3 relation registry and Domain/Range",
                "current stable identifier functions",
                "current Chinese terminology and protected-term validator",
                "frozen document split",
            ],
            "explicit_non_claims": [
                "not a complete validation of every provenance_schema_v3 JSON Schema field",
                "not RDF validation",
                "not SHACL validation",
                "not human expert review",
                "not a Gold-label quality guarantee",
            ],
        },
        "inputs": {
            "graph_root": graph_root.as_posix(),
            "schema": {
                "path": schema_path.as_posix(),
                "schema_version": schema.get("schema_version"),
                "sha256": _sha256_file(schema_path),
            },
            "terminology": {
                "path": terminology_path.as_posix(),
                "version": terminology.get("version"),
                "sha256": _sha256_file(terminology_path),
            },
            "document_split": {
                "path": split_path.as_posix(),
                "version": split.get("version"),
                "sha256": _sha256_file(split_path),
            },
        },
        "packages": package_summaries,
        "summary": {
            "checks": len(builder.checks),
            "status_counts": status_counts,
            "severity_counts": severity_counts,
            "failed_checks": sum(
                check["status"] == "fail" for check in builder.checks
            ),
            "release_blocking_checks": sum(
                check["release_blocking"] is True for check in builder.checks
            ),
            "release_blocked": release_blocked,
            "human_expert_reviewed": False,
            "label_policy": "Silver only; never Gold",
        },
        "checks": builder.checks,
    }


def _md_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_graph_constraint_report_markdown(
    report: Mapping[str, object],
) -> str:
    """Render a compact human-readable companion to the JSON report."""

    summary = report["summary"]
    assert isinstance(summary, Mapping)
    packages = report["packages"]
    assert isinstance(packages, Mapping)
    verdict = "阻止发布" if summary.get("release_blocked") else "未发现发布阻断错误"
    lines = [
        "# KG_v1 标准化约束报告",
        "",
        f"- 报告版本：`{_md_escape(report.get('report_version'))}`",
        f"- 生成时间：`{_md_escape(report.get('generated_at'))}`",
        f"- 校验器：`{_md_escape(report.get('validator_kind'))}`",
        f"- 结论：**{verdict}**",
        f"- 失败检查：{summary.get('failed_checks', 0)}",
        f"- 发布阻断检查：{summary.get('release_blocking_checks', 0)}",
        "- 人工专家审核：否",
        "- 标签政策：Silver only; never Gold",
        "",
        "> 本报告是项目专用Python约束配置的可执行结果，不是完整JSON "
        "Schema验证、RDF验证或SHACL验证。",
        "",
        "## 图谱包统计",
        "",
        "| 图谱 | 源记录 | 实体 | Claim | Evidence | 链接 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for version, package in packages.items():
        assert isinstance(package, Mapping)
        counts = package.get("records", {})
        assert isinstance(counts, Mapping)
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape(version),
                    str(counts.get("source_records", 0)),
                    str(counts.get("entities", 0)),
                    str(counts.get("claims", 0)),
                    str(counts.get("evidence_assertions", 0)),
                    str(counts.get("claim_evidence_links", 0)),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 约束结果",
            "",
            "| 规则 | 范围 | 状态 | 严重度 | 检查数 | 违规数 | 发布阻断 |",
            "|---|---|---|---|---:|---:|---|",
        ]
    )
    checks = report["checks"]
    assert isinstance(checks, Sequence)
    for check in checks:
        assert isinstance(check, Mapping)
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_md_escape(check.get('rule_id'))}` "
                    f"{_md_escape(check.get('title'))}",
                    _md_escape(check.get("scope")),
                    _md_escape(check.get("status")),
                    _md_escape(check.get("severity")),
                    str(check.get("evaluated", 0)),
                    str(check.get("violation_count", 0)),
                    "是" if check.get("release_blocking") else "否",
                ]
            )
            + " |"
        )
    failed = [
        check
        for check in checks
        if isinstance(check, Mapping) and check.get("status") == "fail"
    ]
    lines.extend(["", "## 失败与警告明细", ""])
    if not failed:
        lines.append("没有失败检查。")
    for check in failed:
        lines.extend(
            [
                f"### `{_md_escape(check.get('rule_id'))}` "
                f"{_md_escape(check.get('title'))}",
                "",
                _md_escape(check.get("description")),
                "",
                f"- 严重度：{_md_escape(check.get('severity'))}",
                f"- 违规数：{check.get('violation_count', 0)}",
                f"- 发布阻断：{'是' if check.get('release_blocking') else '否'}",
            ]
        )
        examples = check.get("examples")
        if isinstance(examples, Sequence) and examples:
            lines.extend(["- 示例：", ""])
            for example in examples:
                lines.append(
                    "  - `"
                    + _md_escape(
                        json.dumps(example, ensure_ascii=False, sort_keys=True)
                    )
                    + "`"
                )
        lines.append("")
    lines.extend(
        [
            "## 解释边界",
            "",
            "- `error`表示当前发布约束的硬失败，并令`release_blocked=true`。",
            "- `warning`记录审计质量缺口，但不自动否定已通过门槛的发布子集。",
            "- `info`包括通过项和只作分布统计的审计项。",
            "- 该结果验证结构、溯源和治理状态的一致性，不等价于领域专家确认事实正确。",
            "",
        ]
    )
    return "\n".join(lines)


def write_graph_constraint_report(
    report: Mapping[str, object],
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "graph_constraint_report.json"
    markdown_path = output_dir / "graph_constraint_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_graph_constraint_report_markdown(report),
        encoding="utf-8",
    )
    return json_path, markdown_path
