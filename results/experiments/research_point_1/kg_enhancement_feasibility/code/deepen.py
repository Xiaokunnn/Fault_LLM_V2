"""Additional diagnostic probes and counterfactual sensitivity, never KG writes."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
from investigate import Data,TASK,ROOT,REV,read,save,sha,norm,morphological,concept,cid,node_id,pointer

OUT=TASK/"runs/20261113_v1"
SCOPE_PATTERN=r"crankshaft|propeller|piston|rudder|connecting rod|cylinder liner|compressor"

def component_stats(nodes,edge_pairs):
    adj=defaultdict(set)
    for h,t in edge_pairs:adj[h].add(t);adj[t].add(h)
    unseen=set(nodes);sizes=[]
    while unseen:
        first=next(iter(unseen));part={first};todo=[first]
        while todo:
            for y in adj[todo.pop()]:
                if y not in part:part.add(y);todo.append(y)
        unseen-=part;sizes.append(len(part))
    return dict(nodes=len(nodes),weak_components=len(sizes),largest_component=max(sizes,default=0),degree_one=sum(len(adj[x])==1 for x in nodes))

def alias_sensitivity(g,candidates):
    parent={e["entity_id"]:e["entity_id"] for e in g["entities"]}
    def find(x):
        while parent[x]!=x:x=parent[x]
        return x
    for row in candidates:
        ids=row["entity_ids"]
        for x in ids[1:]:parent[find(x)]=find(ids[0])
    original={(c["head_entity_id"],c["relation"],c["tail_entity_id"]) for c in g["claims"]}
    projected={(find(h),rel,find(t)) for h,rel,t in original}
    return dict(before={**component_stats(set(parent),[(h,t) for h,rel,t in original]),"relations":len(original)},
                hypothetical_exact_surface_alias_merge={**component_stats({find(x) for x in parent},[(h,t) for h,rel,t in projected]),"relations":len(projected)},
                candidate_groups=len(candidates),new_edges_inferred=0,graph_written=False,
                interpretation="What-if sensitivity only; all candidates merged as an upper-bound lexical test, not semantic confirmation or a proposed enhancement algorithm")

def main():
    d=Data();scope=[];negated=[];address=[];formats=[];discuss=[]
    for layer,g in d.graphs.items():
        for r in g["source_records"]:
            text=r["head_surface"]+" "+r["tail_surface"]
            if r["doc_id"]=="MP003" and re.search(SCOPE_PATTERN,text,re.I):scope.append(dict(layer=layer,**pointer(r),status="insufficient_evidence",reason="Document explicitly limits pump/piping scope; nonpump lexical target requires context review, not automatic deletion"))
            if r["relation"] in {"causes","increases_risk_of"} and re.search(r"\b(?:is|are|was|were)?\s*not\s+to\s+(?:cause|result)|\b(?:shall|must|should|does|do|can)\s+not\s+(?:cause|result)",r["evidence_text"],re.I):
                negated.append(dict(layer=layer,**pointer(r),status="insufficient_evidence",reason="Negated/normative causal wording with a positive graph relation; source clause ownership still needs review"))
        for e in g["entities"]:
            label=e.get("canonical_label_zh",e.get("label_zh",""))
            if len(label)>40:discuss.append(dict(layer=layer,entity_id=e["entity_id"],entity_type=e["entity_type"],label=label,characters=len(label),is_error_established=False))
        rs=read(OUT/"integrity/record_provenance.jsonl");rs=[r for r in rs if r["layer"]==layer]
        address.append(dict(layer=layer,E2_records=sum(r["address_check"]["evidence_level"]=="E2" for r in rs),
            all_provided_cells_exact_records=sum(r["address_check"]["nested_unit_count"]>0 and r["address_check"]["nested_unit_count"]==r["address_check"]["nested_units_exact"] for r in rs),
            all_provided_bboxes_exact_records=sum(r["address_check"]["nested_unit_count"]>0 and r["address_check"]["nested_unit_count"]==r["address_check"]["nested_bbox_exact"] for r in rs),
            native_witness_records=sum(r["address_check"]["native_witness_count"]>0 for r in rs),
            all_provided_native_witnesses_exact_records=sum(r["address_check"]["native_witness_count"]>0 and r["address_check"]["native_witness_count"]==r["address_check"]["native_witness_exact"] for r in rs)))
        evidence=g["evidence_assertions"];fields=["evidence_start","evidence_end","evidence_units","source_witnesses","conditions_source","modality","polarity","applicability_scope"]
        formats.append(dict(layer=layer,full_source_presence={f:sum(bool(r.get(f)) or r.get(f)==0 for r in g["source_records"]) for f in fields},
            exported_evidence_presence={f:sum(bool(r.get(f)) or r.get(f)==0 for r in evidence) for f in fields},
            full_source_retained=True,projection_omission_is_not_archive_deletion=True))
    aliases=read(OUT/"integrity/entity_alignment_candidates.jsonl")
    sensitivity={layer:alias_sensitivity(g,[r for r in aliases if r["layer"]==layer and r["kind"]=="source_surface_alignment_candidate"]) for layer,g in d.graphs.items()}
    gaps=read(OUT/"integrity/fault_role_gaps.jsonl");bylabel={(r["layer"],norm(r["label"])):r for r in gaps}
    comparisons=[]
    for r in gaps:
        if not r["structural_role_gap"]:continue
        others={layer:{k:bylabel[layer,norm(r["label"])][k] for k in ["incoming_cause","outgoing_maintenance","outgoing_inspection"]} for layer in d.graphs if layer!=r["layer"] and (layer,norm(r["label"])) in bylabel}
        comparisons.append(dict(**r,other_layer_exact_typed_label_roles=others,
            missing_role_exists_in_other_layer=any((not r["incoming_cause"] and x["incoming_cause"]) or (not r["outgoing_maintenance"] and x["outgoing_maintenance"]) for x in others.values()),
            cannot_infer_source_absence=True))
    summary=dict(scope_lexical_candidates={k:sum(r["layer"]==k for r in scope) for k in d.graphs},
        negated_or_normative_causal_candidates={k:sum(r["layer"]==k for r in negated) for k in d.graphs},
        long_entity_label_candidates_over40={k:sum(r["layer"]==k for r in discuss) for k in d.graphs},
        structural_gap_with_counterpart_role_elsewhere={k:sum(r["layer"]==k and r["missing_role_exists_in_other_layer"] for r in comparisons) for k in d.graphs},
        schema_properties=list(d.schema["properties"]),schema_allows_extra_properties=d.schema.get("additionalProperties"),
        English_cue_scan_does_not_cover_all_languages=True)
    for name,value in [("scope_candidates.jsonl",scope),("negated_causal_candidates.jsonl",negated),("long_entity_labels.jsonl",discuss),
                       ("address_completeness.jsonl",address),("export_projection.jsonl",formats),("role_gap_cross_layer.jsonl",comparisons),
                       ("alias_sensitivity.json",sensitivity),("summary.json",summary)]:save(OUT/"deeper"/name,value)
    save(OUT/"deeper/manifest.json",dict(input_git_commit=REV,input_sha256=d.ar.hashes,
        code_sha256={p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob("*.py")},new_model_calls=0,graph_writes=0))
    print(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(sensitivity,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
