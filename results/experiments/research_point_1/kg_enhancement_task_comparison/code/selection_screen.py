"""Executed restoration screening, not a new enhancement algorithm.

Only expanded1456 and the declared build corpus are read.  Frozen upstream
validator functions are executed in memory; no default pipeline loaders run.
Screen acceptance is NOT semantic truth or permission to modify the graph.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import types

from inputs import (ROOT, TASK, REV, load, save, norm, identifier, core_tuple,
                    record_ids, native_units, digest)

RUN_NAME = os.environ.get("RP1_SELECTION_RUN", "20261114_enhancement_v1")
if not re.fullmatch(r"[A-Za-z0-9_-]+", RUN_NAME):
    raise ValueError("RP1_SELECTION_RUN must be a single safe run name")
OUT = TASK / "runs" / RUN_NAME
OLD = TASK / "runs/20261113_v1"
CODE = "src/research_point_1_graph_evidence/stage03_schema_validation/"
MODULES = ["evidence_span_validator", "relation_type_validator",
           "relation_entailment_validator", "table_alignment_validator", "confidence_policy"]


def read(path):
    p = Path(path)
    s = p.read_text(encoding="utf8")
    return [json.loads(x) for x in s.splitlines() if x.strip()] if p.suffix == ".jsonl" else json.loads(s)


def frozen_validators():
    package = "rp1_selection_frozen"
    p = types.ModuleType(package)
    p.__path__ = []
    sys.modules[package] = p
    mods, hashes = {}, {}
    for name in MODULES:
        path = CODE + name + ".py"
        raw = subprocess.check_output(["git", "show", REV + ":" + path], cwd=ROOT)
        hashes[path] = digest(raw)
        m = types.ModuleType(package + "." + name)
        m.__package__ = package
        sys.modules[m.__name__] = m
        exec(compile(raw, path, "exec"), m.__dict__)
        mods[name] = m
    return mods, hashes


def schema_view(schema):
    s = copy.deepcopy(schema)
    s["node_types"] = list(s["node_type_registry"])
    s["relations"] = list(s["relation_registry"])
    s["relation_type_constraints"] = {k: {"head_types": v["domain"], "tail_types": v["range"]}
                                      for k, v in s["relation_registry"].items()}
    return s


def direct_table_relation(record, units):
    """Infer only the declared header roles, never arbitrary nearby cells."""
    h, t = norm(record["head_surface"]), norm(record["tail_surface"])
    heads = [x for x in units if h and h in norm(x["text"])]
    tails = [x for x in units if t and t in norm(x["text"])]
    proposals = set()
    for a in heads:
        for b in tails:
            ca = norm(str(a.get("column_name", "")) + " " + str(a.get("role", a.get("column_role", ""))))
            cb = norm(str(b.get("column_name", "")) + " " + str(b.get("role", b.get("column_role", ""))))
            if a.get("cell_id") == b.get("cell_id"):
                continue
            if re.search("cause|ursach|causa", ca) and re.search("fault|symptom|trouble", cb):
                proposals.add("causes")
            if re.search("fault|symptom|cause|trouble", ca) and re.search("remed|maintenance|correction|inspection_or_maintenance", cb):
                proposals.add("mitigated_by")
    return record["relation"] if proposals == {record["relation"]} else None


def gate(record, page, schema, mods, *, quote=None, units=None, declared_layout=False):
    tv = mods["relation_type_validator"].validate_relation_type(
        relation=record["relation"], head_type=record["head_type"], tail_type=record["tail_type"], schema=schema)
    if units:
        ev = mods["table_alignment_validator"].validate_table_alignment(
            page_text=page["page_text"], evidence_units=units,
            head_surface=record["head_surface"], tail_surface=record["tail_surface"],
            visual_layout_checked=declared_layout)
        evidence = "\n--- CELL ---\n".join(u["text"] for u in units)
        structured = direct_table_relation(record, units)
    else:
        ev = mods["evidence_span_validator"].validate_evidence_span(
            page_text=page["page_text"], evidence_text=quote if quote is not None else record.get("evidence_text", ""),
            head_surface=record["head_surface"], tail_surface=record["tail_surface"])
        evidence = ev.evidence_text
        structured = None
    ent = mods["relation_entailment_validator"].validate_relation_entailment(
        relation=record["relation"], evidence_text=evidence,
        head_surface=record["head_surface"], tail_surface=record["tail_surface"],
        evidence_level=ev.evidence_level or "", structured_relation=structured)
    decision = mods["confidence_policy"].decide_confidence(
        model_confidence=float(record.get("model_confidence") or 0), evidence_validation=ev,
        relation_type_validation=tv, relation_entailment_validation=ent,
        source_tier=record.get("source_tier", ""), inferred_edge=record.get("inferred_edge", False),
        document_split=record.get("document_split", "build_train"))
    return {"decision": decision.decision, "accepted_by_components": decision.silver_eligible,
            "confidence": decision.final_confidence, "evidence": asdict(ev), "type": asdict(tv),
            "entailment": asdict(ent), "hard_reasons": list(decision.hard_veto_reasons),
            "review_reasons": list(decision.review_reasons),
            "layout_basis": "frozen_record_declared_check_not_new_visual_review" if units and declared_layout else None}


def exact_fragment(text, query):
    parts = query.split()
    if not parts:
        return None
    m = re.search(r"\s+".join(re.escape(x) for x in parts), text, re.I)
    return (m.start(), m.end()) if m else None


def source_rebind(record, page, mods):
    """Bounded quote repair: actual source substring, never synthetic ellipses.

    Tables are not silently promoted to prose.  For prose, only a single native
    block containing both surfaces is usable automatically.  Multi-block and
    complex-list examples remain explicit hard cases for the reviewed overlay.
    """
    if record.get("evidence_mode") == "E2_table_cells" or record.get("evidence_units"):
        return None
    choices = []
    for unit in page.get("text_blocks", []):
        h = exact_fragment(unit["text"], record["head_surface"])
        t = exact_fragment(unit["text"], record["tail_surface"])
        if not h or not t:
            continue
        a, b = min(h[0], t[0]), max(h[1], t[1])
        if b - a > 650:
            continue
        # Keep a real sentence, not a fabricated bridge between endpoints.
        lo = max(unit["text"].rfind(". ", 0, a), unit["text"].rfind("\n\n", 0, a))
        lo = lo + 2 if lo >= 0 else 0
        stop = re.search(r"[.!?](?:\s|$)", unit["text"][b:])
        hi = b + stop.end() if stop else len(unit["text"])
        quote = unit["text"][lo:hi]
        proof = {"kind": "native_block_subspan", "block_id": unit["block_id"],
                 "start": lo, "end": hi, "text": quote, "bbox": unit.get("bbox")}
        # A native-only location is retained but cannot be supplied as a fake page offset.
        page_hit = mods["evidence_span_validator"].locate_surface(page["page_text"], quote)
        if page_hit:
            choices.append((len(quote), page_hit.source_text, proof))
    if not choices:
        return None
    _, quote, proof = min(choices, key=lambda x: (x[0], x[2]["block_id"]))
    return {"quote": quote, "proof": proof, "method": "single_native_block_and_real_page_quote"}


def qualifier_flags(record, page):
    text = str(record.get("evidence_text", ""))
    flags = []
    patterns = {
        "condition_or_sequence": r"\b(if|when|unless|before|after|then|first|only|except)\b|当.+时|如果|之前|之后|除非",
        "negation_or_requirement": r"\b(not|never|shall|must|is to be|are to be)\b|不得|禁止|必须",
        "alternative": r"\b(?:either|or|alternatively)\b|或者|否则",
        "model_or_parameter": r"\b(?:\d+(?:\.\d+)?\s*(?:rpm|bar|psi|Nm|°C)|model|type|standard)\b",
    }
    for kind, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            flags.append(kind)
    if record.get("evidence_units"):
        us = [u for u in record["evidence_units"] if len(re.findall(r"(?:^|\n)\s*\d+\.", u["text"])) > 1]
        if us:
            flags.append("merged_multiple_subrows")
    if record["doc_id"] == "MP003":
        flags.append("mixed_vessel_rulebook_scope_requires_review")
    return flags


def semantic_match(mapping, graph):
    """Executed unsupervised LSA contextual matching, no pretrained LLM/encoder.

    Chinese canonical labels and retained bilingual surfaces are inputs.  Exact
    relation/type constraints are applied AFTER retrieval.  Scores suggest
    duplicate candidates, not equivalence decisions or a calibrated threshold.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize
    def sentence(r):
        return " | ".join(str(r.get(k, "")) for k in ["head_canonical_zh", "head_surface", "relation",
               "tail_canonical_zh", "tail_surface", "evidence_text"])
    texts = [sentence(x) for x in graph] + [sentence(m["normalized_source"]) for m in mapping]
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=2, max_features=30000, sublinear_tf=True)
    x = vec.fit_transform(texts)
    svd = TruncatedSVD(n_components=96, random_state=20261114)
    y = normalize(svd.fit_transform(x))
    gx = normalize(x[:len(graph)]); gy = y[:len(graph)]
    bins = defaultdict(list)
    for j, r in enumerate(graph):
        bins[r["head_type"], r["relation"], r["tail_type"]].append(j)
    out = []
    for i, m in enumerate(mapping):
        if m["current_lineage_assertion_ids"]:
            continue
        r = m["normalized_source"]
        ids = bins[r["head_type"], r["relation"], r["tail_type"]]
        if not ids:
            out.append({"raw_occurrence_id": m["raw_occurrence_id"], "top_matches": []}); continue
        at = len(graph)+i
        lexical = (x[at] @ gx[ids].T).toarray().ravel()
        latent = y[at] @ gy[ids].T
        combined = 0.5 * lexical + 0.5 * latent
        best = np.argsort(-combined, kind="stable")[:3]
        out.append({"raw_occurrence_id": m["raw_occurrence_id"], "top_matches": [dict(
            assertion_id=graph[ids[k]]["expanded_assertion_id"], claim_id=graph[ids[k]]["expanded_claim_id"],
            doc_id=graph[ids[k]]["doc_id"], page=graph[ids[k]]["pdf_page_number"],
            head=graph[ids[k]]["head_canonical_zh"], relation=r["relation"], tail=graph[ids[k]]["tail_canonical_zh"],
            char_tfidf_cosine=float(lexical[k]), lsa_cosine=float(latent[k]), combined=float(combined[k])) for k in best],
            "automatic_merge": False})
    return out, {"method": "char_TFIDF_plus_unsupervised_LSA_not_pretrained_semantic_encoder",
                 "documents": len(texts), "features": int(x.shape[1]), "latent_dimensions": 96,
                 "explained_variance_ratio_sum": float(svd.explained_variance_ratio_.sum()),
                 "no_model_training_for_knowledge_enhancement": True, "relation_type_constraints": True,
                 "not_a_heldout_retrieval_evaluation": True}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = load(); mods, code_hashes = frozen_validators(); schema = schema_view(d["schema"])
    mapping = read(OLD / "mapping/raw_occurrence_mapping.jsonl")
    full = defaultdict(list)
    for r in d["normalized"]:
        for tid in record_ids(r):
            full[tid].append(r)
    allrows = []
    for m in mapping:
        raw = d["raw"][int(m["raw_occurrence_id"].split("-")[1])-1]
        options = [r for tid in m["all_linked_record_ids"] for r in full[tid]]
        exact = [r for r in options if core_tuple(r) == core_tuple(m["normalized_source"])]
        candidate = {**raw, **(exact[0] if exact else {}), **m["normalized_source"]}
        page = d["pages"][candidate["doc_id"],candidate["pdf_page_number"]]
        units = candidate.get("evidence_units") or []
        original = gate(candidate, page, schema, mods, units=units,
                        declared_layout=bool(candidate.get("evidence_validation",{}).get("valid") and units))
        repair = source_rebind(candidate,page,mods) if not original["evidence"]["valid"] else None
        repaired = gate(candidate,page,schema,mods,quote=repair["quote"]) if repair else original
        allrows.append({"raw_occurrence_id":m["raw_occurrence_id"], "raw_id":m["raw_triple_id"],
            "candidate_category":m["candidate_category"], "core_id":m["normalized_candidate_fact_id"],
            "existing_assertions":m["current_core_match_assertion_ids"],
            "source":{k:candidate.get(k) for k in ["doc_id","pdf_page_number","head_surface","head_canonical_zh","head_type","relation","tail_surface","tail_canonical_zh","tail_type","source_family_id","evidence_text"]},
            "before":original,"after_source_rebind":repaired,"source_rebind":repair,
            "qualifier_flags":qualifier_flags(candidate,page),"semantic_support_established_by_gate":False})
    save(OUT / "screen/all_candidate_gate_replays.jsonl",allrows)
    unpublished = [r for r in allrows if r["candidate_category"]!="current_graph_lineage_present"]
    groups = [(key, [r for r in unpublished if r["candidate_category"]==key]) for key in sorted({r["candidate_category"] for r in unpublished})]
    summary = {"raw_occurrences":len(allrows),"unpublished_occurrences_including_duplicate_controls":len(unpublished),
               "counts_are_component_gate_not_truth_or_restored_facts":True,
               "groups":{key:{"occurrences":len(rows),"before_gate_accepted":sum(r["before"]["accepted_by_components"] for r in rows),
                                "after_quote_rebind_gate_accepted":sum(r["after_source_rebind"]["accepted_by_components"] for r in rows),
                                "quote_repairs":sum(r["source_rebind"] is not None for r in rows)} for key,rows in groups}}
    save(OUT / "screen/summary.json",summary)
    # Extra check cohort chosen before source support review; no cherry-picking by correctness.
    pool = [r for r in unpublished if not r["existing_assertions"] and r["after_source_rebind"]["accepted_by_components"] and r["source"]["doc_id"]!="MP003"]
    chosen,used=[],set()
    for stratum, target in [("new_quote_rebind",8),("table",8),("text",8)]:
        rows=[r for r in pool if (stratum=="new_quote_rebind" and r["source_rebind"]) or
              (stratum=="table" and r["before"]["evidence"].get("evidence_level")=="E2") or
              (stratum=="text" and r["before"]["evidence"].get("evidence_level")=="E1")]
        for r in sorted(rows,key=lambda r:identifier(["selection-review-v1",stratum,r["raw_occurrence_id"]])):
            if r["core_id"] in used: continue
            chosen.append({"stratum":stratum,**r}); used.add(r["core_id"])
            if sum(x["stratum"]==stratum for x in chosen)>=target:break
    save(OUT / "screen/extra_review_cohort.jsonl",chosen)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    print("Running constrained TF-IDF/LSA matching",flush=True)
    matches,latent=semantic_match(mapping,d["graph"]["source_records"])
    save(OUT / "matching/candidate_to_base_top3.jsonl",matches)
    save(OUT / "matching/method.json",latent)
    # Every reused prior artifact is hash-pinned, but its old task recommendation is NOT a premise.
    prior=read(TASK/"completion_manifest.json")
    mismatches=[name for name,sha in prior["file_hashes_sha256"].items() if digest((TASK/name).read_bytes())!=sha]
    if mismatches:raise ValueError("Prior run modified: "+str(mismatches))
    save(OUT / "input_manifest.json",{"commit":REV,"base_graph":"expanded1456",
         "data_hashes":d["inputs"].hashes,"validator_code_hashes":code_hashes,
         "reused_prior_files_verified":len(prior["file_hashes_sha256"]),"prior_hash_mismatches":mismatches,
         "new_stage":"actual_sandbox_enhancement_and_direction_selection",
         "prior_task_recommendation_used_as_premise":False,"no_other_graphs_loaded":True,
         "new_llm_calls":0,"formal_graph_writes":0})
    print("Saved screen/matching; extra source-review cohort:",len(chosen),flush=True)


if __name__=="__main__":main()
