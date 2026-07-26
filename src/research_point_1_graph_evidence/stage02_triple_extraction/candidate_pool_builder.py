"""Auditable fault-role retrieval and page-pool construction."""

from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from .page_index import looks_like_low_value_page, looks_like_toc, normalized_text


def _compile(patterns: Sequence[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in patterns]


def _match_count(patterns: Sequence[re.Pattern[str]], text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in patterns)


def _fts_query(terms: Sequence[str]) -> str:
    cleaned = [
        '"' + term.replace('"', '""') + '"'
        for term in terms
        if term.strip()
    ]
    return " OR ".join(cleaned)


def _simhash64(text: str) -> int:
    tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", normalized_text(text))
    vector = [0] * 64
    for token in tokens:
        value = int.from_bytes(
            hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(),
            "big",
        )
        for bit in range(64):
            vector[bit] += 1 if value & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(vector):
        if weight >= 0:
            result |= 1 << bit
    return result


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def build_candidate_pool(
    *,
    database_path: Path,
    ontology: Mapping[str, object],
    config: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    role_patterns = {
        role: _compile(patterns)
        for role, patterns in dict(config["role_patterns"]).items()
    }
    pump_patterns = _compile(list(config["pump_scope_patterns"]))
    generic_sources = set(config.get("generic_source_families", []))
    per_group: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    excluded: list[dict[str, object]] = []
    try:
        for fault in ontology["fault_classes"]:
            fault_id = str(fault["fault_id"])
            fault_patterns = _compile(list(fault["selection_patterns"]))
            exclusion_patterns = _compile(list(fault.get("exclusion_patterns", [])))
            query = _fts_query(config["fault_query_terms"][fault_id])
            rows = connection.execute(
                """
                SELECT p.*, bm25(page_fts) AS bm25_score
                FROM page_fts
                JOIN pages p ON p.page_key = page_fts.page_key
                WHERE page_fts MATCH ? AND p.document_split = ?
                """,
                (query, str(config["eligible_split"])),
            ).fetchall()
            for row in rows:
                text = str(row["page_text"])
                tables = str(row["table_text"])
                combined = text + "\n" + tables
                reason = None
                if (
                    config["page_filters"]["exclude_table_of_contents"]
                    and looks_like_toc(text)
                ):
                    reason = "table_of_contents"
                elif (
                    config["page_filters"]["exclude_low_value_pages"]
                    and looks_like_low_value_page(text, tables)
                ):
                    reason = "low_value_page"
                elif _match_count(exclusion_patterns, combined):
                    reason = "fault_exclusion_pattern"
                fault_hits = _match_count(fault_patterns, combined)
                pump_hits = _match_count(pump_patterns, combined)
                if not fault_hits:
                    reason = reason or "fault_pattern_not_confirmed"
                if (
                    config["require_pump_scope_for_generic_sources"]
                    and row["source_family_id"] in generic_sources
                    and not pump_hits
                ):
                    reason = reason or "generic_source_without_pump_scope"
                if reason:
                    excluded.append(
                        {
                            "page_key": row["page_key"],
                            "fault_id": fault_id,
                            "reason": reason,
                        }
                    )
                    continue
                for role, patterns in role_patterns.items():
                    role_hits = _match_count(patterns, combined)
                    if not role_hits:
                        continue
                    bm25_component = max(0.0, min(5.0, -float(row["bm25_score"])))
                    score = (
                        fault_hits * 4.0
                        + min(role_hits, 8) * 1.5
                        + min(pump_hits, 4) * 0.75
                        + min(int(row["table_count"]), 2) * 1.0
                        + bm25_component
                    )
                    if score < float(config["minimum_page_score"]):
                        continue
                    per_group[(fault_id, role)].append(
                        {
                            "page_key": row["page_key"],
                            "doc_id": row["doc_id"],
                            "pdf_page_number": int(row["pdf_page_number"]),
                            "document_split": row["document_split"],
                            "source_family_id": row["source_family_id"],
                            "publisher": row["publisher"],
                            "source_url": row["source_url"],
                            "normalized_text_sha256": row["normalized_text_sha256"],
                            "retrieval_score": round(score, 4),
                            "bm25_score": round(float(row["bm25_score"]), 4),
                            "fault_hits": fault_hits,
                            "role_hits": role_hits,
                            "pump_scope_hits": pump_hits,
                            "target_fault_class": fault_id,
                            "target_evidence_role": role,
                            "_combined_text": combined,
                        }
                    )
    finally:
        connection.close()

    selected_pairs: list[dict[str, object]] = []
    max_group = int(config["max_pages_per_fault_role"])
    max_family = int(config["max_pages_per_source_family_per_fault_role"])
    for group, values in per_group.items():
        family_counts: dict[str, int] = defaultdict(int)
        for value in sorted(
            values,
            key=lambda item: (
                -float(item["retrieval_score"]),
                str(item["page_key"]),
            ),
        ):
            family = str(value["source_family_id"])
            if family_counts[family] >= max_family:
                continue
            selected_pairs.append(value)
            family_counts[family] += 1
            if sum(
                1
                for selected in selected_pairs
                if (
                    selected["target_fault_class"],
                    selected["target_evidence_role"],
                )
                == group
            ) >= max_group:
                break

    pages: dict[str, dict[str, object]] = {}
    for value in sorted(
        selected_pairs,
        key=lambda item: -float(item["retrieval_score"]),
    ):
        page_key = str(value["page_key"])
        item = pages.setdefault(
            page_key,
            {
                key: value[key]
                for key in (
                    "page_key",
                    "doc_id",
                    "pdf_page_number",
                    "document_split",
                    "source_family_id",
                    "publisher",
                    "source_url",
                    "normalized_text_sha256",
                )
            }
            | {
                "target_fault_classes": [],
                "target_evidence_roles": [],
                "retrieval_details": [],
                "_combined_text": value["_combined_text"],
            },
        )
        fault_id = str(value["target_fault_class"])
        role = str(value["target_evidence_role"])
        if fault_id not in item["target_fault_classes"]:
            item["target_fault_classes"].append(fault_id)
        if role not in item["target_evidence_roles"]:
            item["target_evidence_roles"].append(role)
        item["retrieval_details"].append(
            {
                "fault_id": fault_id,
                "evidence_role": role,
                "score": value["retrieval_score"],
                "fault_hits": value["fault_hits"],
                "role_hits": value["role_hits"],
                "pump_scope_hits": value["pump_scope_hits"],
            }
        )

    context_window = int(config.get("adjacent_page_context_window", 0))
    if context_window > 0 and pages:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        try:
            base_items = list(pages.values())
            for base in base_items:
                base_page = int(base["pdf_page_number"])
                for offset in range(-context_window, context_window + 1):
                    if offset == 0:
                        continue
                    row = connection.execute(
                        """
                        SELECT *
                        FROM pages
                        WHERE doc_id = ? AND pdf_page_number = ?
                          AND document_split = ?
                        """,
                        (
                            str(base["doc_id"]),
                            base_page + offset,
                            str(config["eligible_split"]),
                        ),
                    ).fetchone()
                    if row is None:
                        continue
                    text = str(row["page_text"])
                    tables = str(row["table_text"])
                    if (
                        config["page_filters"]["exclude_table_of_contents"]
                        and looks_like_toc(text)
                    ) or (
                        config["page_filters"]["exclude_low_value_pages"]
                        and looks_like_low_value_page(text, tables)
                    ):
                        excluded.append(
                            {
                                "page_key": row["page_key"],
                                "reason": "adjacent_context_low_value",
                                "context_of": base["page_key"],
                            }
                        )
                        continue
                    page_key = str(row["page_key"])
                    context = pages.setdefault(
                        page_key,
                        {
                            "page_key": page_key,
                            "doc_id": row["doc_id"],
                            "pdf_page_number": int(row["pdf_page_number"]),
                            "document_split": row["document_split"],
                            "source_family_id": row["source_family_id"],
                            "publisher": row["publisher"],
                            "source_url": row["source_url"],
                            "normalized_text_sha256": row[
                                "normalized_text_sha256"
                            ],
                            "target_fault_classes": [],
                            "target_evidence_roles": [],
                            "retrieval_details": [],
                            "_combined_text": text + "\n" + tables,
                        },
                    )
                    for fault_id in base["target_fault_classes"]:
                        if fault_id not in context["target_fault_classes"]:
                            context["target_fault_classes"].append(fault_id)
                    for role in base["target_evidence_roles"]:
                        if role not in context["target_evidence_roles"]:
                            context["target_evidence_roles"].append(role)
                    base_score = max(
                        float(detail["score"])
                        for detail in base["retrieval_details"]
                    )
                    detail = {
                        "fault_id": ",".join(base["target_fault_classes"]),
                        "evidence_role": ",".join(base["target_evidence_roles"]),
                        "score": round(
                            base_score
                            - abs(offset)
                            * float(config.get("adjacent_page_score_decay", 1.0)),
                            4,
                        ),
                        "fault_hits": 0,
                        "role_hits": 0,
                        "pump_scope_hits": 0,
                        "retrieval_mode": "adjacent_context",
                        "context_of": base["page_key"],
                    }
                    if detail not in context["retrieval_details"]:
                        context["retrieval_details"].append(detail)
        finally:
            connection.close()

    ranked = sorted(
        pages.values(),
        key=lambda item: (
            -max(float(detail["score"]) for detail in item["retrieval_details"]),
            str(item["page_key"]),
        ),
    )
    deduplicated: list[dict[str, object]] = []
    document_counts: dict[str, int] = defaultdict(int)
    seen_hashes: dict[str, str] = {}
    seen_simhashes: list[tuple[int, str]] = []
    threshold = int(config["page_filters"]["near_duplicate_hamming_distance"])
    for item in ranked:
        document_id = str(item["doc_id"])
        document_limit = int(config.get("max_pages_per_document", 10**9))
        if document_counts[document_id] >= document_limit:
            excluded.append(
                {
                    "page_key": item["page_key"],
                    "reason": "document_page_limit",
                    "doc_id": document_id,
                }
            )
            continue
        exact_hash = str(item["normalized_text_sha256"])
        if exact_hash in seen_hashes:
            excluded.append(
                {
                    "page_key": item["page_key"],
                    "reason": "exact_duplicate_page",
                    "duplicate_of": seen_hashes[exact_hash],
                }
            )
            continue
        fingerprint = _simhash64(str(item["_combined_text"]))
        near = next(
            (
                page_key
                for existing, page_key in seen_simhashes
                if _hamming(fingerprint, existing) <= threshold
            ),
            None,
        )
        if near:
            excluded.append(
                {
                    "page_key": item["page_key"],
                    "reason": "near_duplicate_page",
                    "duplicate_of": near,
                }
            )
            continue
        seen_hashes[exact_hash] = str(item["page_key"])
        seen_simhashes.append((fingerprint, str(item["page_key"])))
        item.pop("_combined_text", None)
        deduplicated.append(item)
        document_counts[document_id] += 1
        if len(deduplicated) >= int(config["max_total_candidate_pages"]):
            break

    summary = {
        "version": "marine_pump_candidate_page_pool_v1",
        "candidate_pages": len(deduplicated),
        "excluded_records": len(excluded),
        "fault_role_groups_with_candidates": len(per_group),
        "source_family_counts": {
            family: sum(
                item["source_family_id"] == family for item in deduplicated
            )
            for family in sorted(
                {str(item["source_family_id"]) for item in deduplicated}
            )
        },
        "document_counts": dict(sorted(document_counts.items())),
        "configured_max_total_candidate_pages": int(
            config["max_total_candidate_pages"]
        ),
    }
    return deduplicated, excluded, summary
