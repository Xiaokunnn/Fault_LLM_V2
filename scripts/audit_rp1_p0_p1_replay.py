#!/usr/bin/env python3
"""Same-input historical/current RP1 gate replay. No models, API or KG writes.

Replay unmodified versioned rule functions; instrument their returns only.
Semantic judgments are supplied separately by the assistant and are not truth.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
REV = "bd1e7c60972bbc5f34e408cd69f542b10a4ad566"
CODE_ROOT = ROOT / ".tmp/main-review-20261109"
if not CODE_ROOT.exists():
    CODE_ROOT = ROOT
PRIOR = ROOT / "results/experiments/research_point_1/a3_omission_audit_v1_20261110"
OUT = ROOT / "results/experiments/research_point_1/p0_p1_same_input_audit_v1_20261110"
BASE = "results/experiments/research_point_1/"
PREFIX = "research_point_1_graph_evidence.stage03_schema_validation."


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    data = Path(path).read_text(encoding="utf-8")
    return [json.loads(x) for x in data.splitlines() if x.strip()] if str(path).endswith(".jsonl") else json.loads(data)


def save(path, value):
    path = Path(path)
    data = (b"".join(canonical(x)+b"\n" for x in value) if path.suffix == ".jsonl"
            else json.dumps(value, ensure_ascii=False, indent=2).encode()+b"\n")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("Refusing to overwrite audit record: "+str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def git_bytes(path, hashes):
    data = subprocess.check_output(["git", "show", REV+":"+path], cwd=ROOT)
    hashes[path] = sha(data)
    return data


def archive(path, hashes):
    raw = git_bytes(path, hashes)
    return [json.loads(x) for x in raw.splitlines() if x.strip()] if path.endswith(".jsonl") else json.loads(raw)


def load_rules(hashes):
    """Load actual pure rule modules; bind their screen to the archived schema.

    Only top-level file-reading assignments of the screen utility are omitted.
    All function ASTs are compiled unchanged, and hash-checked against Git.
    This avoids using the older main checkout's implicit schema/default paths.
    """
    registry = archive("data/kg/marine_pump/schema/provenance_schema_v3.json", hashes)["relation_registry"]
    path = "scripts/rp1_offline_contract_v3.py"
    tree = ast.parse(git_bytes(path, hashes), filename=path)
    tree.body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    screen = types.ModuleType("p0_p1_archived_screen")
    screen.__dict__["REGISTRY"] = registry
    exec(compile(tree, path, "exec"), screen.__dict__)
    sys.path.insert(0, str(CODE_ROOT/"src"))
    modules = {name: importlib.import_module(PREFIX+name) for name in
               ["automatic_contract_v4_1", "clause_binding_v1", "layout_direction_context_v1",
                "native_local_reconstruction_v1", "relation_type_validator"]}
    return registry, screen, modules


def source_units(source):
    found = {}
    for page in [source["target"], *source.get("context_pages", [])]:
        for block in page.get("text_blocks", []):
            found[block["block_id"]] = block["text"]
        for table in page.get("tables", []):
            for row in table["rows"]:
                for cell in row["cells"]:
                    found[cell["cell_id"]] = cell["text"]
    return found


def addresses_roundtrip(witnesses, units, page):
    checks = []
    for w in witnesses:
        uid = w.get("unit_id") or w.get("block_id") or w.get("cell_id")
        text = units.get(uid) if uid else page["page_text"] if w.get("kind") == "page_span" else None
        valid = text is not None and type(w.get("start")) is int and type(w.get("end")) is int
        valid = bool(valid and 0 <= w["start"] < w["end"] <= len(text) and text[w["start"]:w["end"]] == w["text"])
        checks.append(dict(unit_id=uid, valid=valid))
    return checks


def locate_payload(a, source, screen, modules):
    page = source["target"]
    units = source_units(source)
    layout = modules["layout_direction_context_v1"]
    hits, geometry = layout.locate(page, a["evidence_text"], a["evidence_unit_ids"])
    native = [w for h in hits for w in h["witnesses"]]
    endpoints = {}
    context = modules["automatic_contract_v4_1"]
    for side in ["head", "tail"]:
        surface = a[side+"_surface"]
        in_units = [{**w, "unit_id": uid} for uid, text in units.items() for w in context.spans(text, surface)]
        paths, _ = layout.locate(page, surface)
        endpoints[side] = dict(surface=surface, page_matches=context.spans(page["page_text"], surface),
                               native_unit_matches=in_units, native_path_count=len(paths))
    return dict(contiguous_binding=screen.bind(page, a["evidence_text"]),
                declared_native_ids=a["evidence_unit_ids"],
                unknown_declared_ids=[u for u in a["evidence_unit_ids"] if u not in units],
                native_path_count=len(hits), geometry=geometry, native_witnesses=native,
                native_witness_roundtrips=addresses_roundtrip(native, units, page), endpoints=endpoints)


def snapshot(result):
    return {key: copy.deepcopy(result[key]) for key in
            ["payload", "included", "barriers", "screen_flags", "source_witnesses", "rules", "new_rules",
             "layout_binding", "clause_binding", "normalizer_actions", "batch_reason", "batch_native_proof"]
            if key in result}


def latest_trace(a, page, registry, screen, modules):
    """Record actual calls without duplicating the admission implementation."""
    native = modules["native_local_reconstruction_v1"]
    hooks = [(native, "normalize", "normalize"),
             (modules["automatic_contract_v4_1"], "transform", "context"),
             (modules["clause_binding_v1"], "refine", "clause"),
             (modules["layout_direction_context_v1"], "refine", "layout"),
             (native, "batch_repair", "batch_repair")]
    previous, trace = [], []
    for module, name, label in hooks:
        function = getattr(module, name)
        previous.append((module, name, function))
        def wrapped(*args, _fn=function, _label=label, **kwargs):
            result = _fn(*args, **kwargs)
            trace.append(dict(stage=_label, output=copy.deepcopy(result)))
            return result
        setattr(module, name, wrapped)
    try:
        result = native.legacy_rules(a, page, registry, screen.filter_flags)
    finally:
        for module, name, function in reversed(previous):
            setattr(module, name, function)
    selected, reason = native.local_select({"origin": "cached", "payload": a}, result, registry)
    if bool(selected) != bool(result["included"]):
        raise ValueError("B2 changed a fixed cached candidate; same-input premise violated")
    return result, trace, dict(included=bool(selected), reason=reason)


def adapt_menu(row, source):
    h, t = row["head"], row["tail"]
    return dict(head_surface=h["surface"], head_type=h["type"], relation=row["relation"],
                tail_surface=t["surface"], tail_type=t["type"], conditions=[c["text"] for c in row["conditions"]],
                modality=row["modality"], polarity=row["polarity"], scope="primary",
                applicability=source["target"].get("applicability_scope") or "",
                evidence_text="\n".join(w["text"] for w in row["source_witnesses"]),
                evidence_unit_ids=[w["unit_id"] for w in row["source_witnesses"] if ":t" in w["unit_id"]])


def failure_domains(result):
    flags = set(result.get("screen_flags", [])) | set(result.get("barriers", []))
    quote = {f for f in flags if "quote" in f or "binding" in f and "clause_binding" not in f}
    address = {f for f in flags if "native_unit" in f}
    types_ = {f for f in flags if "schema" in f or "type_direction" in f}
    semantic = flags - quote - address - types_
    return dict(evidence_address=sorted(address), quotation_binding=sorted(quote),
                schema_direction=sorted(types_), bounded_semantic_or_admission_rules=sorted(semantic),
                learned_relation_entailment="not_run_in_this_archived_offline_chain",
                included=bool(result["included"]))


def replay(out):
    if subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=ROOT).decode().strip() != REV:
        raise ValueError("Remote-tracking main changed; pin and inspect the new version before replay")
    if subprocess.check_output(["git", "-C", str(CODE_ROOT), "rev-parse", "HEAD"]).decode().strip() != REV:
        raise ValueError("Code checkout is not the pinned latest revision")
    hashes = {}
    prior_manifest = read(PRIOR/"input_manifest.json")
    if sha((PRIOR/"private/raw_packets.jsonl").read_bytes()) != prior_manifest["raw_packets_sha256"]:
        raise ValueError("Prior original candidates changed")
    ledger = read(PRIOR/"comparison_ledger.jsonl")
    targets = [r for r in ledger if r["category"] in {"validation_rejection", "relation_error"}]
    c_refs = [r for r in targets if r["category"] == "validation_rejection"]
    b_refs = [r for r in targets if r["category"] == "relation_error"]
    if len(c_refs) != 5 or len(b_refs) != 4:
        raise ValueError("Fixed P0/P1 case inventory changed")
    seeds = {m["candidate_id"] for r in targets for m in r["matching_candidates"]}
    keys = {r["page_key"] for r in targets}
    c_keys = {r["page_key"] for r in c_refs}
    sources = {s["page_key"]: s for s in read(PRIOR/"source_only/sources.jsonl") if s["page_key"] in keys}
    packets = {p["page_key"]: p for p in read(PRIOR/"private/raw_packets.jsonl") if p["page_key"] in keys}
    old_outputs = archive(BASE+"ai_review_v1/holdout_comparison_v1/outputs.jsonl", hashes)
    latest_outputs = archive(BASE+"native_fragment_completion_v1/development/outputs.jsonl", hashes)
    old_by_id = {(r["candidate_id"], r["arm"]): r for r in old_outputs}
    latest_by_parent = {r["parent_ids"][0]: r for r in latest_outputs
                        if r["arm"] == "B0" and len(r["parent_ids"]) == 1}
    old_freeze = archive(BASE+"ai_review_v1/holdout_comparison_v1/generation_freeze.json", hashes)
    new_freeze = archive(BASE+"native_fragment_completion_v1/development/protocol.json", hashes)
    registry, screen, modules = load_rules(hashes)
    records, confirmations = [], []
    for key in sorted(keys):
        source = sources[key]
        page = source["target"]
        pdf = ROOT/page["local_file"]
        document_hash = sha(pdf.read_bytes()) if pdf.is_file() else None
        if document_hash != page["document_sha256"].lower():
            raise ValueError("Original PDF missing or hash differs: "+key)
        confirmations.append(dict(page_key=key, pdf=str(pdf.relative_to(ROOT)), document_sha256=document_hash,
                                   source_page_sha256=page["page_text_sha256"],
                                   actual_page_text_sha256=sha(page["page_text"].encode())))
        for item in packets[key]["records"]:
            if item["section"] != "main":
                continue
            cid = item["candidate_id"]
            a = copy.deepcopy(item["payload"]) if packets[key]["batch"] == "freeform29" else adapt_menu(item["payload"], source)
            before = canonical(a)
            flags = screen.filter_flags(a, page)
            context = modules["automatic_contract_v4_1"].transform(a, page, registry, screen.filter_flags, "roles")
            old = modules["clause_binding_v1"].refine(a, page, context, screen.filter_flags, "repair")
            new, trace, b2 = latest_trace(a, page, registry, screen, modules)
            if canonical(a) != before:
                raise ValueError("Replay mutated the input")
            old_match = None
            if packets[key]["batch"] == "freeform29":
                expected = old_by_id[cid, "source_constrained_repair"]
                old_match = all(canonical(value) == canonical(expected[name]) for name, value in old.items())
                if not old_match or bool(not flags) != old_by_id[cid, "mechanical_filter"]["included"]:
                    raise ValueError("Old full-chain replay differs from frozen output: "+cid)
            expected = latest_by_parent[cid]
            for name in ["payload", "included", "barriers", "screen_flags", "normalizer_actions"]:
                if canonical(new.get(name, [])) != canonical(expected.get(name, [])):
                    raise ValueError("Latest replay differs from frozen B0: "+cid+" "+name)
            records.append(dict(candidate_id=cid, page_key=key, batch=packets[key]["batch"],
                                seed_case=cid in seeds, c_page_control=key in c_keys, input=a,
                                raw_model_record=item["payload"].get("raw") if packets[key]["batch"] == "menu10" else item["payload"],
                                original_input_sha256=sha(before), original_input_unchanged=True,
                                old_mechanical=dict(included=not flags, screen_flags=flags),
                                old_context=snapshot(context), old_full_chain=snapshot(old),
                                latest_full_chain=snapshot(new), latest_trace=trace, latest_B2_fixed_pool=b2,
                                old_failure_domains=failure_domains(old), latest_failure_domains=failure_domains(new),
                                old_saved_output_exact_match=old_match, latest_saved_output_exact_match=True,
                                raw_location=locate_payload(a, source, screen, modules) if cid in seeds else None,
                                final_location=locate_payload(new["payload"], source, screen, modules) if cid in seeds else None,
                                final_source_witness_checks=addresses_roundtrip(new.get("source_witnesses", []), source_units(source), page)))
    # Verify every actually imported implementation, normalizing checkout CRLF only.
    code = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith("research_point_1_graph_evidence") or not getattr(module, "__file__", None):
            continue
        path = Path(module.__file__).resolve()
        rel = path.relative_to(CODE_ROOT.resolve()).as_posix()
        blob = git_bytes(rel, hashes)
        if path.read_bytes().replace(b"\r\n", b"\n") != blob.replace(b"\r\n", b"\n"):
            raise ValueError("Imported code differs beyond line endings: "+rel)
        code[rel] = sha(blob)
    for freeze in [old_freeze, new_freeze]:
        for path, expected in freeze["sha256"].items():
            if path in code or path == "scripts/rp1_offline_contract_v3.py":
                if hashes[path] != expected:
                    raise ValueError("Rule source differs from archived execution freeze: "+path)
    requests = archive(BASE+"ai_review_v1/heldout_materials/requests.jsonl", hashes)
    requests += archive(BASE+"sentence_step_extraction/validation/requests.jsonl", hashes)
    b_requests = [r for r in requests if r["page_key"] in {r["page_key"] for r in b_refs}]
    catalogs = {p["page_key"]: archive(BASE+"sentence_step_extraction/validation/catalogs/"+
                                    p["records"][0]["candidate_id"].split(":")[0]+".json", hashes)
                for p in packets.values() if p["batch"] == "menu10"}
    summary = dict(code_commit=REV, c_reference_cases=len(c_refs), c_original_candidates=sum(r["category"]=="validation_rejection" for r in targets for _ in r["matching_candidates"]),
                   b_reference_cases=len(b_refs), total_pages=len(keys), total_original_candidates=len(records),
                   c_page_original_candidates=sum(r["c_page_control"] for r in records),
                   c_page_newly_accepted=[r["candidate_id"] for r in records if r["c_page_control"] and not r["old_full_chain"]["included"] and r["latest_full_chain"]["included"]],
                   all_original_candidates_unchanged=True, old_archive_exact_replays=sum(r["old_saved_output_exact_match"] is True for r in records),
                   latest_archive_exact_replays=len(records), new_model_calls=0,
                   learned_entailment_reexecuted=False, semantic_review_status="pending_separate_AI_review")
    manifest = dict(commit=REV, original_audit_files={n:sha((PRIOR/n).read_bytes()) for n in
                    ["comparison_ledger.jsonl", "private/raw_packets.jsonl", "source_only/sources.jsonl", "reference_specs.json"]},
                    archive_input_sha256=hashes, imported_rule_blob_sha256=code,
                    old_version="2026-10-04 context+clause repair with declared mechanical filter",
                    latest_version="2026-10-30 combined B0: normalize+context+clause+layout+batch, fetched main unchanged",
                    screen_adapter="Unchanged function ASTs compiled with archived REGISTRY; top-level path/file-reading assignments skipped only",
                    unchanged_fixed_candidate_B2=True, new_model_calls=0, graph_writes=0,
                    inference_limits="Deterministic gates are not general semantic entailment or final graph admission; judgments are separate AI source reviews.")
    save(out/"input_manifest.json", manifest)
    save(out/"source_identity_checks.json", confirmations)
    save(out/"fixed_cases.json", targets)
    save(out/"replays.jsonl", records)
    save(out/"B_original_requests.jsonl", b_requests)
    save(out/"B_menu_catalogs.json", catalogs)
    save(out/"replay_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def analyze(out):
    """Validate case coverage and aggregate separate, nonblind AI judgments."""
    records = read(out/"replays.jsonl")
    by_id = {r["candidate_id"]: r for r in records}
    cases = read(out/"fixed_cases.json")
    specs = read(out/"semantic_review_specs.json")
    manifest = read(out/"input_manifest.json")
    for name, expected in manifest["original_audit_files"].items():
        if sha((PRIOR/name).read_bytes()) != expected:
            raise ValueError("Previous audit changed: "+name)
    c_refs = {r["reference_id"]: r for r in cases if r["category"] == "validation_rejection"}
    b_refs = {r["reference_id"]: r for r in cases if r["category"] == "relation_error"}
    new_ids = {r["candidate_id"] for r in records if r["c_page_control"] and
               not r["old_full_chain"]["included"] and r["latest_full_chain"]["included"]}
    if set(specs["C_cases"]) != set(c_refs) or set(specs["B_cases"]) != set(b_refs):
        raise ValueError("All fixed C and B cases need an independent judgment")
    if set(specs["new_acceptance_reviews"]) != new_ids:
        raise ValueError("Review ALL same-page new admissions, not just favorable examples")
    for item in specs["new_acceptance_reviews"].values():
        if item["grade"] not in {"S", "N", "U"} or not item.get("reason"):
            raise ValueError("Every semantic review needs an explicit grade and source-based reason")
    c_results = []
    for rid, case in c_refs.items():
        review = specs["C_cases"][rid]
        group = [by_id[m["candidate_id"]] for m in case["matching_candidates"]]
        c_results.append(dict(reference_id=rid, original_review_category=case["category"], **review,
                             candidate_ids=[r["candidate_id"] for r in group],
                             old_mechanical_decisions=[r["old_mechanical"]["included"] for r in group],
                             old_complete_chain_decisions=[r["old_full_chain"]["included"] for r in group],
                             latest_complete_chain_decisions=[r["latest_full_chain"]["included"] for r in group],
                             raw_locations=[r["raw_location"] for r in group],
                             stage_failures=[r["latest_failure_domains"] for r in group]))
    # Independently replay the original menu compiler: ID->surface/type is copied,
    # not flipped later and falsely attributed to the model.
    hashes = {}
    registry, screen, modules = load_rules(hashes)
    step = importlib.import_module("research_point_1_graph_evidence.stage02_triple_extraction.step_fragment_extraction")
    step_path = "src/research_point_1_graph_evidence/stage02_triple_extraction/step_fragment_extraction.py"
    step_blob = git_bytes(step_path, hashes)
    if Path(step.__file__).read_bytes().replace(b"\r\n", b"\n") != step_blob:
        raise ValueError("Menu compiler code differs from the pinned version")
    catalogs = read(out/"B_menu_catalogs.json")
    requests = {r["page_key"]: r for r in read(out/"B_original_requests.jsonl")}
    raw_pages, compiler = {}, {}
    for key, request in requests.items():
        is_menu = key in catalogs
        path = ("sentence_step_extraction/validation/api/" if is_menu else "ai_review_v1/heldout_api_run_001/")
        raw = archive(BASE+path+request["request_id"]+".parsed.json", hashes)
        raw_pages[key] = raw
        if is_menu:
            compiler[key] = step.compile_local_records(raw, catalogs[key], registry)
    b_results = []
    for rid, case in b_refs.items():
        cid = case["matching_candidates"][0]["candidate_id"]
        record = by_id[cid]
        key = record["page_key"]
        ordinal = int(cid.rsplit(":", 1)[1])-1
        parsed = raw_pages[key]["records" if key in catalogs else "assertions"][ordinal]
        if canonical(parsed) != canonical(record["raw_model_record"]):
            raise ValueError("Error was introduced after parsed generation, not in the model record")
        binding = None
        if key in catalogs:
            compiled = compiler[key][ordinal]
            unit = catalogs[key]["units"][parsed["unit"]]
            binding = {side:dict(selected_id=parsed[side+"_id"],
                                source_text=unit["choices"][parsed[side+"_id"]]["text"],
                                selected_kind=unit["choices"][parsed[side+"_id"]]["kind"],
                                compiler_type_unchanged=compiled[side]["type"] == parsed[side+"_type"],
                                compiler_surface_unchanged=compiled[side]["surface"] == record["input"][side+"_surface"])
                       for side in ["head", "tail"]}
            if compiled["relation"] != parsed["relation"] or not all(
                    e["compiler_type_unchanged"] and e["compiler_surface_unchanged"] for e in binding.values()):
                raise ValueError("Menu compiler changed the original directed relation")
        prompt = request["payload"]["messages"][0]["content"]
        pos = prompt.index('{"contains"')
        prompt_registry, _ = json.JSONDecoder().raw_decode(prompt[pos:])
        rel = parsed["relation"]
        supplied_rule = prompt_registry[rel]
        a = record["input"]
        supplied_type_valid = a["head_type"] in supplied_rule["domain"] and a["tail_type"] in supplied_rule["range"]
        b_results.append(dict(reference_id=rid, candidate_id=cid, **specs["B_cases"][rid],
                             earliest_observed_error_stage="archived_parsed_model_generation",
                             raw_record_matches_original_parsed_response=True,
                             schema_in_original_request=supplied_rule,
                             raw_satisfies_supplied_domain_range=supplied_type_valid,
                             menu_compiler_binding=binding,
                             latest_normalizer_actions=record["latest_full_chain"]["normalizer_actions"],
                             latest_gate_included=record["latest_full_chain"]["included"],
                             latest_failure_domains=record["latest_failure_domains"]))
    audit_rows = [dict(candidate_id=cid, page_key=by_id[cid]["page_key"], **review,
                       old_included=False, latest_included=True,
                       old_payload=by_id[cid]["old_full_chain"]["payload"],
                       latest_payload=by_id[cid]["latest_full_chain"]["payload"])
                  for cid, review in specs["new_acceptance_reviews"].items()]
    latest = modules["native_local_reconstruction_v1"]
    witness_checks = [c for r in records for c in r["final_source_witness_checks"]]
    grades = Counter(r["grade"] for r in audit_rows)
    summary = dict(P0=dict(original_C_targets=5, original_candidate_records=8,
                          original_structured_grade_counts=dict(Counter(r["raw_structured_grade"] for r in c_results)),
                          current_outcomes=dict(Counter(r["latest_outcome"] for r in c_results)),
                          latest_candidate_accepts=sum(by_id[cid]["latest_full_chain"]["included"]
                                                      for case in c_refs.values() for cid in [m["candidate_id"] for m in case["matching_candidates"]]),
                          same_page_controls=57, newly_accepted_count=len(audit_rows),
                          newly_accepted_AI_grades=dict(grades), false_release_ids=[r["candidate_id"] for r in audit_rows if r["grade"] == "N"],
                          unknown_release_ids=[r["candidate_id"] for r in audit_rows if r["grade"] == "U"]),
                   P1=dict(B_targets=4, errors_already_in_parsed_model_output=4,
                           original_prompts_with_raw_schema_violations=sum(not r["raw_satisfies_supplied_domain_range"] for r in b_results),
                           type_direction_reoriented=sum(bool(r["latest_normalizer_actions"]) for r in b_results),
                           latest_gate_admitted=sum(r["latest_gate_included"] for r in b_results),
                           model_internal_semantic_understanding_tested=False,
                           simpler_existing_normalizer_resolves_pressure_example=True,
                           generic_method_stability_or_novel_algorithm_gain_tested=False),
                   checked_source_witnesses=len(witness_checks), all_witness_offsets_valid=all(c["valid"] for c in witness_checks),
                   human_or_domain_expert_labels=False, AI_review_nonblind=True, new_model_calls=0,
                   learned_entailment_reexecuted=False, production_rules_changed=False,
                   limitations=["Same previously seen development pages; no generalization/statistical claims",
                                "Raw binary responses absent; original parsed JSON lineage and response metadata verified",
                                "Semantic grades are assistant judgments, not independent expert truth",
                                "Postprocessing replay cannot identify the model's internal reason for reversing roles",
                                "Offline gate admission is not final Chinese KG publication or a safety guarantee"])
    if not summary["all_witness_offsets_valid"]:
        raise ValueError("A reported source address cannot be read back")
    save(out/"C_case_findings.jsonl", c_results)
    save(out/"B_lineage_findings.jsonl", b_results)
    save(out/"new_acceptance_semantic_audit.jsonl", audit_rows)
    save(out/"semantic_manifest.json", dict(replay_sha256=sha((out/"replays.jsonl").read_bytes()),
         semantic_specs_sha256=sha((out/"semantic_review_specs.json").read_bytes()),
         extra_archived_input_sha256=hashes,
         criteria="Source-supported physical content, complete typed semantics, local context/alternatives, and gate status are separate axes",
         model_internal_reason_not_inferred=True))
    save(out/"findings_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def loss_controls(out):
    """Supplementary check of every old-accepted/current-rejected C-page item.

    This is a transparent additional diagnostic, not a new effectiveness metric.
    Preserve the earlier replay and semantic manifests unchanged.
    """
    records = read(out/"replays.jsonl")
    lost = {r["candidate_id"]: r for r in records if r["c_page_control"] and
            r["old_full_chain"]["included"] and not r["latest_full_chain"]["included"]}
    specs = read(out/"decision_loss_review_specs.json")
    if set(specs) != set(lost):
        raise ValueError("All changed rejections need a review")
    reviews = []
    for cid, r in lost.items():
        review = specs[cid]
        if review["grade"] not in {"S", "N", "U"} or not review.get("reason"):
            raise ValueError("Missing source-based judgment")
        reviews.append(dict(candidate_id=cid, **review, old_included=True, latest_included=False,
                            latest_flags=r["latest_failure_domains"], payload=r["latest_full_chain"]["payload"]))
    checks = read(out/"source_identity_checks.json")
    if any(x["source_page_sha256"] != x["actual_page_text_sha256"] for x in checks):
        raise ValueError("Archived page identity differs from the replayed text")
    images = [dict(page_key="MP016:p0003", path=".tmp/rp1-p0-p1-audit-20261110/MP016-p0003.png",
                   observation="右栏PRESSURE段明确说超过最大运行压差会损坏叶轮，非相反因果。"),
              dict(page_key="MP006:p0006", path=".tmp/rp1-p0-p1-audit-20261110/MP006-p0006.png",
                   observation="第12条为带条件的轴自由转动复查；第13条两种处置以alternatively相连。"),
              dict(page_key="MP021:p0015", path=".tmp/rp1-a3-audit-20261110/MP021-p0015.png",
                   observation="左栏开头为suctions piping；右栏errors in piping layout or assembly属于前一安装条款的另一句，不可拼为旧候选001的完整引文。")]
    for item in images:
        path = ROOT/item["path"]
        item["sha256"] = sha(path.read_bytes())
        item["review_kind"] = "assistant_visual_AI_not_expert_review"
    save(out/"changed_rejection_controls.jsonl", reviews)
    save(out/"final_verification.json", dict(replay_sha256=sha((out/"replays.jsonl").read_bytes()),
         semantic_manifest_sha256=sha((out/"semantic_manifest.json").read_bytes()),
         supplemental_loss_review_specs_sha256=sha((out/"decision_loss_review_specs.json").read_bytes()),
         supplemental_scope="All 3 previously accepted/currently rejected C-page controls, inspected after the primary new-admission audit",
         C_page_gate_counts=dict(original_candidates=57, old_complete_chain_kept=sum(r["c_page_control"] and r["old_full_chain"]["included"] for r in records),
                                latest_complete_chain_kept=sum(r["c_page_control"] and r["latest_full_chain"]["included"] for r in records),
                                newly_accepted=18, newly_rejected=len(reviews)),
         page_text_hashes_match=True, original_PDF_hashes_match=True, visual_checks=images,
         semantic_judgments_are_not_human_truth=True, new_model_calls=0, production_rules_changed=False))
    print(json.dumps(dict(supplementary_changed_rejections=len(reviews), page_hashes_match=True,
                          PDF_visual_checks=len(images), new_model_calls=0), ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["replay", "analyze", "loss-controls"])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    {"replay": replay, "analyze": analyze, "loss-controls": loss_controls}[args.stage](args.out)
