"""Transparent source/table and topology candidate discovery, never admission."""
from collections import defaultdict, Counter
import json
import re
import sys

from inputs import load, save, norm, identifier, native_units, source_pointer
from selection_screen import OUT, OLD, read


def body(cell):
    # Remove only a literal header already present as a prefix in the native cell.
    t = cell["text"].strip()
    header = str(cell.get("column_name", "")).strip()
    if header and norm(t).startswith(norm(header)):
        t = t[len(header):].strip()
    return t


def tuples(rows):
    out = set()
    for r in rows:
        for h in [r.get("head_surface"),r.get("head_canonical_zh")]:
            for t in [r.get("tail_surface"),r.get("tail_canonical_zh")]:
                if h and t:out.add((norm(h),r["relation"],norm(t)))
    return out


def table_candidates(d):
    rawkeys=tuples(d["raw"]+d["normalized"])
    graphkeys=tuples(d["graph"]["source_records"])
    out=[];native_rows=0
    for (doc,pg),page in sorted(d["pages"].items()):
        for table in page.get("tables",[]):
            cells=[c for r in table["rows"] for c in r["cells"]]
            for row in table["rows"]:
                native_rows+=1
                groups={c.get("row_group_id") for c in row["cells"] if c.get("row_group_id")}
                causes=[c for c in row["cells"] if re.search(r"cause|ursach|causa",norm(str(c.get("column_name",""))+" "+str(c.get("column_role",""))))]
                faults=[c for c in cells if re.search(r"fault|symptom|trouble",norm(str(c.get("column_name",""))+" "+str(c.get("column_role",""))))
                        and (c.get("row_id")==row.get("row_id") or c.get("row_group_id") in groups)]
                for a in causes:
                    for b in faults:
                        h,t=body(a),body(b)
                        if not h or not t or len(h)<4 or len(t)<4:continue
                        if norm(h) in ["cause","causes","possible cause"] or norm(t) in ["trouble","fault","symptoms"]:continue
                        key=(norm(h),"causes",norm(t))
                        existing=key in graphkeys; generated=key in rawkeys
                        out.append({"id":"ET-"+identifier([doc,pg,a["cell_id"],b["cell_id"]]),
                            "doc_id":doc,"page":pg,"head_surface":h,"relation":"causes","tail_surface":t,
                            "source_cells":[a,b],"document_sha256":page["document_sha256"],"page_text_sha256":page["page_text_sha256"],
                            "source_url":page.get("source_url"),"existing_exact_source_pair":existing,
                            "raw_exact_source_pair":generated,"discovery":"native_declared_cause_and_fault_row_group",
                            "complex_multiline_or_list":bool(re.search(r"\n\s*(?:\d+\.|[a-z]\.)",h) or len(h)>220 or len(t)>180),
                            "semantic_support":"not_yet_reviewed","trusted_fact":False})
    # Same native pair can be repeated by rows containing the inherited fault cell.
    out=list({r["id"]:r for r in out}.values())
    pool=[r for r in out if not r["existing_exact_source_pair"] and not r["raw_exact_source_pair"] and
          not r["complex_multiline_or_list"] and r["doc_id"]!="MP003"]
    selected=[]
    for doc in sorted({r["doc_id"] for r in pool}):
        selected+=sorted([r for r in pool if r["doc_id"]==doc],key=lambda r:identifier(["E-source-only",r["id"]]))[:2]
    return out,selected,{"native_table_rows_scanned":native_rows,"discovered_native_pairs":len(out),
                        "exact_graph_pairs":sum(r["existing_exact_source_pair"] for r in out),
                        "exact_raw_pairs":sum(r["raw_exact_source_pair"] for r in out),
                        "not_found_exact_in_either":sum(not r["existing_exact_source_pair"] and not r["raw_exact_source_pair"] for r in out),
                        "fixed_review_items":len(selected),"not_semantic_omission_counts":True}


def topology_candidates(d):
    sources=d["graph"]["source_records"]
    adjacency=defaultdict(list); surfaces=defaultdict(set)
    for r in sources:
        for side in ["head","tail"]:
            surfaces[r["expanded_"+side+"_entity_id"]].update([r[side+"_surface"],r[side+"_canonical_zh"]])
        if r["relation"]=="causes":adjacency[r["expanded_head_entity_id"]].append(r)
    current={(r["expanded_head_entity_id"],r["relation"],r["expanded_tail_entity_id"]) for r in sources}
    candidates={}
    for h,first in adjacency.items():
        for a in first:
            for b in adjacency.get(a["expanded_tail_entity_id"], []):
                t=b["expanded_tail_entity_id"]
                if h==t or (h,"causes",t) in current:continue
                k=(h,"causes",t)
                row=candidates.setdefault(k,{"id":"EG-"+identifier(k),"head_entity_id":h,"relation":"causes","tail_entity_id":t,
                    "head":a["head_canonical_zh"],"tail":b["tail_canonical_zh"],"paths":[],
                    "epistemic_status":"topology_only_potential_not_direct_causal_fact","trusted_fact":False})
                row["paths"].append({"assertion_ids":[a["expanded_assertion_id"],b["expanded_assertion_id"]],
                                     "via":a["tail_canonical_zh"]})
    # Bounded transparent source lookup. Co-occurrence is NOT entailment.
    texts={key:norm(page["page_text"]) for key,page in d["pages"].items()}
    index={eid:{key for key,txt in texts.items() if any(norm(s) in txt for s in names if len(norm(s))>=4)}
           for eid,names in surfaces.items() if any(eid==k[0] or eid==k[2] for k in candidates)}
    for (h,_,t),r in candidates.items():
        pages=sorted(index[h]&index[t])
        r["cooccurrence_pages"]=[{"doc_id":a,"page":b} for a,b in pages]
        r["original_evidence_verdict"]="insufficient_for_direct_relation_unless_separately_checked"
    return list(candidates.values())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d=load()
    pairs,selected,summary=table_candidates(d)
    save(OUT/"discovery/native_table_pairs.jsonl",pairs)
    save(OUT/"discovery/source_only_table_review.jsonl",selected)
    topology=topology_candidates(d)
    save(OUT/"discovery/topology_only_potentials.jsonl",topology)
    summary["topology_only_distinct_pairs"]=len(topology)
    summary["topology_with_endpoint_cooccurrence"]=sum(bool(r["cooccurrence_pages"]) for r in topology)
    summary["topology_added_as_facts"]=0
    summary["source_only_review_rule"]="two per eligible non-rulebook document, stable hash, before semantic review"
    save(OUT/"discovery/summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    for r in selected:print(json.dumps({k:r[k] for k in ['id','doc_id','page','head_surface','tail_surface']},ensure_ascii=False))


if __name__=="__main__":main()
