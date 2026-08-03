#!/usr/bin/env python3
"""Dual-prompt qwen3.7-max Silver entailment audit of frozen RP2 answers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_point_1_graph_evidence.stage02_triple_extraction.bailian_client import call_chat_completion  # noqa: E402


SYSTEM_A = """你是严格的回答—证据蕴含裁决器。只能使用每条记录中列出的引用原文，不使用外部知识。
逐项判断answer_text是否被cited_evidence直接支持。必须检查否定、条件、对象、方向、范围和绝对化。
supported表示原文直接支持完整表述；partial表示仅支持部分或回答扩大了范围；unsupported表示矛盾、无依据或引用无关。
每项必须给出引用原文中的连续短引文。输出严格JSON：
{"judgments":[{"item_id":"...","verdict":"supported|partial|unsupported","confidence":0到1,"supporting_quote":"连续原文短引文","reason_code":"短代码"}]}。"""

SYSTEM_B = """你是拒绝优先的回答反证审计器。只能根据给出的cited_evidence，主动寻找answer_text中的过度推断：
对象偷换、因果方向错误、条件被删除、可能性被写成确定性、不同证据错误拼接、维护建议超出原文、摘要加入新事实。
只有排除这些风险后才判supported；存在局部支持但表述更强判partial；找不到直接支持或存在矛盾判unsupported。
每项必须给出引用原文中的连续短引文。输出严格JSON：
{"judgments":[{"item_id":"...","verdict":"supported|partial|unsupported","confidence":0到1,"supporting_quote":"连续原文短引文","reason_code":"短代码"}]}。"""


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def _normalize(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def _quote_verified(item: dict, vote: dict) -> bool:
    quote = _normalize(vote.get("supporting_quote", ""))
    evidence = _normalize("\n".join(row["verbatim"] for row in item["cited_evidence"]))
    return bool(len(quote) >= 8 and quote in evidence)


def _build_items(config: dict) -> tuple[list[dict], dict[str, dict]]:
    generation_rows = _read_jsonl(ROOT / config["source_generation_results"])
    selected = set(config["selected_methods"])
    chosen = [row for row in generation_rows if row["method"] in selected]
    by_answer = {f"{row['method']}::{row['query_id']}": row for row in chosen}
    if len(by_answer) != 40 * len(selected):
        raise RuntimeError(
            f"Expected {40 * len(selected)} unique finalist answers, found {len(by_answer)}"
        )
    benchmark = ROOT / config["benchmark_dir"]
    candidates = {row["evidence_id"]: row for row in _read_jsonl(benchmark / "evidence_candidates.jsonl")}
    queries = {row["query_id"]: row for row in _read_jsonl(benchmark / "queries.jsonl")}
    items = []
    for answer_id, row in sorted(by_answer.items()):
        answer = row.get("answer", {})
        if row.get("validation", {}).get("status") != "answered":
            continue
        all_citations = []
        for point_index, point in enumerate(answer.get("answer_points", [])):
            citations = [str(value) for value in point.get("evidence_ids", [])]
            all_citations.extend(citations)
            items.append({
                "item_id": f"{answer_id}::point::{point_index}",
                "answer_id": answer_id,
                "method": row["method"],
                "query_id": row["query_id"],
                "item_kind": "answer_point",
                "question": queries[row["query_id"]]["question_zh"],
                "answer_text": str(point.get("text", "")),
                "cited_evidence": [
                    {
                        "evidence_id": evidence_id,
                        "claim": (
                            f"{candidates[evidence_id]['head_label_zh']} --"
                            f"{candidates[evidence_id]['relation']}--> "
                            f"{candidates[evidence_id]['tail_label_zh']}"
                        ),
                        "verbatim": candidates[evidence_id]["evidence_text"],
                    }
                    for evidence_id in citations if evidence_id in candidates
                ],
            })
        summary = str(answer.get("summary", "")).strip()
        unique_citations = list(dict.fromkeys(all_citations))
        if summary:
            items.append({
                "item_id": f"{answer_id}::summary",
                "answer_id": answer_id,
                "method": row["method"],
                "query_id": row["query_id"],
                "item_kind": "summary",
                "question": queries[row["query_id"]]["question_zh"],
                "answer_text": summary,
                "cited_evidence": [
                    {
                        "evidence_id": evidence_id,
                        "claim": (
                            f"{candidates[evidence_id]['head_label_zh']} --"
                            f"{candidates[evidence_id]['relation']}--> "
                            f"{candidates[evidence_id]['tail_label_zh']}"
                        ),
                        "verbatim": candidates[evidence_id]["evidence_text"],
                    }
                    for evidence_id in unique_citations if evidence_id in candidates
                ],
            })
    return items, by_answer


def _summarize(items: list[dict], votes: dict[str, dict], by_answer: dict[str, dict], config: dict) -> dict:
    item_rows = []
    for item in items:
        pair = votes.get(item["item_id"], {})
        vote_a, vote_b = pair.get("A", {}), pair.get("B", {})
        verdict_a, verdict_b = vote_a.get("verdict"), vote_b.get("verdict")
        quote_a, quote_b = _quote_verified(item, vote_a), _quote_verified(item, vote_b)
        item_rows.append({
            **{key: item[key] for key in ("item_id", "answer_id", "method", "query_id", "item_kind")},
            "judge_a": vote_a,
            "judge_b": vote_b,
            "judge_agreement": verdict_a == verdict_b,
            "quote_verified_a": quote_a,
            "quote_verified_b": quote_b,
            "dual_strict_supported": verdict_a == verdict_b == "supported" and quote_a and quote_b,
            "dual_no_unsupported": verdict_a != "unsupported" and verdict_b != "unsupported",
        })
    methods = {}
    for method in config["selected_methods"]:
        rows = [row for row in item_rows if row["method"] == method]
        point_rows = [row for row in rows if row["item_kind"] == "answer_point"]
        answer_ids = [key for key, value in by_answer.items() if value["method"] == method]
        answered_ids = {
            key for key in answer_ids
            if by_answer[key].get("validation", {}).get("status") == "answered"
        }
        judged_by_answer = defaultdict(list)
        for row in rows:
            judged_by_answer[row["answer_id"]].append(row)
        methods[method] = {
            "total_answers": len(answer_ids),
            "answered_answers": len(answered_ids),
            "judged_items": len(rows),
            "judged_answer_points": len(point_rows),
            "dual_strict_point_support_rate": statistics.fmean(
                [float(row["dual_strict_supported"]) for row in point_rows]
            ) if point_rows else None,
            "dual_non_unsupported_point_rate": statistics.fmean(
                [float(row["dual_no_unsupported"]) for row in point_rows]
            ) if point_rows else None,
            "judge_agreement_rate": statistics.fmean(
                [float(row["judge_agreement"]) for row in rows]
            ) if rows else None,
            "quote_verification_rate": statistics.fmean(
                [float(row["quote_verified_a"] and row["quote_verified_b"]) for row in rows]
            ) if rows else None,
            "all_text_strictly_supported_answer_rate": (
                sum(
                    bool(judged_by_answer[answer_id])
                    and all(row["dual_strict_supported"] for row in judged_by_answer[answer_id])
                    for answer_id in answered_ids
                ) / len(answered_ids)
                if answered_ids else None
            ),
        }
    return {
        "protocol_id": config["protocol_id"],
        "model": config["model"],
        "independent_models": 1,
        "independent_prompt_roles": 2,
        "selected_methods": config["selected_methods"],
        "answer_records": len(by_answer),
        "judged_items": len(item_rows),
        "methods": methods,
        "item_results": item_rows,
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "metric_boundary": "Dual prompts use the same qwen3.7-max model; this is Silver semantic audit, not independent human verification",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rp2_semantic_judge_qwen3_7_max_v1.json")
    parser.add_argument("--limit", type=int, default=0, help="Limit answer items for smoke testing")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    items, by_answer = _build_items(config)
    if args.limit:
        items = items[: args.limit]
    batch_size = int(config["batch_size"])
    batches = [items[index:index + batch_size] for index in range(0, len(items), batch_size)]
    output = ROOT / config["output_dir"]
    cache = output / "judge_cache"
    cache.mkdir(parents=True, exist_ok=True)
    if not args.dry_run and not os.environ.get("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY is required and is never stored")
    votes: dict[str, dict[str, dict]] = defaultdict(dict)
    started = time.perf_counter()
    total_calls = len(batches) * 2
    completed_calls = 0
    for batch_index, batch in enumerate(batches, start=1):
        prompt = json.dumps({"items": batch}, ensure_ascii=False, indent=2)
        for judge_name, system_prompt in (("A", SYSTEM_A), ("B", SYSTEM_B)):
            cache_key = hashlib.sha256((system_prompt + "\n" + prompt).encode("utf-8")).hexdigest()
            cache_path = cache / f"{cache_key}.json"
            if args.dry_run:
                continue
            if cache_path.exists():
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                source = "CACHE"
                should_cache = False
            else:
                response = call_chat_completion(
                    api_key=os.environ["DASHSCOPE_API_KEY"],
                    base_url=config["base_url"], model=config["model"],
                    system_prompt=system_prompt, user_prompt=prompt,
                    temperature=float(config["temperature"]),
                    enable_thinking=bool(config["enable_thinking"]),
                    response_format=config["response_format"],
                    timeout_seconds=int(config["timeout_seconds"]),
                    max_retries=int(config["max_retries"]),
                    retry_callback=lambda attempt, maximum, reason, wait: print(
                        f"[RP2 Judge][{batch_index}/{len(batches)}][{judge_name}] "
                        f"retry {attempt}/{maximum} in {wait:.0f}s: {reason}", flush=True
                    ),
                )
                payload = {
                    "model": response.model,
                    "request_id": response.request_id,
                    "latency_ms": response.latency_ms,
                    "usage": response.usage,
                    "prompt_sha256": cache_key,
                    "response_json": response.content,
                }
                source = "API"
                should_cache = True
            judgments = payload.get("response_json", {}).get("judgments", [])
            if not isinstance(judgments, list):
                raise ValueError("Judge response judgments must be a list")
            expected = {item["item_id"] for item in batch}
            returned = {str(vote.get("item_id", "")) for vote in judgments}
            if expected != returned:
                raise ValueError(
                    f"Judge {judge_name} batch {batch_index} ID mismatch: "
                    f"missing={sorted(expected-returned)}, extra={sorted(returned-expected)}"
                )
            for vote in judgments:
                if vote.get("verdict") not in {"supported", "partial", "unsupported"}:
                    raise ValueError(
                        f"Judge {judge_name} returned invalid verdict: {vote.get('verdict')}"
                    )
                votes[str(vote["item_id"])][judge_name] = dict(vote)
            if should_cache:
                cache_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            completed_calls += 1
            elapsed = time.perf_counter() - started
            eta = elapsed / completed_calls * (total_calls - completed_calls) / 60
            print(
                f"[RP2 Judge][{batch_index}/{len(batches)}][{judge_name}] "
                f"{source}, elapsed={elapsed:.1f}s, ETA={eta:.1f}m",
                flush=True,
            )
    if args.dry_run:
        print(
            f"[RP2 Judge] dry-run: answers={len(by_answer)}, items={len(items)}, "
            f"batches={len(batches)}, API calls={total_calls}", flush=True
        )
        return 0
    missing = [item["item_id"] for item in items if set(votes[item["item_id"]]) != {"A", "B"}]
    if missing:
        raise RuntimeError(f"Incomplete dual-prompt judgments: {missing[:10]}")
    summary = _summarize(items, votes, by_answer, config)
    summary["formal_full_answer_run"] = not args.limit
    output.mkdir(parents=True, exist_ok=True)
    (output / "semantic_judge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[RP2 Judge] completed: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
