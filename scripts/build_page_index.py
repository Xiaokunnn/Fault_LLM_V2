"""Build the local SQLite FTS5 index with terminal progress."""

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

from research_point_1_graph_evidence.stage02_triple_extraction.page_index import (  # noqa: E402
    create_index,
    iter_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        default="data/interim/parsed_pages/corpus_v2",
    )
    parser.add_argument(
        "--output",
        default="data/interim/page_index/marine_pump_pages_v1.sqlite",
    )
    args = parser.parse_args()
    input_dir = PROJECT_ROOT / args.input_dir
    paths = sorted(input_dir.glob("*.pages.v2.jsonl"))
    if not paths:
        raise FileNotFoundError(f"No corpus page JSONL files in {input_dir}")
    started = time.perf_counter()
    print(
        f"[Corpus Stage 2] 建立页面索引：输入文档={len(paths)}",
        flush=True,
    )
    result = create_index(
        PROJECT_ROOT / args.output,
        iter_jsonl(paths),
        progress_callback=lambda count: print(
            f"[Corpus Stage 2] 已索引 {count} 页",
            flush=True,
        ),
    )
    summary = {
        "version": "marine_pump_page_index_v1",
        **result,
        "input_documents": len(paths),
        "database": args.output,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    summary_path = PROJECT_ROOT / "data/interim/page_index/index_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Corpus Stage 2] 完成：{summary['pages_indexed']}页，"
        f"耗时={summary['elapsed_seconds']}秒",
        flush=True,
    )


if __name__ == "__main__":
    main()
