#!/usr/bin/env python3
"""Read-only source-first omission audit, without model calls or graph edits.

References and semantic comparisons are authored AI judgments, not machine or
human truth. Deterministic checks validate evidence addresses, raw lineage and
category accounting only. Old reference/semantic judgment files are not inputs.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REV = "bd1e7c60972bbc5f34e408cd69f542b10a4ad566"
BASE = "results/experiments/research_point_1/"
OUT = ROOT / "results/experiments/research_point_1/a3_omission_audit_v1_20261110"
BUILD = {f"MP{i:03d}" for i in [*range(1, 8), *range(15, 23)]}
CATEGORIES = {"omitted", "relation_error", "validation_rejection", "present",
              "partial_expression", "auxiliary_or_channel", "input_gap", "uncertain"}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def save(path, value):
    path = Path(path)
    if isinstance(value, str):
        data = value.encode("utf-8")
    elif path.suffix == ".jsonl":
        data = b"".join(canonical(row)+b"\n" for row in value)
    else:
        data = json.dumps(value, ensure_ascii=False, indent=2).encode()+b"\n"
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refusing to overwrite research record: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load(path):
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()] if str(path).endswith(".jsonl") else json.loads(text)


def archive(path, manifest):
    raw = subprocess.check_output(["git", "show", f"{REV}:{path}"], cwd=ROOT)
    manifest[path] = digest(raw)
    return [json.loads(x) for x in raw.splitlines() if x.strip()] if path.endswith(".jsonl") else json.loads(raw)


def norm(text):
    return re.sub(r"\s+", "", text).casefold()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def source_score(page):
    """Selection uses source text alone, not outputs, labels or omissions."""
    text = page["page_text"].casefold()
    terms = {
        "cause": r"\b(?:caus\w*|due to|result\w*|lead\w* to|damage\w*|failure\w*|risk\w*)\b",
        "phenomenon": r"\b(?:cavitat\w*|leak\w*|vibrat\w*|noise|overheat\w*|wear|corrosion|block\w*|pressure|temperature)\b",
        "action": r"\b(?:inspect\w*|check\w*|replac\w*|repair\w*|clean\w*|lubric\w*|greas\w*|maint\w*|align\w*|renew\w*)\b",
    }
    counts = {key: min(12, len(re.findall(pattern, text))) for key, pattern in terms.items()}
    score = 2*counts["cause"]+counts["phenomenon"]+counts["action"]+3*sum(v>0 for v in counts.values())
    tie = digest(("A3-source-density-20261110/"+page["doc_id"]+str(page["pdf_page_number"])).encode())
    return score, counts, tie


def prepare(out):
    hashes = {}
    p29 = archive(BASE+"ai_review_v1/heldout_sources/source_only.jsonl", hashes)
    p10 = archive(BASE+"sentence_step_extraction/validation/sources.jsonl", hashes)
    sources = {p["page_key"]: dict(page_key=p["page_key"], batch="freeform29", target=p, context_pages=[]) for p in p29}
    sources.update({s["page_key"]: dict(**s, batch="menu10") for s in p10})
    ranking = []
    for key, s in sources.items():
        if s["target"]["doc_id"] not in BUILD:
            raise ValueError("Not a build document")
        score, counts, tie = source_score(s["target"])
        ranking.append(dict(page_key=key, doc_id=s["target"]["doc_id"], batch=s["batch"], score=score, counts=counts, tie=tie))
    ranking.sort(key=lambda r:(-r["score"], r["tie"]))
    selected, doc_counts = [], Counter()
    for row in ranking:
        if doc_counts[row["doc_id"]] >= 3:
            continue
        selected.append(row)
        doc_counts[row["doc_id"]] += 1
        if len(selected) == 24:
            break
    if len(selected) != 24:
        raise ValueError("Not enough source pages under frozen cap")
    chosen = [sources[r["page_key"]] for r in selected]
    # Source list and rule fixed before any raw response content is loaded.
    save(out/"selection.json", dict(commit=REV, population_pages=len(sources), selection=selected,
         ranking=ranking, max_pages_per_document=3, source_only_selection=True,
         evaluator_has_prior_project_context=True, independent_holdout=False))
    save(out/"source_only/sources.jsonl", chosen)
    for i, s in enumerate(chosen, 1):
        p = s["target"]
        lines = [f"# S{i:02d} {s['page_key']}", "", f"批次：{s['batch']}；标题：{p['title']}",
                 f"来源：{p['source_url']}", f"适用范围：{p.get('applicability_scope')}", "", p["page_text"], ""]
        for table in p.get("tables", []):
            lines += ["\n## 原生表格 "+table["table_id"], "列名："+repr(table.get("column_names"))]
            for row in table.get("rows", []):
                cells = [c.get("text", "") for c in row.get("cells", [])]
                if any(x.strip() for x in cells):
                    lines.append(repr(cells))
        for ctx in s["context_pages"]:
            lines += [f"\n## 上下文 {ctx['doc_id']} p{ctx['pdf_page_number']}", ctx["page_text"]]
        save(out/f"source_only/S{i:02d}_{s['page_key'].replace(':','_')}.md", "\n".join(lines)+"\n")
    req29 = archive(BASE+"ai_review_v1/heldout_materials/requests.jsonl", hashes)
    req10 = archive(BASE+"sentence_step_extraction/validation/requests.jsonl", hashes)
    request_by_key = {r["page_key"]: r for r in req29+req10}
    legacy = archive(BASE+"ai_review_v1/holdout_comparison_v1/outputs.jsonl", hashes)
    native = archive(BASE+"sentence_step_extraction/validation/decisions.jsonl", hashes)
    latest = archive(BASE+"native_fragment_completion_v1/development/outputs.jsonl", hashes)
    packets = []
    for i, s in enumerate(chosen, 1):
        key = s["page_key"]
        req = request_by_key[key]
        rid = req["request_id"]
        path = ("ai_review_v1/heldout_api_run_001/" if s["batch"]=="freeform29" else "sentence_step_extraction/validation/api/")+rid
        completed = archive(BASE+path+".completed.json", hashes)
        parsed = archive(BASE+path+".parsed.json", hashes)
        if completed["finish_reason"] != "stop" or completed["http_status"] != 200:
            raise ValueError("Incomplete response; cannot prove an omission")
        if completed["payload_sha256"] != req["payload_sha256"]:
            raise ValueError("Response does not match the frozen request")
        expected_sections = ({"assertions", "auxiliary", "unresolved"} if s["batch"] == "freeform29"
                             else {"records", "missing", "scopes_zh"})
        if set(parsed) != expected_sections:
            raise ValueError("Unreviewed response section; do not silently discard it")
        records = []
        if s["batch"] == "freeform29":
            for ordinal, payload in enumerate(parsed["assertions"], 1):
                cid = f"{key}:H29:{ordinal:03d}"
                mirrors = [r for r in legacy if r["candidate_id"]==cid]
                raw = next(r for r in mirrors if r["arm"]=="raw")
                if canonical(raw["payload"]) != canonical(payload):
                    raise ValueError("Raw payload changed")
                records.append(dict(candidate_id=cid, section="main", payload=payload,
                     filters={r["arm"]: r["included"] for r in mirrors}, flags=raw["screen_flags"]))
            if completed["assertion_count"] != len(records):
                raise ValueError("Response count mismatch")
            for section in ["auxiliary", "unresolved"]:
                for ordinal, payload in enumerate(parsed[section], 1):
                    records.append(dict(candidate_id=f"{key}:{section}:{ordinal:03d}", section=section, payload=payload))
        else:
            rows = sorted([r for r in native if r["page_key"]==key], key=lambda r:r["index"])
            if [r["raw"] for r in rows] != parsed["records"] or len(rows) != completed["records"]:
                raise ValueError("Raw menu response lineage mismatch")
            for row in rows:
                records.append(dict(candidate_id=row["candidate_id"], section="main", payload=row,
                                    filters={"original_compiler": row["automatic_pass"]}, flags=row["flags"]))
            for section in ["missing", "scopes_zh"]:
                records.append(dict(candidate_id=f"{key}:{section}", section=section, payload=parsed[section]))
        # Retain the newer transformed branch for context; it is not raw output.
        latest_rows = [r for r in latest if r["page_key"]==key and r["arm"]=="B0"]
        user_input = json.loads(req["payload"]["messages"][1]["content"])
        packets.append(dict(sample_id=f"S{i:02d}", page_key=key, batch=s["batch"], records=records,
                            model_input=user_input, completed=completed, latest_B0=latest_rows,
                            raw_sections=list(parsed), parsed_sha256=digest(canonical(parsed))))
    save(out/"private/raw_packets.jsonl", packets)
    save(out/"input_manifest.json", dict(commit=REV, input_sha256=hashes,
         source_sha256=digest((out/"source_only/sources.jsonl").read_bytes()),
         raw_packets_sha256=digest((out/"private/raw_packets.jsonl").read_bytes()),
         model_calls=0, old_AI_references_loaded=False, old_AI_semantic_labels_loaded=False,
         raw_binary_responses_available_in_git=False,
         limitation="Completeness verified on archived valid parsed JSON and matching request/completion metadata; raw response hashes retained, binary files not reconstructed."))
    print(json.dumps(dict(selected=selected, batch_counts=dict(Counter(s["batch"] for s in chosen)),
                          document_count=len(doc_counts), model_calls=0), ensure_ascii=False, indent=2))


def evidence_locations(page, quote):
    """Whitespace-only matching to real native strings; not semantic support."""
    candidates = [("page_text", page["page_text"])]
    for table in page.get("tables", []):
        for row in table.get("rows", []):
            for cell in row.get("cells", []):
                candidates.append((cell["cell_id"], cell.get("text", "")))
    found = []
    for uid, text in candidates:
        normalized, positions = [], []
        for i, char in enumerate(text):
            if not char.isspace():
                folded = char.casefold()
                normalized.extend(folded)
                positions.extend([i]*len(folded))
        pattern = norm(quote)
        joined = "".join(normalized)
        start = joined.find(pattern)
        if start >= 0 and pattern:
            a, b = positions[start], positions[start+len(pattern)-1]+1
            found.append(dict(unit_id=uid, start=a, end=b, source_quote=text[a:b]))
    return found


def seal(out):
    manifest = load(out/"input_manifest.json")
    sources = load(out/"source_only/sources.jsonl")
    if digest((out/"source_only/sources.jsonl").read_bytes()) != manifest["source_sha256"]:
        raise ValueError("Source data changed")
    specs = load(out/"reference_specs.json")
    references, notes = [], []
    for i, s in enumerate(sources, 1):
        sid = f"S{i:02d}"
        spec = specs[sid]
        if spec["page_key"] != s["page_key"]:
            raise ValueError("Wrong page in reference")
        if len(spec["references"]) > 4:
            raise ValueError("Source-first reference cap exceeded")
        notes.append(dict(sample_id=sid, page_key=s["page_key"], source_review_note=spec["note"],
                          reference_count=len(spec["references"])))
        for j, ref in enumerate(spec["references"], 1):
            anchors = []
            for quote in ref["quotes"]:
                positions = evidence_locations(s["target"], quote)
                if not positions:
                    raise ValueError(f"Source anchor absent: {sid} {j}: {quote}")
                anchors.append(dict(quote=quote, native_matches=positions))
            references.append(dict(reference_id=f"{sid}R{j:02d}", sample_id=sid, page_key=s["page_key"],
                  reference_origin="assistant_source_reading_AI", **ref, anchors=anchors))
    if set(specs) != {r["sample_id"] for r in notes}:
        raise ValueError("Unexpected or missing source page")
    save(out/"references.jsonl", references)
    save(out/"source_review_notes.jsonl", notes)
    save(out/"reference_seal.json", dict(spec_sha256=digest((out/"reference_specs.json").read_bytes()),
         reference_sha256=digest((out/"references.jsonl").read_bytes()), target_count=len(references),
         exhaustive=False, per_page_reference_cap=4, human_review=False,
         selection_policy="Up to four clear diagnostic/inspection/maintenance propositions per page, before raw comparison; no indirect causal expansion."))
    # Only after source references are sealed are candidate packets made readable.
    for packet in load(out/"private/raw_packets.jsonl"):
        lines = [f"# {packet['sample_id']} {packet['page_key']} 原始输出", "",
                 "批次："+packet["batch"], "原始字段："+repr(packet["raw_sections"]), ""]
        for c in packet["records"]:
            lines += [f"## {c['candidate_id']} [{c['section']}]", json.dumps(c["payload"], ensure_ascii=False),
                      "程序去向："+repr(c.get("filters")), ""]
        save(out/f"comparison_packets/{packet['sample_id']}.md", "\n".join(lines))
    print(json.dumps(dict(references=len(references), pages=len(notes), human_review=False), ensure_ascii=False))


def summarize(out):
    sealed = load(out/"reference_seal.json")
    manifest = load(out/"input_manifest.json")
    for relative, expected in [("references.jsonl", sealed["reference_sha256"]),
                               ("source_only/sources.jsonl", manifest["source_sha256"]),
                               ("private/raw_packets.jsonl", manifest["raw_packets_sha256"])]:
        if digest((out/relative).read_bytes()) != expected:
            raise ValueError("Frozen audit input changed: "+relative)
    if digest((out/"reference_specs.json").read_bytes()) != sealed["spec_sha256"]:
        raise ValueError("Reference changed after opening candidates")
    refs = load(out/"references.jsonl")
    comparisons = load(out/"comparison_specs.json")
    packets = {p["page_key"]: p for p in load(out/"private/raw_packets.jsonl")}
    if set(comparisons) != {r["reference_id"] for r in refs}:
        raise ValueError("Every fixed reference needs one comparison")
    rows = []
    for ref in refs:
        comp = comparisons[ref["reference_id"]]
        packet = packets[ref["page_key"]]
        by_id = {c["candidate_id"]: c for c in packet["records"]}
        if comp["category"] not in CATEGORIES or comp.get("all_raw_sections_reviewed") is not True:
            raise ValueError("Incomplete raw review or unknown category")
        if not comp.get("reason"):
            raise ValueError("A semantic judgment needs a written reason")
        input_strings = list(strings(packet["model_input"]))
        visible = all(any(norm(q) in norm(t) for t in input_strings) for q in ref["quotes"])
        matches = comp["matching_candidates"]
        for match in matches:
            if match["candidate_id"] not in by_id or not match.get("reason"):
                raise ValueError("Unknown candidate or no semantic comparison reason")
        if comp["category"] == "omitted":
            if matches or not visible:
                raise ValueError("Omission cannot hide a generated relation or missing input")
            if packet["batch"] != "freeform29":
                raise ValueError("Menu constraints need separate interface analysis; not a clean LLM omission")
        if comp["category"] in {"relation_error", "validation_rejection", "present", "partial_expression", "auxiliary_or_channel"} and not matches:
            raise ValueError("Present/error/rejection categories need an actual generated item")
        if comp["category"] == "validation_rejection":
            correct = [by_id[m["candidate_id"]] for m in matches if m["judgment"]=="complete"]
            if not correct or not any(False in c.get("filters", {}).values() for c in correct):
                raise ValueError("Rejection needs a complete raw relation actually filtered out")
        match_ids = {m["candidate_id"] for m in matches}
        descendants = [dict(output_id=d["output_id"], parent_ids=d["parent_ids"],
                            included=d["included"], reason=d["reason"], screen_flags=d["screen_flags"])
                       for d in packet["latest_B0"] if match_ids.intersection(d["parent_ids"])]
        rows.append(dict(**ref, **comp, source_proposition_visible_in_request=visible,
                         latest_B0_descendants=descendants,
                         raw_packet_sha256=digest(canonical(packet)),
                         evaluated_raw_item_count=len(packet["records"]),
                         model=packet["completed"]["returned_model"],
                         evaluation_origin="single_assistant_nonblind_source_AI_audit"))
    counts = Counter(r["category"] for r in rows)
    omissions = [r for r in rows if r["category"]=="omitted"]
    per_page = [dict(sample_id=p["sample_id"], page_key=p["page_key"], batch=p["batch"],
                    categories=dict(Counter(r["category"] for r in rows if r["page_key"]==p["page_key"])),
                    original_main_candidates=sum(c["section"]=="main" for c in p["records"]))
                for p in packets.values()]
    summary = dict(pages=len(packets), documents=len({p['page_key'].split(':')[0] for p in packets.values()}),
         reference_propositions=len(rows), categories=dict(counts),
         pages_with_reference_propositions=sum(bool(p["categories"]) for p in per_page),
         batch_summaries={batch:dict(pages=sum(p["batch"]==batch for p in packets.values()),
                           references=sum(packets[r["page_key"]]["batch"]==batch for r in rows),
                           categories=dict(Counter(r["category"] for r in rows
                                           if packets[r["page_key"]]["batch"]==batch)))
                          for batch in sorted({p["batch"] for p in packets.values()})},
         original_main_candidates=sum(c["section"]=="main" for p in packets.values() for c in p["records"]),
         evaluated_raw_items=sum(len(p["records"]) for p in packets.values()),
         strict_omissions=len(omissions), strict_omission_pages=len({r["page_key"] for r in omissions}),
         strict_omission_documents=len({r["page_key"].split(":")[0] for r in omissions}),
         strict_omission_proportion_in_selected_AI_references=len(omissions)/len(rows) if rows else None,
         human_ground_truth=False, population_recall_estimated=False, statistical_significance_claim=False,
         new_model_calls=0, recovery_algorithm_implemented=False,
         limitations=["purposively selected previously seen development pages", "nonexhaustive source references",
                     "single nonblind AI semantic judgments", "parsed JSON verified; raw binary not in Git",
                     "freeform and menu extraction batches analyzed separately"])
    save(out/"comparison_ledger.jsonl", rows)
    save(out/"page_summary.jsonl", per_page)
    save(out/"summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def inspect_packets(out, sample_ids):
    """Show every raw item without repeating geometry and document metadata."""
    for packet in load(out/"private/raw_packets.jsonl"):
        if sample_ids and packet["sample_id"] not in sample_ids:
            continue
        print(f"\n# {packet['sample_id']} {packet['page_key']} [{packet['batch']}]")
        shared = {}
        def compact_text(text):
            if len(text) <= 350:
                return text
            key = "shared_"+digest(text.encode())[:10]
            shared[key] = text
            return "@"+key
        for item in packet["records"]:
            payload = item["payload"]
            if packet["batch"] == "menu10" and item["section"] == "main":
                payload = dict(raw=payload["raw"], head=compact_text(payload["head"]["surface"]),
                               tail=compact_text(payload["tail"]["surface"]),
                               conditions=[x["text"] for x in payload["conditions"]],
                               evidence=compact_text("\n".join(x["text"] for x in payload["source_witnesses"])))
            print(item["candidate_id"], item["section"], json.dumps(payload, ensure_ascii=False),
                  "filters="+repr(item.get("filters")))
        for key, value in shared.items():
            print("@"+key, json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "seal", "summarize", "inspect"])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--samples", nargs="*", default=[])
    args = ap.parse_args()
    if args.stage == "inspect":
        inspect_packets(args.out, args.samples)
    else:
        {"prepare": prepare, "seal": seal, "summarize": summarize}[args.stage](args.out)
