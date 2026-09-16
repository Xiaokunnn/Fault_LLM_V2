"""Leakage-resistant and corpus-aware splitting for RP3 supervision."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from typing import Iterable

from .contracts import (
    CompactEvidenceRecord,
    ContractError,
    DataSplit,
    TeacherTrace,
    validate_unique_trace_ids,
)


BUILD_DOCUMENTS = frozenset(
    [*(f"MP{index:03d}" for index in range(1, 8)), *(f"MP{index:03d}" for index in range(15, 23))]
)
DEVELOPMENT_DOCUMENTS = frozenset({"MP008"})
EXTERNAL_EVALUATION_DOCUMENTS = frozenset(f"MP{index:03d}" for index in range(9, 14))
EXCLUDED_DOCUMENTS = frozenset({"MP014"})
_DOC_PATTERN = re.compile(r"(?<![A-Z0-9])MP(\d{3})(?!\d)", re.IGNORECASE)


@dataclass(frozen=True)
class SplitReport:
    seed: str
    validation_fraction: float
    component_count: int
    trace_count_by_split: dict[str, int]
    component_count_by_split: dict[str, int]


def canonical_document_id(value: str) -> str:
    match = _DOC_PATTERN.search(str(value).upper())
    if not match:
        raise ContractError(f"cannot resolve governed document ID from {value!r}")
    return f"MP{int(match.group(1)):03d}"


def corpus_partition(value: str) -> str:
    doc_id = canonical_document_id(value)
    if doc_id in BUILD_DOCUMENTS:
        return "build"
    if doc_id in DEVELOPMENT_DOCUMENTS:
        return "development"
    if doc_id in EXTERNAL_EVALUATION_DOCUMENTS:
        return "external_evaluation"
    if doc_id in EXCLUDED_DOCUMENTS:
        return "excluded"
    raise ContractError(f"document {doc_id} is outside the frozen RP3 corpus policy")


def stable_group_hash(tokens: Iterable[str], *, seed: str = "rp3-split-v1") -> str:
    normalized = sorted({str(token).strip() for token in tokens if str(token).strip()})
    if not normalized:
        raise ContractError("stable_group_hash requires at least one non-empty token")
    payload = (str(seed) + "\n" + "\n".join(normalized)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def trace_group_tokens(trace: TeacherTrace) -> frozenset[str]:
    return frozenset(
        {
            f"scenario:{trace.query.scenario_id}",
            *(f"claim:{item}" for item in trace.claim_group_ids),
            *(f"document:{canonical_document_id(item)}" for item in trace.document_group_ids),
            *(f"source_family:{item}" for item in trace.source_family_group_ids),
        }
    )


def _forced_document_split(
    document_ids: Iterable[str], *, allow_empty: bool = False
) -> DataSplit | None:
    values = tuple(document_ids)
    if not values:
        if allow_empty:
            return None
        raise ContractError("each RP3 trace must declare document_group_ids")
    partitions = {corpus_partition(item) for item in values}
    if "excluded" in partitions:
        raise ContractError("MP014 is excluded and cannot appear in an RP3 trace")
    if "external_evaluation" in partitions:
        if len(partitions) != 1:
            raise ContractError("external-evaluation documents cannot mix with upstream data")
        return DataSplit.EXTERNAL_EVALUATION
    if "development" in partitions:
        if len(partitions) != 1:
            raise ContractError("MP008 development data cannot mix with build data")
        return DataSplit.DEVELOPMENT
    if partitions == {"build"}:
        return None
    raise ContractError(f"unsupported corpus partition combination: {sorted(partitions)}")


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def assign_grouped_splits(
    traces: Iterable[TeacherTrace],
    *,
    seed: str = "rp3-split-v1",
    validation_fraction: float = 0.2,
) -> tuple[tuple[TeacherTrace, ...], SplitReport]:
    """Assign one split to every connected leakage-control group.

    Traces sharing *any* base scenario, claim, document, or source family are joined
    before hashing.  Augmentations and interventions therefore cannot cross a split.
    MP008 is forced to development; MP009--MP013 are forced to external evaluation.
    """

    if not 0.0 <= validation_fraction < 1.0:
        raise ContractError("validation_fraction must be in [0, 1)")
    rows = validate_unique_trace_ids(traces)
    groups = [trace_group_tokens(trace) for trace in rows]
    dsu = _DisjointSet(len(rows))
    token_owner: dict[str, int] = {}
    for index, tokens in enumerate(groups):
        for token in tokens:
            if token in token_owner:
                dsu.union(index, token_owner[token])
            else:
                token_owner[token] = index

    components: dict[int, list[int]] = {}
    for index in range(len(rows)):
        components.setdefault(dsu.find(index), []).append(index)

    assigned: list[TeacherTrace | None] = [None] * len(rows)
    component_count_by_split = {item.value: 0 for item in DataSplit if item != DataSplit.UNASSIGNED}
    for indices in components.values():
        component_corpus_partitions = {
            corpus_partition(document_id)
            for index in indices
            for document_id in rows[index].document_group_ids
        }
        if "excluded" in component_corpus_partitions:
            raise ContractError("MP014 is excluded and cannot appear in an RP3 component")
        governed_non_build = component_corpus_partitions - {"build"}
        if governed_non_build and len(component_corpus_partitions) > 1:
            raise ContractError(
                "a leakage-control component cannot mix build, development, or "
                "external-evaluation corpora"
            )
        forced = {
            value
            for value in (_forced_document_split(rows[index].document_group_ids) for index in indices)
            if value is not None
        }
        if len(forced) > 1:
            raise ContractError("a leakage-control component spans multiple forced corpus splits")
        component_tokens = set().union(*(groups[index] for index in indices))
        if forced:
            split = next(iter(forced))
        else:
            bucket = int(stable_group_hash(component_tokens, seed=seed)[:16], 16) / float(16**16)
            split = DataSplit.VALIDATION if bucket < validation_fraction else DataSplit.TRAIN
        component_count_by_split[split.value] += 1
        for index in indices:
            existing = rows[index].split
            if existing not in {DataSplit.UNASSIGNED, split}:
                raise ContractError(
                    f"trace {rows[index].trace_id} declares split={existing.value}, expected {split.value}"
                )
            assigned[index] = replace(rows[index], split=split)

    output = tuple(item for item in assigned if item is not None)
    trace_count_by_split = {item.value: 0 for item in DataSplit if item != DataSplit.UNASSIGNED}
    for trace in output:
        trace_count_by_split[trace.split.value] += 1
    return output, SplitReport(
        seed=str(seed),
        validation_fraction=float(validation_fraction),
        component_count=len(components),
        trace_count_by_split=trace_count_by_split,
        component_count_by_split=component_count_by_split,
    )


def assign_fixed_memory_query_splits(
    traces: Iterable[TeacherTrace],
    *,
    seed: str = "rp3-fixed-memory-query-v1",
    validation_fraction: float = 0.2,
) -> tuple[tuple[TeacherTrace, ...], SplitReport]:
    """Split by base fault/scenario while explicitly allowing shared evidence memory.

    RP2's top-32 lists repeatedly reuse the same small strict-208 memory.  Joining
    traces through candidate IDs, documents, or broad source families therefore
    creates a single giant component and no estimable validation set.  This mode
    measures *query/fault-scenario generalization under a fixed memory only*; it
    must never be reported as unseen-document or inductive evidence generalization.
    Perturbations retain the base ``scenario_id`` and consequently cannot cross
    the split.  Use :func:`assign_grouped_splits` on a corpus-rebuilt experiment
    for a true claim/document/source-family holdout.
    """

    if not 0.0 <= validation_fraction < 1.0:
        raise ContractError("validation_fraction must be in [0, 1)")
    rows = validate_unique_trace_ids(traces)
    scenario_owner: dict[str, DataSplit] = {}
    assigned: list[TeacherTrace] = []
    for trace in rows:
        # A zero-candidate RP2 role query is valid active-underfill/route
        # supervision.  It has no evidence provenance to name, so its leakage
        # key is the mandatory fault scenario.  Non-empty candidate traces must
        # still expose their actual build-document provenance.
        if not trace.document_group_ids and trace.candidate_evidence_ids:
            raise ContractError(
                "a non-empty fixed-memory trace must declare document_group_ids"
            )
        if _forced_document_split(
            trace.document_group_ids, allow_empty=not trace.candidate_evidence_ids
        ) is not None:
            raise ContractError(
                "fixed-memory build split cannot contain development/external documents"
            )
        token = f"scenario:{trace.query.scenario_id}"
        if token not in scenario_owner:
            bucket = int(stable_group_hash((token,), seed=seed)[:16], 16) / float(16**16)
            scenario_owner[token] = (
                DataSplit.VALIDATION if bucket < validation_fraction else DataSplit.TRAIN
            )
        split = scenario_owner[token]
        if trace.split not in {DataSplit.UNASSIGNED, split}:
            raise ContractError(
                f"trace {trace.trace_id} declares split={trace.split.value}, expected {split.value}"
            )
        assigned.append(replace(trace, split=split))
    trace_counts = {item.value: 0 for item in DataSplit if item != DataSplit.UNASSIGNED}
    component_counts = dict(trace_counts)
    for trace in assigned:
        trace_counts[trace.split.value] += 1
    for split in scenario_owner.values():
        component_counts[split.value] += 1
    return tuple(assigned), SplitReport(
        seed=str(seed),
        validation_fraction=float(validation_fraction),
        component_count=len(scenario_owner),
        trace_count_by_split=trace_counts,
        component_count_by_split=component_counts,
    )


def assert_training_trace_boundary(
    traces: Iterable[TeacherTrace],
    *,
    split_mode: str = "inductive_evidence_holdout",
) -> tuple[TeacherTrace, ...]:
    rows = validate_unique_trace_ids(traces)
    if split_mode not in {
        "fixed_memory_query_generalization",
        "inductive_evidence_holdout",
    }:
        raise ContractError(f"unknown training split mode: {split_mode}")
    for trace in rows:
        allow_empty = (
            split_mode == "fixed_memory_query_generalization"
            and not trace.candidate_evidence_ids
        )
        if not trace.document_group_ids and not allow_empty:
            raise ContractError(
                "a training trace with candidate evidence must declare document_group_ids"
            )
        forced = _forced_document_split(
            trace.document_group_ids, allow_empty=allow_empty
        )
        if trace.split not in {DataSplit.TRAIN, DataSplit.VALIDATION}:
            raise ContractError(
                f"training bundle contains trace {trace.trace_id} with split={trace.split.value}"
            )
        if forced is not None:
            raise ContractError(
                f"training bundle contains governed non-training document in {trace.trace_id}"
            )
    return rows


def assert_memory_partition_boundary(
    records: Iterable[CompactEvidenceRecord], *, purpose: str
) -> tuple[CompactEvidenceRecord, ...]:
    rows = tuple(records)
    purpose = str(purpose).strip()
    allowed_by_purpose = {
        "audit": {
            DataSplit.UNASSIGNED,
            DataSplit.TRAIN,
            DataSplit.VALIDATION,
            DataSplit.DEVELOPMENT,
            DataSplit.EXTERNAL_EVALUATION,
        },
        "training": {DataSplit.TRAIN, DataSplit.VALIDATION},
        "development": {DataSplit.DEVELOPMENT},
        "external_evaluation": {DataSplit.EXTERNAL_EVALUATION},
        "edge_inference": {DataSplit.TRAIN, DataSplit.VALIDATION},
    }
    if purpose not in allowed_by_purpose:
        raise ContractError(f"unknown evidence-memory purpose: {purpose}")
    allowed = allowed_by_purpose[purpose]
    for record in rows:
        actual_partition = corpus_partition(record.provenance.doc_id)
        if actual_partition == "excluded":
            raise ContractError("MP014 cannot enter an RP3 evidence memory")
        expected = {
            "build": {DataSplit.TRAIN, DataSplit.VALIDATION},
            "development": {DataSplit.DEVELOPMENT},
            "external_evaluation": {DataSplit.EXTERNAL_EVALUATION},
        }[actual_partition]
        if purpose != "audit" and record.partition not in expected:
            raise ContractError(
                f"evidence {record.evidence_id} partition disagrees with {record.provenance.doc_id}"
            )
        if record.partition not in allowed:
            raise ContractError(
                f"{purpose} evidence memory cannot contain {record.partition.value} record "
                f"{record.evidence_id}"
            )
    return rows
