"""Emit bounded diagnostic proposals from controls, without graph edits."""
import re
import json
from pathlib import Path
from inputs import TASK, REV, SCHEMA, Inputs, norm, save, digest
from run_baselines import OUT, read


def cell_body(field):
    value=norm(field["text"]);header=norm(field.get("column_name"))
    return value[len(header):].strip() if header and value.startswith(header+" ") else value


def policy(task,item,control,schema=None):
    result={"automatic_graph_write":False,"full_semantic_correctness_claimed":False}
    if task.startswith("D"):
        flags=item["flags"];ref=item["source"]
        tail=ref.get("tail_canonical_zh","")+" "+ref.get("tail_surface","")
        if "prohibition_as_operating_condition" in flags and re.search(r"不得|禁止|切勿|do not|never|must not",tail,re.I):
            result.update(action="retain_literal_negation_no_reversal",safe_use_requires_separate_structure=True)
        elif "normative_as_positive_cause" in flags or "prohibition_as_operating_condition" in flags:
            result.update(action="quarantine_positive_reading",do_not_infer_opposite_physical_cause=True)
        elif "literal_direction_probe" in flags:
            fields=[field for row in control["source_controls"][0]["native_table_context"] for field in row["fields"]]
            head=[f for f in fields if cell_body(f)==norm(ref["head_surface"])]
            tail_fields=[f for f in fields if cell_body(f)==norm(ref["tail_surface"])]
            cause=any(f["column_role"]=="cause_or_mechanism" for f in head)
            symptom=any(f["column_role"]=="fault_or_symptom" for f in tail_fields)
            result.update(action="retain_native_role_direction" if cause and symptom else "defer_direction",native_head_cause=cause,native_tail_symptom=symptom)
        elif "action_as_component_probe" in flags:
            result.update(action="defer_event_component_referent")
        elif "equipment_scope" in flags:
            text=ref["head_surface"]+" "+ref["tail_surface"]
            explicit=re.search(r"finished propellers|propeller hub|propeller entanglement|propulsion motors?|crankshaft|compressor wheels?",text,re.I)
            result.update(action="quarantine_explicit_other_equipment" if explicit else "defer_transferability",scope_match=explicit.group() if explicit else None)
    elif task=="C":
        stratum=item["stratum"]
        if stratum=="typed_surface_alias":
            ref=item["source_records"][0]
            event_component=any("operation" in ref.get(side+"_surface","").casefold() and ref.get(side+"_type")=="Component" for side in ["head","tail"])
            result.update(action="defer_event_component_referent" if event_component else "propose_concept_alias_preserve_assertions",not_physical_instance_identity=True)
        elif stratum=="same_label_different_types":
            result.update(action="block_unconditional_instance_merge",conceptual_role_alignment_not_decided=True)
        elif stratum=="multi_evidence_claim":
            result.update(action="retain_assertions_in_claim_family_deduplicate_source_family",independent_supports_added=0)
    elif task=="A" or task=="E":
        covered=item.get("graph_core_matches") or []
        baseline=item.get("baseline",{})
        result.update(action="do_not_add_duplicate_core" if covered else "defer_semantics_and_quality_contract",
            covered_assertion_ids=covered,address_schema_screen=baseline.get("address_and_schema_screen_pass"),
            restore_as_qualified_fact=False)
        source=item.get("proposed_source") or item.get("source")
        if source and schema:
            rule=schema["relation_registry"].get(source["relation"],{})
            valid=source["head_type"] in rule.get("domain",[]) and source["tail_type"] in rule.get("range",[])
            result["schema_type_pass"]=valid
            if not valid:result["action"]="block_unchanged_schema"
    if task.startswith("B"):
        local=[]
        for source in control["source_controls"]:
            clauses=source["stronger_clause_proposals"]
            candidates=[]
            for clause in clauses:
                cue=clause["cue"].casefold()
                modal="possible" if cue in {"may","might","could","can"} else "recommended" if cue=="should" else "required" if cue in {"must","shall","is to be","are to be"} else None
                if modal:candidates.append({"candidate_modality":modal,"cue":clause["cue"],"source_text":clause["original_text"],"needs_scope_check":True})
            local.append(dict(modality_candidates=candidates,condition_clause_candidates=[c for c in clauses if c["cue"].casefold() in {"if","when","unless","before","after"}],
                temporal_clause_candidates=[c for c in clauses if c["cue"].casefold()=="then"],
                existing_role_fields_readback=source["structured_condition_readback"],native_row_fields=source["native_table_context"],
                endpoint_alternative_groups=source["endpoint_alternatives"],operator_argument_graph_completed=False))
        result.update(action="bounded_field_proposals_and_readback",local_fields=local)
    return result


def main():
    inputs=Inputs();schema=inputs.rows(SCHEMA)
    controls={(r["task"],r["opportunity_id"]):r for r in read(OUT/"controls/sample_predictions_v2.jsonl")}
    rows=[]
    for task in [*"ABCDE","B_supplement","D_supplement"]:
        for item in read(OUT/f"review/{task}_sample.jsonl" if len(task)==1 else OUT/f"review/{task}.jsonl"):
            rows.append(dict(task=task,opportunity_id=item["opportunity_id"],proposal=policy(task,item,controls[task,item["opportunity_id"]],schema)))
    save(OUT/"controls/bounded_action_proposals_v2.jsonl",rows)
    save(OUT/"controls/policy_manifest_v2.json",dict(input_git_commit=REV,program_sha256=digest(Path(__file__).read_bytes()),input_sha256=inputs.hashes,
        source_control_sha256=digest((OUT/"controls/sample_predictions_v2.jsonl").read_bytes()),proposals=len(rows),graph_writes=0,
        output_is_diagnostic_not_a_new_research_algorithm=True))
    print(json.dumps(dict(proposals=len(rows),formal_writes=0),indent=2))


if __name__=="__main__":main()
