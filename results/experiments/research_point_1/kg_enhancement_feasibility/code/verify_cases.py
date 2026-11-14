"""Validate AI-review pointers/quotes and compile diagnostic cases, not truth labels."""
import ast
import copy
from collections import Counter,defaultdict
from pathlib import Path
import re
from investigate import Data,TASK,REV,read,save,sha,pointer,source_key,units,literal,locate_record

OUT=TASK/"runs/20261113_v1"

def locator(ar):
    path="src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py"
    tree=ast.parse(ar.raw(path),filename=path)
    tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {"flat","native_views","locate"}]
    module={"copy":copy,"re":re};exec(compile(tree,path,"exec"),module);return module["locate"]

def bind_quote(page,quote,locate):
    pattern=r"\s+".join(re.escape(s) for s in quote.split())
    found=re.search(pattern,page["page_text"])
    if found:return dict(kind="page_text_span",start=found.start(),end=found.end(),text=page["page_text"][found.start():found.end()])
    hits,geometry=locate(page,quote)
    if len(hits)!=1:raise ValueError(f"Quote not uniquely bound: {page['doc_id']} p{page['pdf_page_number']} {quote}")
    native=units(page)
    for w in hits[0]["witnesses"]:
        uid=w.get("cell_id") or w.get("block_id");u=native.get(uid)
        if not u or u["text"][w["start"]:w["end"]]!=w["text"]:raise ValueError("Native witness roundtrip failed")
    return dict(kind="native_path_not_contiguous_page_offset",witnesses=hits[0]["witnesses"],geometry=geometry)

def main():
    d=Data();locate=locator(d.ar);spec=read(TASK/"case_specs.json")
    index={};layers=defaultdict(set)
    for layer,rs in [("audited",d.audit),("raw_cached",d.raw),("terminology",d.zh),*[(k,g["source_records"]) for k,g in d.graphs.items()]]:
        for r in rs:
            index[r["triple_id"]]=r;layers[r["triple_id"]].add(layer)
    results=[]
    for c in spec["cases"]:
        if c["status"] not in {"explicit_support","conditional_support","insufficient_evidence","contradiction"}:raise ValueError("Invalid support status")
        records=[]
        for rid in c["record_ids"]:
            if rid not in index:raise ValueError("Unknown candidate/record ID: "+rid)
            r=index[rid];p=d.pages[r["doc_id"],r["pdf_page_number"]]
            records.append(dict(**pointer(r),layers=sorted(layers[rid]),address_check=locate_record(r,p),
                current_decision=r.get("decision"),page_title=p["title"],
                published_exact_source_membership={label:source_key(r) in keys for label,keys in d.record_sets.items()},
                raw_same_source_endpoints_count=sum(x["doc_id"]==r["doc_id"] and x["pdf_page_number"]==r["pdf_page_number"] and x["head_surface"]==r["head_surface"] and x["tail_surface"]==r["tail_surface"] and x["relation"]==r["relation"] for x in d.raw)))
        witnesses=[]
        for s in c.get("sources",[]):
            p=d.pages[s["doc_id"],s["page"]];bound=bind_quote(p,s["quote"],locate)
            witnesses.append(dict(**s,address=bound,source_family_id=p["source_family_id"],source_url=p["source_url"],
                page_text_sha256=p["page_text_sha256"],document_sha256=p["document_sha256"],applicability_scope=p["applicability_scope"]))
        results.append(dict(**c,records=records,source_witnesses=witnesses,reviewer=spec["reviewer"],human_gold=False,
            different_source_families=sorted({r["source_family_id"] for r in records}),
            automatic_check="IDs, source identities and quote addresses verified; semantic review remains nonblind AI judgment"))
    scope=spec["scope_candidate_review"];probes=read(OUT/"deeper/scope_candidates.jsonl")
    std_ids={r["triple_id"] for r in probes if r["layer"]=="standard1326"}
    if std_ids!=set(scope["explicitly_outside_declared_pump_scope_ids"]+scope["scope_not_resolved_ids"]):raise ValueError("Scope probe review coverage differs")
    # Reconcile full-cell byte mismatches before calling them evidence failures.
    differences=[]
    for layer,g in d.graphs.items():
        for r in g["source_records"]:
            native=d.page_units[r["doc_id"],r["pdf_page_number"]]
            for u in r.get("evidence_units") or []:
                n=native.get(u.get("cell_id"))
                if n and n["text"]!=u["text"]:differences.append(dict(layer=layer,triple_id=r["triple_id"],doc_id=r["doc_id"],page=r["pdf_page_number"],cell_id=u["cell_id"],
                    stored=u["text"],actual_native=n["text"],whitespace_equal=literal(u["text"])==literal(n["text"]),
                    stored_is_native_subspan=literal(u["text"]) in literal(n["text"])))
    schema_review={name:dict(additional_properties=d.schema["$defs"][name].get("additionalProperties"),
        explicit_qualifier_fields=[k for k in ["conditions","polarity","modality","applicability_scope"] if k in d.schema["$defs"][name].get("properties",{})]) for name in ["Claim","EvidenceAssertion","DocumentSource"]}
    summary=dict(diagnostic_cases=len(results),case_proposition_status_counts=dict(Counter(r["status"] for r in results)),
        statuses_are_not_extraction_precision_or_diagnostic_accuracy=True,
        record_ids_are_not_independent_cases=True,unique_referenced_record_ids=len({rid for c in spec["cases"] for rid in c["record_ids"]}),
        unique_source_pages=len({(r["doc_id"],r["pdf_page_number"]) for c in results for r in c["records"]}|{(r["doc_id"],r["page"]) for c in results for r in c["source_witnesses"]}),
        source_quote_addresses_verified=sum(len(r["source_witnesses"]) for r in results),
        alias_probe_review=dict(candidate_groups=5,AI_supported_lexical_naming_groups=4,context_or_type_unresolved_groups=1),
        scope_probe_review=dict(candidate_records=10,AI_supported_outside_declared_scope=7,unresolved=3,denominator="10 lexical candidates in standard1326, not all source knowledge"),
        cross_family_match_review=dict(candidate_records=4,conditional_additional_evidence=1,insufficient_object_or_scope_binding=3,new_relation_count_established=0),
        source_cell_difference_review={k:dict(cell_differences=sum(r["layer"]==k for r in differences),whitespace_equal=sum(r["layer"]==k and r["whitespace_equal"] for r in differences),
            stored_subspan=sum(r["layer"]==k and r["stored_is_native_subspan"] for r in differences)) for k in d.graphs},
        schema_nested_definition_review=schema_review,independent_reviewer_model_used=False,
        no_operating_advice="Source limits are audited for representation only, never permission to operate equipment")
    save(OUT/"case_review/cases.jsonl",results);save(OUT/"case_review/summary.json",summary)
    save(OUT/"case_review/native_cell_text_differences.jsonl",differences)
    for c in results:
        lines=["# "+c["case_id"]+" "+c["category"],"",c["proposition"],"",f"Support: {c['status']} | verdict: {c['issue_verdict']}","",c["engineering"],"","AI audit; not human/independent Gold."]
        for r in c["records"]:lines.extend(["",f"## {r['triple_id']} {r['doc_id']} physical page {r['pdf_page_number']}",f"{r['head_canonical_zh']} --{r['relation']}--> {r['tail_canonical_zh']}",r["evidence_text"],r["source_url"]])
        for s in c["source_witnesses"]:lines.extend(["",f"## Additional exact source {s['doc_id']} p{s['page']}",s["quote"],str(s["address"])])
        save(OUT/f"case_review/{c['case_id']}.md","\n".join(lines)+"\n")
    save(OUT/"case_review/manifest.json",dict(input_git_commit=REV,input_sha256=d.ar.hashes,case_spec_sha256=sha((TASK/"case_specs.json").read_bytes()),
        verifier_sha256=sha(Path(__file__).read_bytes()),new_model_calls=0,graph_writes=0,all_reviews_disclosed_as_AI=True))
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
