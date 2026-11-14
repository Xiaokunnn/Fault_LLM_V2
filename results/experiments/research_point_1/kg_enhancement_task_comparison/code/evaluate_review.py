"""Compile disclosed AI source judgments and task-comparison measurements."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from inputs import ROOT, TASK, REV, GRAPH, load, norm, core_tuple, source_pointer, native_units, save, digest
from run_baselines import OUT, read

STATUSES={"explicit_support","conditional_support","insufficient_evidence","contradiction"}
OUTCOMES={"resolved","partial","unresolved","not_applicable"}
EVAL=OUT/"evaluation_v2"


def prove_query(page,query):
    pattern=r"\s+".join(re.escape(word) for word in query.split())
    match=re.search(pattern,page["page_text"],re.I)
    if match:
        return dict(kind="physical_page_text_span",start=match.start(),end=match.end(),text=page["page_text"][match.start():match.end()])
    matches=[]
    for uid,unit in native_units(page).items():
        match=re.search(pattern,unit["text"],re.I)
        if match:
            matches.append(dict(kind="native_unit_subspan",unit_id=uid,start=match.start(),end=match.end(),
                text=unit["text"][match.start():match.end()],bbox=unit.get("bbox")))
    if not matches:
        raise ValueError(f"No source witness for {page['doc_id']} p{page['pdf_page_number']}: {query}")
    return dict(kind="native_unit_candidates",witnesses=matches,uniquely_matched=len(matches)==1)


def refs(item):
    return item.get("source_records",[item.get("proposed_source",item.get("source",item))])


def common_core(item):
    source=item.get("proposed_source") or item.get("source")
    return core_tuple(source) if source and source.get("relation") else None


def main():
    d=load();spec=read(TASK/"review_labels.json");labels={r["id"]:r for r in spec["labels"]}
    assert len(labels)==len(spec["labels"])==66
    contexts={(r["task"],r["opportunity_id"]):r for r in read(OUT/"review/source_contexts.jsonl")}
    controls={(r["task"],r["opportunity_id"]):r for r in read(OUT/"controls/sample_predictions_v2.jsonl")}
    policies={(r["task"],r["opportunity_id"]):r for r in read(OUT/"controls/bounded_action_proposals_v2.jsonl")}
    pools={task:read(OUT/f"baselines/{task}_opportunities.jsonl") for task in "ABCDE"}
    samples={task:read(OUT/f"review/{task}_sample.jsonl") for task in "ABCDE"}
    samples.update({task:read(OUT/f"review/{task}.jsonl") for task in ["B_supplement","D_supplement"]})
    expected={r["opportunity_id"] for rows in samples.values() for r in rows}
    assert set(labels)==expected
    compiled=[];statistics={}
    for task,items in samples.items():
        for item in items:
            label=labels[item["opportunity_id"]]
            assert label["support"] in STATUSES and label["baseline"] in OUTCOMES
            context=contexts[task,item["opportunity_id"]]
            compiled.append(dict(task=task,primary=len(task)==1,**label,
                candidate=item,original_source_context=context,
                executed_controls=controls[task,item["opportunity_id"]],
                bounded_action_proposal=policies[task,item["opportunity_id"]]["proposal"],
                human_gold=False,independent_review=False,
                automatic_check="input IDs, page provenance and source-address controls; semantic verdict is disclosed AI review"))
        rows=[r for r in compiled if r["task"]==task]
        statistics[task]=dict(checked_task_items=len(rows),distinct_opportunity_ids=len({r["id"] for r in rows}),
            support_status_counts={s:sum(r["support"]==s for r in rows) for s in sorted(STATUSES)},
            baseline_outcome_counts={s:sum(r["baseline"]==s for r in rows) for s in sorted(OUTCOMES)},
            result_categories=dict(Counter(r["result"] for r in rows)),
            enhancement_supported_items=sum(r["enhancement"] for r in rows),
            enhancement_supported_in_scope_items=sum(r["enhancement"] and r["domain"]=="in_scope" for r in rows),
            remaining_in_scope_enhancement_items=sum(r["enhancement"] and r["domain"]=="in_scope" and r["baseline"] in {"partial","unresolved"} for r in rows),
            remaining_in_scope_items_by_cause=dict(Counter(r["residual"] for r in rows if r["enhancement"] and r["domain"]=="in_scope" and r["baseline"] in {"partial","unresolved"})),
            counts_are_not_accuracy_or_prevalence=True)
    save(EVAL/"review_labels_used.json",spec)
    save(EVAL/"cases.jsonl",compiled)
    for task in samples:
        save(EVAL/f"{task}_cases.jsonl",[r for r in compiled if r["task"]==task])
    by_reference=defaultdict(set)
    for case in compiled:
        for source in refs(case["candidate"]):
            assertion=source.get("assertion_id") or case["candidate"].get("assertion_id")
            if assertion:by_reference["assertion:"+assertion].add(case["task"].split("_")[0])
            by_reference[f"page:{source['doc_id']}:{source['pdf_page_number']}"].add(case["task"].split("_")[0])
    overlap=[dict(source_key=key,tasks=sorted(tasks)) for key,tasks in sorted(by_reference.items()) if len(tasks)>1]
    save(EVAL/"cross_task_source_overlap.jsonl",overlap)

    # Separate heterogeneous E opportunity keys from normalized relation cores.
    ecores={common_core(row) for row in pools["E"] if common_core(row) is not None}
    esource={row["opportunity_id"] for row in pools["E"] if common_core(row) is None}
    population={task:dict(opportunity_rows=len(rows),original_dedup_index_keys=len({r["fact_id"] for r in rows}),
        distinct_normalized_core_tuples=len({common_core(r) for r in rows if common_core(r) is not None}),
        nontuple_discovery_units=sum(common_core(r) is None for r in rows),
        not_a_semantically_verified_fact_count=True) for task,rows in pools.items()}
    population["E"]["unified_core_groups"]=len(ecores)
    population["E"]["unique_source_first_probe_units"]=len(esource)
    population["E"]["heterogeneous_total_is_not_fact_count"]=True
    population["C"]["nontuple_unit_meaning"]="entity ambiguity groups and existing multi-evidence claim families, not unidentified facts"
    save(EVAL/"population_units.json",population)

    # Bind independently quoted source propositions to actual text/native units.
    source_spec=read(TASK/"source_propositions.json");source_rows=[]
    for proposition in source_spec["propositions"]:
        page=d["pages"][proposition["doc_id"],proposition["page"]]
        proofs=[dict(query=query,proof=prove_query(page,query)) for query in proposition["queries"]]
        source_rows.append(dict(**proposition,source_proofs=proofs,document_sha256=page["document_sha256"],
            page_text_sha256=page["page_text_sha256"],source_url=page["source_url"],applicability_scope=page["applicability_scope"],
            bounded_review_not_global_absence_proof=True,human_gold=False))
    conflict=source_spec["supplementary_conflict_probe"]
    cp=[]
    for source in conflict["sources"]:
        page=d["pages"][source["doc_id"],source["page"]];units=native_units(page)
        cp.append(dict(**source,source_query_proofs=[prove_query(page,q) for q in source.get("queries",[])],
            original_native_cells=[units[cell] for cell in source.get("native_cells",[])],
            document_sha256=page["document_sha256"],page_text_sha256=page["page_text_sha256"],source_url=page["source_url"]))
    save(EVAL/"source_propositions.jsonl",source_rows)
    save(EVAL/"supplementary_conflict_probe.json",dict(**conflict,source_proofs=cp,human_gold=False,independent_review=False))
    source_stats=dict(checked_source_units=4,decomposed_frames=len(source_rows),
        distinct_qualified_frames=len({json.dumps(r["frame"],sort_keys=True) for r in source_rows}),
        source_support_counts=dict(Counter(r["support"] for r in source_rows)),
        initial_candidate_omission_probes=sum(not r["raw_frame_found"] for r in source_rows),
        omission_probe_documents=sorted({r["doc_id"] for r in source_rows if not r["raw_frame_found"]}),
        already_generated_frames=sum(r["raw_frame_found"] for r in source_rows),
        already_in_current_graph_frames=sum(r["current_frame_found"] for r in source_rows),
        global_semantic_omission_rate=None,complete_historical_model_requests_not_replayed=True)
    save(EVAL/"source_proposition_summary.json",source_stats)

    # Current graph only: provenance and ID consistency are controls, not accuracy.
    graph=d["graph"];entities={r["entity_id"] for r in graph["entities"]};claims={r["claim_id"]:r for r in graph["claims"]}
    assertions={r["assertion_id"]:r for r in graph["evidence_assertions"]}
    assert all(r["head_entity_id"] in entities and r["tail_entity_id"] in entities for r in claims.values())
    assert all(r["claim_id"] in claims for r in assertions.values())
    root=ET.fromstring(d["inputs"].raw(GRAPH+"graph.graphml"));ns={"g":"http://graphml.graphdrawing.org/xmlns"}
    gn=root.find("g:graph",ns);gnodes={r.attrib["id"] for r in gn.findall("g:node",ns)};gedges={r.attrib["id"] for r in gn.findall("g:edge",ns)}
    assert gnodes==entities and gedges==set(claims)
    pdfs=[]
    for row in d["manifest"]:
        path=ROOT/"data/source_docs/marine_pump/raw"/row["file_name"]
        actual=digest(path.read_bytes());assert actual==row["sha256"].lower()
        pdfs.append(dict(doc_id=row["doc_id"],path=path.relative_to(ROOT).as_posix(),sha256=actual,preserved=True))
    save(EVAL/"source_pdf_preservation.jsonl",pdfs)
    summary=dict(input_git_commit=REV,sole_base_graph="expanded1456",primary_items=60,
        primary_task_items_are_not_independent_facts=True,all_main_and_supplementary_rows=len(compiled),
        distinct_review_opportunity_ids=len(labels),additional_conflict_probe=1,
        unique_source_pages=len({(s["doc_id"],s["pdf_page_number"]) for case in compiled for s in refs(case["candidate"])}),
        task_statistics=statistics,source_proposition_statistics=source_stats,
        D_total_unique_candidates_checked=16,B_total_unique_items_checked=14,
        current_graph_ID_and_GraphML_consistency=True,original_PDFs_preserved=len(pdfs),
        full_initial_pool_semantically_supported_fact_count=None,
        full_initial_pool_support_count_reason="Only the disclosed fixed cases/source frames were semantically reviewed; candidate core counts are not correct-fact counts",
        no_independent_human_or_model_reference=True,model_calls=0,formal_graph_modifications=0)
    save(EVAL/"summary.json",summary)
    save(EVAL/"manifest.json",dict(input_git_commit=REV,input_sha256=d["inputs"].hashes,
        labels_sha256=digest((TASK/"review_labels.json").read_bytes()),source_proposition_spec_sha256=digest((TASK/"source_propositions.json").read_bytes()),
        code_sha256=digest(Path(__file__).read_bytes()),other_graphs_loaded=0,new_model_calls=0))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
