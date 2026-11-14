"""Run lexical-clause, native-table, typed-dictionary and scope controls."""
from collections import defaultdict
import json
from pathlib import Path
import re

from inputs import TASK, REV, load, native_units, norm, core_tuple, source_pointer, digest, save
from run_baselines import OUT, read, cue_spans, table_readback
from prepare_review import similarity


def clause_proposals(text):
    result=[]
    # Deliberately simple: punctuation/newline segmentation has documented failures.
    for match in re.finditer(r"\b(?:if|when|unless|before|after|then|must|shall|should|may|can|do not|is to be|are to be)\b",text,re.I):
        end=re.search(r"[.;\n]",text[match.end():])
        stop=match.end()+end.start() if end else len(text)
        result.append(dict(cue=match.group(),start=match.start(),end=stop,text=text[match.start():stop]))
    return result


def normalized_clause_proposals(text):
    """Stronger generic control: layout whitespace removed, decimals/refs kept."""
    tokens=list(re.finditer(r"\S+",text));flat=[];positions=[]
    for token in tokens:
        if flat:flat.append(" ");positions.append(token.start())
        flat.extend(token.group());positions.extend(range(token.start(),token.end()))
    normalized="".join(flat);result=[]
    for match in re.finditer(r"\b(?:if|when|unless|before|after|then|must|shall|should|may|might|could|can|do not|is to be|are to be)\b",normalized,re.I):
        terminal=re.search(r";|\.(?=\s+[A-Z]|$)",normalized[match.end():])
        stop=match.end()+terminal.start() if terminal else len(normalized)
        a,b=positions[match.start()],positions[stop-1]+1
        result.append(dict(cue=match.group(),normalized_text=normalized[match.start():stop],
            original_start=a,original_end=b,original_text=text[a:b],source_roundtrip=norm(text[a:b])==norm(normalized[match.start():stop])))
    return result


def compact_table(table):
    rows=table["same_row_or_declared_group_rows"]
    return [dict(row_id=row["row_id"],row_group_id=row.get("row_group_id"),
        fields=[dict(cell_id=c["cell_id"],column_name=c.get("column_name"),column_role=c.get("column_role"),text=c["text"]) for c in row["cells"]]) for row in rows]


def list_membership(source,page):
    match=re.search(r"Spare parts list\s+([^\n]+)",page["page_text"],re.I)
    head=source.get("head_surface","")
    return dict(model_heading=match.group(1).strip() if match else None,
        part_surface_occurs=bool(head and norm(head) in norm(page["page_text"])),
        interpretation="Parts-list membership only; not a measured spatial position or qualified executable action")


def main():
    d=load();samples={task:read(OUT/f"review/{task}_sample.jsonl") for task in "ABCDE"}
    samples["B_supplement"]=read(OUT/"review/B_supplement.jsonl")
    samples["D_supplement"]=read(OUT/"review/D_supplement.jsonl")
    graph={r["expanded_assertion_id"]:r for r in d["graph"]["source_records"]}
    results=[]
    for task,items in samples.items():
        for item in items:
            refs=item.get("source_records",[item.get("proposed_source",item.get("source",item))])
            controls=[]
            for ref in refs:
                page=d["pages"][ref["doc_id"],ref["pdf_page_number"]]
                text=ref.get("evidence_text",ref.get("text",""))
                table=table_readback(ref,page)
                native=native_units(page)
                conditions=ref.get("conditions_source") or []
                condition_readback=[]
                for condition in conditions:
                    unit=native.get(condition.get("cell_id") or condition.get("block_id"))
                    condition_readback.append(dict(**condition,native_unit_found=unit is not None,
                        verbatim_equal=bool(unit and norm(unit["text"])==norm(condition["text"]))))
                controls.append(dict(doc_id=ref["doc_id"],page=ref["pdf_page_number"],
                    source_clause_proposals=clause_proposals(text),stronger_clause_proposals=normalized_clause_proposals(text),source_cues=cue_spans(text),
                    endpoint_alternatives={side:re.split(r"\s+or\s+|或者|或",ref.get(side+"_surface",""),flags=re.I) for side in ["head","tail"]},
                    native_table_context=compact_table(table),structured_condition_readback=condition_readback,
                    parts_list_membership=list_membership(ref,page),
                    document_scope=page["applicability_scope"],
                    page_section_header=" ".join(page["page_text"].split())[:600],
                    any_rule_output_is_not_a_verified_enhancement=True))
            pair_controls=[]
            if task=="C":
                for i,a in enumerate(refs):
                    for b in refs[i+1:]:
                        pair_controls.append(dict(assertions=[a["assertion_id"],b["assertion_id"]],
                            same_core_tuple=core_tuple(a)==core_tuple(b),same_source_family=a["source_family_id"]==b["source_family_id"],
                            same_document=a["doc_id"]==b["doc_id"],
                            scope_similarity=round(similarity(a["applicability_scope"],b["applicability_scope"]),6),
                            source_text_similarity=round(similarity(a["evidence_text"],b["evidence_text"]),6),
                            same_source_does_not_mean_same_conditions=True))
            results.append(dict(task=task,opportunity_id=item["opportunity_id"],source_controls=controls,pairwise_context_controls=pair_controls))
    # Preserve the first diagnostic baseline; upgraded results have a new name.
    save(OUT/"controls/sample_predictions_v2.jsonl",results)
    queries={
        "restart_drainage_procedures":dict(doc="MP007",expression=r"vent plug|drainage valve|drain plug|bypass valve|排气塞|排水阀|排放阀|旁通阀"),
        "concern_pareto_rca":dict(doc="MP002",expression=r"Pareto|areas of concern|Root Cause Failure|根本原因|帕累托"),
        "seal_material_fields":dict(doc="MP022",expression=r"stationary seal ring|rotating seal ring|Material, O-rings|Alternative material, O-rings|静环|动环|O型圈.*材料|材料.*O型圈"),
        "fire_pump_exception":dict(doc="MP004",expression=r"fire pump|消防泵"),
        "delivery_motor_inspection":dict(doc="MP019",expression=r"receipt|delivery|réception|recepción|Empfang|收货|接收|到货|交付")}
    search=[]
    for name,query in queries.items():
        for stage,rows in [("initial_raw",d["raw"]),("current_graph",d["graph"]["source_records"])]:
            hits=[r for r in rows if r["doc_id"]==query["doc"] and re.search(query["expression"]," ".join(str(r.get(k,"")) for k in ["evidence_text","head_surface","tail_surface","head_canonical_zh","tail_canonical_zh"]),re.I)]
            search.append(dict(query_name=name,stage=stage,doc_id=query["doc"],regex=query["expression"],
                hits=[dict(**source_pointer(r),current_assertion_id=r.get("expanded_assertion_id"),current_claim_id=r.get("expanded_claim_id")) for r in hits],
                no_hit_is_not_exhaustive_semantic_absence=True))
    save(OUT/"controls/source_proposition_searches.jsonl",search)
    save(OUT/"controls/manifest_v2.json",dict(input_git_commit=REV,input_sha256=d["inputs"].hashes,program_sha256=digest(Path(__file__).read_bytes()),
        all_controls_executed=True,no_other_graph_inputs=True,semantic_review_still_required=True))
    print(json.dumps(dict(task_sample_rows=len(results),source_searches=len(search),new_models=0,graph_writes=0),indent=2))


if __name__=="__main__":main()
