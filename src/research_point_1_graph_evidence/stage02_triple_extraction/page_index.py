"""SQLite/FTS5 page index for local corpus-wide candidate discovery."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping


def normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def normalized_sha256(value: str) -> str:
    return hashlib.sha256(normalized_text(value).encode("utf-8")).hexdigest()


def table_text(page: Mapping[str, object]) -> str:
    values: list[str] = []
    for table in page.get("tables", []) or []:
        if not isinstance(table, Mapping):
            continue
        for row in table.get("rows", []) or []:
            if not isinstance(row, Mapping):
                continue
            values.extend(
                str(cell.get("text", ""))
                for cell in row.get("cells", []) or []
                if isinstance(cell, Mapping) and str(cell.get("text", "")).strip()
            )
    return "\n".join(values)


def iter_jsonl(paths: Iterable[Path]) -> Iterable[dict[str, object]]:
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def create_index(
    database_path: Path,
    pages: Iterable[Mapping[str, object]],
    *,
    progress_callback=None,
) -> dict[str, int]:
    temporary = database_path.with_suffix(database_path.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE pages (
                page_key TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                pdf_page_number INTEGER NOT NULL,
                document_split TEXT NOT NULL,
                source_family_id TEXT NOT NULL,
                publisher TEXT NOT NULL,
                pump_type TEXT,
                service TEXT,
                applicability_scope TEXT,
                source_url TEXT NOT NULL,
                page_text TEXT NOT NULL,
                table_text TEXT NOT NULL,
                page_text_sha256 TEXT NOT NULL,
                normalized_text_sha256 TEXT NOT NULL,
                text_length INTEGER NOT NULL,
                table_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE page_fts USING fts5(
                page_key UNINDEXED,
                page_text,
                table_text,
                tokenize='unicode61'
            );
            CREATE INDEX pages_split_idx ON pages(document_split);
            CREATE INDEX pages_source_idx ON pages(source_family_id);
            CREATE INDEX pages_hash_idx ON pages(normalized_text_sha256);
            """
        )
        count = 0
        for page in pages:
            text = str(page.get("page_text", ""))
            tables = table_text(page)
            page_key = (
                f"{page['doc_id']}:{int(page['pdf_page_number'])}"
            )
            values = (
                page_key,
                str(page["doc_id"]),
                int(page["pdf_page_number"]),
                str(page["document_split"]),
                str(page["source_family_id"]),
                str(page["publisher"]),
                page.get("pump_type"),
                page.get("service"),
                page.get("applicability_scope"),
                str(page["source_url"]),
                text,
                tables,
                str(page["page_text_sha256"]),
                normalized_sha256(text + "\n" + tables),
                len(text),
                len(page.get("tables", []) or []),
                len(page.get("warnings", []) or []),
            )
            connection.execute(
                "INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            connection.execute(
                "INSERT INTO page_fts(page_key,page_text,table_text) VALUES (?,?,?)",
                (page_key, text, tables),
            )
            count += 1
            if progress_callback and (count == 1 or count % 100 == 0):
                progress_callback(count)
        connection.commit()
    finally:
        connection.close()
    if database_path.exists():
        database_path.unlink()
    temporary.replace(database_path)
    return {"pages_indexed": count}


def looks_like_toc(text: str) -> bool:
    lowered = text.casefold()
    if "table of contents" in lowered or re.search(r"(?m)^\s*contents\s*$", lowered):
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    dotted = sum(bool(re.search(r"\.{4,}\s*\d+\s*$", line)) for line in lines)
    return len(lines) >= 5 and dotted / len(lines) >= 0.25


def looks_like_low_value_page(text: str, table_value: str) -> bool:
    combined = (text + "\n" + table_value).strip()
    if len(combined) < 80:
        return True
    lowered = combined.casefold()
    marketing = (
        "all rights reserved",
        "contact us",
        "www.",
        "copyright",
    )
    technical_cues = re.search(
        r"\b(?:pump|impeller|seal|bearing|motor|valve|pipe|"
        r"failure|fault|damage|inspect|maintenance|repair|replace|"
        r"leak|vibration|noise|temperature|cavitat)\w*\b",
        lowered,
    )
    return sum(term in lowered for term in marketing) >= 2 and not technical_cues
