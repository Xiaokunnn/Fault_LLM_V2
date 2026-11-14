"""Add source-context and lexical controls without changing frozen cohorts."""
from collections import defaultdict
import json
from pathlib import Path
import re
import argparse

from inputs import TASK, REV, load, norm, identifier, record_ids, core_tuple, source_pointer, native_units, save, address_check, digest
from run_baselines import OUT, ordered, read, cue_spans


def lexical_units(text):
    text=norm(text)
    english=set(re.findall(r"[a-z0-9]+",text))
    chinese=set()
    for phrase in re.findall(r"[\u4e00-\u9fff]+",text):
        chinese.update(phrase[i:i+2] for i in range(len(phrase)-1))
    return english|chinese


def similarity(a,b):
    a,b=lexical_units(a),lexical_units(b)
    return len(a&b)/max(1,len(a|b))


def reference_context(source,page):
    quote=source.get("evidence_text","")
    start=source.get("evidence_start")
    if not isinstance(start,int) or start<0:
        start=page["page_text"].casefold().find(quote[:min(35,len(quote))].casefold()) if quote else -1
    if start>=0:
        text_context=page["page_text"][max(0,start-550):min(len(page["page_text"]),start+max(len(quote),500)+650)]
    else:text_context=page["page_text"]
    return dict(doc_id=source["doc_id"],pdf_page_number=source["pdf_page_number"],page_title=page["title"],
        source_url=page["source_url"],applicability_scope=page["applicability_scope"],source_family_id=page["source_family_id"],
        page_text_sha256=page["page_text_sha256"],document_sha256=page["document_sha256"],
        original_page_text_context=text_context,original_page_characters=len(page["page_text"]),
        full_page_context_stored=True,address_check=address_check(source,page))


def main():
    d=load();samples={key:read(OUT/f"review/{key}_sample.jsonl") for key in "ABCDE"}
    selected_d={row["opportunity_id"] for row in samples["D"]}
    ds=[row for row in read(OUT/"baselines/D_opportunities.jsonl") if row["opportunity_id"] not in selected_d]
    sb=[row for row in read(OUT/"baselines/B_opportunities.jsonl") if row["baseline"]["conditions_source_present"]]
    bs=ordered(sb,"B-structured-supplement")[:3]
    save(OUT/"review/D_supplement.jsonl",ds);save(OUT/"review/B_supplement.jsonl",bs)
    contexts=[]
    graph=d["graph"]["source_records"]
    for task,rows in {**samples,"B_supplement":bs,"D_supplement":ds}.items():
        for item in rows:
            refs=item.get("source_records",[item.get("proposed_source",item.get("source",item))])
            item_contexts=[]
            for ref in refs:
                page=d["pages"][ref["doc_id"],ref["pdf_page_number"]]
                if "text" in ref and "evidence_text" not in ref:
                    ref={**ref,"evidence_text":ref["text"]}
                item_contexts.append(reference_context(ref,page))
                save(OUT/f"review/pages/{ref['doc_id']}_p{ref['pdf_page_number']:04d}.json",page)
            lexical=[]
            if task in {"A","E"}:
                ref=refs[0]
                if ref.get("relation"):
                    key=core_tuple(ref)
                    for source in graph:
                        if source["relation"]!=ref["relation"]:continue
                        other=core_tuple(source)
                        score=(similarity(key[1],other[1])+similarity(key[4],other[4]))/2
                        if score:
                            lexical.append(dict(assertion_id=source["expanded_assertion_id"],claim_id=source["expanded_claim_id"],
                                score=round(score,6),core_tuple=other,doc_id=source["doc_id"],pdf_page_number=source["pdf_page_number"],
                                evidence_text=source["evidence_text"],applicability_scope=source["applicability_scope"]))
            page_raw=[]
            if task=="E" and item["stratum"]=="source_first_omission_probe":
                page_raw=[source_pointer(row) for row in d["raw"] if row["doc_id"]==item["doc_id"] and row["pdf_page_number"]==item["pdf_page_number"]]
            contexts.append(dict(task=task,opportunity_id=item["opportunity_id"],source_contexts=item_contexts,
                lexical_current_graph_candidates=sorted(lexical,key=lambda r:(-r["score"],r["assertion_id"]))[:5],
                all_raw_candidates_on_source_probe_page=page_raw,lexical_scores_are_not_semantic_equivalence=True))
    save(OUT/"review/source_contexts.jsonl",contexts)
    # Audit-only orphans are retained, never silently manufactured into raw occurrences.
    mapped=read(OUT/"mapping/raw_occurrence_mapping.jsonl")
    linked={rid for row in mapped for rid in row["audit_record_ids"]}
    orphan=[]
    for row in d["audit"]:
        if row["triple_id"] not in linked:
            ids=set(record_ids(row))
            matches=[r for r in graph if ids&set(record_ids(r))]
            orphan.append(dict(audit_record_id=row["triple_id"],source=source_pointer(row),decision=row.get("decision"),
                current_assertion_ids=[r["expanded_assertion_id"] for r in matches],raw_lineage_status="not_present_in_retained_raw_cache",
                count_as_extra_raw_occurrence=False))
    save(OUT/"mapping/audit_only_orphans.jsonl",orphan)
    save(OUT/"review/preparation_manifest.json",dict(input_git_commit=REV,input_sha256=d["inputs"].hashes,
        code_sha256=digest(Path(__file__).read_bytes()),primary_items=sum(len(rs) for rs in samples.values()),
        supplementary_B_items=len(bs),supplementary_D_items=len(ds),audit_only_orphans=len(orphan),
        supplement_selection_disclosed_before_its_labels=True,other_graphs_loaded=0))
    print(json.dumps(dict(primary=60,B_supplement=len(bs),D_supplement=len(ds),audit_only_orphans=len(orphan)),indent=2))


if __name__=="__main__":main()
