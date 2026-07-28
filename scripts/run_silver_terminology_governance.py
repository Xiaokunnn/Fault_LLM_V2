"""Govern fault-related Chinese endpoints with cached dual-pass verification.

The extraction model's Chinese proposal is never release-eligible by itself.
An endpoint becomes ``secondary_ai_verified`` only when two independent,
conservative verifier prompts agree on the same Chinese canonical label with
high confidence and local protected-token checks pass.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Iterable, Mapping
import unicodedata


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
    contains_han,
    enrich_stable_ids,
    load_chinese_terminology,
    load_fault_ontology,
    normalize_lookup_text,
    validate_chinese_canonicalization,
)


SYSTEM_A = """你是船舶机舱泵系中文术语的保守核验员。输入给出英文/中文来源词形、实体类型、抽取模型提出的中文规范名和原文上下文。
只判断来源词形是否可在该上下文中无损映射为一个中文规范名。必须保留型号、标准号、数值、否定、程度、部件范围和动作方向。
不能因为中文通顺就批准；不能使用上下文中没有的工程结论。若同组包含多个来源词形，必须全部与同一中文概念等价。
输出严格JSON：{"judgments":[{"id":"...","verdict":"approved|rejected|uncertain","canonical_label_zh":"...","confidence":0到1,"reason_code":"..."}]}。"""

SYSTEM_B = """你是拒绝优先的船舶泵系双语术语审计员。逐项检查英文/中文来源词形与候选中文规范名是否存在范围扩大、部件混淆、故障与症状混淆、动作方向改变、条件或型号丢失。
只有无需依赖未给出的外部知识、所有来源词形均与同一中文概念严格等价时才批准。可以纠正候选中文，但不得省略技术限定词。
输出严格JSON：{"judgments":[{"id":"...","verdict":"approved|rejected|uncertain","canonical_label_zh":"...","confidence":0到1,"reason_code":"..."}]}。"""


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def endpoint_key(entity_type: str, surface: str) -> tuple[str, str]:
    return entity_type, normalize_lookup_text(surface)


def stable_term_id(entity_type: str, canonical_zh: str) -> str:
    identity = f"{entity_type}\u241f{normalize_lookup_text(canonical_zh)}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"MPTERM-SILVER-{digest}"


def morphology_forms(value: str) -> set[str]:
    """Generate only conservative English orthographic/number variants."""
    normalized = normalize_lookup_text(value)
    forms = {normalized, normalized.replace("-", " ")}
    for item in list(forms):
        if re.fullmatch(r"[a-z][a-z0-9 /-]{2,}", item):
            words = item.split()
            if words:
                last = words[-1]
                if last.endswith("ies") and len(last) > 4:
                    forms.add(" ".join([*words[:-1], last[:-3] + "y"]))
                elif last.endswith("s") and not last.endswith(("ss", "us")):
                    forms.add(" ".join([*words[:-1], last[:-1]]))
    return {item for item in forms if item}


def terminology_indexes(
    terminology: Mapping[str, object],
) -> tuple[
    dict[tuple[str, str], Mapping[str, object]],
    dict[tuple[str, str], Mapping[str, object]],
]:
    exact: dict[tuple[str, str], Mapping[str, object]] = {}
    morphology: dict[tuple[str, str], Mapping[str, object]] = {}
    for entry in terminology.get("terms", []) or []:
        entity_type = str(entry.get("entity_type", ""))
        for form in entry.get("source_forms", []) or []:
            surface = str(form.get("surface", ""))
            exact[endpoint_key(entity_type, surface)] = entry
            for variant in morphology_forms(surface):
                key = (entity_type, variant)
                if key not in morphology:
                    morphology[key] = entry
                elif morphology[key].get("terminology_id") != entry.get(
                    "terminology_id"
                ):
                    morphology.pop(key, None)
    return exact, morphology


def protected_tokens(
    surfaces: Iterable[str], terminology: Mapping[str, object]
) -> list[str]:
    found: dict[str, str] = {}
    for surface in surfaces:
        for pattern in terminology.get("protected_term_patterns", []) or []:
            for match in re.finditer(str(pattern), surface, flags=re.IGNORECASE):
                token = match.group(0).strip()
                if token:
                    found.setdefault(token.casefold(), token)
    return sorted(found.values(), key=str.casefold)


def token_check(tokens: Iterable[str], canonical_zh: str) -> bool:
    normalized = normalize_lookup_text(canonical_zh)
    return all(normalize_lookup_text(token) in normalized for token in tokens)


def collect_fault_endpoints(
    records: Iterable[Mapping[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    endpoints: dict[tuple[str, str], dict[str, object]] = {}
    for record in records:
        if (
            record.get("decision") != "silver_candidate"
            or not record.get("fault_class_ids")
        ):
            continue
        for side in ("head", "tail"):
            surface = str(record.get(f"{side}_surface") or record.get(side) or "")
            entity_type = str(record.get(f"{side}_type") or "")
            key = endpoint_key(entity_type, surface)
            item = endpoints.setdefault(
                key,
                {
                    "entity_type": entity_type,
                    "surface_forms": set(),
                    "proposed_labels": Counter(),
                    "contexts": [],
                },
            )
            item["surface_forms"].add(surface)
            proposed = str(record.get(f"{side}_canonical_zh") or "").strip()
            if proposed:
                item["proposed_labels"][proposed] += 1
            if len(item["contexts"]) < 2:
                item["contexts"].append(
                    {
                        "doc_id": record.get("doc_id"),
                        "pdf_page_number": record.get("pdf_page_number"),
                        "relation": record.get("relation"),
                        "evidence_text": str(record.get("evidence_text") or "")[
                            :600
                        ],
                    }
                )
    return endpoints


def add_form_to_term(
    term: dict[str, object], surface: str, *, language: str = "en"
) -> None:
    forms = list(term.get("source_forms", []) or [])
    normalized = {
        (str(item.get("language", "")), normalize_lookup_text(item.get("surface")))
        for item in forms
    }
    key = (language, normalize_lookup_text(surface))
    if key not in normalized:
        forms.append({"language": language, "surface": surface})
    term["source_forms"] = forms


def build_queue(
    endpoints: Mapping[tuple[str, str], Mapping[str, object]],
    terminology: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    exact, morphology = terminology_indexes(terminology)
    clusters: dict[tuple[str, str], dict[str, object]] = {}
    counts = Counter()
    terms_by_id = {
        str(item["terminology_id"]): item
        for item in terminology.get("terms", []) or []
    }
    for key, endpoint in endpoints.items():
        entity_type, normalized_surface = key
        surfaces = sorted(endpoint["surface_forms"])
        if key in exact:
            counts["existing_dictionary"] += 1
            continue
        morphology_match = morphology.get((entity_type, normalized_surface))
        if morphology_match is not None:
            term = terms_by_id[str(morphology_match["terminology_id"])]
            for surface in surfaces:
                add_form_to_term(term, surface)
            counts["safe_morphology_alias"] += 1
            continue
        labels = endpoint["proposed_labels"]
        proposed = labels.most_common(1)[0][0] if labels else ""
        if contains_han(normalized_surface) and (
            not proposed
            or normalize_lookup_text(proposed) == normalized_surface
        ):
            counts["source_zh_exact"] += 1
            continue
        cluster_key = (entity_type, normalize_lookup_text(proposed))
        cluster = clusters.setdefault(
            cluster_key,
            {
                "entity_type": entity_type,
                "surface_forms": set(),
                "proposed_canonical_zh": proposed,
                "alternative_proposals": Counter(),
                "contexts": [],
            },
        )
        cluster["surface_forms"].update(surfaces)
        cluster["alternative_proposals"].update(labels)
        for context in endpoint["contexts"]:
            if len(cluster["contexts"]) < 3:
                cluster["contexts"].append(context)
    queue: list[dict[str, object]] = []
    for index, (_, cluster) in enumerate(
        sorted(clusters.items(), key=lambda item: item[0]), start=1
    ):
        surfaces = sorted(cluster["surface_forms"])
        queue.append(
            {
                "id": f"TERM-{index:04d}",
                "entity_type": cluster["entity_type"],
                "source_forms": surfaces,
                "proposed_canonical_zh": cluster["proposed_canonical_zh"],
                "alternative_proposals": [
                    {"label": label, "count": count}
                    for label, count in cluster[
                        "alternative_proposals"
                    ].most_common()
                ],
                "protected_tokens": protected_tokens(surfaces, terminology),
                "contexts": cluster["contexts"],
            }
        )
    counts["dual_pass_queue"] = len(queue)
    return queue, dict(counts)


def normalized_label(value: object) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(value or "")).split()
    )


def build_prompt(batch: list[dict[str, object]]) -> str:
    return json.dumps({"terminology_candidates": batch}, ensure_ascii=False)


def verify_queue(
    queue: list[dict[str, object]],
    *,
    config: Mapping[str, object],
    output_dir: Path,
    batch_size: int,
    dry_run: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    cache_dir = output_dir / "verification_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run and not os.environ.get("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY is required and is never stored.")
    batches = [
        queue[index : index + batch_size]
        for index in range(0, len(queue), batch_size)
    ]
    votes: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    started = time.perf_counter()
    print(
        f"[Terminology] 待双重核验概念={len(queue)}，批次={len(batches)}，"
        f"调用={len(batches)*2}，dry_run={dry_run}",
        flush=True,
    )
    for batch_index, batch in enumerate(batches, start=1):
        prompt = build_prompt(batch)
        for judge, system in (("A", SYSTEM_A), ("B", SYSTEM_B)):
            digest = hashlib.sha256(
                (system + "\n" + prompt).encode("utf-8")
            ).hexdigest()
            cache_path = cache_dir / f"{digest}.json"
            if dry_run:
                continue
            if cache_path.exists():
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                source = "CACHE"
            else:
                response = call_chat_completion(
                    api_key=str(os.environ["DASHSCOPE_API_KEY"]),
                    base_url=str(config["base_url"]),
                    model=str(config["model"]),
                    system_prompt=system,
                    user_prompt=prompt,
                    temperature=0,
                    enable_thinking=False,
                    response_format={"type": "json_object"},
                    timeout_seconds=int(config["timeout_seconds"]),
                    max_retries=int(config["max_retries"]),
                    retry_callback=lambda attempt, maximum, reason, wait: print(
                        f"[Terminology][{batch_index}/{len(batches)}][{judge}] "
                        f"失败 {attempt}/{maximum}，{wait:.0f}s后重试：{reason}",
                        flush=True,
                    ),
                )
                payload = {
                    "model": response.model,
                    "request_id": response.request_id,
                    "latency_ms": response.latency_ms,
                    "prompt_sha256": digest,
                    "response_json": response.content,
                }
                write_json(cache_path, payload)
                source = "API"
            judgments = payload.get("response_json", {}).get("judgments", [])
            if not isinstance(judgments, list):
                raise ValueError("Terminology judgments must be an array")
            for vote in judgments:
                votes[str(vote.get("id", ""))][judge] = dict(vote)
            completed = (batch_index - 1) * 2 + (1 if judge == "A" else 2)
            elapsed = time.perf_counter() - started
            eta = elapsed / completed * (len(batches) * 2 - completed)
            print(
                f"[Terminology][{batch_index}/{len(batches)}][{judge}] "
                f"{source}，累计={elapsed:.1f}s，ETA={eta/60:.1f}分钟",
                flush=True,
            )
    if dry_run:
        return [], []

    approved: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    by_id = {str(item["id"]): item for item in queue}
    for item_id, item in by_id.items():
        pair = votes.get(item_id, {})
        a, b = pair.get("A"), pair.get("B")
        verdicts = [
            str((vote or {}).get("verdict", "")) for vote in (a, b)
        ]
        labels = [
            normalized_label((vote or {}).get("canonical_label_zh"))
            for vote in (a, b)
        ]
        confidences = [
            float((vote or {}).get("confidence", 0) or 0) for vote in (a, b)
        ]
        local_checks = {
            "two_votes_present": a is not None and b is not None,
            "unanimous_approved": verdicts == ["approved", "approved"],
            "minimum_confidence_0_9": (
                len(confidences) == 2 and min(confidences) >= 0.9
            ),
            "same_nonempty_chinese_label": (
                len(labels) == 2
                and bool(labels[0])
                and labels[0] == labels[1]
                and contains_han(labels[0])
            ),
            "protected_tokens_preserved": (
                len(labels) == 2
                and token_check(item["protected_tokens"], labels[0])
            ),
        }
        result = {
            **item,
            "votes": [vote for vote in (a, b) if vote is not None],
            "local_checks": local_checks,
        }
        if all(local_checks.values()):
            result["canonical_label_zh"] = labels[0]
            result["approval_status"] = "secondary_ai_verified"
            approved.append(result)
        else:
            unresolved.append(result)
    return approved, unresolved


def append_verified_terms(
    terminology: dict[str, object],
    approved: list[dict[str, object]],
) -> None:
    terms = list(terminology.get("terms", []) or [])
    by_concept: dict[tuple[str, str], dict[str, object]] = {
        (
            str(term["entity_type"]),
            normalize_lookup_text(term["canonical_label_zh"]),
        ): term
        for term in terms
    }
    for item in approved:
        entity_type = str(item["entity_type"])
        label = str(item["canonical_label_zh"])
        key = (entity_type, normalize_lookup_text(label))
        term = by_concept.get(key)
        if term is None:
            term = {
                "terminology_id": stable_term_id(entity_type, label),
                "entity_type": entity_type,
                "canonical_label_zh": label,
                "source_forms": [],
                "approval_status": "secondary_ai_verified",
                "verification": {
                    "version": "dual_pass_qwen_terminology_v1",
                    "model": "qwen3.7-max",
                    "independent_prompt_roles": 2,
                    "human_expert_reviewed": False,
                    "label_policy": "Silver only; never Gold",
                },
            }
            terms.append(term)
            by_concept[key] = term
        for surface in item["source_forms"]:
            language = "zh" if contains_han(surface) else "en"
            add_form_to_term(term, str(surface), language=language)
        add_form_to_term(term, label, language="zh")
    terminology["terms"] = terms


def recanonicalize_records(
    records: list[dict[str, object]],
    terminology: Mapping[str, object],
) -> list[dict[str, object]]:
    governed: list[dict[str, object]] = []
    for source in records:
        record = dict(source)
        chinese = validate_chinese_canonicalization(
            head_surface=str(record["head_surface"]),
            head_type=str(record["head_type"]),
            relation=str(record["relation"]),
            tail_surface=str(record["tail_surface"]),
            tail_type=str(record["tail_type"]),
            candidate=record,
            terminology=terminology,
        )
        record.update(
            {
                "head_canonical_zh": chinese.head.canonical_label_zh,
                "head_terminology_id": chinese.head.terminology_id,
                "head_source_language": chinese.head.source_language,
                "head_translation_method": chinese.head.translation_method,
                "head_translation_status": chinese.head.translation_status,
                "head_type_label_zh": chinese.head_type_label_zh,
                "tail_canonical_zh": chinese.tail.canonical_label_zh,
                "tail_terminology_id": chinese.tail.terminology_id,
                "tail_source_language": chinese.tail.source_language,
                "tail_translation_method": chinese.tail.translation_method,
                "tail_translation_status": chinese.tail.translation_status,
                "tail_type_label_zh": chinese.tail_type_label_zh,
                "relation_label_zh": chinese.relation_label_zh,
                "graph_display_language": chinese.graph_display_language,
                "terminology_version": chinese.terminology_version,
                "chinese_canonicalization": chinese.to_dict(),
                "chinese_canonicalization_reasons": list(chinese.reasons),
                "eligible_for_chinese_graph": bool(
                    record.get("decision") == "silver_candidate"
                    and chinese.graph_ready
                    and record.get("inferred_edge") is not True
                ),
            }
        )
        record["graph_release_status"] = (
            "core_silver_ready"
            if record["eligible_for_chinese_graph"]
            else "candidate_needs_chinese_normalization"
            if record.get("decision") == "silver_candidate"
            else "not_silver_evidence"
        )
        record["terminology_governance"] = {
            "version": str(
                terminology.get(
                    "version", "marine_pump_zh_terminology_v3_0_silver"
                )
            ),
            "human_expert_reviewed": False,
            "label_policy": "Silver only; never Gold",
        }
        previous_ids = {
            key: record.get(key)
            for key in (
                "head_entity_id",
                "tail_entity_id",
                "claim_id",
                "evidence_id",
                "assertion_id",
                "triple_id",
            )
        }
        for key in previous_ids:
            record.pop(key, None)
        record = enrich_stable_ids(record)
        record["terminology_governance"]["previous_ids"] = previous_ids
        governed.append(record)
    return governed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_evidence_repaired/"
            "candidate_triples.evidence_repaired.jsonl"
        ),
    )
    parser.add_argument(
        "--base-terminology",
        default="configs/entity_terminology_zh_marine_pump_v2.json",
    )
    parser.add_argument(
        "--config",
        default="configs/triple_extraction_qwen3_7_max_full_corpus_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_zh_governed"
        ),
    )
    parser.add_argument(
        "--terminology-output",
        default="configs/entity_terminology_zh_marine_pump_v3_silver.json",
    )
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help=(
            "Write quarantined first-pass outputs without failing when the "
            "Chinese release gate is below 10/10. Intended only when the "
            "gap-reconciliation stage immediately follows."
        ),
    )
    args = parser.parse_args()

    records = read_jsonl(PROJECT_ROOT / args.input)
    terminology = copy.deepcopy(
        load_chinese_terminology(PROJECT_ROOT / args.base_terminology)
    )
    terminology["version"] = "marine_pump_zh_terminology_v3_0_silver"
    terminology["status"] = "secondary_ai_verified_fault_core"
    terminology["human_expert_reviewed"] = False
    terminology["label_policy"] = "Silver only; never Gold"
    endpoints = collect_fault_endpoints(records)
    queue, deterministic_counts = build_queue(endpoints, terminology)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "terminology_verification_queue.json", queue)
    config = json.loads((PROJECT_ROOT / args.config).read_text(encoding="utf-8"))
    approved, unresolved = verify_queue(
        queue,
        config=config,
        output_dir=output_dir,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        summary = {
            "version": "marine_pump_silver_terminology_governance_v1",
            "dry_run": True,
            "fault_related_endpoint_keys": len(endpoints),
            "deterministic_counts": deterministic_counts,
            "dual_pass_queue": len(queue),
            "estimated_api_calls": (
                (len(queue) + args.batch_size - 1) // args.batch_size * 2
            ),
            "human_expert_reviewed": False,
            "label_policy": "Silver only; never Gold",
        }
        write_json(output_dir / "terminology_governance_summary.json", summary)
        print(
            f"[Terminology] dry-run完成：端点={len(endpoints)}，"
            f"双重核验概念={len(queue)}，预计调用="
            f"{summary['estimated_api_calls']}",
            flush=True,
        )
        return

    append_verified_terms(terminology, approved)
    terminology_path = PROJECT_ROOT / args.terminology_output
    write_json(terminology_path, terminology)
    governed = recanonicalize_records(records, terminology)
    governed_path = output_dir / "candidate_triples.zh_governed.jsonl"
    write_jsonl(governed_path, governed)
    write_json(output_dir / "terminology_approved.json", approved)
    write_json(output_dir / "terminology_unresolved.json", unresolved)

    ontology = load_fault_ontology(project_root=PROJECT_ROOT)
    fault_ids = [
        str(item["fault_id"]) for item in ontology["fault_classes"]
    ]
    thresholds = CoverageThresholds.from_ontology(ontology)
    evidence_coverage = build_coverage_report(
        governed,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=False,
    )
    chinese_coverage = build_coverage_report(
        governed,
        fault_ids=fault_ids,
        thresholds=thresholds,
        require_chinese_graph_ready=True,
    )
    write_json(output_dir / "coverage_evidence_only.json", evidence_coverage)
    write_json(output_dir / "coverage_chinese_release.json", chinese_coverage)
    decisions = Counter(str(record.get("decision", "")) for record in governed)
    summary = {
        "version": "marine_pump_silver_terminology_governance_v1",
        "dry_run": False,
        "input_records": len(records),
        "fault_related_silver_records": sum(
            record.get("decision") == "silver_candidate"
            and bool(record.get("fault_class_ids"))
            for record in records
        ),
        "fault_related_endpoint_keys": len(endpoints),
        "deterministic_counts": deterministic_counts,
        "dual_pass_concepts_approved": len(approved),
        "dual_pass_concepts_unresolved": len(unresolved),
        "records_eligible_for_chinese_graph": sum(
            record.get("eligible_for_chinese_graph") is True
            for record in governed
        ),
        "decisions": dict(sorted(decisions.items())),
        "evidence_only_classes_passing": evidence_coverage[
            "fault_classes_passing_gate"
        ],
        "chinese_release_classes_passing": chinese_coverage[
            "fault_classes_passing_gate"
        ],
        "terminology_artifact": str(terminology_path.relative_to(PROJECT_ROOT)),
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    write_json(output_dir / "terminology_governance_summary.json", summary)
    print(
        f"[Terminology] 批准概念={len(approved)}，未决={len(unresolved)}，"
        f"中文图谱记录={summary['records_eligible_for_chinese_graph']}，"
        f"中文覆盖={summary['chinese_release_classes_passing']}/"
        f"{len(fault_ids)}",
        flush=True,
    )
    if (
        summary["chinese_release_classes_passing"] != len(fault_ids)
        and not args.allow_incomplete
    ):
        raise RuntimeError(
            "Chinese release coverage remains below 10/10; unresolved "
            "terminology must remain quarantined."
        )


if __name__ == "__main__":
    main()
