"""Dual-pass semantic adjudication for locally valid, non-E3 Silver candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage02_triple_extraction.bailian_client import (  # noqa: E402
    call_chat_completion,
)
from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    CoverageThresholds,
    build_coverage_report,
    decide_confidence,
    deduplicate_triples,
    load_fault_ontology,
)


RELATION_GLOSS = {
    "causes": "头实体直接导致尾实体",
    "indicates": "头部症状或信号直接指示尾部故障/原因/风险",
    "manifests_as": "头部故障直接表现为尾部症状或信号",
    "evolves_to": "头部故障直接演化为尾部故障或风险",
    "diagnosed_by": "头部诊断目标可由尾部方法或动作诊断",
    "inspected_by": "头部设备/部件/故障可由尾部动作检查",
    "mitigated_by": "头部故障/原因/风险可由尾部维护动作缓解",
    "prevented_by": "头部故障/机理/不期望工况可由尾部维护动作预防",
    "maintained_by": "头部设备或部件通过尾部动作维护",
    "contains": "头部设备或部件包含尾部部件",
    "located_in": "头部部件位于尾部设备或部件",
    "occurs_at": "头部故障发生于尾部设备或部件",
    "operates_under": "头部设备或部件运行于尾部工况",
    "increases_risk_of": "头部条件直接增加尾部风险",
    "specified_by": "头部实体由尾部规范规定",
}

SYSTEM_A = """你是保守的证据关系裁决器。只根据给出的原文，不使用外部知识。
逐条判断“头实体—关系—尾实体”是否被原文直接支持。必须检查否定、条件、方向、
并列项和表格行对应。只有普通读者无需工程常识即可从原文得到该命题时才判
entailed；方向错误或矛盾判not_entailed；其余判uncertain。不得改写实体或关系。
输出严格JSON对象：{"judgments":[{"id":"...","verdict":"entailed|not_entailed|uncertain",
"confidence":0到1,"supporting_quote":"原文中的连续短引文","reason_code":"短代码"}]}。"""

SYSTEM_B = """你是拒绝优先的反证审计器。给定候选关系和原文，主动寻找以下失败：
原文只同时提到两实体、因果/诊断方向相反、关系仅依赖常识、条件句被绝对化、
不同列表项或表格行被错误拼接、否定被忽略。只有排除这些风险且原文直接表达
完整命题时才判entailed。输出严格JSON对象，格式与要求：
{"judgments":[{"id":"...","verdict":"entailed|not_entailed|uncertain",
"confidence":0到1,"supporting_quote":"原文中的连续短引文","reason_code":"短代码"}]}。"""


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def normalized(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def eligible(record: dict[str, object], allowed_splits: set[str] | None = None) -> bool:
    allowed_splits = allowed_splits or {"build_train"}
    evidence = record.get("evidence_validation", {}) or {}
    entailment = record.get("relation_entailment_validation", {}) or {}
    return bool(
        record.get("decision") == "candidate_needs_review"
        and record.get("evidence_level") in {"E1", "E2"}
        and evidence.get("valid") is True
        and evidence.get("silver_eligible") is True
        and record.get("relation_type_valid") is True
        and entailment.get("status") == "undetermined"
        and record.get("document_split") in allowed_splits
        and record.get("inferred_edge") is not True
        and not record.get("semantic_adjudication")
    )


def build_prompt(batch: list[dict[str, object]]) -> str:
    items = []
    for record in batch:
        items.append(
            {
                "id": record["triple_id"],
                "head": record["head"],
                "head_type": record["head_type"],
                "relation": record["relation"],
                "relation_meaning": RELATION_GLOSS.get(
                    str(record["relation"]), str(record["relation"])
                ),
                "tail": record["tail"],
                "tail_type": record["tail_type"],
                "evidence_level": record["evidence_level"],
                "evidence_text": record["evidence_text"],
            }
        )
    return json.dumps({"records": items}, ensure_ascii=False, indent=2)


def quote_verified(record: dict[str, object], vote: dict[str, object]) -> bool:
    quote = normalized(vote.get("supporting_quote", ""))
    evidence = normalized(record.get("evidence_text", ""))
    return bool(quote and len(quote) >= 8 and quote in evidence)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--config", default="configs/triple_extraction_qwen3_7_max_targeted_zh_v1.json")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allowed-splits",
        default="build_train",
        help="Comma-separated document splits eligible for adjudication.",
    )
    parser.add_argument(
        "--reuse-cache-dir",
        action="append",
        default=[],
        help="Additional adjudication output directory whose cache may be reused.",
    )
    args = parser.parse_args()

    config = json.loads((PROJECT_ROOT / args.config).read_text(encoding="utf-8"))
    source_path = PROJECT_ROOT / args.input_dir / "candidate_triples.strict_v2.jsonl"
    records = read_jsonl(source_path)
    allowed_splits = {value.strip() for value in args.allowed_splits.split(",") if value.strip()}
    queue = [record for record in records if eligible(record, allowed_splits)]
    if args.limit is not None:
        queue = queue[: args.limit]
    output_dir = PROJECT_ROOT / args.output_dir
    cache_dir = output_dir / "adjudication_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run and not os.environ.get("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY is required and is never stored.")

    batches = [
        queue[index : index + args.batch_size]
        for index in range(0, len(queue), args.batch_size)
    ]
    votes: dict[str, dict[str, dict[str, object]]] = {}
    started = time.perf_counter()
    print(
        f"[Auto Silver] 开始：可裁决={len(queue)}，批次={len(batches)}，"
        f"双重裁决调用={len(batches) * 2}，dry_run={args.dry_run}",
        flush=True,
    )
    for batch_index, batch in enumerate(batches, start=1):
        prompt = build_prompt(batch)
        for judge_name, system_prompt in (("A", SYSTEM_A), ("B", SYSTEM_B)):
            cache_key = hashlib.sha256(
                (system_prompt + "\n" + prompt).encode("utf-8")
            ).hexdigest()
            cache_path = cache_dir / f"{cache_key}.json"
            reusable_paths = [
                PROJECT_ROOT / value / "adjudication_cache" / cache_path.name
                for value in args.reuse_cache_dir
            ]
            if args.dry_run:
                continue
            if cache_path.exists():
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                source = "CACHE"
            elif next((path for path in reusable_paths if path.exists()), None):
                reusable = next(path for path in reusable_paths if path.exists())
                payload = json.loads(reusable.read_text(encoding="utf-8"))
                cache_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                source = "REUSED_CACHE"
            else:
                response = call_chat_completion(
                    api_key=str(os.environ["DASHSCOPE_API_KEY"]),
                    base_url=str(config["base_url"]),
                    model=str(config["model"]),
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    temperature=0,
                    enable_thinking=False,
                    response_format={"type": "json_object"},
                    timeout_seconds=int(config["timeout_seconds"]),
                    max_retries=int(config["max_retries"]),
                    retry_callback=lambda attempt, maximum, reason, wait: print(
                        f"[Auto Silver][{batch_index}/{len(batches)}][{judge_name}] "
                        f"请求失败 {attempt}/{maximum}，{wait:.0f}s后重试：{reason}",
                        flush=True,
                    ),
                )
                payload = {
                    "model": response.model,
                    "request_id": response.request_id,
                    "latency_ms": response.latency_ms,
                    "prompt_sha256": cache_key,
                    "response_json": response.content,
                }
                cache_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                source = "API"
            judgments = payload.get("response_json", {}).get("judgments", [])
            if not isinstance(judgments, list):
                raise ValueError("Adjudicator judgments must be an array")
            for vote in judgments:
                record_id = str(vote.get("id", ""))
                votes.setdefault(record_id, {})[judge_name] = dict(vote)
            elapsed = time.perf_counter() - started
            completed_calls = (batch_index - 1) * 2 + (1 if judge_name == "A" else 2)
            total_calls = max(1, len(batches) * 2)
            eta = elapsed / completed_calls * (total_calls - completed_calls)
            print(
                f"[Auto Silver][{batch_index}/{len(batches)}][{judge_name}] "
                f"{source}，累计={elapsed:.1f}s，ETA={eta/60:.1f}分钟",
                flush=True,
            )

    if args.dry_run:
        print(
            f"[Auto Silver] dry-run完成：记录={len(queue)}，"
            f"预计API调用={len(batches) * 2}",
            flush=True,
        )
        return

    by_id = {str(record["triple_id"]): record for record in records}
    promoted = rejected = unresolved = 0
    for record_id, judge_votes in votes.items():
        if record_id not in by_id:
            continue
        record = by_id[record_id]
        ordered = [judge_votes.get("A"), judge_votes.get("B")]
        usable = [vote for vote in ordered if isinstance(vote, dict)]
        verdicts = [str(vote.get("verdict", "")) for vote in usable]
        confidences = [
            float(vote.get("confidence", 0) or 0) for vote in usable
        ]
        quote_checks = [quote_verified(record, vote) for vote in usable]
        record["semantic_adjudication"] = {
            "version": "dual_qwen_relation_entailment_v1",
            "model": config["model"],
            "votes": usable,
            "quote_verified": quote_checks,
            "human_expert_reviewed": False,
        }
        unanimous_entailment = bool(
            len(usable) == 2
            and verdicts == ["entailed", "entailed"]
            and min(confidences) >= 0.9
            and all(quote_checks)
        )
        unanimous_rejection = bool(
            len(usable) == 2
            and all(verdict == "not_entailed" for verdict in verdicts)
            and min(confidences) >= 0.9
        )
        if unanimous_entailment:
            relation_entailment = {
                "valid": True,
                "status": "entailed",
                "matched_cues": ["dual_qwen_direct_entailment"],
                "silver_eligible": True,
                "hard_veto_reasons": [],
                "silver_veto_reasons": [],
                "review_reasons": [],
            }
            decision = decide_confidence(
                model_confidence=min(
                    float(record.get("model_confidence", 0) or 0),
                    min(confidences),
                ),
                evidence_validation=record["evidence_validation"],
                relation_type_validation=record["relation_type_validation"],
                relation_entailment_validation=relation_entailment,
                source_tier=str(record.get("source_tier", "")),
                inferred_edge=bool(record.get("inferred_edge", False)),
                document_split=str(record.get("document_split", "")),
            )
            record["relation_entailment_validation"] = relation_entailment
            record["relation_entailment_valid"] = True
            record["decision"] = decision.decision
            record["validation_status"] = decision.decision
            record["final_confidence"] = decision.final_confidence
            record["confidence_components"] = decision.__dict__
            record["review_reasons"] = list(decision.review_reasons)
            record["rejection_reasons"] = list(decision.rejection_reasons)
            record["validator"] = (
                "local:marine_pump_strict_validation_v3_"
                "dual_qwen_semantic_adjudication"
            )
            record["eligible_for_chinese_graph"] = False
            record["graph_release_status"] = (
                "candidate_needs_chinese_normalization"
            )
            promoted += decision.decision == "silver_candidate"
        elif unanimous_rejection:
            record["decision"] = "rejected"
            record["validation_status"] = "rejected"
            record["rejection_reasons"] = list(
                dict.fromkeys(
                    [
                        *(record.get("rejection_reasons", []) or []),
                        "dual_qwen_relation_not_entailed",
                    ]
                )
            )
            rejected += 1
        else:
            unresolved += 1

    deduplicated = deduplicate_triples(records)
    write_jsonl(
        output_dir / "candidate_triples.auto_adjudicated_silver.jsonl",
        list(deduplicated.records),
    )
    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    fault_ids = [str(item["fault_id"]) for item in ontology["fault_classes"]]
    evidence_coverage = build_coverage_report(
        deduplicated.records,
        fault_ids=fault_ids,
        thresholds=CoverageThresholds.from_ontology(ontology),
        require_chinese_graph_ready=False,
    )
    chinese_coverage = build_coverage_report(
        deduplicated.records,
        fault_ids=fault_ids,
        thresholds=CoverageThresholds.from_ontology(ontology),
        require_chinese_graph_ready=True,
    )
    (output_dir / "auto_adjudicated_coverage_evidence_only.json").write_text(
        json.dumps(evidence_coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "auto_adjudicated_coverage_chinese_release.json").write_text(
        json.dumps(chinese_coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    decisions = Counter(str(record["decision"]) for record in deduplicated.records)
    summary = {
        "version": "marine_pump_dual_qwen_auto_silver_v1",
        "input_records": len(records),
        "eligible_for_adjudication": len(queue),
        "promoted_to_silver": promoted,
        "rejected_by_unanimous_adjudication": rejected,
        "unresolved": unresolved,
        "decisions": dict(decisions),
        "evidence_only_classes_passing": evidence_coverage[
            "fault_classes_passing_gate"
        ],
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    (output_dir / "auto_adjudication_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Auto Silver] 完成：晋级Silver={promoted}，自动拒绝={rejected}，"
        f"仍不确定={unresolved}，覆盖={summary['evidence_only_classes_passing']}/10",
        flush=True,
    )


if __name__ == "__main__":
    main()
