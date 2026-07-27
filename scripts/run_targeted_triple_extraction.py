"""Run resumable qwen3.7-max extraction on the frozen 24-page plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage02_triple_extraction.bailian_client import (  # noqa: E402
    call_chat_completion,
)
from research_point_1_graph_evidence.stage02_triple_extraction.chinese_extraction_contract import (  # noqa: E402
    build_user_prompt,
    normalize_model_candidate,
    system_prompt_for_version,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _load_pages(
    input_dir: Path,
    plan_path: Path,
) -> list[dict[str, object]]:
    page_lookup: dict[tuple[str, int], dict[str, object]] = {}
    for path in input_dir.glob("*.pages.v2.jsonl"):
        for page in _read_jsonl(path):
            key = (str(page["doc_id"]), int(page["pdf_page_number"]))
            page_lookup[key] = page
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    pages: list[dict[str, object]] = []
    for item in plan["phase_1_pages"]:
        key = (str(item["doc_id"]), int(item["pdf_page"]))
        if key not in page_lookup:
            raise KeyError(f"Targeted parsed page not found: {key[0]}:{key[1]}")
        page = dict(page_lookup[key])
        page["target_fault_classes"] = list(item["target_fault_classes"])
        page["target_evidence_roles"] = list(item["target_evidence_roles"])
        page["scope_note"] = item.get("scope_note")
        pages.append(page)
    if len(pages) != int(plan["phase_1_page_count"]):
        raise ValueError("Loaded page count does not match the targeted plan")
    return pages


def _load_candidate_pool_pages(
    input_dir: Path,
    candidate_pool_path: Path,
) -> list[dict[str, object]]:
    pool_items = _read_jsonl(candidate_pool_path)
    needed = {
        (str(item["doc_id"]), int(item["pdf_page_number"]))
        for item in pool_items
    }
    page_lookup: dict[tuple[str, int], dict[str, object]] = {}
    for path in input_dir.glob("*.pages.v2.jsonl"):
        for page in _read_jsonl(path):
            key = (str(page["doc_id"]), int(page["pdf_page_number"]))
            if key in needed:
                page_lookup[key] = page
    pages: list[dict[str, object]] = []
    for item in pool_items:
        key = (str(item["doc_id"]), int(item["pdf_page_number"]))
        if key not in page_lookup:
            raise KeyError(f"Candidate page not parsed: {key[0]}:{key[1]}")
        page = dict(page_lookup[key])
        page["target_fault_classes"] = list(
            item.get("target_fault_classes", []) or []
        )
        page["target_evidence_roles"] = list(
            item.get("target_evidence_roles", []) or []
        )
        page["retrieval_details"] = list(
            item.get("retrieval_details", []) or []
        )
        page["scope_note"] = "corpus_retrieval_v1"
        pages.append(page)
    return pages


def _page_key(page: dict[str, object]) -> str:
    return f"{page['doc_id']}:p{int(page['pdf_page_number']):04d}"


def _candidate_id(candidate: dict[str, object]) -> str:
    identity = "\u241f".join(
        str(candidate.get(key, ""))
        for key in (
            "doc_id",
            "pdf_page_number",
            "head_surface",
            "head_type",
            "relation",
            "tail_surface",
            "tail_type",
            "evidence_text",
        )
    )
    return "MPT-" + _sha256(identity)[:20]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _chunk_table_page(
    page: dict[str, object],
    *,
    max_row_groups: int,
) -> list[dict[str, object]]:
    """Split a dense table page without breaking parser row groups."""
    tables = list(page.get("tables", []) or [])
    if max_row_groups <= 0 or not tables:
        return [page]
    rows = [
        (table_index, row)
        for table_index, table in enumerate(tables)
        for row in list(table.get("rows", []) or [])
    ]
    group_order: list[str] = []
    for table_index, row in rows:
        group_id = str(
            row.get("row_group_id")
            or row.get("row_id")
            or f"table-{table_index}-row-{len(group_order)}"
        )
        qualified = f"{table_index}:{group_id}"
        if qualified not in group_order:
            group_order.append(qualified)
    if len(group_order) <= max_row_groups:
        return [page]

    chunks: list[dict[str, object]] = []
    for offset in range(0, len(group_order), max_row_groups):
        selected = set(group_order[offset : offset + max_row_groups])
        chunk = dict(page)
        chunk_tables: list[dict[str, object]] = []
        text_parts: list[str] = []
        for table_index, table in enumerate(tables):
            chunk_table = dict(table)
            selected_rows = []
            for row in list(table.get("rows", []) or []):
                group_id = str(row.get("row_group_id") or row.get("row_id"))
                if f"{table_index}:{group_id}" in selected:
                    selected_rows.append(row)
                    for cell in list(row.get("cells", []) or []):
                        cell_text = str(cell.get("text", "")).strip()
                        if cell_text:
                            text_parts.append(cell_text)
            if selected_rows:
                chunk_table["rows"] = selected_rows
                chunk_tables.append(chunk_table)
        chunk["tables"] = chunk_tables
        chunk["page_text"] = "\n".join(text_parts)
        chunk["scope_note"] = (
            str(page.get("scope_note") or "")
            + f"; dense_table_chunk={len(chunks)+1}"
        )
        chunks.append(chunk)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/triple_extraction_qwen3_7_max_targeted_zh_v1.json",
    )
    parser.add_argument(
        "--plan",
        default="configs/targeted_page_plan_marine_pump_v2.json",
    )
    parser.add_argument("--candidate-pool")
    parser.add_argument("--input-dir")
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--reuse-cache-dir",
        action="append",
        default=[],
        help="Additional extraction directory whose raw_responses may be reused",
    )
    parser.add_argument(
        "--pages",
        help="Comma-separated DOC_ID:PAGE keys; default is all 24 planned pages",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and prompts without calling Bailian",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore cached page responses",
    )
    args = parser.parse_args()

    config = json.loads(
        (PROJECT_ROOT / args.config).read_text(encoding="utf-8")
    )
    system_prompt = system_prompt_for_version(str(config["prompt_version"]))
    input_dir = PROJECT_ROOT / str(
        args.input_dir or config["input_page_dir"]
    )
    output_dir = PROJECT_ROOT / str(
        args.output_dir or config["output_dir"]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw_responses"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pages = (
        _load_candidate_pool_pages(
            input_dir,
            PROJECT_ROOT / args.candidate_pool,
        )
        if args.candidate_pool
        else _load_pages(input_dir, PROJECT_ROOT / args.plan)
    )
    if args.pages:
        selected = {
            value.strip().replace(":p", ":")
            for value in args.pages.split(",")
            if value.strip()
        }
        pages = [
            page
            for page in pages
            if f"{page['doc_id']}:{int(page['pdf_page_number'])}" in selected
        ]
        if len(pages) != len(selected):
            found = {
                f"{page['doc_id']}:{int(page['pdf_page_number'])}"
                for page in pages
            }
            raise KeyError(f"Requested pages not in plan: {sorted(selected - found)}")
    if args.limit is not None:
        pages = pages[: args.limit]
    if not pages:
        raise ValueError("No pages selected")

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not args.dry_run and not api_key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY is not set in this terminal. "
            "Set it as an environment variable; never write it into the project."
        )

    started = time.perf_counter()
    run_id = (
        "qwen3_7_max_targeted_zh_v1_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    all_candidates: list[dict[str, object]] = []
    rejected_proposals: list[dict[str, object]] = []
    page_results: list[dict[str, object]] = []
    print(
        f"[Stage 2] 开始：模型={config['model']}，页面={len(pages)}，"
        f"dry_run={args.dry_run}，resume={not args.no_resume}",
        flush=True,
    )

    for index, page in enumerate(pages, start=1):
        key = _page_key(page)
        cache_path = raw_dir / f"{key.replace(':', '_')}.json"
        prompt = build_user_prompt(page)
        prompt_hash = _sha256(system_prompt + "\n" + prompt)
        chunk_config = dict(
            dict(config.get("request_chunking", {})).get(key, {}) or {}
        )
        request_pages = _chunk_table_page(
            page,
            max_row_groups=int(chunk_config.get("max_table_row_groups", 0)),
        )
        elapsed = time.perf_counter() - started
        print(
            f"[Stage 2][{index}/{len(pages)}] 开始 {key}，累计耗时={elapsed:.1f}s",
            flush=True,
        )

        if args.dry_run:
            page_results.append(
                {
                    "page_key": key,
                    "status": "dry_run",
                    "prompt_sha256": prompt_hash,
                    "prompt_chars": len(prompt),
                }
            )
            print(
                f"[Stage 2][{index}/{len(pages)}] 校验完成 {key}，"
                f"prompt_chars={len(prompt)}",
                flush=True,
            )
            continue

        cached = None
        cache_candidates = [cache_path]
        cache_candidates.extend(
            PROJECT_ROOT / value / "raw_responses" / cache_path.name
            for value in args.reuse_cache_dir
        )
        if not args.no_resume:
            for candidate_path in cache_candidates:
                if not candidate_path.exists():
                    continue
                candidate_cache = json.loads(
                    candidate_path.read_text(encoding="utf-8")
                )
                if (
                    candidate_cache.get("prompt_sha256") == prompt_hash
                    and candidate_cache.get("model_requested") == config["model"]
                ):
                    cached = candidate_cache
                    if candidate_path != cache_path:
                        cache_path.write_text(
                            json.dumps(cached, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8",
                        )
                    break

        if cached is None:
            part_records = []
            for part_index, request_page in enumerate(request_pages, start=1):
                part_prompt = build_user_prompt(request_page)
                part_hash = _sha256(system_prompt + "\n" + part_prompt)
                part_path = (
                    raw_dir
                    / f"{key.replace(':', '_')}_part{part_index:02d}.json"
                )
                part_cached = None
                if not args.no_resume and part_path.exists():
                    candidate_part = json.loads(
                        part_path.read_text(encoding="utf-8")
                    )
                    if (
                        candidate_part.get("prompt_sha256") == part_hash
                        and candidate_part.get("model_requested") == config["model"]
                    ):
                        part_cached = candidate_part
                if part_cached is None:
                    if len(request_pages) > 1:
                        print(
                            f"[Stage 2][{index}/{len(pages)}] {key} "
                            f"表格分块 {part_index}/{len(request_pages)}",
                            flush=True,
                        )
                    response = call_chat_completion(
                        api_key=str(api_key),
                        base_url=str(config["base_url"]),
                        model=str(config["model"]),
                        system_prompt=system_prompt,
                        user_prompt=part_prompt,
                        temperature=float(config["temperature"]),
                        enable_thinking=bool(config["enable_thinking"]),
                        response_format=dict(config["response_format"]),
                        timeout_seconds=int(config["timeout_seconds"]),
                        max_retries=int(config["max_retries"]),
                        retry_callback=lambda attempt, maximum, reason, wait: print(
                            f"[Stage 2][{index}/{len(pages)}] {key} 请求失败，"
                            f"第{attempt}/{maximum}次，{wait:.0f}s后重试：{reason}",
                            flush=True,
                        ),
                    )
                    part_cached = {
                        "page_key": key,
                        "request_part": part_index,
                        "request_part_count": len(request_pages),
                        "model_requested": config["model"],
                        "model_returned": response.model,
                        "request_id": response.request_id,
                        "finish_reason": response.finish_reason,
                        "usage": response.usage,
                        "latency_ms": response.latency_ms,
                        "attempt": response.attempt,
                        "prompt_sha256": part_hash,
                        "response_json": response.content,
                    }
                    part_path.write_text(
                        json.dumps(part_cached, ensure_ascii=False, indent=2)
                        + "\n",
                        encoding="utf-8",
                    )
                part_records.append(part_cached)
            triples = []
            warnings = []
            for part in part_records:
                triples.extend(
                    list(part.get("response_json", {}).get("triples", []) or [])
                )
                warnings.extend(
                    list(part.get("response_json", {}).get("warnings", []) or [])
                )
            cached = {
                "page_key": key,
                "model_requested": config["model"],
                "model_returned": config["model"],
                "request_id": "chunked:" + ",".join(
                    str(part.get("request_id") or "") for part in part_records
                ),
                "finish_reason": "merged_chunks",
                "usage": {"request_parts": len(part_records)},
                "latency_ms": sum(
                    int(part.get("latency_ms") or 0) for part in part_records
                ),
                "attempt": max(
                    int(part.get("attempt") or 1) for part in part_records
                ),
                "prompt_sha256": prompt_hash,
                "response_json": {
                    "triples": triples,
                    "warnings": list(dict.fromkeys(warnings)),
                },
            }
            cache_path.write_text(
                json.dumps(cached, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            cache_status = "API"
        else:
            cache_status = "CACHE"

        proposals = cached.get("response_json", {}).get("triples", [])
        if not isinstance(proposals, list):
            raise ValueError(f"Model triples must be a list for {key}")
        retained = 0
        for proposal_index, proposal in enumerate(proposals):
            try:
                candidate = normalize_model_candidate(proposal, page=page)
                candidate["triple_id"] = _candidate_id(candidate)
                candidate["extractor"] = (
                    f"bailian:{config['model']}:{config['prompt_version']}"
                )
                candidate["extraction_run_id"] = run_id
                candidate["model_request_id"] = cached.get("request_id")
                candidate["api_latency_ms"] = cached.get("latency_ms")
                candidate["prompt_sha256"] = prompt_hash
                candidate["model_page_warnings"] = list(
                    cached.get("response_json", {}).get("warnings", []) or []
                )
                all_candidates.append(candidate)
                retained += 1
            except (TypeError, ValueError) as error:
                rejected_proposals.append(
                    {
                        "page_key": key,
                        "proposal_index": proposal_index,
                        "reason": str(error),
                        "proposal": proposal,
                    }
                )
        elapsed = time.perf_counter() - started
        eta = (
            elapsed / index * (len(pages) - index)
            if index > 0
            else 0.0
        )
        page_results.append(
            {
                "page_key": key,
                "status": "completed",
                "source": cache_status,
                "raw_proposals": len(proposals),
                "retained_candidates": retained,
                "rejected_proposals": len(proposals) - retained,
                "request_id": cached.get("request_id"),
                "latency_ms": cached.get("latency_ms"),
                "usage": cached.get("usage", {}),
            }
        )
        print(
            f"[Stage 2][{index}/{len(pages)}] 完成 {key}："
            f"来源={cache_status}，原始={len(proposals)}，保留={retained}，"
            f"拒绝={len(proposals)-retained}，累计耗时={elapsed:.1f}s，"
            f"ETA={eta/60:.1f}分钟",
            flush=True,
        )

    if not args.dry_run:
        _write_jsonl(output_dir / "candidate_triples.raw_zh.jsonl", all_candidates)
        _write_jsonl(
            output_dir / "rejected_model_proposals.jsonl",
            rejected_proposals,
        )
    summary = {
        "version": "qwen3_7_max_targeted_zh_v1_run",
        "run_id": run_id,
        "dry_run": args.dry_run,
        "model": config["model"],
        "pages_selected": len(pages),
        "pages_completed": len(page_results),
        "raw_proposals": sum(
            int(item.get("raw_proposals", 0)) for item in page_results
        ),
        "retained_candidates": len(all_candidates),
        "rejected_proposals": len(rejected_proposals),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "page_results": page_results,
    }
    (output_dir / "extraction_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Stage 2] 完成：页面={len(page_results)}，"
        f"候选={len(all_candidates)}，拒绝提议={len(rejected_proposals)}，"
        f"总耗时={summary['elapsed_seconds']}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
