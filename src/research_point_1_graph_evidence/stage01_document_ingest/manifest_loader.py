"""Load and integrity-check the versioned source manifest and document split."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentDescriptor:
    doc_id: str
    file_name: str
    title: str
    publisher: str
    source_family_id: str
    source_url: str
    pages: int
    bytes: int
    sha256: str
    source_tier: str
    primary_use: str
    document_split: str
    pump_type: str | None = None
    service: str | None = None
    applicability_scope: str | None = None


def _source_family_fallback(publisher: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", publisher.upper()).strip("_")
    return normalized or "UNSPECIFIED"


def _load_split(path: Path) -> dict[str, str]:
    split = json.loads(path.read_text(encoding="utf-8"))
    assignments: dict[str, str] = {}
    keys = {
        "build_train_doc_ids": "build_train",
        "development_doc_ids": "development",
        "held_out_test_doc_ids": "held_out_test",
    }
    for key, label in keys.items():
        for doc_id in split.get(key, []):
            if doc_id in assignments:
                raise ValueError(f"{doc_id} occurs in more than one split")
            assignments[doc_id] = label
    return assignments


def load_document_manifest(
    project_root: Path,
    *,
    split_path: Path | None = None,
    require_source_family: bool = True,
    require_split_assignment: bool = True,
) -> dict[str, DocumentDescriptor]:
    manifest_path = project_root / "data/source_docs/marine_pump/source_manifest.csv"
    split_path = (
        split_path
        or project_root / "configs/document_split_marine_pump_v4.json"
    )
    if not split_path.exists():
        split_path = project_root / "configs/document_split_marine_pump_pilot_v1.json"
    assignments = _load_split(split_path)

    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    documents: dict[str, DocumentDescriptor] = {}
    for row in rows:
        doc_id = row["doc_id"].strip()
        if doc_id in documents:
            raise ValueError(f"Duplicate document id: {doc_id}")
        source_family_id = (row.get("source_family_id") or "").strip()
        if require_source_family and not source_family_id:
            raise ValueError(
                f"{doc_id} has no source_family_id; formal coverage cannot infer "
                "independent publishers from display names"
            )
        if require_split_assignment and doc_id not in assignments:
            raise ValueError(
                f"{doc_id} is not assigned by {split_path.name}; "
                "formal ingestion cannot emit unassigned evidence"
            )
        documents[doc_id] = DocumentDescriptor(
            doc_id=doc_id,
            file_name=row["file_name"].strip(),
            title=row["title"].strip(),
            publisher=row["publisher"].strip(),
            source_family_id=source_family_id or _source_family_fallback(row["publisher"]),
            source_url=row["source_url"].strip(),
            pages=int(row["pages"]),
            bytes=int(row["bytes"]),
            sha256=row["sha256"].strip().upper(),
            source_tier=row["source_tier"].strip(),
            primary_use=row["primary_use"].strip(),
            document_split=assignments.get(doc_id, "unassigned"),
            pump_type=(row.get("pump_type") or "").strip() or None,
            service=(row.get("service") or "").strip() or None,
            applicability_scope=(row.get("applicability_scope") or "").strip() or None,
        )
    return documents


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_local_file(
    project_root: Path,
    document: DocumentDescriptor,
    *,
    count_pdf_pages: bool = True,
) -> list[str]:
    """Return integrity errors; an empty list means the local asset is valid."""

    path = project_root / "data/source_docs/marine_pump/raw" / document.file_name
    errors: list[str] = []
    if not path.exists():
        return [f"missing_file:{path}"]
    stat = path.stat()
    if stat.st_size != document.bytes:
        errors.append(f"byte_count_mismatch:expected={document.bytes}:actual={stat.st_size}")
    actual_sha = sha256_file(path)
    if actual_sha != document.sha256:
        errors.append(f"sha256_mismatch:expected={document.sha256}:actual={actual_sha}")
    if count_pdf_pages:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            actual_pages = len(pdf.pages)
        if actual_pages != document.pages:
            errors.append(f"page_count_mismatch:expected={document.pages}:actual={actual_pages}")
    return errors
