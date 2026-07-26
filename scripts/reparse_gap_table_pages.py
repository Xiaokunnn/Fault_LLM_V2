"""Reparse only visually checked table pages in the frozen gap-repair plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
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
    PdfDocumentParser,
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def review_metadata(
    path: Path,
) -> tuple[dict[str, dict[int, str]], dict[str, set[int]]]:
    review = json.loads(path.read_text(encoding="utf-8"))
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan",
        default="data/interim/candidate_pages/gap_repair_v1/candidate_pages.jsonl",
    )
    parser.add_argument(
        "--parsed-dir",
        default="data/interim/parsed_pages/corpus_v2",
    )
    parser.add_argument(
        "--review-config",
        default="configs/page_layout_review_marine_pump_v3.json",
    )
    parser.add_argument(
        "--split",
        default="configs/document_split_marine_pump_v3.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate selected page and table metadata without replacing files.",
    )
    args = parser.parse_args()

    plan_path = PROJECT_ROOT / args.plan
    parsed_dir = PROJECT_ROOT / args.parsed_dir
    selected_by_doc: dict[str, set[int]] = defaultdict(set)
    for item in read_jsonl(plan_path):
        if item.get("table_reparse_required") is True:
            selected_by_doc[str(item["doc_id"])].add(
                int(item["pdf_page_number"])
            )
    if not selected_by_doc:
        raise ValueError("Gap plan has no verified table pages to reparse")

    manifest = load_document_manifest(
        PROJECT_ROOT,
        split_path=PROJECT_ROOT / args.split,
    )
    printed, checked = review_metadata(PROJECT_ROOT / args.review_config)
    parser_impl = PdfDocumentParser(PROJECT_ROOT)
    total = sum(len(value) for value in selected_by_doc.values())
    completed = 0
    started = time.perf_counter()
    results: list[dict[str, object]] = []
    print(
        f"[Gap Tables] 开始：文档={len(selected_by_doc)}，页面={total}，"
        f"dry_run={args.dry_run}",
        flush=True,
    )

    for doc_index, doc_id in enumerate(sorted(selected_by_doc), start=1):
        if doc_id not in manifest:
            raise KeyError(f"Unknown document in gap plan: {doc_id}")
        descriptor = manifest[doc_id]
        integrity_errors = validate_local_file(PROJECT_ROOT, descriptor)
        if integrity_errors:
            raise ValueError(f"{doc_id} integrity failed: {integrity_errors}")
        page_numbers = selected_by_doc[doc_id]
        unreviewed = page_numbers - checked.get(doc_id, set())
        if unreviewed:
            raise ValueError(
                f"Refusing to mark unreviewed tables as valid: {doc_id}:{sorted(unreviewed)}"
            )
        output_path = parsed_dir / f"{doc_id}.pages.v2.jsonl"
        existing_rows = read_jsonl(output_path)
        before_sha = file_sha256(output_path)
        by_page = {
            int(record["pdf_page_number"]): record for record in existing_rows
        }
        if len(by_page) != descriptor.pages:
            raise ValueError(
                f"{doc_id} parsed corpus is incomplete: "
                f"{len(by_page)}/{descriptor.pages}"
            )

        reparsed: list[dict[str, object]] = []
        for page in parser_impl.iter_parse(
            descriptor,
            page_numbers,
            printed_page_overrides=printed.get(doc_id),
            visual_layout_checked_pages=checked.get(doc_id),
        ):
            record = page.to_dict()
            if record.get("visual_layout_checked") is not True:
                raise ValueError(
                    f"Visual layout flag lost: {doc_id}:{page.pdf_page_number}"
                )
            if not record.get("tables"):
                raise ValueError(
                    f"Expected explicit table was not parsed: "
                    f"{doc_id}:{page.pdf_page_number}"
                )
            for table in record.get("tables", []):
                for row in table.get("rows", []):
                    if not row.get("row_id") or not row.get("row_group_id"):
                        raise ValueError(
                            f"Missing row/row-group identity: "
                            f"{doc_id}:{page.pdf_page_number}"
                        )
            reparsed.append(record)
            completed += 1
            elapsed = time.perf_counter() - started
            eta = elapsed / completed * (total - completed)
            print(
                f"[Gap Tables][{completed}/{total}] "
                f"{doc_id}:p{page.pdf_page_number:04d}，"
                f"tables={len(record['tables'])}，ETA={eta/60:.1f}分钟",
                flush=True,
            )

        if {int(item["pdf_page_number"]) for item in reparsed} != page_numbers:
            raise ValueError(f"Reparse page set mismatch for {doc_id}")
        for record in reparsed:
            by_page[int(record["pdf_page_number"])] = record

        after_sha = before_sha
        if not args.dry_run:
            temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                for page_number in sorted(by_page):
                    handle.write(
                        json.dumps(by_page[page_number], ensure_ascii=False) + "\n"
                    )
            temp_path.replace(output_path)
            after_sha = file_sha256(output_path)
        results.append(
            {
                "doc_id": doc_id,
                "pages": sorted(page_numbers),
                "before_sha256": before_sha,
                "after_sha256": after_sha,
                "status": "validated_only" if args.dry_run else "reparsed_and_replaced",
            }
        )
        print(
            f"[Gap Tables][{doc_index}/{len(selected_by_doc)}] "
            f"{doc_id}完成：页面={len(page_numbers)}",
            flush=True,
        )

    summary = {
        "version": "marine_pump_gap_table_reparse_v1",
        "dry_run": args.dry_run,
        "documents": len(results),
        "pages": total,
        "same_row_and_row_group_required": True,
        "visual_layout_review_required": True,
        "results": results,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    summary_path = (
        PROJECT_ROOT
        / "data/interim/candidate_pages/gap_repair_v1/table_reparse_summary.json"
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Gap Tables] 完成：页面={total}，耗时={summary['elapsed_seconds']}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
