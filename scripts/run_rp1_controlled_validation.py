#!/usr/bin/env python3
"""Small, source-first RP1 human-reference pilot. No network or graph writes.

prepare -> human source annotation -> seal -> human candidate review -> audit.
Archived assets are read from a pinned Git commit, including Linux-only paths.
No old AI labels or heuristic semantic matches are promoted to human labels.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/rp1_controlled_validation_v1.json"
DEFAULT_OUT = ROOT / "results/experiments/research_point_1/controlled_validation_v1_20261109"
BUILD = {f"MP{i:03d}" for i in [*range(1, 8), *range(15, 23)]}
VERDICTS = {"complete", "wrong_role", "wrong_direction", "partial_conditions",
            "insufficient_evidence", "unsupported", "out_of_scope", "unresolved"}


class PilotError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    data = Path(path).read_text(encoding="utf-8")
    return [json.loads(x) for x in data.splitlines() if x.strip()] if str(path).endswith(".jsonl") else json.loads(data)


def write(path, value, *, text=False):
    """Generated research records are immutable; editable templates are separate."""
    path = Path(path)
    if text:
        data = value.encode("utf-8")
    elif path.suffix == ".jsonl":
        data = b"".join(canonical(row) + b"\n" for row in value)
    else:
        data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    if path.exists():
        if path.read_bytes() != data:
            raise PilotError(f"Refusing to overwrite research record: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def git_json(repo, commit, path, manifest):
    raw = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=repo)
    manifest[path] = sha(raw)
    return [json.loads(x) for x in raw.splitlines() if x.strip()] if path.endswith(".jsonl") else json.loads(raw)


def page_key(page):
    return f"{page['doc_id']}:p{page['pdf_page_number']:04d}"


def native_units(source):
    """Real block/cell addresses only. No synthesized page-wide offsets."""
    result = {}
    for page in [source["target"], *source["context_pages"]]:
        for block in page.get("text_blocks", []):
            result[block["block_id"]] = block["text"]
        for table in page.get("tables", []):
            for row in table.get("rows", []):
                for cell in row.get("cells", []):
                    result[cell["cell_id"]] = cell.get("text", "")
    return result


def source_packet(source):
    target = source["target"]
    lines = [f"# {page_key(target)} 源文标注页", "", "只标目标页；前页仅供理解条件和适用范围。", "",
             f"文档：{target.get('title', '')}", f"来源：{target.get('source_url', '')}",
             f"物理页：{target['pdf_page_number']}", ""]
    for page in [*source["context_pages"], target]:
        role = "目标页" if page is target else "上下文页（不新增本页参考关系）"
        lines += [f"## {role} {page_key(page)}", "", "### 原始页面文本", "", page.get("page_text", ""), "",
                  "### 原生正文块及表格单元地址", ""]
        for block in page.get("text_blocks", []):
            lines += [f"#### {block['block_id']}", "", block["text"], ""]
        for table in page.get("tables", []):
            lines += [f"#### 表 {table['table_id']}", "", "列名：" + repr(table.get("column_names", [])), ""]
            for row in table.get("rows", []):
                for cell in row.get("cells", []):
                    if cell.get("text", "").strip():
                        lines += [f"- 单元 `{cell['cell_id']}`：{cell['text']}"]
            lines.append("")
    return "\n".join(lines)


def original_payload(row):
    head, tail = row.get("head") or {}, row.get("tail") or {}
    return dict(head_surface=head.get("surface"), head_type=head.get("type"),
                head_canonical_zh=head.get("canonical_zh"), relation=row.get("relation"),
                tail_surface=tail.get("surface"), tail_type=tail.get("type"),
                tail_canonical_zh=tail.get("canonical_zh"), conditions=row.get("conditions", []),
                modality=row.get("modality"), polarity=row.get("polarity"),
                raw_selection=row["raw"], source_witnesses=row.get("source_witnesses", []))


def prepare(repo, config_path, out):
    config = read(config_path)
    if not re.fullmatch(r"[0-9a-f]{40}", config["input_commit"]):
        raise PilotError("Pin an exact input commit")
    commit = config["input_commit"]
    manifest = {}
    base = config["archive_root"] + "/"
    old = base + config["source_batch"] + "/"
    new = base + config["latest_baseline_batch"] + "/"
    load = lambda path: git_json(repo, commit, path, manifest)
    sources = load(old + "sources.jsonl")
    if [s["page_key"] for s in sources] != config["page_keys"]:
        raise PilotError("Frozen page list changed")
    for source in sources:
        for page in [source["target"], *source["context_pages"]]:
            if page["doc_id"] not in BUILD:
                raise PilotError("Development/external/excluded document in pilot")
        if page_key(source["target"]) != source["page_key"]:
            raise PilotError("Wrong target page")
    registry = load(config["schema_path"])["relation_registry"]
    registry = {k: v for k, v in registry.items() if v.get("core_diagnostic_relation")}
    decisions = load(old + "decisions.jsonl")
    outputs = load(new + "outputs.jsonl")
    latest = [r for r in outputs if r["arm"] == "B0" and r["page_key"] in config["page_keys"]]
    usage, original_count = [], 0
    by_request = defaultdict(list)
    for row in decisions:
        by_request[row["candidate_id"].split(":")[0]].append(row)
    for rid, rows in sorted(by_request.items()):
        completed = load(old + f"api/{rid}.completed.json")
        parsed = load(old + f"api/{rid}.parsed.json")
        if completed["finish_reason"] != "stop" or completed["http_status"] != 200:
            raise PilotError("Incomplete raw generation; cannot infer raw recall")
        ordered = sorted(rows, key=lambda r: r["index"])
        if [r["raw"] for r in ordered] != parsed["records"]:
            raise PilotError("Raw response/candidate lineage mismatch")
        original_count += len(parsed["records"])
        usage.append(dict(request_id=rid, records=len(parsed["records"]), model=completed["returned_model"],
                          usage=completed["usage"], elapsed_seconds=completed["elapsed_seconds"]))
    if original_count != config["expected_raw_candidates"] or len(latest) != original_count:
        raise PilotError("Candidate count mismatch")
    if sum(r["automatic_pass"] for r in decisions) != config["expected_original_pipeline_kept"]:
        raise PilotError("Original pipeline membership mismatch")
    if sum(r["included"] for r in latest) != config["expected_latest_baseline_kept"]:
        raise PilotError("Latest B0 membership mismatch")
    raw_ids = {r["candidate_id"] for r in decisions}
    parents = [r["parent_ids"] for r in latest]
    if any(len(p) != 1 or p[0] not in raw_ids for p in parents) or {p[0] for p in parents} != raw_ids:
        raise PilotError("Latest baseline does not preserve one-to-one original lineage")
    candidates = [dict(candidate_id="RAW-" + r["candidate_id"], parent_id=r["candidate_id"],
                       page_key=r["page_key"], stage="raw", payload=original_payload(r),
                       original_pipeline_kept=r["automatic_pass"], historical_flags=r["flags"])
                  for r in decisions]
    candidates += [dict(candidate_id="LATEST-" + r["parent_ids"][0], parent_id=r["parent_ids"][0],
                        page_key=r["page_key"], stage="latest", payload=r["payload"],
                        latest_pipeline_kept=r["included"], historical_flags=r["screen_flags"] + r["barriers"])
                   for r in latest]
    # Old AI reference and judgment files are intentionally never loaded here.
    frozen = dict(config=config, input_sha256=manifest, source_count=len(sources),
                  raw_candidates=original_count,
                  original_pipeline_kept=sum(r["automatic_pass"] for r in decisions),
                  latest_baseline_kept=sum(r["included"] for r in latest),
                  model_calls_this_run=0, historical_model_calls=len(usage), historical_usage=usage,
                  old_AI_labels_loaded=False, reference_status="pending_human_annotation")
    write(out / "private/sources.jsonl", sources)
    write(out / "private/candidates.jsonl", candidates)
    write(out / "private/relation_registry.json", registry)
    for index, source in enumerate(sources, 1):
        write(out / f"source_only/{index:02d}_{source['page_key'].replace(':', '_')}.md", source_packet(source), text=True)
    template = [dict(page_key=s["page_key"], reviewer_kind="human", reviewer_id="",
                     coverage_complete=False, zero_target_reason="", targets=[], unresolved_notes=[])
                for s in sources]
    editable = out / "annotations/page_annotations.jsonl"
    if not editable.exists():
        write(editable, template)
    frozen["prepared_payloads"] = {
        name: sha((out / name).read_bytes()) for name in
        ["private/sources.jsonl", "private/candidates.jsonl", "private/relation_registry.json"]}
    frozen["tool_sha256"] = sha(Path(__file__).read_bytes())
    write(out / "preparation_manifest.json", frozen)
    write(out / "STATUS.md", "# 第一轮受控验证\n\n已固定10个既有开发目标页及上下文。\n"
          "原始响应162条、原编译器保留107条、最近完整规则链B0保留116条，均已核对逐条血缘。\n"
          "这些是候选和程序计数，不是正确关系数。\n\n"
          "**待人工参考：正式候选召回、角色错误比例和验证损失尚未计算。**\n"
          "旧AI参考未导入。新模型调用0，主图谱及RP2/RP3教师未改。\n\n"
          "先阅读source_only及标注规范，填写annotations/page_annotations.jsonl，再执行seal。\n", text=True)
    return frozen


def verify_preparation(out):
    manifest = read(out / "preparation_manifest.json")
    for name, expected in manifest["prepared_payloads"].items():
        if sha((out / name).read_bytes()) != expected:
            raise PilotError(f"Prepared source changed: {name}")
    if sha(Path(__file__).read_bytes()) != manifest["tool_sha256"]:
        raise PilotError("Pilot code changed after preparation; use a new version")
    return manifest


def validate_annotations(sources, rows, registry):
    source_by_key = {s["page_key"]: s for s in sources}
    if len(rows) != len(sources) or {r["page_key"] for r in rows} != set(source_by_key):
        raise PilotError("Human annotation must cover every fixed target page exactly once")
    targets = {}
    exact_relations = set()
    for row in rows:
        if row.get("reviewer_kind") != "human" or not str(row.get("reviewer_id", "")).strip():
            raise PilotError("Human reviewer declaration missing; AI drafts cannot be sealed as human references")
        if row.get("coverage_complete") is not True or row.get("unresolved_notes"):
            raise PilotError("Source annotation incomplete or unresolved")
        if not row["targets"] and not row.get("zero_target_reason", "").strip():
            raise PilotError("Zero-target page needs an explicit source-based explanation")
        units = native_units(source_by_key[row["page_key"]])
        target_prefix = row["page_key"] + ":"
        for target in row["targets"]:
            tid = target.get("reference_id")
            if not tid or tid in targets:
                raise PilotError("Duplicate or missing reference ID")
            for field in ["head", "head_type", "relation", "tail", "tail_type", "modality", "polarity", "applicability"]:
                if not isinstance(target.get(field), str) or not target[field].strip():
                    raise PilotError(f"Missing target field: {field}")
            relation = registry.get(target["relation"])
            if not relation or target["head_type"] not in relation["domain"] or target["tail_type"] not in relation["range"]:
                raise PilotError("Target is outside frozen core schema or has incompatible roles")
            if not isinstance(target.get("conditions"), list) or not target.get("evidence"):
                raise PilotError("Explicit conditions list and source anchors required")
            if any(not isinstance(x, str) or not x.strip() for x in target["conditions"]):
                raise PilotError("Conditions must be explicit nonempty text entries")
            if target["polarity"] not in {"positive", "negative"}:
                raise PilotError("Polarity must be explicit")
            exact_key = canonical([row["page_key"], *[target[k] for k in
                                  ["head", "head_type", "relation", "tail", "tail_type", "conditions", "modality", "polarity", "applicability"]]])
            if exact_key in exact_relations:
                raise PilotError("Duplicate reference relation on the same page")
            exact_relations.add(exact_key)
            has_target_anchor = False
            for anchor in target["evidence"]:
                uid = anchor["unit_id"]
                if uid not in units or not isinstance(anchor.get("quote"), str) or not anchor["quote"]:
                    raise PilotError("Unknown native unit or empty quote")
                if "start" not in anchor and "end" not in anchor:
                    if units[uid].count(anchor["quote"]) != 1:
                        raise PilotError("Quote is absent or repeated; specify exact native offsets")
                    start = units[uid].index(anchor["quote"])
                    end = start + len(anchor["quote"])
                else:
                    start, end = anchor.get("start"), anchor.get("end")
                if uid not in units or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(units[uid]):
                    raise PilotError("Invalid native source address")
                if units[uid][start:end] != anchor["quote"]:
                    raise PilotError("Reference quote cannot be read back exactly")
                has_target_anchor |= uid.startswith(target_prefix)
            if not has_target_anchor:
                raise PilotError("Context-only knowledge cannot enter target-page denominator")
            targets[tid] = dict(target, page_key=row["page_key"])
    return targets


def seal(out):
    verify_preparation(out)
    sources = read(out / "private/sources.jsonl")
    rows = read(out / "annotations/page_annotations.jsonl")
    registry = read(out / "private/relation_registry.json")
    targets = validate_annotations(sources, rows, registry)
    seal_record = dict(annotation_sha256=sha((out / "annotations/page_annotations.jsonl").read_bytes()),
                       page_count=len(rows), reference_count=len(targets), origin="human_declared",
                       limitation="Reviewer identity and exhaustiveness are human declarations, not machine-certified facts")
    write(out / "reference_seal.json", seal_record)
    candidates = read(out / "private/candidates.jsonl")
    # Candidate judgments are obtained only after source references are sealed.
    order = sorted(candidates, key=lambda c: sha(("rp1-controlled-v1/" + c["candidate_id"]).encode()))
    mapping = []
    review = []
    for c in order:
        rid = "J-" + sha(c["candidate_id"].encode())[:20]
        mapping.append(dict(review_id=rid, candidate_id=c["candidate_id"]))
        review.append(dict(review_id=rid, page_key=c["page_key"], payload=c["payload"], reviewer_kind="human",
                           reviewer_id="", verdict="pending", reference_id=None, related_reference_ids=[], reason=""))
    write(out / "private/review_mapping.jsonl", mapping)
    if not (out / "annotations/candidate_reviews.jsonl").exists():
        write(out / "annotations/candidate_reviews.jsonl", review)
    return seal_record


def validate_reviews(candidates, targets, reviews, mapping):
    by_id = {c["candidate_id"]: c for c in candidates}
    mapped = {r["review_id"]: r["candidate_id"] for r in mapping}
    if len(reviews) != len(candidates) or len({r["review_id"] for r in reviews}) != len(reviews):
        raise PilotError("Every candidate version needs exactly one human judgment")
    result = {}
    for row in reviews:
        cid = mapped.get(row["review_id"])
        if cid not in by_id or cid in result:
            raise PilotError("Unknown or repeated candidate judgment")
        c = by_id[cid]
        if row.get("page_key") != c["page_key"] or canonical(row.get("payload")) != canonical(c["payload"]):
            raise PilotError("Candidate was edited during human review")
        if row.get("reviewer_kind") != "human" or not str(row.get("reviewer_id", "")).strip() or row.get("verdict") not in VERDICTS:
            raise PilotError("Candidate review missing, nonhuman or pending")
        if not row.get("reason", "").strip():
            raise PilotError("Source-based judgment explanation required")
        linked = list(row.get("related_reference_ids", []))
        if row.get("reference_id"):
            linked.append(row["reference_id"])
        for rid in linked:
            if rid not in targets or targets[rid]["page_key"] != c["page_key"]:
                raise PilotError("Unknown or cross-page reference match")
        if row["verdict"] == "complete" and not row.get("reference_id"):
            raise PilotError("Complete atomic relation must name one human reference")
        if row["verdict"] != "complete" and row.get("reference_id"):
            raise PilotError("A defective relation cannot count as a complete match")
        if row["verdict"] in {"wrong_role", "wrong_direction", "partial_conditions", "insufficient_evidence"} and not row.get("related_reference_ids"):
            raise PilotError("Attributed defect must identify its closest reference relation")
        result[cid] = row
    if set(result) != set(by_id):
        raise PilotError("Human candidate review is not exhaustive")
    return result


def compute_metrics(candidates, targets, judgments):
    def covered(rows):
        return {judgments[c["candidate_id"]]["reference_id"] for c in rows
                if judgments[c["candidate_id"]]["verdict"] == "complete"}
    raw = [c for c in candidates if c["stage"] == "raw"]
    original = [c for c in raw if c["original_pipeline_kept"]]
    latest = [c for c in candidates if c["stage"] == "latest" and c["latest_pipeline_kept"]]
    stages = {}
    for name, rows in [("raw", raw), ("original_pipeline", original), ("latest_pipeline", latest)]:
        hits = covered(rows)
        verdicts = Counter(judgments[c["candidate_id"]]["verdict"] for c in rows)
        unresolved_pages = {c["page_key"] for c in rows if judgments[c["candidate_id"]]["verdict"] == "unresolved"}
        possible_hits = hits | {rid for rid,t in targets.items() if t["page_key"] in unresolved_pages}
        stages[name] = dict(records=len(rows), unique_targets_covered=len(hits),
                            recall=len(hits)/len(targets) if targets else None,
                            recall_upper_bound=len(possible_hits)/len(targets) if targets else None,
                            complete_record_precision=verdicts["complete"]/len(rows) if rows else None,
                            unresolved_records=verdicts["unresolved"], verdict_counts=dict(verdicts))
    raw_hits, kept_hits, latest_hits = covered(raw), covered(original), covered(latest)
    ledger = []
    for rid, target in sorted(targets.items()):
        links = [judgments[c["candidate_id"]] for c in raw if c["page_key"] == target["page_key"] and
                 (judgments[c["candidate_id"]].get("reference_id") == rid or
                  rid in judgments[c["candidate_id"]].get("related_reference_ids", []))]
        problems = {r["verdict"] for r in links}
        if rid in kept_hits:
            category = "retained"
        elif rid in raw_hits:
            category = "validation_rejection"
        elif "wrong_role" in problems or "wrong_direction" in problems:
            category = "relation_or_role_error"
        elif "partial_conditions" in problems:
            category = "incomplete_conditions_or_scope"
        elif "insufficient_evidence" in problems:
            category = "insufficient_evidence"
        elif "unresolved" in problems or any(judgments[c["candidate_id"]]["verdict"] == "unresolved"
                                             for c in raw if c["page_key"] == target["page_key"]):
            category = "unresolved_not_proven_absent"
        elif "unsupported" in problems:
            category = "unsupported_relation"
        elif "out_of_scope" in problems:
            category = "scope_mismatch"
        else:
            category = "not_generated"
        ledger.append(dict(reference_id=rid, page_key=target["page_key"], primary_loss_category=category,
                           all_related_defects=sorted(problems - {"complete"}),
                           original_raw_complete=rid in raw_hits, original_pipeline_complete=rid in kept_hits,
                           latest_pipeline_complete=rid in latest_hits))
    conditional_loss = len(raw_hits-kept_hits)/len(raw_hits) if raw_hits else None
    return dict(stages=stages, reference_denominator=len(targets),
                original_validation_conditional_recall_loss=conditional_loss,
                original_raw_to_pipeline_drop_count=len(raw_hits-kept_hits),
                latest_gain_over_raw_count=len(latest_hits-raw_hits),
                latest_loss_from_raw_count=len(raw_hits-latest_hits),
                latest_is_not_a_monotone_filter=True,
                loss_categories=dict(Counter(r["primary_loss_category"] for r in ledger)),
                unresolved_warning=any(r["primary_loss_category"].startswith("unresolved") for r in ledger)), ledger


def audit(out):
    manifest = verify_preparation(out)
    sealed = read(out / "reference_seal.json")
    if sha((out / "annotations/page_annotations.jsonl").read_bytes()) != sealed["annotation_sha256"]:
        raise PilotError("Human references changed after sealing")
    targets = validate_annotations(read(out / "private/sources.jsonl"), read(out / "annotations/page_annotations.jsonl"),
                                   read(out / "private/relation_registry.json"))
    candidates = read(out / "private/candidates.jsonl")
    judgments = validate_reviews(candidates, targets, read(out / "annotations/candidate_reviews.jsonl"),
                                 read(out / "private/review_mapping.jsonl"))
    metrics, ledger = compute_metrics(candidates, targets, judgments)
    metrics.update(status="human_reference_development_diagnostic", model_calls_this_run=0,
                   human_reference_sha256=sealed["annotation_sha256"],
                   candidate_review_sha256=sha((out / "annotations/candidate_reviews.jsonl").read_bytes()),
                   prepared_input_commit=manifest["config"]["input_commit"],
                   statistical_significance_claim_allowed=False)
    write(out / "audit/metrics.json", metrics)
    write(out / "audit/loss_ledger.jsonl", ledger)
    lines = ["# 第一轮：知识损失位置诊断", "", "固定开发集；人标来源为标注者声明，非独立外部泛化证据。", "",
             "| 阶段 | 记录数 | 完整参考覆盖 | 参考召回率 | 未决记录 |", "| --- | --- | --- | --- | --- |"]
    for stage, m in metrics["stages"].items():
        recall = "NA" if m["recall"] is None else f"{m['recall']:.2%}"
        lines.append(f"| {stage} | {m['records']} | {m['unique_targets_covered']}/{len(targets)} | {recall} | {m['unresolved_records']} |")
    lines += ["", "互斥主因：`" + json.dumps(metrics["loss_categories"], ensure_ascii=False) + "`。", "",
              "主因用于定位，所有并存缺陷保留在loss_ledger。最新B0会修改载荷，必须同时报告新增和丢失，不能视为纯过滤阶段。", "",
              "存在未决候选时，召回率为已确认覆盖下界，上界另存metrics.json；未决不作为错误或缺失的确定证据。", "",
              "尚未执行候选恢复/角色评分新对照，不能由本诊断宣布新方法有效或统计显著。"]
    write(out / "audit/REPORT.md", "\n".join(lines) + "\n", text=True)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "seal", "audit"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        result = prepare(ROOT, args.config, args.out) if args.stage == "prepare" else seal(args.out) if args.stage == "seal" else audit(args.out)
    except (PilotError, FileNotFoundError) as exc:
        parser.exit(2, f"BLOCKED: {exc}\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ["input_sha256", "historical_usage", "prepared_payloads"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
