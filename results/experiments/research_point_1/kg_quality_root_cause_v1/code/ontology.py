"""Frozen-schema inventory and representation-risk signals, not new ontology."""
import ast
from common import *


def main():
    if (OUT/'ontology/complete.json').exists():print('REUSE ontology inventory');return
    d,E,C,S=dataset();N=d['normalized'];reg=d['schema']['relation_registry'];source=d['graph']['source_records']
    contract=ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/chinese_extraction_contract.py';tree=ast.parse(contract.read_text());prompts=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('SYSTEM_PROMPT') for t in node.targets):
            prompts.extend(n.value for n in ast.walk(node.value) if isinstance(n,ast.Constant) and isinstance(n.value,str))
    bodies='\n'.join(prompts)
    rows=[];dups=defaultdict(list);surface=defaultdict(list);entitysrc=defaultdict(list)
    for s in source:
        for side in ['head','tail']:
            eid=s['expanded_'+side+'_entity_id'];entitysrc[eid].append(s);surface[s[side+'_type'],I.norm(s[side+'_surface'])].append(eid)
    for e in E.values():dups[I.norm(e['label_zh'])].append(e)
    for name,r in sorted(reg.items()):
        nn=[x for x in N if x['relation']==name];cc=[c for c in C.values() if c['relation']==name];ss=[s for s in source if s['relation']==name]
        actions=Counter(z for x in nn for z in x.get('normalization_actions',[]))
        rows.append(dict(relation=name,label_zh=r['label_zh'],definition=r.get('canonical_direction',''),domain='|'.join(r['domain']),range='|'.join(r['range']),raw_export_records=sum(x['relation']==name for x in d['raw']),normalized_records=len(nn),published_claims=len(cc),published_assertions=len(ss),schema_illegal_normalized=sum(not legal(x,reg) for x in nn),saved_entailed=sum(x.get('relation_entailment_validation',{}).get('status')=='entailed' for x in nn),saved_not_entailed=sum(x.get('relation_entailment_validation',{}).get('status')=='not_entailed' for x in nn),saved_undetermined=sum(x.get('relation_entailment_validation',{}).get('status')=='undetermined' for x in nn),enumerated_in_extraction_contract=True,explicit_prompt_instruction_mention=name in bodies,normalization_actions=canon(actions),source_example_claim=cc[0]['claim_id'] if cc else '',source_example_doc=ss[0]['doc_id'] if ss else '',source_example_page=ss[0]['pdf_page_number'] if ss else '',source_example_text=ss[0]['evidence_text'] if ss else ''))
    csvsave('ontology/relation_inventory.csv',rows)
    examples=[];features=[]
    for eid,e in sorted(E.items()):
        label=e['label_zh'];kind=e['entity_type'];conditional=bool(re.search(r'如果|若|否则|必要时|如已|之前|之后|禁止|不得|仅当|\b(if|when|before|after|never)\b',label,re.I));compound=bool(re.search(r'并|且|和/或|或者|；|;|\b(and|or)\b',label,re.I));part=bool(kind=='Component' and re.search(r'\(\d{2,5}\)',I.norm(label)))
        features.append(dict(entity_id=eid,entity_type=kind,label=label,length=len(label),conditional_lexical_flag=conditional,compound_lexical_flag=compound,part_number_component=part,source_documents=sorted({s['doc_id'] for s in entitysrc[eid]})))
        if (kind in ['InspectionAction','MaintenanceAction'] and len(label)>=35) or conditional or part:
            examples.append(dict(entity=e,flags=[z for z,b in [('long_action_label',kind in ['InspectionAction','MaintenanceAction'] and len(label)>=35),('condition_in_label',conditional),('compound_text',compound),('part_number',part)] if b],source=pointer(entitysrc[eid][0]),not_a_confirmed_error=True))
    save('ontology/entity_features.jsonl',features);save('ontology/entity_granularity_examples.jsonl',examples)
    crossrole=[dict(label=k,entities=vv,source_examples=[pointer(entitysrc[e['entity_id']][0]) for e in vv],same_identity_confirmed=False) for k,vv in dups.items() if len(vv)>1]
    save('ontology/same_label_cross_type.jsonl',crossrole)
    multi_surface=[dict(type=k[0],source_surface=k[1],entities=[E[e] for e in sorted(set(ids))],confirmed_alias=False) for k,ids in surface.items() if len(set(ids))>1]
    save('ontology/source_surface_variant_entities.jsonl',multi_surface)
    variant=defaultdict(list)
    for n in N:variant[n['doc_id'],n['pdf_page_number'],I.norm(n['head_surface']),I.norm(n['tail_surface'])].append(n)
    confusion=[]
    for k,rr in variant.items():
        rels={r['relation'] for r in rr}
        target=(rels&{'diagnosed_by','inspected_by'}=={'diagnosed_by','inspected_by'} or rels&{'maintained_by','mitigated_by'}=={'maintained_by','mitigated_by'})
        if target:confusion.append(dict(doc_id=k[0],physical_page=k[1],head_surface=k[2],tail_surface=k[3],relations=sorted(rels),records=[dict(record_id=r['triple_id'],head_type=r['head_type'],relation=r['relation'],tail_type=r['tail_type'],normalization_actions=r.get('normalization_actions',[]),old_status=r['decision']) for r in rr],not_necessarily_error=True))
    save('ontology/relation_variant_cases.jsonl',confusion)
    bytype=[]
    for kind in d['schema']['node_type_registry']:
        ff=[f for f in features if f['entity_type']==kind];bytype.append(dict(entity_type=kind,entities=len(ff),median_label_length=float(np.median([f['length'] for f in ff])) if ff else 0,labels_ge35=sum(f['length']>=35 for f in ff),labels_with_condition_cues=sum(f['conditional_lexical_flag'] for f in ff),labels_with_compound_cues=sum(f['compound_lexical_flag'] for f in ff)))
    csvsave('ontology/type_inventory.csv',bytype)
    save('ontology/complete.json',dict(entity_types=len(d['schema']['node_type_registry']),relation_types=len(reg),relation_claim_counts={r['relation']:r['published_claims'] for r in rows},entity_counts=dict(Counter(e['entity_type'] for e in E.values())),same_label_cross_type_groups=len(crossrole),source_surface_multiple_entities=len(multi_surface),action_entities=sum(f['entity_type'] in ['InspectionAction','MaintenanceAction'] for f in features),action_labels_ge35=sum(f['length']>=35 and f['entity_type'] in ['InspectionAction','MaintenanceAction'] for f in features),condition_label_flags=sum(f['conditional_lexical_flag'] for f in features),numbered_components=sum(f['part_number_component'] for f in features),relation_pair_variant_groups=len(confusion),template_all_relations_available=True,condition_flags_not_binding_error_counts=True,extractor_counts=dict(Counter(x['extractor'] for x in N)),prompt_source_sha256=sha(contract),no_schema_change=True))
    print(read(OUT/'ontology/complete.json'),flush=True)


if __name__=='__main__':main()
