"""Transparent task-discovery baselines; no learned enhancement algorithm."""
from collections import Counter, defaultdict
import itertools
import json
from pathlib import Path
import re

from inputs import TASK, REV, GRAPH, load, save, norm, identifier, core_tuple, source_pointer, address_check, native_units, digest

OUT = TASK / "runs/20261113_v1"
SEED = "rp1-task-comparison-v1-20261113"
PATTERNS = {
    "condition": r"\b(?:if|when|unless|provided that|in case|only when)\b|如果|当.+时|仅当|除非",
    "prohibition": r"\b(?:do not|must not|shall not|should not|never)\b|不得|禁止|切勿",
    "normative_causal": r"\b(?:is|are) not to (?:cause|result)|\b(?:shall|must|should) not (?:cause|result)",
    "requirement": r"\b(?:must|shall|required|is to be|are to be)\b|必须|应当|要求",
    "suggestion": r"\b(?:should|recommend(?:ed)?|advisable)\b|建议|推荐|宜",
    "possibility": r"\b(?:may|might|could|can)\b|可能|可以",
    "sequence": r"\b(?:before|after|then|first|finally|step(?:s)?)\b|之前|之后|首先|然后|步骤",
    "alternative": r"\b(?:either|or|otherwise|alternatively)\b|或者|否则|或是",
    "equipment_model": r"\b(?:model|type)\s+[A-Z0-9][A-Z0-9/-]*|\b(?:NSL|LKH|NSLH|FS)\b|型号",
    "quantity": r"\b\d+(?:\.\d+)?\s*(?:seconds?|secs?|minutes?|mins?|hours?|months?|years?|rpm|psi|bar|°?[CF])\b",
    "causal": r"\b(?:caus(?:e|es|ed|ing)|results? in|leads? to|due to)\b|导致|引起",
}


def read(path):
    path = Path(path)
    text = path.read_text(encoding="utf8")
    return [json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix == ".jsonl" else json.loads(text)


def cue_spans(text):
    return [{"kind": kind, "start": hit.start(), "end": hit.end(), "text": hit.group()}
            for kind, expression in PATTERNS.items() for hit in re.finditer(expression, text, re.I)]


def ordered(items, salt):
    return sorted(items, key=lambda row: identifier([SEED, salt, row]))


def sample_strata(items, key, quotas, identity):
    selected, used = [], set()
    for stratum, quota in quotas:
        subset = [row for row in items if key(row) == stratum and identity(row) not in used]
        for row in ordered(subset, stratum)[:quota]:
            selected.append(row)
            used.add(identity(row))
    return selected


def morphology(text):
    text = norm(text).replace("-", " ")
    parts = text.split()
    if parts and re.fullmatch(r"[a-z0-9 /]+", text) and parts[-1].endswith("s") and not parts[-1].endswith(("ss", "us")):
        parts[-1] = parts[-1][:-1]
    return " ".join(parts)


def table_readback(record, page):
    units = native_units(page)
    ids = set(record.get("evidence_unit_ids") or [])
    ids.update(unit.get("cell_id") for unit in record.get("evidence_units") or [])
    ids.update(w.get("cell_id") for w in record.get("expansion_source_witnesses") or [])
    cells = [units[uid] for uid in sorted(uid for uid in ids if uid) if uid in units and "cell_id" in units[uid]]
    row_ids = {c.get("row_id") for c in cells}
    groups = {c.get("row_group_id") for c in cells if c.get("row_group_id")}
    rows = []
    for table in page.get("tables", []):
        for row in table["rows"]:
            if row.get("row_id") in row_ids or any(cell.get("row_group_id") in groups for cell in row["cells"] if cell.get("row_group_id")):
                rows.append({"table_id": table.get("table_id"), **row})
    return dict(referenced_native_cells=cells, same_row_or_declared_group_rows=rows,
                limit="Row/group membership supplies source context, not automatically correct relation or qualifier scope")


def role_schema(record, schema):
    rule = schema["relation_registry"].get(record["relation"], {})
    return record["head_type"] in rule.get("domain", []) and record["tail_type"] in rule.get("range", [])


def build_A(mapping, d):
    rows = []
    for m in mapping:
        if m["candidate_category"] == "current_graph_lineage_present":
            continue
        representative = m["normalized_source"]
        status = m["historical_audit_statuses"]
        if m["current_core_match_assertion_ids"]:
            stratum = "same_core_control"
        elif "silver_candidate" in status:
            stratum = "unpublished_historically_qualified"
        elif "candidate_needs_review" in status:
            stratum = "unpublished_quarantined"
        else:
            stratum = "unpublished_rejected_or_unmapped"
        checks = m["normalized_address_checks"]
        source_bound = any(x["exact_contiguous_offset"] or x["all_provided_cells_match"] or x["all_native_witnesses_match"] for x in checks)
        passed = source_bound and role_schema(representative, d["schema"])
        rows.append(dict(opportunity_id="A-" + m["raw_occurrence_id"], raw_occurrence_id=m["raw_occurrence_id"],
            fact_id=m["normalized_candidate_fact_id"], stratum=stratum,
            historical_audit_statuses=status, historical_reasons=m["historical_reasons"],
            proposed_source=representative, graph_core_matches=m["current_core_match_assertion_ids"],
            lineage_ids=m["all_linked_record_ids"],
            baseline={"current_core_tuple_covered": bool(m["current_core_match_assertion_ids"]),
                      "address_and_schema_screen_pass": passed,
                      "recovery_permitted_by_screen_alone": False,
                      "limitation": "Semantic support, conditions, terminology and duplication must still be checked; no gate relaxed"}))
    # One deterministic representative per candidate core in each stratum.
    unique = {}
    for row in ordered(rows, "A-dedup"):
        unique.setdefault((row["stratum"], row["fact_id"]), row)
    sample = sample_strata(list(unique.values()), lambda r:r["stratum"], [(x,3) for x in ["unpublished_historically_qualified", "unpublished_quarantined", "unpublished_rejected_or_unmapped", "same_core_control"]], lambda r:r["fact_id"])
    return rows, sample


def build_B_D(d):
    b_rows, d_rows = [], []
    for source in d["graph"]["source_records"]:
        page = d["pages"][source["doc_id"], source["pdf_page_number"]]
        text = source["evidence_text"]
        spans = cue_spans(text)
        kinds = {s["kind"] for s in spans}
        payload = str(source["head_surface"]) + " " + str(source["tail_surface"])
        missing_kinds = kinds - {s["kind"] for s in cue_spans(payload)}
        table = table_readback(source, page)
        sid = source["expanded_assertion_id"]
        if kinds or table["referenced_native_cells"]:
            stratum = "table" if table["referenced_native_cells"] else "operators" if kinds & {"prohibition", "normative_causal", "requirement"} else "condition_sequence" if kinds & {"condition", "sequence", "alternative", "equipment_model", "quantity"} else "possibility_causal"
            b_rows.append(dict(opportunity_id="B-" + sid, assertion_id=sid, claim_id=source["expanded_claim_id"],
                fact_id="CORE-" + identifier(core_tuple(source)), stratum=stratum, source=source_pointer(source),
                baseline={"literal_operator_spans":spans, "cue_kinds_not_in_endpoints":sorted(missing_kinds),
                          "conditions_source_present":bool(source.get("conditions_source")),
                          "modality_field":source.get("modality"), "table_readback":table,
                          "semantic_scope_or_completeness_certified":False},
                address_check=address_check(source,page)))
        flags = []
        if not role_schema(source, d["schema"]):
            flags.append("schema_direction_or_type")
        if "normative_causal" in kinds and source["relation"] in {"causes", "increases_risk_of"}:
            flags.append("normative_as_positive_cause")
        if "prohibition" in kinds and source["relation"] == "operates_under":
            flags.append("prohibition_as_operating_condition")
        if source["doc_id"] == "MP003" and re.search(r"propeller|crankshaft|piston|rudder|connecting rod|cylinder liner|compressor", source["head_surface"] + " " + source["tail_surface"],re.I):
            flags.append("equipment_scope")
        if source["head_type"] == "Component" and re.search(r"\boperation\b",source["head_surface"],re.I) or source["tail_type"] == "Component" and re.search(r"\boperation\b",source["tail_surface"],re.I):
            flags.append("action_as_component_probe")
        # Only literal single-clause direction probes, not a semantic direction oracle.
        h, t, quote = norm(source["head_surface"]),norm(source["tail_surface"]),norm(text)
        if source["relation"] == "causes" and h and t and quote.count(h)==quote.count(t)==1:
            cause = re.search(r"\b(?:causes?|causing)\b",quote)
            if cause and quote.index(t)<cause.start()<quote.index(h):
                flags.append("literal_direction_probe")
        if flags:
            d_rows.append(dict(opportunity_id="D-" + sid, assertion_id=sid,claim_id=source["expanded_claim_id"],
                fact_id="CORE-"+identifier(core_tuple(source)), stratum=flags[0], flags=flags,source=source_pointer(source),
                baseline={"schema_type_pass":role_schema(source,d["schema"]),"rule_flags":flags,
                          "automatic_correction_permitted":False,"table_readback":table},address_check=address_check(source,page)))
    b_sample=sample_strata(b_rows,lambda r:r["stratum"],[(k,3) for k in ["table","operators","condition_sequence","possibility_causal"]],lambda r:r["assertion_id"])
    d_sample=sample_strata(d_rows,lambda r:r["stratum"],[("normative_as_positive_cause",2),("prohibition_as_operating_condition",2),("equipment_scope",6),("action_as_component_probe",2),("literal_direction_probe",2),("schema_direction_or_type",2)],lambda r:r["assertion_id"])
    if len(d_sample)>12:d_sample=d_sample[:12]
    if len(d_sample)<12:
        existing={r["assertion_id"] for r in d_sample}
        d_sample.extend(ordered([r for r in d_rows if r["assertion_id"] not in existing],"D-fill")[:12-len(d_sample)])
    return b_rows,b_sample,d_rows,d_sample


def build_C(d):
    entities={r["entity_id"]:r for r in d["graph"]["entities"]}
    bysurface,bylabel,byclaim,numeric=defaultdict(set),defaultdict(set),defaultdict(list),defaultdict(list)
    source=d["graph"]["source_records"]
    for row in source:
        byclaim[row["expanded_claim_id"]].append(row)
        for side in ["head","tail"]:
            eid=row["expanded_"+side+"_entity_id"]
            bysurface[row[side+"_type"],morphology(row[side+"_surface"])].add(eid)
            bylabel[norm(row[side+"_canonical_zh"])].add(eid)
        values=re.findall(PATTERNS["quantity"],row["evidence_text"],re.I)
        if values:numeric[row["head_type"],norm(row["head_canonical_zh"]),row["relation"]].append(row)
    rows=[]
    for (typ,surface),ids in bysurface.items():
        if len(ids)>1:
            refs=[r for r in source if r["expanded_head_entity_id"] in ids or r["expanded_tail_entity_id"] in ids]
            rows.append(dict(stratum="typed_surface_alias",group_key=[typ,surface],entity_ids=sorted(ids),
                labels=[entities[i]["label_zh"] for i in sorted(ids)],source_records=refs,
                baseline={"string_normalized_source_match":True,"type_constraint_pass":True,"auto_merge_permitted":False}))
    for label,ids in bylabel.items():
        if len({entities[i]["entity_type"] for i in ids})>1:
            refs=[r for r in source if r["expanded_head_entity_id"] in ids or r["expanded_tail_entity_id"] in ids]
            rows.append(dict(stratum="same_label_different_types",group_key=label,entity_ids=sorted(ids),
                labels=[entities[i] for i in sorted(ids)],source_records=refs,
                baseline={"string_normalized_label_match":True,"type_constraint_pass":False,"auto_merge_permitted":False}))
    for cid,refs in byclaim.items():
        if len(refs)>1:
            rows.append(dict(stratum="multi_evidence_claim",group_key=cid,claim_id=cid,source_records=refs,
                baseline={"same_current_claim":True,"source_family_count":len({r["source_family_id"] for r in refs}),
                          "distinct_document_count":len({r["doc_id"] for r in refs}),"independent_support_certified":False}))
    for key,refs in numeric.items():
        # One group per shared typed head/relation. Numeric disagreement alone is not conflict.
        if len({norm(r["evidence_text"]) for r in refs})>1 and len({r["doc_id"] for r in refs})>1:
            rows.append(dict(stratum="apparent_numeric_conflict",group_key=key,source_records=refs,
                baseline={"same_head_and_relation":True,"scopes":[[r["doc_id"],r.get("pump_type"),r.get("service")] for r in refs],
                          "contradiction_established":False}))
    for row in rows:
        row["opportunity_id"]="C-"+identifier([row["stratum"],row["group_key"]])
        row["fact_id"]=row["opportunity_id"]
        row["assertion_ids"]=sorted({r["expanded_assertion_id"] for r in row["source_records"]})
        row["claim_ids"]=sorted({r["expanded_claim_id"] for r in row["source_records"]})
        row["source_records"]=[dict(assertion_id=r["expanded_assertion_id"],claim_id=r["expanded_claim_id"],**source_pointer(r)) for r in row["source_records"]]
    sample=sample_strata(rows,lambda r:r["stratum"],[(k,3) for k in ["typed_surface_alias","same_label_different_types","multi_evidence_claim","apparent_numeric_conflict"]],lambda r:r["opportunity_id"])
    if len(sample)<12:
        used={r["opportunity_id"] for r in sample}
        sample.extend(ordered([r for r in rows if r["opportunity_id"] not in used],"C-fill")[:12-len(sample)])
    return rows,sample


def source_first(d):
    hits=[]
    raw_by_page=defaultdict(list)
    graph_by_page=defaultdict(list)
    for row in d["raw"]:raw_by_page[row["doc_id"],row["pdf_page_number"]].append(row["triple_id"])
    for row in d["graph"]["source_records"]:graph_by_page[row["doc_id"],row["pdf_page_number"]].append(row["expanded_assertion_id"])
    bydoc=defaultdict(list)
    for (doc,page_number),page in sorted(d["pages"].items()):
        for uid,unit in native_units(page).items():
            spans=cue_spans(unit["text"])
            kinds={s["kind"] for s in spans}
            if not kinds & {"causal","condition","prohibition","sequence","alternative","requirement"}:continue
            # Discovery selection never consults graph/candidate presence.
            score=len(kinds & {"condition","prohibition","sequence","alternative","equipment_model","quantity","causal"})
            score+=bool(re.search(r"pump|bearing|seal|impeller|cavitation",unit["text"],re.I))
            item=dict(opportunity_id="SRC-"+identifier([doc,page_number,uid]),doc_id=doc,pdf_page_number=page_number,
                native_unit_id=uid,text=unit["text"],cue_spans=spans,source_only_priority=score,
                source_url=page["source_url"],document_sha256=page["document_sha256"],page_text_sha256=page["page_text_sha256"],
                source_family_id=page["source_family_id"],applicability_scope=page["applicability_scope"],
                graph_absence_is_not_omission=True,semantic_omission_status="not_reviewed")
            hits.append(item);bydoc[doc].append(item)
    sample=[]
    for doc,rows in sorted(bydoc.items()):
        used=set()
        for row in sorted(rows,key=lambda r:(-r["source_only_priority"],identifier([SEED,r["opportunity_id"]]))):
            if row["pdf_page_number"] in used:continue
            selected={**row,"raw_candidate_ids_on_page":raw_by_page[doc,row["pdf_page_number"]],
                      "current_assertion_ids_on_page":graph_by_page[doc,row["pdf_page_number"]]}
            sample.append(selected);used.add(row["pdf_page_number"])
            if len(used)==2:break
    return hits,sample


def main():
    d=load();mapping=read(OUT/"mapping/raw_occurrence_mapping.jsonl")
    a,sa=build_A(mapping,d);b,sb,dr,sd=build_B_D(d);c,sc=build_C(d);source_hits,source_sample=source_first(d)
    # E mixes three explicitly disclosed discovery strata, never topology-generated positives.
    er=[]
    for row in a:
        er.append(dict(**{k:v for k,v in row.items() if k not in {"opportunity_id","stratum","baseline"}},opportunity_id="E-"+row["opportunity_id"],
            stratum="candidate_pool_association",parent_opportunity_id=row["opportunity_id"],
            baseline={**row["baseline"],"new_relation_established":False}))
    for row in source_sample:
        er.append(dict(**{k:v for k,v in row.items() if k!="opportunity_id"},opportunity_id="E-"+row["opportunity_id"],stratum="source_first_omission_probe",fact_id=row["opportunity_id"],
            baseline={"native_source_span_available":True,"raw_omission_established":False,"new_relation_established":False}))
    for row in b:
        kinds={s["kind"] for s in row["baseline"]["literal_operator_spans"]}
        if kinds & {"sequence","alternative","condition","equipment_model","quantity"}:
            er.append(dict(**{k:v for k,v in row.items() if k not in {"opportunity_id","stratum","baseline"}},opportunity_id="E-"+row["opportunity_id"],stratum="schema_or_qualified_association",parent_opportunity_id=row["opportunity_id"],
                baseline={**row["baseline"],"new_relation_established":False,"schema_expressibility_requires_review":True}))
    se=sample_strata(er,lambda r:r["stratum"],[(k,4) for k in ["candidate_pool_association","source_first_omission_probe","schema_or_qualified_association"]],lambda r:r["fact_id"])
    summary={"input_git_commit":REV,"sole_base_graph":"expanded1456","base_assertions":1456,"base_claims":1400,
             "models_trained":0,"formal_graph_changes":0,"reference_labels":"not yet reviewed; no human Gold",
             "source_first":{"all_native_cue_units":len(source_hits),"selected_units":len(source_sample),"selected_distinct_pages":len({(r["doc_id"],r["pdf_page_number"]) for r in source_sample}),
                             "selection":"two distinct source pages per document, source-only lexical complexity priority then stable hash; not a prevalence sample"},"tasks":{}}
    for task,pool,sample in [("A",a,sa),("B",b,sb),("C",c,sc),("D",dr,sd),("E",er,se)]:
        save(OUT/f"baselines/{task}_opportunities.jsonl",pool)
        save(OUT/f"review/{task}_sample.jsonl",sample)
        summary["tasks"][task]=dict(candidate_opportunity_occurrences=len(pool),distinct_candidate_units=len({r["fact_id"] for r in pool}),
            candidate_counts_are_not_supported_facts=True,strata=dict(Counter(r["stratum"] for r in pool)),
            fixed_semantic_review_items=len(sample),sample_strata=dict(Counter(r["stratum"] for r in sample)))
    save(OUT/"source_first/native_cue_units.jsonl",source_hits);save(OUT/"source_first/selected_units.jsonl",source_sample)
    for row in source_sample:
        page=d["pages"][row["doc_id"],row["pdf_page_number"]]
        save(OUT/f"source_first/pages/{row['doc_id']}_p{row['pdf_page_number']:04d}.json",page)
    # Full page/table context for each fixed sample, avoiding invented linearized table evidence.
    pagekeys=set()
    for sample in [sa,sb,sc,sd,se]:
        for item in sample:
            refs=item.get("source_records",[item.get("proposed_source",item.get("source",item))])
            for ref in refs:pagekeys.add((ref["doc_id"],ref["pdf_page_number"]))
    for doc,p in sorted(pagekeys):save(OUT/f"review/pages/{doc}_p{p:04d}.json",d["pages"][doc,p])
    save(OUT/"baselines/summary.json",summary)
    save(OUT/"baselines/input_manifest.json",dict(input_git_commit=REV,input_sha256=d["inputs"].hashes,
        program_sha256=digest(Path(__file__).read_bytes()),input_module_sha256=digest((TASK/"code/inputs.py").read_bytes()),
        mapping_manifest_sha256=digest((OUT/"mapping/input_manifest.json").read_bytes()),
        no_other_graph_loaded=True,sampling_seed=SEED,no_human_reference=True))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
