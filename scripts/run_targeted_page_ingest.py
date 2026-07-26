"""Parse every page in the frozen targeted-page plan with terminal progress."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import OrderedDict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage01_document_ingest.pipeline import (  # noqa: E402
    ingest_documents,
)


def _load_selections(plan_path: Path) -> OrderedDict[str, list[int]]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    selections: OrderedDict[str, list[int]] = OrderedDict()
    for item in plan["phase_1_pages"]:
        doc_id = str(item["doc_id"])
        selections.setdefault(doc_id, []).append(int(item["pdf_page"]))
    for pages in selections.values():
        pages.sort()
    planned_count = int(plan["phase_1_page_count"])
    actual_count = sum(len(pages) for pages in selections.values())
    if actual_count != planned_count:
        raise ValueError(
            f"Target page plan count mismatch: declared={planned_count}, actual={actual_count}"
        )
    return selections


def _review_metadata() -> tuple[dict[str, dict[int, str]], dict[str, set[int]]]:
    path = PROJECT_ROOT / "configs/page_layout_review_marine_pump_v2.json"
    review = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    printed_overrides: dict[str, dict[int, str]] = {}
    checked_pages: dict[str, set[int]] = {}
    for page_key, metadata in review.get("pages", {}).items():
        doc_id, page_number = page_key.split(":", 1)
        page_number_int = int(page_number)
        if metadata.get("printed_page_label") is not None:
            printed_overrides.setdefault(doc_id, {})[page_number_int] = str(
                metadata["printed_page_label"]
            )
        if metadata.get("visual_layout_checked") is True:
            checked_pages.setdefault(doc_id, set()).add(page_number_int)
    return printed_overrides, checked_pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan",
        default="configs/targeted_page_plan_marine_pump_v2.json",
    )
    parser.add_argument(
        "--output-dir",
        default="data/interim/parsed_pages/targeted_24_v2",
    )
    args = parser.parse_args()

    plan_path = PROJECT_ROOT / args.plan
    selections = _load_selections(plan_path)
    printed_overrides, checked_pages = _review_metadata()
    total_pages = sum(len(pages) for pages in selections.values())
    started = time.perf_counter()

    print(
        f"[Stage 1] 开始解析：{len(selections)}份文档，{total_pages}个定向页面",
        flush=True,
    )

    def report(event: dict[str, object]) -> None:
        kind = event["event"]
        index = event["document_index"]
        total = event["total_documents"]
        doc_id = event["doc_id"]
        elapsed = time.perf_counter() - started
        if kind == "document_started":
            pages = ",".join(str(page) for page in event["selected_pages"])
            print(
                f"[Stage 1][{index}/{total}] 开始 {doc_id}，页码={pages}，"
                f"累计耗时={elapsed:.1f}s",
                flush=True,
            )
        elif kind == "document_completed":
            print(
                f"[Stage 1][{index}/{total}] 完成 {doc_id}："
                f"{event['pages_written']}页，{event['tables']}表，"
                f"{event['text_blocks']}文本块，累计耗时={elapsed:.1f}s",
                flush=True,
            )
        elif kind == "document_failed":
            print(
                f"[Stage 1][{index}/{total}] 失败 {doc_id}：{event['errors']}",
                flush=True,
            )

    summary = ingest_documents(
        PROJECT_ROOT,
        selections,
        PROJECT_ROOT / args.output_dir,
        split_path=PROJECT_ROOT / "configs/document_split_marine_pump_v2.json",
        printed_page_overrides=printed_overrides,
        visual_layout_checked_pages=checked_pages,
        progress_callback=report,
    )
    elapsed = time.perf_counter() - started
    parsed_pages = sum(
        int(item["pages_written"]) for item in summary["documents"].values()
    )
    print(
        f"[Stage 1] 完成：{parsed_pages}/{total_pages}页，"
        f"错误={len(summary['errors'])}，总耗时={elapsed:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
