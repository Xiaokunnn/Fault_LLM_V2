#!/usr/bin/env python3
"""Build-only six-check diagnostic. No models, API calls or graph publication.

All original assets are read from a pinned Git commit, including Linux-only
filenames. New records are immutable. AI source judgments are separate inputs.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import copy
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import types
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
DATA_ROOT=ROOT.parents[1] if ROOT.parent.name==".tmp" else ROOT
REV="bd1e7c60972bbc5f34e408cd69f542b10a4ad566"
BASE="results/experiments/research_point_1/"
CORPUS="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl"
RAW="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl"
TERM="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/"
EXPANDED="data/kg/marine_pump/versions/expanded_v1_20261012/"
STRICT="data/kg/marine_pump/triples/KG_v1_validated/"
BENCH="data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2/"
BUILD={f"MP{i:03d}" for i in [*range(1,8),*range(15,23)]}
OUT=DATA_ROOT/(BASE+"six_checks_final_v1_20261110")


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def norm(text):return " ".join(unicodedata.normalize("NFKC",str(text)).casefold().split())
def load(path):
    s=Path(path).read_text(encoding="utf-8")
    return [json.loads(x) for x in s.splitlines() if x.strip()] if str(path).endswith(".jsonl") else json.loads(s)
def save(path,value):
    path=Path(path)
    raw=value.encode() if isinstance(value,str) else b"".join(canonical(r)+b"\n" for r in value) if path.suffix==".jsonl" else json.dumps(value,ensure_ascii=False,indent=2).encode()+b"\n"
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError("Refuse overwrite: "+str(path))
        return
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)


class Archive:
    def __init__(self,repo=DATA_ROOT):self.repo=Path(repo);self.hashes={}
    def raw(self,path):
        raw=subprocess.check_output(["git","show",REV+":"+path],cwd=self.repo)
        self.hashes[path]=sha(raw);return raw
    def get(self,path):
        raw=self.raw(path)
        return [json.loads(x) for x in raw.splitlines() if x.strip()] if path.endswith(".jsonl") else json.loads(raw)
    def seal(self,out,stage):
        code={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [Path(__file__),
              *sorted((ROOT/"src/research_point_1_graph_evidence/stage03_schema_validation").glob("*.py"))]}
        save(out/(stage+"_manifest.json"),dict(input_commit=REV,input_sha256=self.hashes,code_sha256=code,
             model_calls=0,graph_publication=False,human_truth=False))


def key(r):return tuple(r.get(k) for k in ["doc_id","pdf_page_number","relation","head_surface","tail_surface","evidence_text"])
def chinese_key(r):
    return (r["head_type"],norm(r.get("head_canonical_zh",r.get("head"))),r["relation"],
            r["tail_type"],norm(r.get("tail_canonical_zh",r.get("tail"))))
def source_key(r):return (r["head_type"],norm(r["head_surface"]),r["relation"],r["tail_type"],norm(r["tail_surface"]))


def population(ar):
    audit=ar.get(CORPUS);zh=ar.get(TERM+"candidate_triples.zh_local_full.jsonl")
    if len(audit)!=8003 or Counter(r["decision"] for r in audit)!={"silver_candidate":1698,"candidate_needs_review":881,"rejected":5424}:
        raise ValueError("Frozen audit population changed")
    by_key=defaultdict(list)
    for r in audit:
        if r["doc_id"] not in BUILD or r["document_split"]!="build_train":raise ValueError("Audit corpus split violation")
        by_key[key(r)].append(r)
    by_id={r["triple_id"]:r for r in audit}
    for r in zh:
        previous=r.get("terminology_governance",{}).get("previous_ids",{}).get("triple_id")
        if previous not in by_id or key(by_id[previous])!=key(r):raise ValueError("Original-to-terminology ID lineage differs")
        if r["decision"]=="silver_candidate" and len(by_key[key(r)])!=1:raise ValueError("Ambiguous qualified source key")
    return audit,zh,by_key


def graphs(ar):
    result={"strict208":ar.get(STRICT+"source_records.jsonl"),
            "conservative620":ar.get(TERM+"conservative_graph/triples/KG_v1_validated/source_records.jsonl"),
            "standard1326":ar.get(TERM+"standard_graph/triples/KG_v1_validated/source_records.jsonl"),
            "expanded1456":ar.get(EXPANDED+"source_records.jsonl")}
    if [len(v) for v in result.values()]!=[208,620,1326,1456]:raise ValueError("Graph inventories changed")
    return result


def summarize(rows):
    return dict(evidence_records=len(rows),distinct_source_relation_keys=len({source_key(r) for r in rows}),
         distinct_chinese_proposal_relation_keys=len({chinese_key(r) for r in rows}),
         typed_source_entities=len({(r[s+"_type"],norm(r[s+"_surface"])) for r in rows for s in ["head","tail"]}),
         typed_chinese_proposal_entities=len({(r[s+"_type"],norm(r.get(s+"_canonical_zh",r.get(s)))) for r in rows for s in ["head","tail"]}),
         source_documents=len({r["doc_id"] for r in rows}),physical_pages=len({(r["doc_id"],r["pdf_page_number"]) for r in rows}),
         relation_counts=dict(Counter(r["relation"] for r in rows)),
         head_type_counts=dict(Counter(r["head_type"] for r in rows)),tail_type_counts=dict(Counter(r["tail_type"] for r in rows)),
         document_counts=dict(Counter(r["doc_id"] for r in rows)),
         explicit_conditions_field=sum("conditions" in r for r in rows),
         explicit_polarity_field=sum("polarity" in r for r in rows),
         explicit_modality_field=sum("modality" in r for r in rows),
         expansion_context_field=sum(bool(r.get("conditions_source")) for r in rows))


def inventory(out):
    ar=Archive();audit,zh,by_key=population(ar);gs=graphs(ar)
    qualified=[r for r in audit if r["decision"]=="silver_candidate"]
    stats={"raw_candidate_pool":summarize(ar.get(RAW)),"evidence_audit_pool":summarize(audit),
           "automatically_evidence_qualified":summarize(qualified)}
    for label,rows in gs.items():stats[label]=summarize(rows)
    actual={}
    for label,prefix in [("strict208",STRICT),("conservative620",TERM+"conservative_graph/triples/KG_v1_validated/"),
                         ("standard1326",TERM+"standard_graph/triples/KG_v1_validated/"),("expanded1456",EXPANDED)]:
        actual[label]=dict(entities=len(ar.get(prefix+"entities.jsonl")),claims=len(ar.get(prefix+"claims.jsonl")),
                           assertions=len(ar.get(prefix+"evidence_assertions.jsonl")))
    save(out/"inventory/stage_counts.json",dict(stages=stats,serialized_graph_counts=actual,
         active_RP2_RP3_teacher="strict208",latest_separate_research_graph="expanded1456",
         source_key_definition="typed normalized source endpoints + relation; not complete semantic dedup",
         canonical_key_definition="typed normalized proposed Chinese endpoints + relation; raw proposals are not approved Chinese entities",
         human_verified=False,new_graph_built=False))
    memberships={label:{key(r) for r in rows} for label,rows in gs.items()}
    published_aliases=defaultdict(set)
    for r in gs["standard1326"]:
        for side in ["head","tail"]:
            published_aliases[r["doc_id"],r[side+"_type"],norm(r[side+"_surface"])].add(r[side+"_canonical_zh"])
    losses=[]
    for r in zh:
        if r["decision"]!="silver_candidate":continue
        original=by_key[key(r)][0];eligible={label:key(r) in ks for label,ks in memberships.items()}
        inherited={}
        for side in ["head","tail"]:
            aliases=published_aliases.get((r["doc_id"],r[side+"_type"],norm(r[side+"_surface"])),set())
            inherited[side]=dict(unique_existing_document_alias=next(iter(aliases)) if len(aliases)==1 else None,
                                 ambiguous_alias_count=len(aliases))
        reasons={side:r.get("chinese_canonicalization",{}).get(side,{}).get("reasons",[]) for side in ["head","tail"]}
        losses.append(dict(original_triple_id=original["triple_id"],terminology_triple_id=r["triple_id"],
                           doc_id=r["doc_id"],page=r["pdf_page_number"],relation=r["relation"],
                           head_surface=r["head_surface"],tail_surface=r["tail_surface"],
                           head_proposed_zh=r.get("head_canonical_zh"),tail_proposed_zh=r.get("tail_canonical_zh"),
                           publication_membership=eligible,endpoint_reasons=reasons,
                           local_exact_alias_preview=inherited,
                           evidence_contract_qualified_not_expert_fact=True))
    added=[r for r in gs["expanded1456"] if r.get("expansion_layer")=="new_recovered"]
    recovered_qualified={r["expansion_parent_triple_id"] for r in added if r["expansion_prior_validation"]["decision"]=="silver_candidate"}
    strict_missing=[r for r in losses if not r["publication_membership"]["strict208"]]
    standard_missing=[r for r in losses if not r["publication_membership"]["standard1326"]]
    exp_missing=[r for r in standard_missing if r["original_triple_id"] not in recovered_qualified]
    failure_counts={side:dict(Counter(v for r in standard_missing for v in r["endpoint_reasons"][side])) for side in ["head","tail"]}
    unresolved=ar.get(TERM+"terminology_unresolved.json")
    if isinstance(unresolved,dict):raise ValueError("Unexpected unresolved terminology format")
    safe_alias=[r for r in standard_missing if all(r["local_exact_alias_preview"][s]["unique_existing_document_alias"] for s in ["head","tail"])]
    loss_summary=dict(qualified=1698,strict_unpublished=len(strict_missing),standard_unpublished=len(standard_missing),
                      expanded_unpublished_from_qualified=len(exp_missing),
                      strict_missing_but_already_standard=len(strict_missing)-len(standard_missing),
                      qualified_recovered_in_separate_expansion=len(recovered_qualified),
                      expanded_additions_from_previously_not_qualified=len(added)-len(recovered_qualified),
                      standard_endpoint_block_reasons=failure_counts,
                      unresolved_term_groups=len(unresolved),unresolved_term_reasons=dict(Counter(t["decision_reason"] for t in unresolved)),
                      within_document_exact_existing_alias_previews=len(safe_alias),
                      alias_previews_are_not_authorized_publications=True,
                      safety_boundary="Evidence-qualified records remain candidate source evidence; no threshold relaxation, invented translation or clinical/engineering truth assertion")
    save(out/"inventory/publication_lineage.jsonl",losses)
    save(out/"inventory/publication_loss_summary.json",loss_summary)
    save(out/"inventory/exact_alias_previews.jsonl",safe_alias)
    ar.seal(out,"inventory")
    print(json.dumps(dict(counts={k:v["evidence_records"] for k,v in stats.items()},serialized_graphs=actual,publication_losses=loss_summary),ensure_ascii=False,indent=2))


def screen_from_archive(ar):
    path="scripts/rp1_offline_contract_v3.py";tree=ast.parse(ar.raw(path),filename=path)
    tree.body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))]
    module=types.ModuleType("six_checks_screen")
    module.REGISTRY=ar.get("data/kg/marine_pump/schema/provenance_schema_v3.json")["relation_registry"]
    exec(compile(tree,path,"exec"),module.__dict__);return module


def replay(out):
    ar=Archive();screen=screen_from_archive(ar)
    sys.path.insert(0,str(ROOT/"src"))
    native=importlib.import_module("research_point_1_graph_evidence.stage03_schema_validation.native_local_reconstruction_v1")
    sources={p["page_key"]:dict(target=p,context_pages=[]) for p in ar.get(BASE+"ai_review_v1/heldout_sources/source_only.jsonl")}
    sources.update({p["page_key"]:p for p in ar.get(BASE+"sentence_step_extraction/validation/sources.jsonl")})
    original=[dict(candidate_id=r["candidate_id"],page_key=r["page_key"],payload=r["payload"]) for r in
              ar.get(BASE+"ai_review_v1/holdout_comparison_v1/outputs.jsonl") if r["arm"]=="raw"]
    for r in ar.get(BASE+"sentence_step_extraction/validation/decisions.jsonl"):
        h,t=r["head"],r["tail"];a=dict(head_surface=h["surface"],head_type=h["type"],relation=r["relation"],
          tail_surface=t["surface"],tail_type=t["type"],conditions=[c["text"] for c in r["conditions"]],
          modality=r["modality"],polarity=r["polarity"],scope="primary",applicability=sources[r["page_key"]]["target"].get("applicability_scope") or "",
          evidence_text="\n".join(w["text"] for w in r["source_witnesses"]),evidence_unit_ids=[w["unit_id"] for w in r["source_witnesses"] if ":t" in w["unit_id"]])
        original.append(dict(candidate_id=r["candidate_id"],page_key=r["page_key"],payload=a))
    baseline={r["parent_ids"][0]:r for r in ar.get(BASE+"native_fragment_completion_v1/development/outputs.jsonl")
              if r["arm"]=="B0" and len(r["parent_ids"])==1}
    if len(original)!=484 or len(sources)!=39:raise ValueError("Fixed replay inventory changed")
    results=[];changed=[]
    for item in original:
        cid=item["candidate_id"];a=item["payload"];page=sources[item["page_key"]]["target"]
        before=sha(canonical([a,page]));fixed=native.legacy_rules(a,page,screen.REGISTRY,screen.filter_flags)
        if before!=sha(canonical([a,page])):raise ValueError("Input mutated")
        old=baseline[cid];semantic_changed=canonical(old["payload"])!=canonical(fixed["payload"])
        if semantic_changed:raise ValueError("Evidence interface patch changed a semantic payload: "+cid)
        row=dict(candidate_id=cid,page_key=item["page_key"],baseline_included=old["included"],fixed_included=bool(fixed["included"]),
                 baseline_flags=old["screen_flags"],fixed_flags=fixed["screen_flags"],
                 baseline_barriers=old["barriers"],fixed_barriers=fixed["barriers"],
                 payload=fixed["payload"],semantic_payload_unchanged=True,input_sha256=before,
                 batch_binding_contract=fixed.get("batch_binding_contract"),layout_binding=fixed.get("layout_binding"))
        results.append(row)
        if old["included"]!=bool(fixed["included"]):changed.append(row)
    positive=[r for r in changed if r["fixed_included"]]
    report=dict(original_candidates=484,pages=39,baseline_included=sum(r["baseline_included"] for r in results),
                fixed_included=sum(r["fixed_included"] for r in results),newly_accepted=[r["candidate_id"] for r in positive],
                newly_rejected=[r["candidate_id"] for r in changed if not r["fixed_included"]],
                all_semantic_payloads_unchanged=True,new_model_calls=0,new_graph_records=0,
                prior_known_semantic_bad_admissions={cid:next(r["fixed_included"] for r in results if r["candidate_id"]==cid)
                 for cid in ["MP021:p0015:H29:021","MP021:p0015:H29:023"]},
                semantic_review_of_new_acceptances="pending_separate_AI_source_review")
    save(out/"regression/replays.jsonl",results);save(out/"regression/changed_admissions.jsonl",changed)
    save(out/"regression/changed_source_pages.jsonl",[dict(page_key=k,**sources[k]) for k in sorted({r["page_key"] for r in changed})])
    save(out/"regression/summary.json",report);ar.seal(out,"regression")
    print(json.dumps(report,ensure_ascii=False,indent=2))


CUES={"condition":r"\b(?:if|when|unless|provided that|in case|only if|before|after)\b",
      "negation":r"\b(?:not|never|no|without|mustn't)\b",
      "alternative":r"\b(?:alternatively|either|otherwise)\b|\bor\b",
      "action_chain":r"\b(?:then|subsequently|first|finally)\b|\b(?:check|inspect|replace|remove|clean|install)\b.*\band\b.*\b(?:check|inspect|replace|remove|clean|install)\b"}


def frequency_prepare(out):
    ar=Archive();frames=[];counts={};samples=[];all_cues=Counter()
    for doc in sorted(BUILD):
        pages=ar.get(f"data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl")
        counts[doc]=len(pages)
        if any(p["doc_id"]!=doc or p["document_split"]!="build_train" for p in pages):raise ValueError("Split violation")
        for p in pages:
            if sha(p["page_text"].encode())!=p["page_text_sha256"]:raise ValueError("Source text identity mismatch")
            cues={k:bool(re.search(v,p["page_text"],re.I|re.S)) for k,v in CUES.items()}
            all_cues.update(k for k,v in cues.items() if v)
            frames.append(dict(doc_id=doc,page=p["pdf_page_number"],page_text_sha256=p["page_text_sha256"],
                               automatic_English_cue_hits=cues))
        selected=sorted(pages,key=lambda p:sha(f"RP1-six-checks-source-probability-20261110/{doc}/{p['pdf_page_number']}".encode()))[:2]
        for p in selected:samples.append(dict(page_key=f"{doc}:p{p['pdf_page_number']:04d}",doc_population_pages=len(pages),
                                             sample_pages_in_document=2,weight=len(pages)/2,target=p))
    if len(frames)!=1934 or len(samples)!=30:raise ValueError("Page population inventory changed")
    save(out/"frequency/population_frame.jsonl",frames);save(out/"frequency/source_sample.jsonl",samples)
    save(out/"frequency/sampling.json",dict(seed="RP1-six-checks-source-probability-20261110",population_pages=1934,
         documents=counts,sample_pages=30,allocation="2 pages per build document; source-only deterministic SHA priorities; no replacement",
         automatic_English_cue_page_counts=dict(all_cues),automatic_cues_are_not_semantic_frequency=True,
         weights="N_document/2; report unweighted sample counts and weighted descriptive page incidence separately",
         external_and_MP008_excluded=True,reference_exhaustiveness_claim=False,human_labels=False))
    for i,s in enumerate(samples,1):
        p=s["target"];lines=[f"# F{i:02d} {s['page_key']}",p['title'],p['applicability_scope'],"",p['page_text']]
        for t in p.get('tables',[]):
            lines.append("\n## Native table "+t['table_id'])
            lines.extend(repr([c['text'] for c in row['cells']]) for row in t['rows'])
        save(out/f"frequency/source_only/F{i:02d}_{s['page_key'].replace(':','_')}.md","\n".join(lines)+"\n")
    ar.seal(out,"frequency_prepare")
    print(json.dumps([dict(sample_id=f"F{i:02d}",page_key=s["page_key"],source_characters=len(s['target']['page_text'])) for i,s in enumerate(samples,1)],ensure_ascii=False))


def blocking_endpoint_reasons(record):
    """Informational dictionary overrides are not failed release conditions."""
    cc=record["chinese_canonicalization"]
    return {s:cc[s]["reasons"] for s in ["head","tail"] if not cc[s]["graph_ready"]}


def loss_detail(out):
    ar=Archive();audit,zh,by_key=population(ar);gs=graphs(ar)
    standard={key(r) for r in gs["standard1326"]}
    unresolved=ar.get(TERM+"terminology_unresolved.json");term_index=defaultdict(set)
    for t in unresolved:
        for surface in t["source_forms"]:term_index[t["entity_type"],norm(surface)].add(t["decision_reason"])
    rows=[]
    for r in zh:
        if r["decision"]!="silver_candidate" or key(r) in standard:continue
        sides=blocking_endpoint_reasons(r);groups=set();detail={}
        for s,reasons in sides.items():
            group=term_index.get((r[s+"_type"],norm(r[s+"_surface"])),set())
            groups.update(group)
            detail[s]=dict(graph_ready=False,executable_reasons=reasons,unresolved_group_reasons=sorted(group))
        if not sides:raise ValueError("Unexplained standard publication loss")
        groups=sorted(groups)
        rows.append(dict(original_triple_id=by_key[key(r)][0]["triple_id"],doc_id=r["doc_id"],page=r["pdf_page_number"],
                         blocked_sides=detail,exclusive_reason_signature=" + ".join(groups) or "unmapped_endpoint_gate",
                         groups_overlap_within_record=True,relation_schema_already_passed=True,
                         proposed_use="Keep source-linked evidence candidate outside Chinese semantic graph; no automatic release or translated-label acceptance"))
    gap=ar.get("data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/evidence_gap_repair_summary.json")
    raw=ar.get(RAW)
    report=dict(standard_missing=len(rows),mutually_exclusive_record_reason_signatures=dict(Counter(r["exclusive_reason_signature"] for r in rows)),
                blocked_endpoint_flags=dict(Counter(v for r in rows for s in r["blocked_sides"].values() for v in s["executable_reasons"])),
                pure_Schema_failure_among_this_prequalified_subset=0,
                generic_dictionary_override_is_not_a_block=True,
                raw_cache_records=len(raw),raw_cache_unique_triple_ids=len({r["triple_id"] for r in raw}),
                frozen_audit_construction=gap,
                audit_is_not_a_pure_filter_of_raw_cache=True,
                raw_minus_audit_is_not_four_proven_lost_facts=True,
                safe_use_boundary="Source evidence sidecar/quarantine only; correct translation and relation semantics need separate verification before graph admission")
    save(out/"inventory/blocked_endpoint_details.jsonl",rows);save(out/"inventory/loss_detail_summary.json",report)
    ar.seal(out,"loss_detail");print(json.dumps(report,ensure_ascii=False,indent=2))


def source_anchor(page,quote):
    # Locate whitespace-tolerant verbatim spans, retaining actual unmodified text.
    pattern=r"\s+".join(re.escape(t) for t in quote.split())
    units=[("page_text",page["page_text"])]
    units.extend((b["block_id"],b["text"]) for b in page.get("text_blocks",[]))
    units.extend((c["cell_id"],c["text"]) for t in page.get("tables",[]) for row in t["rows"] for c in row["cells"])
    for uid,text in units:
        match=re.search(pattern,text)
        if match:return dict(unit_id=uid,start=match.start(),end=match.end(),text=text[match.start():match.end()])
    sys.path.insert(0,str(ROOT/"src"))
    from research_point_1_graph_evidence.stage03_schema_validation.layout_direction_context_v1 import locate
    from research_point_1_graph_evidence.stage03_schema_validation.native_evidence_binding_v2 import exact_witness_roundtrip
    hits,geometry=locate(page,quote)
    if len(hits)==1 and all(exact_witness_roundtrip(page,w) for w in hits[0]["witnesses"]):
        return dict(kind="native_multiline_path",witnesses=hits[0]["witnesses"],geometry=geometry,
                    not_a_contiguous_page_text_offset=True)
    raise ValueError(f"Not a source-bound quote on {page['doc_id']}:{page['pdf_page_number']}: {quote}")


def source_review_prepare(out):
    config=ROOT/"configs/research/rp1_six_checks_source_review_v1.json";review=load(config)
    samples=load(out/"frequency/source_sample.jsonl");by_id={f"F{i:02d}":s for i,s in enumerate(samples,1)}
    if {r["sample_id"] for r in review["page_reviews"]}!=set(by_id):raise ValueError("Page review coverage differs")
    for r in [*review["page_reviews"],*review["representation_targets"]]:
        page=by_id[r["sample_id"]]["target"];r["page_key"]=by_id[r["sample_id"]]["page_key"]
        anchors=r["anchors"]
        if isinstance(anchors,dict):anchors=[q for v in anchors.values() for q in (v if isinstance(v,list) else [v])]
        r["source_witnesses"]=[source_anchor(page,q) for q in anchors]
    ar=Archive()
    prior_sources={r["page_key"] for r in ar.get(BASE+"ai_review_v1/heldout_sources/source_only.jsonl")}
    prior_sources.update(r["page_key"] for r in ar.get(BASE+"sentence_step_extraction/validation/sources.jsonl"))
    overlaps=[sid for sid,s in by_id.items() if s["page_key"] in prior_sources]
    # References are source judgments, not independent blinded human labels.
    save(out/"frequency/source_review_seal.json",dict(config_sha256=sha(config.read_bytes()),
         source_samples_sha256=sha((out/"frequency/source_sample.jsonl").read_bytes()),
         reviewer=review["reviewer"],human_labels=False,exhaustive_reference=False,
         overlap_with_39_page_prior_audit=overlaps,
         preexisting_exposure="Reference judgments reused from AI source-only pass; not an independent blinded benchmark. Earlier A3/P0/P1 sources have also been seen."))
    save(out/"frequency/page_reviews.jsonl",review["page_reviews"])
    save(out/"frequency/representation_targets.jsonl",review["representation_targets"])
    totals={k:sum(k in r["tags"] for r in review["page_reviews"]) for k in CUES}
    weighted={k:sum(by_id[r["sample_id"]]["weight"] for r in review["page_reviews"] if k in r["tags"])/1934 for k in CUES}
    save(out/"frequency/semantic_frequency_summary.json",dict(sample_pages=30,documents=15,nonexclusive_tag_page_counts=totals,
         any_complex_page_count=sum(bool(r["tags"]) for r in review["page_reviews"]),
         any_complex_documents=len({r["page_key"].split(":")[0] for r in review["page_reviews"] if r["tags"]}),
         weighted_descriptive_page_incidence=weighted,
         interpretation="AI-coded scoped page incidence; only two pages/document, unequal weights and multilingual uncertainty; not relation frequency, independent human recall or stable prevalence estimate",
         annotation_definition=review["label_scope"],excluded_documents=["MP008","MP009-MP014"]))
    audit,_,_=population(ar);gs=graphs(ar);raw=ar.get(RAW)
    target_keys={r["page_key"] for r in review["representation_targets"]}
    pack=[]
    for layer,records in [("raw_cached",raw),("audited",audit),("standard1326",gs["standard1326"]),("expanded1456",gs["expanded1456"])]:
        for r in records:
            pk=f"{r['doc_id']}:p{r['pdf_page_number']:04d}"
            if pk in target_keys:pack.append(dict(layer=layer,page_key=pk,record=r))
    save(out/"frequency/representation_candidates.jsonl",pack);ar.seal(out,"source_review_prepare")
    print(json.dumps(dict(page_counts=totals,any_complex_pages=sum(bool(r['tags']) for r in review['page_reviews']),
                         weighted_incidence=weighted,targets=len(review['representation_targets']),candidate_rows=len(pack)),ensure_ascii=False,indent=2))


def representation_replay(out):
    ar=Archive();screen=screen_from_archive(ar);sys.path.insert(0,str(ROOT/"src"))
    from research_point_1_graph_evidence.stage03_schema_validation.native_local_reconstruction_v1 import legacy_rules
    samples=load(out/"frequency/source_sample.jsonl");pages={s["page_key"]:s["target"] for s in samples}
    rows=[]
    for item in load(out/"frequency/representation_candidates.jsonl"):
        if item["layer"]!="raw_cached":continue
        raw=item["record"];page=pages[item["page_key"]];before=sha(canonical([raw,page]))
        adapter={**raw,"conditions":[],"modality":"unspecified","polarity":"unspecified",
                 "scope":"primary","applicability":page["applicability_scope"]}
        result=legacy_rules(adapter,page,screen.REGISTRY,screen.filter_flags)
        if before!=sha(canonical([raw,page])):raise ValueError("Replay mutated source")
        rows.append(dict(triple_id=raw["triple_id"],page_key=item["page_key"],input_sha256=before,
                         adapter="Missing legacy context fields explicit; no inferred modality/polarity truth",**result))
    save(out/"frequency/native_baseline_replays.jsonl",rows)
    ar.seal(out,"representation_replay")
    print(json.dumps(dict(raw_candidates=len(rows),included=sum(r["included"] for r in rows),
        barriers=dict(Counter(x for r in rows for x in r["barriers"])),new_model_calls=0),ensure_ascii=False,indent=2))


def loss_reuse(out):
    ar=Archive();audit,zh,by_key=population(ar);gs=graphs(ar)
    standard={key(r) for r in gs["standard1326"]};by_doc=defaultdict(set);global_alias=defaultdict(set)
    for r in gs["standard1326"]:
        for s in ["head","tail"]:
            k=(r[s+"_type"],norm(r[s+"_surface"]));alias=r[s+"_canonical_zh"]
            by_doc[(r["doc_id"],*k)].add(alias);global_alias[k].add(alias)
    rows=[]
    for r in zh:
        if r["decision"]!="silver_candidate" or key(r) in standard:continue
        sides=blocking_endpoint_reasons(r);details={}
        for s in sides:
            k=(r[s+"_type"],norm(r[s+"_surface"]));local=by_doc.get((r["doc_id"],*k),set());glob=global_alias.get(k,set())
            details[s]=dict(within_document_aliases=sorted(local),global_typed_exact_aliases=sorted(glob),
                proposed_label_already_equals_unique_global_alias=len(glob)==1 and norm(next(iter(glob)))==norm(r[s+"_canonical_zh"]))
        rows.append(dict(original_triple_id=by_key[key(r)][0]["triple_id"],doc_id=r["doc_id"],page=r["pdf_page_number"],blocked_endpoints=details,
            all_blocked_sides_have_unique_local_alias=all(len(d["within_document_aliases"])==1 for d in details.values()),
            all_blocked_sides_have_unique_global_alias=all(len(d["global_typed_exact_aliases"])==1 for d in details.values()),
            all_blocked_proposals_equal_existing_global_alias=all(d["proposed_label_already_equals_unique_global_alias"] for d in details.values()),
            release_authorized=False))
    report=dict(standard_unpublished=372,
        within_document_unique_alias_reuse_previews=sum(r["all_blocked_sides_have_unique_local_alias"] for r in rows),
        global_typed_exact_unique_alias_previews=sum(r["all_blocked_sides_have_unique_global_alias"] for r in rows),
        global_previews_with_unchanged_proposed_labels=sum(r["all_blocked_proposals_equal_existing_global_alias"] for r in rows),
        correction_to_initial_alias_test="Check blocked endpoints only, retaining endpoints already graph-ready. Initial exact_alias_previews required both endpoints to recur and is not the final reuse test.",
        unmapped_four_are_unlisted_translation_status_failures=True,
        publication_or_threshold_change=False,
        remaining_checks="An existing dictionary label is not proof of same referent or source-supported relation; check contextual identity and protected tokens before a separately versioned terminology repair.")
    save(out/"inventory/blocked_endpoint_alias_reuse.jsonl",rows);save(out/"inventory/alias_reuse_summary.json",report)
    ar.seal(out,"loss_reuse");print(json.dumps(report,ensure_ascii=False,indent=2))


def coverage(out):
    ar=Archive();audit,_,_=population(ar);gs=graphs(ar);raw=ar.get(RAW)
    ar.raw("src/research_point_3/evidence_memory.py")
    sys.path.insert(0,str(ROOT/"src"))
    from research_point_3.evidence_memory import RELATION_ROLE,_normalized_declared_role
    queries=ar.get(BENCH+"queries.jsonl");refs=ar.get(BENCH+"evidence_candidates.jsonl")
    retrieval=ar.get("results/experiments/research_point_2/graphrag_v6_equal_budget/retrieval_replay.jsonl")
    generation=ar.get("results/experiments/research_point_2/graphrag_v6_equal_budget/generation_results.jsonl")
    by_ret={(r["method"],r["query_id"]):r for r in retrieval}
    by_gen={(r["method"],r["query_id"]):r for r in generation}
    methods=sorted({r["method"] for r in generation});rows=[]
    def tagged(r,q):return q["fault_id"] in r.get("fault_class_ids",[]) and RELATION_ROLE.get(r["relation"])==q["role"]
    layers={"raw_cached":raw,"audited":audit,"evidence_qualified":[r for r in audit if r["decision"]=="silver_candidate"],**gs}
    if len(queries)!=40 or len(refs)!=208:raise ValueError("Controlled benchmark differs")
    for q in queries:
        ids=set(q["relevant_evidence_ids"]);matched={label:[r for r in records if tagged(r,q)] for label,records in layers.items()}
        available={label:len(rs) for label,rs in matched.items()}
        teacher=matched["strict208"]
        candidate_ids={r.get("evidence_id",r.get("assertion_id")) for r in teacher}
        if not ids<={r["evidence_id"] for r in refs}:raise ValueError("Reference outside frozen memory")
        tag_reference_difference=dict(tag_only=sorted(candidate_ids-ids),reference_only=sorted(ids-candidate_ids))
        if ids:kind="strict_graph_reference_available"
        elif available["standard1326"] or available["expanded1456"]:kind="strict_empty_larger_graph_has_automatic_tag_matches"
        elif available["evidence_qualified"]:kind="strict_empty_unpublished_qualified_tag_matches"
        elif available["raw_cached"] or available["audited"]:kind="only_unverified_or_rejected_tag_matches"
        else:kind="no_automatic_tag_match_not_proof_of_source_absence"
        for method in methods:
            ret=by_ret[method,q["query_id"]];gen=by_gen[method,q["query_id"]]
            selected={r["evidence_id"] for r in ret["ranked"]}
            cited={eid for p in gen["answer"]["answer_points"] for eid in p["evidence_ids"]}
            if not cited<=selected:raise ValueError("Citation outside replay selection")
            rows.append(dict(query_id=q["query_id"],fault_id=q["fault_id"],role=q["role"],method=method,
                availability=available,coverage_class=kind,automatic_reference_count=len(ids),
                strict_tag_reference_difference=tag_reference_difference,
                automatic_references_selected=len(ids&selected),automatic_references_cited=len(ids&cited),
                automatic_references_not_selected=sorted(ids-selected),selected_but_not_cited=sorted(ids&selected-cited),
                answer_status=gen["answer"]["status"],cited_evidence_ids=sorted(cited),
                source_support_or_exhaustive_coverage_confirmed=False))
    primary=[r for r in rows if r["method"]=="Ours_v6_k3_equal"]
    summary=dict(controlled_queries=40,methods=methods,query_classes=dict(Counter(r["coverage_class"] for r in primary)),
        empty_strict_reference_queries=[dict(query_id=r["query_id"],availability=r["availability"],coverage_class=r["coverage_class"]) for r in primary if r["automatic_reference_count"]==0],
        method_summaries={m:dict(answer_status_counts=dict(Counter(r["answer_status"] for r in rows if r["method"]==m)),
            reference_bearing_queries_with_no_citation=sum(r["automatic_reference_count"]>0 and r["automatic_references_cited"]==0 for r in rows if r["method"]==m),
            reference_bearing_queries_with_none_selected=sum(r["automatic_reference_count"]>0 and r["automatic_references_selected"]==0 for r in rows if r["method"]==m),
            reference_bearing_queries_with_some_unselected=sum(r["automatic_reference_count"]>r["automatic_references_selected"] for r in rows if r["method"]==m)) for m in methods},
        corpus_knowledge_recall_estimable=False,
        role_protocol="Frozen RP2 governed-relation role, not extraction-time evidence_role; upstream records unchanged",
        source_declared_role_string_differences=sum(r.get("evidence_role")!=RELATION_ROLE.get(r["relation"]) for r in gs["strict208"]),
        source_declared_role_discrepancies_after_alias_normalization=sum(_normalized_declared_role(r)!=RELATION_ROLE[r["relation"]] for r in gs["strict208"]),
        queries_with_fault_role_tag_reference_disagreement=sum(any(r["strict_tag_reference_difference"].values()) for r in primary),
        reason="Labels are derived from strict graph, not independent source-complete references. Larger graph matches use existing fault-role tags only, not new relevance verification.",
        single_role_queries_not_complete_diagnosis=True,new_retrieval_or_LLM_calls=0)
    save(out/"coverage/query_method_coverage.jsonl",rows);save(out/"coverage/summary.json",summary)
    ar.seal(out,"coverage");print(json.dumps(summary,ensure_ascii=False,indent=2))


def finalize(out):
    config=ROOT/"configs/research/rp1_six_checks_representation_judgments_v1.json";judgments=load(config)
    targets={r["target_id"]:r for r in load(out/"frequency/representation_targets.jsonl")}
    rows=load(out/"frequency/representation_candidates.jsonl")
    raw={r["record"]["triple_id"]:r for r in rows if r["layer"]=="raw_cached"}
    native={r["triple_id"]:r for r in load(out/"frequency/native_baseline_replays.jsonl")}
    if {r["target_id"] for r in judgments["judgments"]}!=set(targets):raise ValueError("Unreviewed representation target")
    for r in judgments["judgments"]:
        for cid in r["related_raw_ids"]:
            if cid not in raw or raw[cid]["page_key"]!=targets[r["target_id"]]["page_key"]:raise ValueError("Wrong candidate pointer: "+cid)
        if r["native_baseline_target_recovered"] and not any(native[cid]["included"] for cid in r["related_raw_ids"]):raise ValueError("No admitted baseline pointer")
    changed=load(out/"regression/changed_admissions.jsonl")
    if {r["candidate_id"] for r in changed}!={r["candidate_id"] for r in judgments["regression_admission_review"]}:raise ValueError("Unreviewed admission change")
    for r in changed:
        if not r["semantic_payload_unchanged"] or not r["fixed_included"]:raise ValueError("Unexpected regression delta")
        if set(r["baseline_flags"])-set(r["fixed_flags"])!={"unbound_quote"}:raise ValueError("Patch removed non-quote flags")
    coverage_rows=load(out/"coverage/query_method_coverage.jsonl")
    primary=[r for r in coverage_rows if r["method"]=="Ours_v6_k3_equal"]
    summary=dict(review_input_sha256=sha(config.read_bytes()),reviewer=judgments["reviewer"],
        representation_targets=len(targets),nonexclusive_complex_tags_not_relation_recall=True,
        raw_target_preservation=dict(Counter(r["raw_preservation"] for r in judgments["judgments"])),
        native_rule_target_complete=sum(r["native_baseline_target_recovered"] for r in judgments["judgments"]),
        targets_requiring_scope_or_schema_definition=[r["target_id"] for r in judgments["judgments"] if r.get("schema_scope")],
        new_admissions=len(changed),new_admissions_AI_source_supported=3,new_admissions_human_validated=0,
        residual_preexisting_semantic_bad_admissions=["MP021:p0015:H29:021","MP021:p0015:H29:023"],
        teacher_reference_available_but_uncited=[dict(query_id=r["query_id"],status=r["answer_status"],
            selected_reference_count=r["automatic_references_selected"],cited_ids=r["cited_evidence_ids"]) for r in primary
            if r["automatic_reference_count"] and not r["automatic_references_cited"]],
        sixth_check_result=dict(cross_document_complex_semantics_observed=True,
            existing_generic_same_budget_stable_failure_demonstrated=False,
            novel_algorithm_go=False,
            reason="One deterministic replay is not a matched-budget model baseline or cross-run stability study; source judgments are AI-only and 17 targets non-exhaustive. Keep only a narrow hypothesis for a later controlled experiment."),
        new_model_calls=0,graph_or_teacher_modified=False,external_documents_read=False,
        completed_checks=["interface_regression","graph_inventory","publication_loss","source_complexity_spot_check","40_query_coverage","research_direction_go_no_go"],
        limits=judgments["limits"])
    save(out/"frequency/representation_judgments.json",judgments)
    save(out/"completion_summary.json",summary)
    manifests={p.name:sha(p.read_bytes()) for p in sorted(out.glob("*_manifest.json"))}
    save(out/"completion_seal.json",dict(stages=manifests,summary_sha256=sha((out/"completion_summary.json").read_bytes()),
        source_judgments_sha256=sha((out/"frequency/representation_judgments.json").read_bytes()),
        implementation_sha256=sha(Path(__file__).read_bytes()),input_commit=REV))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    stages={"inventory":inventory,"replay":replay,"frequency-prepare":frequency_prepare,
            "loss-detail":loss_detail,"source-review-prepare":source_review_prepare,"coverage":coverage,
            "representation-replay":representation_replay,"loss-reuse":loss_reuse,"finalize":finalize}
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("stage",choices=["all",*sorted(stages)])
    ap.add_argument("--out",type=Path,default=OUT);args=ap.parse_args()
    if args.stage=="all":
        for stage in ["replay","inventory","loss-detail","loss-reuse","frequency-prepare","source-review-prepare","representation-replay","coverage","finalize"]:
            print("[RP1 diagnostic] "+stage,flush=True);stages[stage](args.out)
    else:stages[args.stage](args.out)
