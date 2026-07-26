"""Run the coordinate-preserving document parser on selected pages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage01_document_ingest.pipeline import (  # noqa: E402
    ingest_documents,
)


def parse_selection(value: str) -> tuple[str, list[int] | None]:
    doc_id, separator, page_spec = value.partition(":")
    if not separator or page_spec.lower() == "all":
        return doc_id, None
    pages: set[int] = set()
    for part in page_spec.split(","):
        if "-" in part:
            start, end = (int(token) for token in part.split("-", 1))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return doc_id, sorted(pages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "selections",
        nargs="+",
        help="DOC_ID:page,page-range or DOC_ID:all",
    )
    parser.add_argument(
        "--output-dir",
        default="data/interim/parsed_pages/layout_v2",
    )
    parser.add_argument(
        "--split",
        default="configs/document_split_marine_pump_v2.json",
    )
    args = parser.parse_args()
    selections = dict(parse_selection(value) for value in args.selections)
    review_config_path = (
        PROJECT_ROOT / "configs/page_layout_review_marine_pump_v2.json"
    )
    review = (
        json.loads(review_config_path.read_text(encoding="utf-8"))
        if review_config_path.exists()
        else {"pages": {}}
    )
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
    summary = ingest_documents(
        PROJECT_ROOT,
        selections,
        PROJECT_ROOT / args.output_dir,
        split_path=PROJECT_ROOT / args.split,
        printed_page_overrides=printed_overrides,
        visual_layout_checked_pages=checked_pages,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
