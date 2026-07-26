"""Document ingestion orchestration and JSONL persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable

from .manifest_loader import load_document_manifest, validate_local_file
from .pdf_parser import PdfDocumentParser


def ingest_documents(
    project_root: Path,
    selections: dict[str, Iterable[int] | None],
    output_dir: Path,
    *,
    split_path: Path | None = None,
    printed_page_overrides: dict[str, dict[int, str]] | None = None,
    visual_layout_checked_pages: dict[str, set[int]] | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    manifest = load_document_manifest(project_root, split_path=split_path)
    parser = PdfDocumentParser(project_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "schema_version": "marine_pump_ingest_run_v2",
        "documents": {},
        "errors": [],
    }
    overrides = printed_page_overrides or {}
    checked_pages = visual_layout_checked_pages or {}

    total_documents = len(selections)
    for document_index, (doc_id, pages) in enumerate(selections.items(), start=1):
        if doc_id not in manifest:
            raise KeyError(f"Document not in manifest: {doc_id}")
        descriptor = manifest[doc_id]
        selected_pages = list(pages) if pages is not None else None
        if progress_callback:
            progress_callback(
                {
                    "event": "document_started",
                    "document_index": document_index,
                    "total_documents": total_documents,
                    "doc_id": doc_id,
                    "selected_pages": selected_pages,
                }
            )
        integrity_errors = validate_local_file(project_root, descriptor)
        if integrity_errors:
            summary["errors"].append({"doc_id": doc_id, "errors": integrity_errors})
            if progress_callback:
                progress_callback(
                    {
                        "event": "document_failed",
                        "document_index": document_index,
                        "total_documents": total_documents,
                        "doc_id": doc_id,
                        "errors": integrity_errors,
                    }
                )
            continue
        parsed = parser.parse(
            descriptor,
            page_numbers=selected_pages,
            printed_page_overrides=overrides.get(doc_id),
            visual_layout_checked_pages=checked_pages.get(doc_id),
        )
        output_path = output_dir / f"{doc_id}.pages.v2.jsonl"
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            for page in parsed:
                handle.write(json.dumps(page.to_dict(), ensure_ascii=False) + "\n")
        summary["documents"][doc_id] = {
            "pages_written": len(parsed),
            "tables": sum(len(page.tables) for page in parsed),
            "text_blocks": sum(len(page.text_blocks) for page in parsed),
            "output": output_path.relative_to(project_root).as_posix(),
        }
        if progress_callback:
            progress_callback(
                {
                    "event": "document_completed",
                    "document_index": document_index,
                    "total_documents": total_documents,
                    "doc_id": doc_id,
                    "pages_written": len(parsed),
                    "tables": sum(len(page.tables) for page in parsed),
                    "text_blocks": sum(len(page.text_blocks) for page in parsed),
                    "output": output_path.relative_to(project_root).as_posix(),
                }
            )

    summary_path = output_dir / "ingest_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
