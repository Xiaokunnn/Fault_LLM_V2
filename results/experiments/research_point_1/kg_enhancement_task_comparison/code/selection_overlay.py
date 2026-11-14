"""Source-checked experimental graph deltas and A--E comparison.

These are nonblind AI-reviewed source-supported TRIAL additions, not a release
through the entire frozen publication pipeline and not independent Gold.
The unchanged executable component gate is reported separately.  Official
graph records are only copied; all changes live in this experiment sandbox.
"""
from collections import Counter,defaultdict
import ast
import copy
import json
import re
import subprocess
import sys

from inputs import ROOT,TASK,REV,load,save,norm,identifier,core_tuple,native_units,digest
from selection_screen import OUT,OLD,read,exact_fragment

REVIEWER="current_assistant_nonblind_source_review_not_independent_model_or_human"
SANDBOX=OUT/"sandbox_v2"


def native_locator():
    path="src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py"
    raw=subprocess.check_output(["git","show",REV+":"+path],cwd=ROOT)
    tree=ast.parse(raw);names={"flat","norm","contained","native_views","locate"}
    pure=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    ns={"copy":copy,"re":re};exec(compile(pure,path,"exec"),ns)
    return ns["locate"]


LOCATE=None


def proof(page,query):
    """Return existing original page/native offsets, never derived offsets."""
    hit=exact_fragment(page["page_text"],query)
    if hit:
        a,b=hit;return {"kind":"page_span","start":a,"end":b,"text":page["page_text"][a:b]}
    for key,unit in native_units(page).items():
        at=exact_fragment(unit["text"],query)
        if at:
            a,b=at;kind="cell_id" if "cell_id" in unit else "block_id"
            return {"kind":"native_subspan",kind:key,"start":a,"end":b,
                    "text":unit["text"][a:b],"bbox":unit.get("bbox")}
    hits,_=LOCATE(page,query)
    if hits:return {"kind":"native_multiunit_quote","witnesses":hits[0]["witnesses"],
                    "quote":query,"ambiguous_native_locations":len(hits)}
    raise ValueError(f"No real original-source witness: {page['doc_id']}:{page['pdf_page_number']}: {query}")


def prove_queries(d,doc,pg,queries):
    page=d["pages"][doc,pg]
    return [{"doc_id":doc,"page":pg,"document_sha256":page["document_sha256"],
             "page_text_sha256":page["page_text_sha256"],"source_url":page.get("source_url"),
             "query":q,"proof":proof(page,q)} for q in queries]


def restoration_specs():
    # Explicit review decisions, not hidden reference labels for training a model.
    # Tuple: ordinal, support, simple-control sufficient, queries, guards, optional canonical overrides.
    return [
      (7520,"explicit_support",True,["Keep pump as clean as possible."],{"scope":"Viking pumps, cleaning maintenance"},{}),
      (3430,"conditional_support",False,["The pump has no or too low capacity","Wrong direction of rotation","Change direction of rotation to clockwise when viewed from shaft end (the direction of the arrow)"],
        {"cause":"wrong direction of rotation","viewpoint":"shaft end","equipment":"DESMI SA"},{"tail_canonical_zh":"从轴端观察将旋转方向改为顺时针（按箭头方向）"}),
      (3881,"conditional_support",False,["The pump has no or too low capacity","Wrong direction of rotation","Change direction of rotation to clockwise when viewed from shaft end (the direction of the arrow)"],
        {"cause":"wrong direction of rotation","viewpoint":"shaft end","equipment":"DESMI NSL"},{"tail_canonical_zh":"从轴端观察将旋转方向改为顺时针（按箭头方向）"}),
      (3441,"conditional_support",False,["RPM too low","Fit smaller V-belt pulley on pump. Change RPM of electric motor"],
        {"cause":"RPM too low","equipment":"DESMI SA","not_unconditional_speed_change_advice":True},{}),
      (3440,"explicit_support",True,["The pump has no or too low capacity","RPM too low"],
        {"equipment":"DESMI SA","modality":"listed_possible_cause"},{}),
      (6102,"explicit_support",True,["Noisy operation","Air gap not uniform"],
        {"equipment":"ABB low voltage motor, not every pump component","modality":"listed_possible_cause"},{}),
      (6104,"explicit_support",True,["Noisy operation","Rotor unbalance"],
        {"equipment":"ABB low voltage motor","modality":"listed_possible_cause"},{}),
      (7341,"conditional_support",False,["Do not use many fittings. This creates high","friction losses and may cause cavitation,","trapped air and reduced performance."],
        {"equipment":"Cornell pump suction piping","modality":"may_cause","antecedent":"use of many fittings"},{}),
      (7947,"explicit_support",True,["Fit O-ring (12) on stationary seal ring (11) and lubricate"],
        {"equipment":"LKH Prime, O-ring 12, seal assembly Step 4","part_number_preserved":12},{}),
      (7802,"explicit_support",True,["Design suction line with slope down toward the pump to avoid air entrapments"],
        {"equipment":"LKH Prime self-priming installation, not a universal suction-pipe rule"},{}),
      (4845,"conditional_support",False,["Slide the rotating part of the mechanical seal onto the pump shaft.","Put some glycerine or silicon spray on the O-ring to prevent it from rolling on the shaft sleeve."],
        {"phase":"FreFlow mechanical-seal assembly","pronoun_it":"O-ring","alternatives":["glycerine","silicon spray"]},{}),
      (7693,"conditional_support",False,["Starving or cavitating. Increase suction pipe size or reduce length."],
        {"equipment":"Viking pump","fault":"pump not up to capacity","cause_alternatives":["starving","cavitating"],
         "action_alternatives":["increase suction pipe size","reduce suction pipe length"]},{}),
      (7936,"conditional_support",False,["Fit air screw (58) and tighten with a spanner (Torque: see table below)","LKH Prime 10:","LKH Prime 20:","LKH Prime 40:","Torque = 20 Nm (15 lbf-ft)","Torque = 40 Nm (30 lbf-ft)"],
        {"equipment":"LKH Prime, Step 8, air screw 58","parameter_map_Nm":{"LKH Prime 10":20,"LKH Prime 20":20,"LKH Prime 40":40},
         "parameter_binding_basis":"original PDF table visually checked; merged cells not flattened reading order"},{}),
      (7663,"conditional_support",False,["VACUUM GAUGE - SUCTION PORT","High reading would indicate:","Line is too small."],
        {"sensor":"vacuum gauge","location":"suction port","list_branch":"high reading, item d","modality":"possible_indicator"},{}),
      (6540,"conditional_support",False,["A su recepción, verifique inmediatamente si el motor presenta daños externos"],
        {"phase":"upon receipt","equipment":"ABB low voltage motor","same_family_translations_not_independent_facts":True},{}),
    ]


def new_trial(d,candidate,case,task,queries,guards,support,simple,overrides=None,existing_claim=None,extra_proofs=None):
    r=copy.deepcopy(candidate);r.update(overrides or {})
    schema=d["schema"]["relation_registry"][r["relation"]]
    if r["head_type"] not in schema["domain"] or r["tail_type"] not in schema["range"]:
        raise ValueError("No schema relaxation allowed: "+case)
    evidence=prove_queries(d,r["doc_id"],r["pdf_page_number"],queries)+(extra_proofs or [])
    return {"trial_assertion_id":"TA-"+identifier([case,core_tuple(r),guards]),"case_id":case,"task":task,
            "source_record_id":candidate.get("triple_id"),"doc_id":r["doc_id"],"pdf_page_number":r["pdf_page_number"],
            **{k:r[k] for k in ["head_surface","head_canonical_zh","head_type","relation","tail_surface","tail_canonical_zh","tail_type"]},
            "source_family_id":r.get("source_family_id"),"applicability_scope":r.get("applicability_scope"),
            "source_proofs":evidence,"qualifiers":guards,"source_support":support,
            "simple_control_sufficient_for_whole_enhancement":simple,"existing_claim_override":existing_claim,
            "reviewer":REVIEWER,"automatic_contract":"exact_source_addresses+unchanged_type_schema+explicit_guards+AI_semantic_review",
            "full_frozen_publication_pipeline_passed":False,"formal_release_permitted":False,"inferred_edge":False}


def build_A(d):
    old=[r for r in read(OLD/"evaluation_v2/cases.jsonl") if r["task"]=="A"]
    extra=read(OUT/"screen/extra_review_cohort.jsonl")
    ids={r["id"] for r in old}|{"A-"+r["raw_occurrence_id"] for r in extra}|{"A-RAW-06540"}
    caseledger={r["id"]:{"case_id":r["id"],"task":"A","support":r["support"],"domain":r["domain"],
          "action":"retain_rejection" if r["result"].startswith("continue_reject") else
                   "already_covered" if "duplicate" in r["result"] else "unresolved",
          "reason":r["reason"],"simple_sufficient":r["baseline"]=="resolved"} for r in old}
    mapping={m["raw_occurrence_id"]:m for m in read(OLD/"mapping/raw_occurrence_mapping.jsonl")}
    additions=[]
    for n,support,simple,queries,guards,overrides in restoration_specs():
        case=f"A-RAW-{n:05d}";raw={**d["raw"][n-1],**mapping[f"RAW-{n:05d}"]["normalized_source"]}
        additions.append(new_trial(d,raw,case,"A",queries,guards,support,simple,overrides))
        caseledger[case]={"case_id":case,"task":"A","support":support,"action":"trial_restore",
                          "simple_sufficient":simple,"reason":"source-addressed reviewed restoration with preserved applicability/guards"}
    # This is additional evidence for a semantically aligned CURRENT claim, not a new Claim.
    case="A-RAW-03392";r=d["raw"][3391]
    additions.append(new_trial(d,r,case,"A",["When the pump has been assembled, check that the shaft rotates freely."],
        {"phase":"after pump assembly","equipment":"DESMI SA"},"conditional_support",False,
        existing_claim="EXC-a3d68208696d47c416efaf3c"))
    caseledger[case]={"case_id":case,"task":"A","support":"conditional_support","action":"new_evidence_existing_claim",
                      "simple_sufficient":False,"reason":"matched free-rotation shaft check; retains assembly guard and SA source"}
    special={
      "A-RAW-00670":("contradiction","retain_rejection","A definition of equipment possessing self-checking features is not equipment inspected_by a method. The cue-only gate accepts it incorrectly."),
      "A-RAW-05980":("insufficient_evidence","unresolved","Inspection method is source-supported, but bearing condition is not a physical Component. Endpoint/type repair has not been independently established."),
      "A-RAW-00042":("explicit_support","already_covered","Current condition-monitoring claims cover this broad method; cannot count rewording as a new fact."),
    }
    for case,(support,action,reason) in special.items():
        caseledger[case]={"case_id":case,"task":"A","support":support,"action":action,"reason":reason,"simple_sufficient":False}
    # One retained initial candidate absent from the main fixed cohort: literal parent/value binding.
    flush=next(r for r in d["raw"] if r["triple_id"]=="MPT-4b9650a3a9e1015987d0")
    case="A-FLUSH-70C";ids.add(case)
    additions.append(new_trial(d,flush,case,"A",["Seal types","External single or double mechanical seal","Max. temperature flush medium 70oC"],
       {"equipment":"LKH Prime shaft-seal specification","limit_type":"maximum flush-medium temperature","value_C":70},
       "conditional_support",False))
    caseledger[case]={"case_id":case,"task":"A","support":"conditional_support","action":"trial_restore","simple_sufficient":False,
                      "reason":"Candidate already existed; source seal-type/value binding restored. Not a generation omission."}
    if set(caseledger)!=ids:raise ValueError("A cohort ledger does not close: "+str(ids^set(caseledger)))
    return additions,list(caseledger.values())


def build_E(d):
    table=read(OUT/"discovery/source_only_table_review.jsonl")
    joins=read(OUT/"discovery/reference_join_review.jsonl")
    sourceframes=read(OLD/"evaluation_v2/source_propositions.jsonl")
    ledger=[];additions=[];frames=[]
    for r in table:
        doc,pg=r["doc_id"],r["page"]
        if doc=="MP001":
            support,action,reason="contradiction","reject_false_cause","Element-source column describes material origin, not source_component causes excessive wear; additive is a confounder."
        elif doc=="MP005":
            support,action,reason="explicit_support","already_covered","Leading list number caused false exact-match novelty; native cause is already generated/current in the same manual family."
        elif doc=="MP019":
            support,action,reason="explicit_support","already_covered","Italian row matches current English ABB starting-load/terminal-voltage cause; not a new fact or independent family."
        elif doc=="MP015":
            support,action,reason="conditional_support","resolved_by_reference_join","Numeric IDs are not Cause entities; explicit Table 5 lookup produces actual possible-cause associations, separately counted below."
        elif "specific gravity" in r["head_surface"]:
            support,action,reason="conditional_support","unresolved_semantic_novelty","Source supports driver overload, but current high-density to motor-overload fact overlaps. Driver versus motor scope cannot be silently merged."
            frames.append({"id":r["id"],"task":"E","kind":"source_relation_pending_semantic_novelty","frame":r,
                "source_proofs":prove_queries(d,doc,pg,[r["head_surface"],r["tail_surface"]]),"source_support":support,
                "new_claim_counted":False,"reviewer":REVIEWER})
        else:
            support,action,reason="conditional_support","trial_new_relation","Explicit Cornell cause row absent from bounded source-form and current semantic review; preserve disjunction and driver scope."
            raw={"doc_id":doc,"pdf_page_number":pg,"head_surface":r["head_surface"],"head_canonical_zh":"泵越曲线运行或系统不当",
                "head_type":"Cause","relation":"causes","tail_surface":r["tail_surface"],"tail_canonical_zh":"驱动机过载",
                "tail_type":"FaultMode","source_family_id":"INDICOR__CORNELL_PUMP","applicability_scope":d["pages"][doc,pg].get("applicability_scope")}
            additions.append(new_trial(d,raw,r["id"],"E",[r["head_surface"],r["tail_surface"]],
                {"equipment":"Cornell pump driver","modality":"listed_possible_cause","cause_is_disjunctive":True},support,True))
        ledger.append({"case_id":r["id"],"task":"E","subexperiment":"source_only_table","support":support,"action":action,"reason":reason,
                       "simple_sufficient":action in {"already_covered","resolved_by_reference_join","trial_new_relation"}})
    translations={4:"有效汽蚀余量过低",7:"吸入管路泄漏",9:"液体析出气体或空气",14:"管路堵塞"}
    for r in joins:
        cross=prove_queries(d,"MP015",31,[r["tail_surface"],r["proof_cells"][1]["text"],"Possible causes, see Table 5."])
        cross+=prove_queries(d,"MP015",32,[r["head_surface"]])
        number=r["source_reference_number"]
        if norm(r["tail_surface"])=="irregular delivery":
            raw={"doc_id":"MP015","pdf_page_number":31,"head_surface":r["head_surface"],"head_canonical_zh":translations[number],
                 "head_type":"Cause","relation":"causes","tail_surface":"Irregular delivery","tail_canonical_zh":"泵流量不稳定",
                 "tail_type":"FaultMode","source_family_id":"SPX_FLOW__JOHNSON_PUMP","applicability_scope":"SPX Johnson FreFlow Table 4/5, possible causes, not universal causal law"}
            # The leakage relation already exists: add one provenance Assertion only.
            current=next(x for x in d["graph"]["source_records"] if x["expanded_assertion_id"]=="EXA-da7727814d509a8dff26cd82") if number==7 else None
            additions.append(new_trial(d,raw,r["id"],"E",[],{"equipment":"SPX FreFlow","cause_index":number,
                "modality":"possible_cause","explicit_reference":"Table 4 -> Table 5"},"conditional_support",True,
                existing_claim=current["expanded_claim_id"] if current else None,extra_proofs=cross))
            action="new_evidence_existing_claim" if current else "trial_new_relation"
            reason="Explicit numbered cause lookup; current leakage fact reused, other three bounded source-qualified cores retained."
        else:
            # Do NOT inflate new-claim count by OR-vs-AND target rewording.
            action="source_bound_pending_semantic_novelty"
            reason="Reference lookup succeeds, but composite 'vibrates OR is noisy' overlaps current individual/AND targets. No unsupported split or automatic new-Claim credit."
            frames.append({"id":r["id"],"task":"E","kind":"composite_diagnostic_target","frame":r,"source_proofs":cross,
                           "source_support":"conditional_support","new_claim_counted":False,"reviewer":REVIEWER})
        ledger.append({"case_id":r["id"],"task":"E","subexperiment":"explicit_reference_join","support":"conditional_support",
                       "action":action,"reason":reason,"simple_sufficient":action!="source_bound_pending_semantic_novelty"})
    for r in sourceframes:
        if r["id"] in {"SP09","SP10"}:
            action="already_covered" if r["id"]=="SP09" else "overlaps_A_restoration"
        else:
            action="trial_source_frame"
            frames.append({"id":r["id"],"task":"E","kind":"procedure_material_or_method_selection",
                "frame":r["frame"],"source_proofs":prove_queries(d,r["doc_id"],r["page"],r["queries"]),
                "source_support":r["support"],"raw_frame_found":r["raw_frame_found"],"base_frame_found":r["current_frame_found"],
                "new_claim_counted":False,"reason":"Auxiliary frame/properties, not invented schema relations or direct causal links.","reviewer":REVIEWER})
        ledger.append({"case_id":r["id"],"task":"E","subexperiment":"prior_source_proposition_compilation",
                       "support":r["support"],"action":action,"reason":r["reason"],"simple_sufficient":r["id"]=="SP09"})
    return additions,frames,ledger


def auxiliary_changes(d):
    source={r["expanded_assertion_id"]:r for r in d["graph"]["source_records"]}
    specs=[
      ("EXA-60591b991e3b8f6a16a26910",{"fault_context":"Hot bearings"},["Hot bearings","Excessive belt pull","Decrease belt tension."]),
      ("EXA-5672baf4a29e34a80aa14b37",{"modality":"required"},["is to be fitted"]),
      ("EXA-319ea694a2f79b1fb4b0fb5f",{"trigger":"when the installation is secured","location":"between pump base plate and foundation"},["Use shims between pump base plate and foundation to avoid tension in the pump foot when the installation is secured."]),
      ("EXA-ce5e84b1fe933576f22c4d3b",{"modality":"possible_cause","application":"water-lubricated stuffing box"},["For Pumps Equipped with Water Lubrication of Stuffing Box","Improper seal water conditions can cause"]),
      ("EXA-a16cf539e1d1c2570004426a",{"modality":"recommended","phase":"after installing thrust bearing drain pipe"},["After the drain pipe is installed, a sealing material such as caulk should be applied around the pipe where it enters into the bearing housing"]),
      ("EXA-b189096e5da927bd26b71c7d",{"action_operator":"OR","action_options":["straighten","replace"],"part_operator":"OR","part_options":["bent shaft","rotor tooth"]},["May have a bent shaft or rotor tooth. Straighten or replace."]),
    ]
    updates=[]
    for sid,fields,queries in specs:
        r=source[sid]
        updates.append({"task":"B","assertion_id":sid,"claim_id":r["expanded_claim_id"],"operation":"add_namespaced_qualifier_overlay",
                        "fields":fields,"source_proofs":prove_queries(d,r["doc_id"],r["pdf_page_number"],queries),
                        "reviewer":REVIEWER,"new_claim_counted":False})
    prior=read(OLD/"evaluation_v2/cases.jsonl")
    aliases=[]
    for row in prior:
        if row["task"]=="C" and row["result"] in ["cleanable_alias","cleanable_alias_with_scope_preservation"]:
            c=row["candidate"]
            aliases.append({"task":"C","case_id":row["id"],"entity_ids":c["entity_ids"],"operation":"concept_alias_view_not_physical_entity_merge",
                            "source_records":c["source_records"],"scope_preservation_required":True,"new_claim_counted":False,"reviewer":REVIEWER})
    quarantine=[]
    seen=set()
    for row in prior:
        if row["task"] not in ["D","D_supplement"] or row["id"] in seen:continue
        seen.add(row["id"])
        if row["result"].startswith("clear_"):
            r=row["candidate"]
            quarantine.append({"task":"D","case_id":row["id"],"assertion_id":r["assertion_id"],"claim_id":r["claim_id"],
                "operation":"quarantine_in_sandbox_only_not_delete_official_record","reason":row["reason"],
                "category":row["result"],"source":r["source"],"original_source_context":row["original_source_context"],
                "reviewer":REVIEWER,"not_automatic_causal_negation_flip":True})
    return updates,aliases,quarantine


def compile_sandbox(d,additions,updates,aliases,quarantine):
    entities=copy.deepcopy(d["graph"]["entities"]);claims=copy.deepcopy(d["graph"]["claims"])
    assertions=copy.deepcopy(d["graph"]["evidence_assertions"])
    entity_index={(r["entity_type"],norm(r["label_zh"])):r["entity_id"] for r in entities}
    claim_index={(r["head_entity_id"],r["relation"],r["tail_entity_id"]):r["claim_id"] for r in claims}
    base_claims={r["claim_id"] for r in claims}
    for r in additions:
        existing = next((c for c in claims if c["claim_id"]==r["existing_claim_override"]), None)
        if r["existing_claim_override"] and not existing:
            raise ValueError("Existing Claim override not real")
        pair=[]
        for side in ["head","tail"]:
            if existing:
                pair.append(existing[side+"_entity_id"])
                continue
            key=(r[side+"_type"],norm(r[side+"_canonical_zh"]))
            if key not in entity_index:
                eid="TE-"+identifier(key);entity_index[key]=eid
                entities.append({"entity_id":eid,"label_zh":r[side+"_canonical_zh"],"entity_type":key[0],"layer":"trial_only"})
            pair.append(entity_index[key])
        key=(pair[0],r["relation"],pair[1])
        cid=r["existing_claim_override"] or claim_index.get(key)
        if not cid:
            cid="TC-"+identifier(key);claim_index[key]=cid
            claims.append({"claim_id":cid,"head_entity_id":pair[0],"relation":r["relation"],"tail_entity_id":pair[1],
                           "interpretation":"Qualified trial claim; assertion guards are mandatory, not unconditional truth.","layer":"trial_only"})
        if cid not in {c["claim_id"] for c in claims}:raise ValueError("Existing Claim override not real")
        r["sandbox_claim_id"]=cid;r["new_claim_relative_to_base"]=cid not in base_claims
        assertions.append({"assertion_id":r["trial_assertion_id"],"claim_id":cid,"doc_id":r["doc_id"],
            "pdf_page_number":r["pdf_page_number"],"qualifiers":r["qualifiers"],"source_proofs":r["source_proofs"],
            "reviewer":REVIEWER,"layer":"source_supported_AI_reviewed_trial_not_frozen_release","case_id":r["case_id"]})
    blocked={r["assertion_id"] for r in quarantine}
    scoped=[r for r in assertions if r["assertion_id"] not in blocked]
    active_claims={r["claim_id"] for r in scoped}
    summary={"before":{"assertions":len(d["graph"]["evidence_assertions"]),"claims":len(base_claims),"entities":len(d["graph"]["entities"])},
        "additive_trial_view":{"assertions":len(assertions),"claims":len(claims),"entities":len(entities)},
        "scope_filtered_trial_view":{"assertions":len(scoped),"active_claims":len(active_claims)},
        "delta":{"source_checked_trial_assertions":len(additions),"new_claims_deduplicated":len(claims)-len(base_claims),
                 "new_entities":len(entities)-len(d["graph"]["entities"]),"existing_assertions_with_qualifier_overlays":len(updates),
                 "concept_alias_groups":len(aliases),"sandbox_quarantined_original_assertions":len(quarantine)},
        "per_task_additions":{},"no_official_graph_or_RP2_RP3_writes":True,"not_a_frozen_publication_pipeline_release":True}
    for task in ["A","E"]:
        rows=[r for r in additions if r["task"]==task]
        summary["per_task_additions"][task]={"trial_assertions":len(rows),"distinct_new_claims":len({r["sandbox_claim_id"] for r in rows if r["new_claim_relative_to_base"]}),
            "new_evidence_existing_base_claims":sum(not r["new_claim_relative_to_base"] for r in rows),
            "simple_control_whole_enhancement_sufficient":sum(r["simple_control_sufficient_for_whole_enhancement"] for r in rows),
            "needs_reviewed_binding_or_alignment":sum(not r["simple_control_sufficient_for_whole_enhancement"] for r in rows)}
    save(SANDBOX/"entities.jsonl",entities);save(SANDBOX/"claims.jsonl",claims)
    save(SANDBOX/"evidence_assertions_additive.jsonl",assertions)
    save(SANDBOX/"evidence_assertions_scope_filtered.jsonl",scoped)
    save(SANDBOX/"delta_assertions.jsonl",additions);save(SANDBOX/"qualifier_overlays.jsonl",updates)
    save(SANDBOX/"concept_alias_views.jsonl",aliases);save(SANDBOX/"quarantine_overlay.jsonl",quarantine)
    save(SANDBOX/"before_after.json",summary)
    return summary


def main():
    global LOCATE
    sys.stdout.reconfigure(encoding="utf-8");LOCATE=native_locator();d=load()
    a,aledger=build_A(d);e,frames,eledger=build_E(d)
    updates,aliases,quarantine=auxiliary_changes(d)
    summary=compile_sandbox(d,a+e,updates,aliases,quarantine)
    save(OUT/"review/A_decisions.jsonl",aledger);save(OUT/"review/E_decisions.jsonl",eledger)
    save(SANDBOX/"auxiliary_source_frames.jsonl",frames)
    save(OUT/"review/protocol.json",{"reviewer":REVIEWER,"blind":False,"human_expert":False,"independent_model":False,
        "generation_and_review_information_independence":False,"source_locator_independent_of_candidate_quote":True,
        "independent_original_evidence_means_original_document_not_independent_statistical_corrobation":True,
        "semantic_source_support_not_real_precision":True,"manuals_only_build_15":True,
        "all_other_join_pairs_retained_as_candidates_not_released_facts":True})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('A',len(aledger),Counter(r['action'] for r in aledger),'E',len(eledger),Counter(r['action'] for r in eledger),'frames',len(frames))


if __name__=="__main__":main()
