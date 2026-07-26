"""Stream and resume coordinate-preserving parsing for the full corpus."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage01_document_ingest.manifest_loader import (  # noqa: E402
    load_document_manifest,
    validate_local_file,
)
from research_point_1_graph_evidence.stage01_document_ingest.pdf_parser import (  # noqa: E402
    PARSER_VERSION,
    PdfDocumentParser,
)


def _existing_pages(path: Path, document_sha256: str) -> set[int]:
    if not path.exists():
        return set()
    valid_lines: list[str] = []
    pages: set[int] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                break
            if (
                record.get("parser_version") != PARSER_VERSION
                or record.get("document_sha256") != document_sha256
            ):
                return set()
            pages.add(int(record["pdf_page_number"]))
            valid_lines.append(line.rstrip("\n"))
    if len(valid_lines) != len(pages):
        return set()
    path.write_text(
        "".join(line + "\n" for line in valid_lines),
        encoding="utf-8",
    )
    return pages


def _review_metadata() -> tuple[dict[str, dict[int, str]], dict[str, set[int]]]:
    path = PROJECT_ROOT / "configs/page_layout_review_marine_pump_v4.json"
    if not path.exists():
        path = PROJECT_ROOT / "configs/page_layout_review_marine_pump_v3.json"
    review = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    printed: dict[str, dict[int, str]] = {}
    checked: dict[str, set[int]] = {}
    for key, metadata in review.get("pages", {}).items():
        doc_id, page_value = key.split(":", 1)
        page_number = int(page_value)
        if metadata.get("printed_page_label") is not None:
            printed.setdefault(doc_id, {})[page_number] = str(
                metadata["printed_page_label"]
            )
        if metadata.get("visual_layout_checked") is True:
            checked.setdefault(doc_id, set()).add(page_number)
    return printed, checked


def _eta(seconds_elapsed: float, completed: int, total: int) -> str:
    if completed <= 0:
        return "计算中"
    remaining = max(0.0, seconds_elapsed / completed * (total - completed))
    if remaining < 60:
        return f"{remaining:.0f}秒"
    return f"{remaining / 60:.1f}分钟"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="data/interim/parsed_pages/corpus_v2",
    )
    parser.add_argument(
        "--split",
        default="configs/document_split_marine_pump_v4.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reparse all pages even when matching output exists",
    )
    parser.add_argument(
        "--doc-ids",
        help="Optional comma-separated document IDs for smoke tests",
    )
    parser.add_argument(
        "--summary-name",
        default="ingest_run_summary.json",
        help="Summary filename inside --output-dir",
    )
    args = parser.parse_args()
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_document_manifest(
        PROJECT_ROOT,
        split_path=PROJECT_ROOT / args.split,
    )
    if args.doc_ids:
        requested = {
            value.strip() for value in args.doc_ids.split(",") if value.strip()
        }
        missing = requested - set(manifest)
        if missing:
            raise KeyError(f"Unknown document IDs: {sorted(missing)}")
        manifest = {
            doc_id: descriptor
            for doc_id, descriptor in manifest.items()
            if doc_id in requested
        }
    printed_overrides, checked_pages = _review_metadata()
    pdf_parser = PdfDocumentParser(PROJECT_ROOT)
    total_pages = sum(item.pages for item in manifest.values())
    total_completed = 0
    started = time.perf_counter()
    summary: dict[str, object] = {
        "version": "marine_pump_corpus_ingest_v2",
        "parser_version": PARSER_VERSION,
        "documents": {},
        "errors": [],
    }
    print(
        f"[Corpus Stage 1] 开始：文档={len(manifest)}，页面={total_pages}",
        flush=True,
    )

    for document_index, descriptor in enumerate(manifest.values(), start=1):
        output_path = output_dir / f"{descriptor.doc_id}.pages.v2.jsonl"
        if args.force and output_path.exists():
            output_path.unlink()
        existing = _existing_pages(output_path, descriptor.sha256)
        if output_path.exists() and not existing:
            output_path.unlink()
        if existing and len(existing) != descriptor.pages:
            print(
                f"[Corpus Stage 1][{document_index}/{len(manifest)}] "
                f"{descriptor.doc_id} 断点续跑：已有={len(existing)}/{descriptor.pages}",
                flush=True,
            )
        if len(existing) == descriptor.pages:
            total_completed += descriptor.pages
            summary["documents"][descriptor.doc_id] = {
                "pages_written": descriptor.pages,
                "status": "cache_complete",
                "output": output_path.relative_to(PROJECT_ROOT).as_posix(),
            }
            print(
                f"[Corpus Stage 1][{document_index}/{len(manifest)}] "
                f"跳过 {descriptor.doc_id}：{descriptor.pages}页已完成，"
                f"总体={total_completed}/{total_pages}",
                flush=True,
            )
            continue
        # A partially parsed document contributes its cached pages to the
        # corpus-wide progress count. Previously only newly parsed pages were
        # counted after resume, so a complete 1706-page corpus could be
        # reported as 1700/1706.
        total_completed += len(existing)
        integrity_errors = validate_local_file(PROJECT_ROOT, descriptor)
        if integrity_errors:
            summary["errors"].append(
                {"doc_id": descriptor.doc_id, "errors": integrity_errors}
            )
            print(
                f"[Corpus Stage 1] 失败 {descriptor.doc_id}：{integrity_errors}",
                flush=True,
            )
            continue

        missing = set(range(1, descriptor.pages + 1)) - existing
        document_started = time.perf_counter()
        parsed_now = 0
        with output_path.open("a", encoding="utf-8", newline="\n") as handle:
            for page in pdf_parser.iter_parse(
                descriptor,
                missing,
                printed_page_overrides=printed_overrides.get(descriptor.doc_id),
                visual_layout_checked_pages=checked_pages.get(descriptor.doc_id),
            ):
                handle.write(json.dumps(page.to_dict(), ensure_ascii=False) + "\n")
                handle.flush()
                parsed_now += 1
                total_completed += 1
                if (
                    parsed_now == 1
                    or parsed_now % 10 == 0
                    or parsed_now == len(missing)
                ):
                    elapsed = time.perf_counter() - started
                    print(
                        f"[Corpus Stage 1][{document_index}/{len(manifest)}] "
                        f"{descriptor.doc_id} 页={len(existing)+parsed_now}/"
                        f"{descriptor.pages}，总体={total_completed}/{total_pages}，"
                        f"ETA={_eta(elapsed, total_completed, total_pages)}",
                        flush=True,
                    )
        summary["documents"][descriptor.doc_id] = {
            "pages_written": len(existing) + parsed_now,
            "pages_reused": len(existing),
            "pages_parsed_now": parsed_now,
            "elapsed_seconds": round(
                time.perf_counter() - document_started,
                3,
            ),
            "status": "completed",
            "output": output_path.relative_to(PROJECT_ROOT).as_posix(),
        }
    summary["total_pages"] = total_pages
    summary["completed_pages"] = total_completed
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    summary_path = output_dir / args.summary_name
    if summary_path.parent != output_dir:
        raise ValueError("--summary-name must be a filename, not a path")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Corpus Stage 1] 完成：{total_completed}/{total_pages}页，"
        f"错误={len(summary['errors'])}，耗时={summary['elapsed_seconds']}秒",
        flush=True,
    )


if __name__ == "__main__":
    main()
