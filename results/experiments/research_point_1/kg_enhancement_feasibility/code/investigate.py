#!/usr/bin/env python3
"""Algorithm-neutral, read-only KG diagnostics. No training or graph writes.

Counts are inventories or explicitly labelled diagnostic proxies, not accuracy.
All candidate rows retain original record/claim/page/source pointers. Inputs are
read from a pinned Git tree; only this experiment directory receives output.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict,deque
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import unicodedata

ROOT=Path(__file__).resolve().parents[5]
TASK=Path(__file__).resolve().parents[1]
REV="833c8040058055434c7f6a9595ec524c3935755f"
BUILD={f"MP{i:03d}" for i in [*range(1,8),*range(15,23)]}
AUDIT="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl"
RAW="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl"
TERM="data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/"
PREFIXES={"strict208":"data/kg/marine_pump/triples/KG_v1_validated/",
          "standard1326":TERM+"standard_graph/triples/KG_v1_validated/",
          "expanded1456":"data/kg/marine_pump/versions/expanded_v1_20261012/"}
QUALIFIED="silver_candidate" # Historical executable status, not truth quality.
CUES={"condition":r"\b(?:if|when|unless|only|before|after|provided that|in case)\b",
      "negation":r"\b(?:not|never|without|cannot|no)\b",
      "modality":r"\b(?:may|might|could|can|should|must|shall)\b",
      "alternative":r"\b(?:or|either|otherwise|alternatively)\b",
      "sequence":r"\b(?:before|after|then|first|finally|followed by)\b"}
SOURCE_CUES={"causal":r"\b(?:caus(?:e|es|ed|ing)|results? in|leads? to|due to)\b",
             "conditional_action":r"\b(?:if|when|before|after|only)\b.*\b(?:check|replace|inspect|clean|remove|operate|run|lubricate|grease)\b",
             "prohibition":r"\b(?:do not|must not|shall not|should not|cannot|never)\b",
             "alternative_action":r"\b(?:check|replace|inspect|clean|remove|repair|use)\b.*\bor\b.*\b(?:check|replace|inspect|clean|remove|repair|use)\b"}

def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):return " ".join(unicodedata.normalize("NFKC",str(s or "")).casefold().split())
def literal(s):return "".join(str(s or "").split())
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def stable(v):return sha(canon(v))[:20]
def read(path):
    p=Path(path);s=p.read_text(encoding="utf8")
    return [json.loads(x) for x in s.splitlines() if x.strip()] if p.suffix==".jsonl" else json.loads(s)
def save(path,value):
    p=Path(path)
    if not p.resolve().is_relative_to(TASK.resolve()):raise ValueError("Output escaped experiment")
    b=value.encode() if isinstance(value,str) else b"".join(canon(x)+b"\n" for x in value) if p.suffix==".jsonl" else json.dumps(value,ensure_ascii=False,indent=2).encode()+b"\n"
    if p.exists():
        if p.read_bytes()!=b:raise ValueError("Immutable output differs: "+str(p))
    else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)

class Archive:
    def __init__(self):self.hashes={};self.cache={}
    def raw(self,p):
        if p not in self.cache:
            b=subprocess.check_output(["git","show",REV+":"+p],cwd=ROOT);self.hashes[p]=sha(b);self.cache[p]=b
        return self.cache[p]
    def get(self,p):
        b=self.raw(p)
        return [json.loads(x) for x in b.splitlines() if x.strip()] if p.endswith("jsonl") else json.loads(b)

def source_key(r):return tuple(r.get(k) for k in ["doc_id","pdf_page_number","head_surface","relation","tail_surface","evidence_text"])
def concept(r,s):return (r[s+"_type"],norm(r.get(s+"_canonical_zh",r.get(s))))
def relation_key(r):return (*concept(r,"head"),r["relation"],*concept(r,"tail"))
def cid(r,layer):return r["expanded_claim_id"] if layer=="expanded1456" else r["claim_id"]
def node_id(r,s,layer):return r["expanded_"+s+"_entity_id"] if layer=="expanded1456" else r[s+"_entity_id"]
def pointer(r):
    return {k:r.get(k) for k in ["triple_id","claim_id","evidence_id","expanded_claim_id","expanded_assertion_id","doc_id","pdf_page_number","source_family_id","source_url","document_sha256","page_text_sha256","head_surface","head_type","relation","tail_surface","tail_type","head_canonical_zh","tail_canonical_zh","evidence_text","applicability_scope"]}
def flags(text,patterns=CUES):return [k for k,p in patterns.items() if re.search(p,str(text or ""),re.I|re.S)]
def units(page):
    d={b["block_id"]:b for b in page.get("text_blocks",[])}
    d.update({c["cell_id"]:c for t in page.get("tables",[]) for row in t["rows"] for c in row["cells"]})
    return d
def bbox(b):return [b.get(k) for k in ["x0","top","x1","bottom"]] if isinstance(b,dict) else b
def morphological(s):
    s=norm(s).replace("-"," ");s=" ".join(s.split())
    if re.fullmatch(r"[a-z][a-z /0-9]+",s):
        w=s.split()
        if w[-1].endswith("ies") and len(w[-1])>4:w[-1]=w[-1][:-3]+"y"
        elif w[-1].endswith("s") and not w[-1].endswith(("ss","us")):w[-1]=w[-1][:-1]
        s=" ".join(w)
    return s

class Data:
    def __init__(self):
        self.ar=Archive();self.audit=self.ar.get(AUDIT);self.raw=self.ar.get(RAW)
        self.zh=self.ar.get(TERM+"candidate_triples.zh_local_full.jsonl")
        self.schema=self.ar.get("data/kg/marine_pump/schema/provenance_schema_v3.json")
        self.pages={};self.doc_counts={};self.page_units={}
        for doc in sorted(BUILD):
            rows=self.ar.get(f"data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl");self.doc_counts[doc]=len(rows)
            for p in rows:
                if p["document_split"]!="build_train" or p["doc_id"] not in BUILD:raise ValueError("Corpus split violation")
                if sha(p["page_text"].encode())!=p["page_text_sha256"].lower():raise ValueError("Page text hash mismatch")
                k=(doc,p["pdf_page_number"]);self.pages[k]=p;self.page_units[k]=units(p)
        if len(self.pages)!=1934 or len(self.audit)!=8003 or len(self.raw)!=8007:raise ValueError("Inventory differs")
        self.graphs={label:{name:self.ar.get(p+name+".jsonl") for name in ["entities","claims","evidence_assertions","source_records"]} for label,p in PREFIXES.items()}
        for label,p in PREFIXES.items():
            if label!="expanded1456":self.graphs[label]["claim_evidence_links"]=self.ar.get(p+"claim_evidence_links.jsonl")
        self.audited_by_source=defaultdict(list)
        for r in self.audit:
            if r["doc_id"] not in BUILD or r["document_split"]!="build_train":raise ValueError("Audit split violation")
            self.audited_by_source[source_key(r)].append(r)
        self.record_sets={label:{source_key(r) for r in g["source_records"]} for label,g in self.graphs.items()}
    def seal(self,out,stage):
        save(out/(stage+"_manifest.json"),dict(input_git_commit=REV,input_sha256=self.ar.hashes,
             program_sha256=sha(Path(__file__).read_bytes()),new_model_calls=0,new_graph_edges=0,
             human_reference=False,mode="diagnostic_only_not_an_enhancement_algorithm"))

def locate_record(r,page):
    """Check address identity, not semantic entailment or engineering truth."""
    start,end=r.get("evidence_start"),r.get("evidence_end");text=r.get("evidence_text","")
    direct=isinstance(start,int) and isinstance(end,int) and 0<=start<end<=len(page["page_text"]) and page["page_text"][start:end]==text
    result=dict(evidence_level=r.get("evidence_level"),contiguous_offset_present=isinstance(start,int) and start>=0,
                contiguous_offset_exact=bool(direct),nested_unit_count=len(r.get("evidence_units") or []),
                nested_units_exact=0,nested_units_whitespace_equal=0,nested_bbox_exact=0,native_witness_count=0,native_witness_exact=0)
    native=units(page)
    for u in r.get("evidence_units") or []:
        found=native.get(u.get("cell_id"))
        if not found:continue
        if found["text"]==u["text"]:result["nested_units_exact"]+=1
        if literal(found["text"])==literal(u["text"]):result["nested_units_whitespace_equal"]+=1
        if bbox(found.get("bbox"))==bbox(u.get("bbox")):result["nested_bbox_exact"]+=1
    for w in r.get("expansion_source_witnesses") or []:
        result["native_witness_count"]+=1;uid=w.get("cell_id") or w.get("block_id");u=native.get(uid)
        a,b=w.get("start"),w.get("end")
        if u and isinstance(a,int) and isinstance(b,int) and 0<=a<b<=len(u["text"]) and u["text"][a:b]==w.get("text"):result["native_witness_exact"]+=1
    result["some_address_verified"]=bool(direct or result["nested_units_exact"] or result["native_witness_exact"])
    result["semantic_support_certified"]=False
    return result

def inventory(d,out):
    manifest=list(csv.DictReader(io.StringIO(d.ar.raw("data/source_docs/marine_pump/source_manifest.csv").decode("utf-8-sig"))))
    local_files=[]
    for m in manifest:
        if m["doc_id"] not in BUILD:continue
        p=ROOT/"data/source_docs/marine_pump/raw"/m["file_name"]
        h=sha(p.read_bytes()) if p.exists() else None
        expected=m["sha256"].lower();local_files.append(dict(doc_id=m["doc_id"],relative_path=p.relative_to(ROOT).as_posix(),exists=p.exists(),sha256=h,expected_sha256=expected,matches=h==expected))
    frames=[]
    source_pages={(r["doc_id"],r["pdf_page_number"]) for r in d.audit}
    graphpages={k:{(r["doc_id"],r["pdf_page_number"]) for r in g["source_records"]} for k,g in d.graphs.items()}
    for k,p in d.pages.items():frames.append(dict(doc_id=k[0],page=k[1],source_family_id=p["source_family_id"],title=p["title"],text_characters=len(p["page_text"].strip()),
        native_text_units=len(p.get("text_blocks",[])),native_cells=sum(len(r["cells"]) for t in p.get("tables",[]) for r in t["rows"]),
        has_audited_candidate=k in source_pages,graph_membership={label:k in ks for label,ks in graphpages.items()},page_text_sha256=p["page_text_sha256"]))
    stats=dict(build_documents=15,physical_pages=len(frames),documents=d.doc_counts,
               audited_candidate_pages=len(source_pages),page_absence_is_not_knowledge_absence=True,
               raw_cache_records=len(d.raw),audited_records=len(d.audit),decisions=dict(Counter(r["decision"] for r in d.audit)),
               layers={k:{name:len(rows) for name,rows in g.items()} for k,g in d.graphs.items()},
               graph_pages={k:len(v) for k,v in graphpages.items()},local_pdf_count=len(local_files),local_pdf_hash_matches=sum(r["matches"] for r in local_files))
    save(out/"inventory/summary.json",stats);save(out/"inventory/page_frame.jsonl",frames);save(out/"inventory/local_source_hashes.jsonl",local_files)
    d.seal(out,"inventory");print(json.dumps(stats,ensure_ascii=False,indent=2))

def integrity(d,out):
    summaries={};ledger=[];closure=[];qualifiers=[];aliasrows=[];duplicates=[];attributes=[];graphrows=[];gaprows=[];bidirectional=[]
    for label,g in d.graphs.items():
        records=g["source_records"];entities={r["entity_id"]:r for r in g["entities"]};claims={r["claim_id"]:r for r in g["claims"]}
        links=g["evidence_assertions"] if label=="expanded1456" else g["claim_evidence_links"]
        evid={r.get("assertion_id") if label=="expanded1456" else r["evidence_id"]:r for r in g["evidence_assertions"]}
        errors=[]
        for c in claims.values():
            if c["head_entity_id"] not in entities or c["tail_entity_id"] not in entities:errors.append(dict(kind="missing_claim_endpoint",claim_id=c["claim_id"]))
        for lk in links:
            if lk["claim_id"] not in claims or (lk.get("assertion_id") if label=="expanded1456" else lk["evidence_id"]) not in evid:errors.append(dict(kind="dangling_claim_evidence_link",link=lk))
        byclaim=defaultdict(list);byconcept=defaultdict(set);bysurface=defaultdict(set);bylabel=defaultdict(set)
        for r in records:
            p=d.pages[r["doc_id"],r["pdf_page_number"]];loc=locate_record(r,p)
            id_ok=all(node_id(r,s,label) in entities for s in ["head","tail"]) and cid(r,label) in claims
            meta=dict(page_hash_matches=str(r.get("page_text_sha256","")).lower()==p["page_text_sha256"].lower(),
                      document_hash_matches=str(r.get("document_sha256","")).lower()==p["document_sha256"].lower(),
                      source_url_present=bool(r.get("source_url")),scope_present=bool(r.get("applicability_scope")),id_closure=id_ok)
            rule=d.schema["relation_registry"].get(r["relation"],{})
            type_ok=r["head_type"] in rule.get("domain",[]) and r["tail_type"] in rule.get("range",[])
            ledger.append(dict(layer=label,**pointer(r),address_check=loc,provenance_check=meta,schema_type_direction_valid=type_ok,
                counts_as_semantic_truth=False))
            byclaim[cid(r,label)].append(r)
            source_cues=flags(r.get("evidence_text"));payload_cues=flags(str(r["head_surface"])+" "+str(r["tail_surface"]))
            if source_cues:qualifiers.append(dict(layer=label,**pointer(r),source_lexical_cues=source_cues,endpoint_lexical_cues=payload_cues,
                source_cues_not_in_endpoints=sorted(set(source_cues)-set(payload_cues)),
                conditions_field_present="conditions" in r,polarity_field_present="polarity" in r,modality_field_present="modality" in r,
                conditions_source_present=bool(r.get("conditions_source")),
                interpretation="Lexical/representation proxy; absence of a structured field is NOT loss of all source information"))
            for s in ["head","tail"]:
                node=node_id(r,s,label);byconcept[concept(r,s)].add(node);bysurface[(r[s+"_type"],morphological(r[s+"_surface"]))].add(node)
                bylabel[norm(r[s+"_canonical_zh"])].add((r[s+"_type"],node))
        for (typ,name),ids in byconcept.items():
            if len(ids)>1:duplicates.append(dict(layer=label,kind="exact_typed_canonical_identity_split",entity_type=typ,canonical=name,entity_ids=sorted(ids)))
        for (typ,surface),ids in bysurface.items():
            if len(ids)>1:aliasrows.append(dict(layer=label,kind="source_surface_alignment_candidate",entity_type=typ,normalized_source=surface,
                entity_ids=sorted(ids),labels=[entities[i].get("canonical_label_zh",entities[i].get("label_zh")) for i in sorted(ids)],
                auto_merge_authorized=False,context_equivalence_proven=False))
        for name,values in bylabel.items():
            if len({v[0] for v in values})>1:aliasrows.append(dict(layer=label,kind="same_label_different_types_not_automatic_duplicate",label=name,typed_entities=sorted(values),auto_merge_authorized=False))
        for claim,rs in byclaim.items():
            fams=sorted({r["source_family_id"] for r in rs});docs=sorted({r["doc_id"] for r in rs})
            closure.append(dict(layer=label,claim_id=claim,record_count=len(rs),family_count=len(fams),source_families=fams,doc_count=len(docs),doc_ids=docs,
                source_family_is_independence_proxy_not_proof=True))
            union=sorted({x for r in rs for x in r.get("fault_class_ids",[])})
            projected=sorted(claims[claim].get("fault_class_ids",[]))
            if label!="expanded1456" and set(union)-set(projected):attributes.append(dict(layer=label,claim_id=claim,union_source_fault_classes=union,
                projected_fault_classes=projected,missing_in_projection=sorted(set(union)-set(projected)),records=[pointer(r) for r in rs],
                reason="Base builder keeps first claim attributes; source records are preserved. Classification correctness not adjudicated."))
        edges={relation_key(r) for r in records};seen=set()
        for k in edges:
            htype,h,rel,ttype,t=k;rev=(ttype,t,rel,htype,h)
            if rel=="causes" and rev in edges and k!=rev and tuple(sorted((k,rev))) not in seen:
                seen.add(tuple(sorted((k,rev))));bidirectional.append(dict(layer=label,keys=[k,rev],status="insufficient_evidence",reason="Reverse causal edges may be feedback, type/context errors, or true contradiction; not adjudicated from topology"))
        adj=defaultdict(set);incoming=defaultdict(list);outgoing=defaultdict(list)
        for c in claims.values():
            h,t=c["head_entity_id"],c["tail_entity_id"];adj[h].add(t);adj[t].add(h);outgoing[h].append(c);incoming[t].append(c)
        remaining=set(entities);sizes=[]
        while remaining:
            first=next(iter(remaining));component={first};q=[first]
            while q:
                x=q.pop()
                for y in adj[x]:
                    if y not in component:component.add(y);q.append(y)
            remaining-=component;sizes.append(len(component))
        for eid,e in entities.items():
            if e["entity_type"]!="FaultMode":continue
            cause=any(c["relation"] in {"causes","increases_risk_of","evolves_to"} for c in incoming[eid])
            maintenance=any(c["relation"] in {"mitigated_by","prevented_by"} for c in outgoing[eid])
            inspection=any(c["relation"] in {"diagnosed_by","inspected_by"} for c in outgoing[eid])
            gaprows.append(dict(layer=label,entity_id=eid,label=e.get("canonical_label_zh",e.get("label_zh")),entity_type="FaultMode",
                incoming_cause=cause,outgoing_maintenance=maintenance,outgoing_inspection=inspection,
                incoming_claim_ids=[c["claim_id"] for c in incoming[eid]],outgoing_claim_ids=[c["claim_id"] for c in outgoing[eid]],
                structural_role_gap=not(cause and maintenance),true_missing_knowledge_established=False))
        graphrows.append(dict(layer=label,entities=len(entities),claims=len(claims),weak_components=len(sizes),largest_component=max(sizes,default=0),
            component_sizes=sorted(sizes,reverse=True),degree_one_entities=sum(len(adj[eid])==1 for eid in entities),
            relation_reachability_is_not_entailment=True))
        locrows=[r for r in ledger if r["layer"]==label];qs=[r for r in qualifiers if r["layer"]==label];cs=[r for r in closure if r["layer"]==label];gaps=[r for r in gaprows if r["layer"]==label]
        summaries[label]=dict(records=len(records),closure_errors=len(errors),provenance_bad_records=sum(not all(r["provenance_check"].values()) for r in locrows),
            schema_type_failures=sum(not r["schema_type_direction_valid"] for r in locrows),
            address_verified_records=sum(r["address_check"]["some_address_verified"] for r in locrows),
            E1_records=sum(r["address_check"]["evidence_level"]=="E1" for r in locrows),
            E1_exact_offsets=sum(r["address_check"]["evidence_level"]=="E1" and r["address_check"]["contiguous_offset_exact"] for r in locrows),
            source_cue_records=len(qs),source_cue_not_in_endpoints_records=sum(bool(r["source_cues_not_in_endpoints"]) for r in qs),
            structured_conditions_records=sum("conditions" in r for r in records),structured_polarity_records=sum("polarity" in r for r in records),
            structured_modality_records=sum("modality" in r for r in records),conditions_source_records=sum(bool(r.get("conditions_source")) for r in records),
            exact_typed_canonical_splits=sum(r["layer"]==label for r in duplicates),
            source_surface_alignment_candidates=sum(r["layer"]==label and r["kind"]=="source_surface_alignment_candidate" for r in aliasrows),
            same_label_type_ambiguities=sum(r["layer"]==label and r["kind"]!="source_surface_alignment_candidate" for r in aliasrows),
            multi_evidence_claims=sum(r["record_count"]>1 for r in cs),multi_family_claims=sum(r["family_count"]>1 for r in cs),
            first_record_attribute_loss_claims=sum(r["layer"]==label for r in attributes),
            fault_nodes=len(gaps),structural_role_gap_fault_nodes=sum(r["structural_role_gap"] for r in gaps))
        save(out/f"integrity/{label}_closure_errors.jsonl",errors)
    for name,rows in [("record_provenance",ledger),("qualifier_proxies",qualifiers),("claim_source_families",closure),
                      ("entity_alignment_candidates",aliasrows),("exact_identity_splits",duplicates),("claim_attribute_projection_loss",attributes),
                      ("topology",graphrows),("fault_role_gaps",gaprows),("reverse_causal_candidates",bidirectional)]:save(out/f"integrity/{name}.jsonl",rows)
    save(out/"integrity/summary.json",summaries);d.seal(out,"integrity");print(json.dumps(summaries,ensure_ascii=False,indent=2))

def publication(d,out):
    rows=[];qualified=[r for r in d.audit if r["decision"]==QUALIFIED];standard=d.record_sets["standard1326"]
    expanded_parents={r["expansion_parent_triple_id"] for r in d.graphs["expanded1456"]["source_records"] if r.get("expansion_layer")=="new_recovered"}
    zh_by_parent={z.get("terminology_governance",{}).get("previous_ids",{}).get("triple_id"):z for z in d.zh}
    zh={source_key(r):r for r in d.zh if r["decision"]==QUALIFIED};keygroups=defaultdict(list)
    for r in d.graphs["standard1326"]["source_records"]:keygroups[relation_key(r)].append(r)
    corroboration=[]
    for r in qualified:
        z=zh[source_key(r)];members={k:source_key(r) in ks for k,ks in d.record_sets.items()};blocked={}
        for side in ["head","tail"]:
            ep=z["chinese_canonicalization"][side]
            if not ep["graph_ready"]:blocked[side]=ep["reasons"]
        rows.append(dict(**pointer(r),publication=members,expanded_parent_lineage=r["triple_id"] in expanded_parents,
                         blocked_terminology_endpoints=blocked,qualified_is_not_expert_truth=True))
    for r in d.audit:
        if source_key(r) in standard:continue
        z=zh_by_parent.get(r["triple_id"],r)
        matches=[s for s in keygroups.get(relation_key(z),[]) if s["source_family_id"]!=r["source_family_id"]]
        if matches:corroboration.append(dict(candidate=pointer(r),candidate_decision=r["decision"],proposed_canonical_key=relation_key(z),
            other_family_graph_records=[pointer(s) for s in matches],support_status="insufficient_evidence",
            reason="Exact proposed canonical tuple in a different source family; source/role equivalence still requires original-text verification"))
    summary=dict(qualified_records=len(qualified),outside_strict=sum(not r["publication"]["strict208"] for r in rows),
        outside_standard=sum(not r["publication"]["standard1326"] for r in rows),
        missing_standard_endpoint_reason_signatures=dict(Counter(" + ".join(sorted({v for vs in r["blocked_terminology_endpoints"].values() for v in vs})) for r in rows if not r["publication"]["standard1326"])),
        qualified_not_in_expanded_by_exact_original_payload=sum(not r["publication"]["expanded1456"] for r in rows),
        qualified_not_in_expanded_after_parent_lineage=sum(not r["publication"]["expanded1456"] and not r["expanded_parent_lineage"] for r in rows),
        cross_family_tuple_match_candidates=len(corroboration),cross_family_tuple_matches_are_not_factual_confirmation=True,
        audit_decisions=dict(Counter(r["decision"] for r in d.audit)))
    save(out/"publication/qualified_record_membership.jsonl",rows);save(out/"publication/cross_family_candidate_matches.jsonl",corroboration)
    save(out/"publication/summary.json",summary);d.seal(out,"publication");print(json.dumps(summary,ensure_ascii=False,indent=2))

def source_scan(d,out):
    """Source-first cue inventory, not extraction of asserted new KG edges."""
    graphpages={label:{(r["doc_id"],r["pdf_page_number"]) for r in g["source_records"]} for label,g in d.graphs.items()}
    items=[];pagecounts=Counter();bydoc=defaultdict(Counter)
    for key,p in d.pages.items():
        found_on_page=set()
        # Exact native lines/cells only; no synthetic flattened-table sentence.
        for uid,u in d.page_units[key].items():
            text=u["text"];hits=flags(text,SOURCE_CUES)
            if not hits or len(text.strip())<20:continue
            found_on_page.update(hits)
            items.append(dict(candidate_id="SC-"+stable([key,uid,text]),doc_id=key[0],pdf_page_number=key[1],
                source_family_id=p["source_family_id"],source_url=p["source_url"],page_text_sha256=p["page_text_sha256"],
                native_unit_id=uid,unit_start=0,unit_end=len(text),verbatim_source=text,source_bbox=u.get("bbox"),
                lexical_issue_probes=hits,published_page_presence={label:key in ks for label,ks in graphpages.items()},
                applicability_scope=p["applicability_scope"],support_status="insufficient_evidence",
                interpretation="Source cue candidate only; a matching cue/blank graph page is not a proven omitted relation; multilingual and cross-line recall are incomplete"))
        for h in found_on_page:pagecounts[h]+=1;bydoc[key[0]][h]+=1
    # Draw source-only probes across categories/documents; do not inspect graph output to select them.
    chosen={}
    for category in SOURCE_CUES:
        for doc in sorted(BUILD):
            rows=[r for r in items if r["doc_id"]==doc and category in r["lexical_issue_probes"]]
            if rows:
                r=min(rows,key=lambda r:stable(["source-probe-20261113",category,r["candidate_id"]]));chosen[r["candidate_id"]]=r
    save(out/"source_scan/native_cue_candidates.jsonl",items);save(out/"source_scan/source_only_probe_sample.jsonl",list(chosen.values()))
    save(out/"source_scan/summary.json",dict(physical_pages=1934,native_units=sum(len(v) for v in d.page_units.values()),
        native_cue_units=len(items),page_cue_counts=dict(pagecounts),by_document={k:dict(v) for k,v in bydoc.items()},
        source_only_probe_sample=len(chosen),source_cues_not_semantic_recall=True,
        knowledge_omission_count_not_estimable_without_semantic_verification=True))
    d.seal(out,"source_scan");print(json.dumps(dict(native_cue_units=len(items),page_cue_counts=pagecounts,source_only_probe_sample=len(chosen)),ensure_ascii=False,indent=2))

def diagnostic_packets(d,out):
    # Packets from three independent diagnostic axes, preserving all original evidence.
    packs=[]
    for label,g in d.graphs.items():
        for r in g["source_records"]:
            probes=[];label_text=str(r["head_surface"])+" "+str(r["tail_surface"])
            if r["relation"]=="operates_under" and re.search(r"\b(?:do not|must not|shall not|never)\b",r["evidence_text"],re.I):probes.append("prohibition_with_positive_operating_relation")
            if any(len(str(r.get(s+"_canonical_zh","")))>60 for s in ["head","tail"]):probes.append("long_sentence_entity_proxy")
            if any(r[s+"_type"] in {"Cause","FaultMode"} and re.fullmatch(r"[\d\s,;()/.\-]+",r[s+"_surface"]) for s in ["head","tail"]):probes.append("identifier_only_diagnostic_endpoint")
            if re.search(r"\b(?:if|only|unless|before|after)\b",r["evidence_text"],re.I) and not flags(label_text):probes.append("qualifier_only_in_evidence_proxy")
            if probes:packs.append(dict(layer=label,**pointer(r),probes=probes,support_status="insufficient_evidence"))
    save(out/"packets/record_issue_candidates.jsonl",packs)
    # Keep the old 17 AI targets as prior evidence, not an exhaustive or blinded new benchmark.
    old="results/experiments/research_point_1/six_checks_final_v1_20261110/frequency/representation_targets.jsonl"
    prior=d.ar.get(old);save(out/"packets/prior_17_targets.jsonl",prior)
    source_probes=read(out/"source_scan/source_only_probe_sample.jsonl")
    for r in source_probes:
        p=d.pages[r["doc_id"],r["pdf_page_number"]]
        lines=[f"# {r['candidate_id']} {r['doc_id']} physical page {r['pdf_page_number']}",p["title"],p["applicability_scope"],
               "",f"Exact native unit: {r['native_unit_id']}",r["verbatim_source"],"","## Complete parsed page (may interleave columns)",p["page_text"]]
        save(out/f"packets/source_only/{r['candidate_id']}.md","\n".join(lines))
    summary=dict(record_issue_candidates=len(packs),nonexclusive_counts_by_layer={label:dict(Counter(p for r in packs if r["layer"]==label for p in r["probes"])) for label in d.graphs},
                 source_probe_packets=len(source_probes),prior_targets=17,all_labels_are_development_AI_or_automatic_proxies=True)
    save(out/"packets/summary.json",summary);d.seal(out,"packets");print(json.dumps(summary,ensure_ascii=False,indent=2))

def main():
    stages={"inventory":inventory,"integrity":integrity,"publication":publication,"source-scan":source_scan,"packets":diagnostic_packets}
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("stage",choices=["all",*stages]);ap.add_argument("--out",type=Path,default=TASK/"runs/20261113_v1");a=ap.parse_args()
    d=Data()
    for name in stages if a.stage=="all" else [a.stage]:
        print("[diagnostic only] "+name,flush=True);stages[name](d,a.out)

if __name__=="__main__":main()
