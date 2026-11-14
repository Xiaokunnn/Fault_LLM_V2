"""Close evidence/novelty ledgers and summarize the executed trial, no training."""
from collections import Counter,defaultdict
import copy
import json
import re
import sys

from inputs import TASK,load,save,norm,record_ids,core_tuple,identifier
from selection_screen import OUT,OLD,read
import selection_overlay as overlay
from selection_overlay import SANDBOX
from selection_discovery import tuples


def summary_rows(rows):
    return {"reviewed_task_items":len(rows),"distinct_case_ids":len({r["case_id"] for r in rows}),
            "support_status_counts":dict(Counter(r["support"] for r in rows)),
            "action_counts":dict(Counter(r["action"] for r in rows)),
            "not_population_prevalence_or_true_precision":True}


def coverage(rows,head=None,tail=None,rel=None):
    return len({core_tuple(r) for r in rows if (head is None or norm(r.get("head_canonical_zh"))==norm(head))
          and (tail is None or norm(r.get("tail_canonical_zh"))==norm(tail)) and (rel is None or r["relation"]==rel)})


def main():
    sys.stdout.reconfigure(encoding="utf-8");overlay.LOCATE=overlay.native_locator();d=load()
    a=read(OUT/"review/A_decisions.jsonl");e=read(OUT/"review/E_decisions.jsonl")
    prior=read(OLD/"evaluation_v2/cases.jsonl")
    prior_e=[]
    for r in prior:
        if r["task"]!="E":continue
        category=r["result"]
        action=("overlaps_A_restoration" if category=="qualified_recovery_same_family_variants" else
                "retain_rejection" if category=="reject_definition_as_mitigation" else
                "already_covered" if category=="already_generated_and_published_control" else
                "trial_source_frame_parent" if category in ["component_material_attribute_association_probe","source_supported_missing_procedure_probes","source_supported_analysis_association_probe"] else "unresolved")
        prior_e.append({"case_id":r["id"],"task":"E","subexperiment":"reused_prior_primary_parent_cases","support":r["support"],
                        "action":action,"reason":r["reason"],"overlap_with_new_fine_grained_cases":True})
    save(OUT/"review/E_prior_parent_decisions.jsonl",prior_e)
    # Review source lookup results for ALL six topology candidates.
    topology=read(OUT/"discovery/topology_only_potentials.jsonl")
    topo=[]
    explicit={
      "EG-51e39d18cee07cfeea23ea62":("MP005",58,"Too high density of the fluid pumped could lead to motor overload, which could damage the motor."),
      "EG-5129c11a5545b14df56ed50a":("MP005",55,"Start-up against open discharge line could lead to motor overload, which could damage the motor."),
      "EG-3af86d617fbbe47aa7e76c9a":("MP007",9,"In case that ambient temperature exceeds +40°C or the motor is installed above 1,000m altitude, the motor rated output power (P2) will decrease due to the poor motor cooling effect caused by low air density, as shown in Chart 1."),
    }
    for r in topology:
        item={"case_id":r["id"],"proposed_pair":[r["head"],"causes",r["tail"]],"trusted_direct_edge_added":False,
              "premise_assertion_ids":[p["assertion_ids"] for p in r["paths"]],"reviewer":overlay.REVIEWER}
        if r["id"] in explicit:
            doc,pg,q=explicit[r["id"]]
            item.update(verdict="source_supported_mediated_chain_not_new_direct_relation",source_proofs=overlay.prove_queries(d,doc,pg,[q]),
                        independent_new_evidence=False,reason="Original source itself states a qualified mediated chain. It is not a transitivity license or independent new support.")
        else:
            item.update(verdict="insufficient_evidence_for_direct_relation",source_proofs=[],independent_new_evidence=False,
                        reason="No endpoint co-occurrence under disclosed source forms; chained premises may mix equipment scopes. Search incompleteness is not proof of falsity.")
        topo.append(item)
    save(OUT/"review/topology_decisions.jsonl",topo)
    # Full original records accompany every A trial, not just paraphrased evidence.
    mapping={r["raw_occurrence_id"]:r for r in read(OLD/"mapping/raw_occurrence_mapping.jsonl")}
    provenance=[]
    for r in read(SANDBOX/"delta_assertions.jsonl"):
        if r["task"]!="A":continue
        if r["case_id"].startswith("A-RAW-"):
            oid=r["case_id"][2:];raw=d["raw"][int(oid.split("-")[1])-1];m=mapping[oid]
        else:
            raw=next(x for x in d["raw"] if x["triple_id"]=="MPT-4b9650a3a9e1015987d0")
            m=next(x for x in mapping.values() if x["raw_triple_id"]==raw["triple_id"])
        ids=set(m["all_linked_record_ids"])
        refs=[x for x in d["normalized"] if ids & set(record_ids(x))]
        provenance.append({"trial_assertion_id":r["trial_assertion_id"],"case_id":r["case_id"],
                           "original_raw_record_unchanged":raw,"normalized_candidate_records_unchanged":refs,
                           "normalization_mapping_unchanged":m})
    save(SANDBOX/"original_candidate_provenance.jsonl",provenance)
    # An actual number-prefix normalization ablation on discovered source pairs.
    discovered=read(OUT/"discovery/native_table_pairs.jsonl")
    def clean(s):return re.sub(r"^\s*\d+[.)]\s*","",norm(s))
    rawkeys={(clean(h),r,clean(t)) for h,r,t in tuples(d["raw"]+d["normalized"])}
    basekeys={(clean(h),r,clean(t)) for h,r,t in tuples(d["graph"]["source_records"])}
    ablation=[]
    for r in discovered:
        key=(clean(r["head_surface"]),r["relation"],clean(r["tail_surface"]))
        ablation.append({"case_id":r["id"],"raw_covered_before":r["raw_exact_source_pair"],"base_covered_before":r["existing_exact_source_pair"],
                         "raw_covered_after_list_prefix_normalization":key in rawkeys,"base_covered_after_list_prefix_normalization":key in basekeys})
    save(OUT/"evaluation/list_prefix_control.jsonl",ablation)
    additions=read(SANDBOX/"delta_assertions.jsonl");base=d["graph"]["source_records"]
    measures=[]
    for label,kw in [("流量不稳定的来源支持原因数",dict(tail="泵流量不稳定",rel="causes")),
                     ("运行噪声大的来源支持原因数",dict(tail="运行噪声大",rel="causes")),
                     ("泵无流量或流量过低的维护措施数",dict(head="泵无流量或流量过低",rel="mitigated_by"))]:
        measures.append({"label":label,"before_distinct_typed_cores":coverage(base,**kw),
                         "after_additive_trial_distinct_typed_cores":coverage(base+additions,**kw),
                         "mandatory_assertion_scope":True,"not_diagnostic_accuracy_or_full_relation_recall":True})
    save(OUT/"evaluation/diagnostic_knowledge_coverage.json",measures)
    # Preserve prior auxiliary task denominators and verdict meaning.
    taskstats={"A":summary_rows(a),"E_new_fine_grained":summary_rows(e),"E_reused_parent":summary_rows(prior_e),
               "E_all_task_items":summary_rows(e+prior_e)}
    for task in ["B","C","D"]:
        rows=[];used=set()
        for r in prior:
            if r["task"].split("_")[0]!=task or r["id"] in used:continue
            used.add(r["id"])
            rows.append({"case_id":r["id"],"support":r["support"],"action":r["result"]})
        taskstats[task]=summary_rows(rows)
    save(OUT/"evaluation/task_comparison.json",taskstats)
    # Concrete high-similarity WRONG-neighbor examples; do not call an accuracy estimate.
    matches={r["raw_occurrence_id"]:r for r in read(OUT/"matching/candidate_to_base_top3.jsonl")}
    confusing=[]
    for oid in ["RAW-03430","RAW-03441","RAW-03440"]:
        confusing.append({"raw_occurrence_id":oid,"top3":matches[oid]["top_matches"],
                          "failure":"Same merged evidence block dominates whole-record similarity; endpoint predicate/argument differs.",
                          "automatic_merge_allowed":False})
    save(OUT/"evaluation/context_similarity_hard_negatives.jsonl",confusing)
    # Seal quantitative evidence before final written method recommendation.
    snapshot={"A":taskstats["A"],"E":taskstats["E_all_task_items"],
        "sandbox":read(SANDBOX/"before_after.json"),"source_discovery":read(OUT/"discovery/summary.json"),
        "explicit_reference_join":read(OUT/"discovery/reference_join_summary.json"),"coverage":measures,
        "simple_number_prefix_control":{"pairs":len(ablation),"new_initial_matches":sum(not r["raw_covered_before"] and r["raw_covered_after_list_prefix_normalization"] for r in ablation),
             "new_base_matches":sum(not r["base_covered_before"] and r["base_covered_after_list_prefix_normalization"] for r in ablation)},
        "auxiliary_frames":{"new_source_procedure_material_method_frames":8,"source_bound_novelty_not_decided":14,
                            "mediated_chains_consolidated_not_new_direct_facts":3},
        "topology_review":dict(Counter(r["verdict"] for r in topo)),"no_human_or_independent_model_reference":True,
        "known_relation_masked_recovery_experiment_run":False,"no_masked_recovery_generalization_claim":True,
        "all_new_claim_counts_are_reviewed_trial_scope_not_full_semantic_absence_proof":True}
    save(OUT/"evaluation/quantitative_snapshot.json",snapshot)
    print(json.dumps(snapshot,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
