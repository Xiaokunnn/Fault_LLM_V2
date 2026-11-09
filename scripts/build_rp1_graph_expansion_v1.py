#!/usr/bin/env python3
"""Build an additive Chinese graph from all 8003 archived candidates, offline."""
import copy
import csv
import io
import json
import hashlib
import sys
from collections import Counter,defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import audit_rp1_loss_pages as old
from rp1_offline_contract_v3 import write,sha,object_sha,rows,REGISTRY
from run_local_full_terminology_experiment import collect_candidates,append_local_terms
from run_silver_terminology_governance import recanonicalize_records, terminology_indexes
from research_point_1_graph_evidence.stage03_schema_validation.batch_evidence_repair_v1 import repair

OUT=ROOT/'results/experiments/research_point_1/graph_expansion_v1_20261012'
GRAPH=ROOT/'data/kg/marine_pump/versions/expanded_v1_20261012'
TERMS=ROOT/'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/entity_terminology_zh_marine_pump_v5_local_full.json'
ENGINE=ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/batch_evidence_repair_v1.py'

def relation_key(r):
    return tuple(' '.join(str(r[k]).casefold().split()) for k in ['head_type','head_canonical_zh','relation','tail_type','tail_canonical_zh'])

def sid(prefix,value):return prefix+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]

def summarize(records):
    return dict(evidence_records=len(records),normalized_relations=len({relation_key(r) for r in records}),
        contextual_assertions=len({sid('',[relation_key(r),r.get('conditions_source',[]),r.get('modality','legacy_unspecified'),r.get('applicability_scope')]) for r in records}),
        entities=len({(r[f'{side}_type'],r[f'{side}_canonical_zh'].casefold().strip()) for r in records for side in ['head','tail']}),
        documents=len({r['doc_id'] for r in records}),pages=len({(r['doc_id'],r['pdf_page_number']) for r in records}),
        relations=dict(Counter(r['relation'] for r in records)))

def export(records):
    GRAPH.mkdir(parents=True,exist_ok=False)
    entities={};claims={};links=[]
    for r in records:
        for side in ['head','tail']:
            entity_id=sid('EXE-',[r[f'{side}_type'],r[f'{side}_canonical_zh'].casefold().strip()])
            entities.setdefault(entity_id,dict(entity_id=entity_id,label_zh=r[f'{side}_canonical_zh'],entity_type=r[f'{side}_type']))
            r['expanded_'+side+'_entity_id']=entity_id
        cid=sid('EXC-',relation_key(r));r['expanded_claim_id']=cid
        claims.setdefault(cid,dict(claim_id=cid,head_entity_id=r['expanded_head_entity_id'],relation=r['relation'],relation_label_zh=REGISTRY[r['relation']]['label_zh'],tail_entity_id=r['expanded_tail_entity_id'],
            interpretation='evidence-linked claim family; conditions and modality reside on each assertion; not an unconditional fact'))
        eid=sid('EXA-',[r['triple_id'],r['doc_id'],r['pdf_page_number'],r.get('conditions_source',[]),r.get('modality','legacy_unspecified')]);r['expanded_assertion_id']=eid
        if r['expansion_layer']=='new_recovered':
            r.update(head_entity_id=r['expanded_head_entity_id'],tail_entity_id=r['expanded_tail_entity_id'],claim_id=cid,evidence_id=eid,assertion_id=eid)
        links.append(dict(assertion_id=eid,claim_id=cid,parent_triple_id=r.get('expansion_parent_triple_id',r['triple_id']),
            doc_id=r['doc_id'],pdf_page_number=r['pdf_page_number'],source_url=r['source_url'],document_sha256=r['document_sha256'],page_text_sha256=r['page_text_sha256'],
            applicability_scope=r['applicability_scope'],conditions_source=r.get('conditions_source'),modality=r.get('modality','legacy_unspecified'),
            layer=r['expansion_layer'],source_witnesses=r.get('expansion_source_witnesses'),original_evidence_text=r['evidence_text']))
    write(GRAPH/'source_records.jsonl',records);write(GRAPH/'entities.jsonl',list(entities.values()));write(GRAPH/'claims.jsonl',list(claims.values()));write(GRAPH/'evidence_assertions.jsonl',links)
    # Ready-to-open tabular artifact; source language/provenance retained.
    f=io.StringIO();fields=['expanded_assertion_id','head_canonical_zh','head_type','relation','tail_canonical_zh','tail_type','doc_id','pdf_page_number','expansion_layer','source_url','evidence_text','applicability_scope','modality','conditions_source']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for r in records:w.writerow({k:json.dumps(r.get(k),ensure_ascii=False) if k=='conditions_source' else r.get(k,'legacy_unspecified' if k=='modality' else '') for k in fields})
    with (GRAPH/'triples.csv').open('x') as h:h.write(f.getvalue())
    ns='http://graphml.graphdrawing.org/xmlns';ET.register_namespace('',ns)
    root=ET.Element('{'+ns+'}graphml')
    for name,target in [('label','node'),('entity_type','node'),('relation','edge'),('assertions','edge')]:ET.SubElement(root,'{'+ns+'}key',{'id':name,'for':target,'attr.name':name,'attr.type':'string'})
    graph=ET.SubElement(root,'{'+ns+'}graph',{'id':'RP1_expanded_v1','edgedefault':'directed'})
    for e in entities.values():
        node=ET.SubElement(graph,'{'+ns+'}node',{'id':e['entity_id']})
        for k,v in [('label',e['label_zh']),('entity_type',e['entity_type'])]:ET.SubElement(node,'{'+ns+'}data',{'key':k}).text=v
    references=defaultdict(list)
    for a in links:references[a['claim_id']].append(a['assertion_id'])
    for c in claims.values():
        edge=ET.SubElement(graph,'{'+ns+'}edge',{'id':c['claim_id'],'source':c['head_entity_id'],'target':c['tail_entity_id']})
        ET.SubElement(edge,'{'+ns+'}data',{'key':'relation'}).text=c['relation_label_zh']
        ET.SubElement(edge,'{'+ns+'}data',{'key':'assertions'}).text=json.dumps(references[c['claim_id']])
    with (GRAPH/'graph.graphml').open('xb') as f:f.write(ET.tostring(root,encoding='utf-8',xml_declaration=True))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'counts.json').exists(), 'Completed graph preserved'
    records=old.read_rows(old.SOURCE);baseline=old.read_rows(old.TIERS['standard']);pages,files=old.load_pages()
    assert len(records)==8003 and len(baseline)==1326
    base_keys={old.source_key(r) for r in baseline}
    deps=[old.SOURCE,*old.TIERS.values(),TERMS,ENGINE,Path(__file__),*files]
    write(OUT/'input_freeze.json',dict(sha256={str(p.relative_to(ROOT)):sha(p) for p in deps},
        inputs=8003,baseline=1326,policy='additive; pump-manual source roles only; no prior dual-model rejection override; same standard terminology 0.90 thresholds',
        quality_sample=dict(seed=20261012,baseline_n=40,added_n=40,method='uniform deterministic SHA256 priority per cohort after graph freeze; no replacement'),
        new_API_calls=0,comparison='same standard graph before/after plus original incoming records paired to repairs'))
    decisions=[];proposals=[]
    for r in records:
        if old.source_key(r) in base_keys:
            decisions.append(dict(parent_triple_id=r['triple_id'],status='baseline_reused'));continue
        p=pages[f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}'];proposal,reason=repair(r,p,REGISTRY)
        if proposal:
            proposed=proposal.pop('payload');proposed['decision']='silver_candidate' # temporary adapter for frozen terminology utility only
            proposed['expansion_parent_triple_id']=r['triple_id'];proposed['expansion_original_decision']=r['decision']
            proposals.append((r,proposed,proposal))
            decisions.append(dict(parent_triple_id=r['triple_id'],status='source_role_proof',mechanism=proposal['mechanism']))
        else:decisions.append(dict(parent_triple_id=r['triple_id'],status=reason))
    terms=json.loads(TERMS.read_text());terms['version']='rp1_expansion_standard_090_20261012'
    candidates=collect_candidates([r for _,r,_ in proposals])
    exact,_=terminology_indexes(terms)
    # Reuse established Chinese aliases before adding a concept; otherwise a
    # synonym can collide with an existing type-scoped dictionary surface.
    alias_reuses=[]
    for (etype,surface),item in candidates.items():
        if len(item['labels'])==1:
            label=next(iter(item['labels']));known=exact.get((etype,label))
            if known and known['canonical_label_zh']!=label:
                canonical=' '.join(known['canonical_label_zh'].casefold().split())
                item['labels']=Counter({canonical:sum(item['labels'].values())})
                alias_reuses.append(dict(entity_type=etype,surface=surface,alias=label,canonical=canonical))
    approved,unresolved=append_local_terms(terms,candidates,repeated_min_confidence=.90,singleton_min_confidence=.90)
    write(OUT/'terminology_alias_reuses.json',alias_reuses)
    governed=recanonicalize_records([r for _,r,_ in proposals],terms)
    write(OUT/'terminology.json',terms);write(OUT/'new_terminology.json',approved);write(OUT/'unresolved_terminology.json',unresolved)
    accepted=[];seen={(relation_key(r),r['doc_id'],r['pdf_page_number']) for r in baseline};dindex={r['parent_triple_id']:r for r in decisions}
    for (original,proposed,proof),canon in zip(proposals,governed):
        decision=dindex[original['triple_id']]
        if not canon.get('eligible_for_chinese_graph'):
            decision['status']='terminology_blocked';continue
        key=(relation_key(canon),canon['doc_id'],canon['pdf_page_number'])
        if key in seen:decision['status']='same_relation_same_page_duplicate';continue
        seen.add(key)
        # Retain old validator outputs as history; no new support flag is passed
        # off as an old validator/model result.
        result=copy.deepcopy(original)
        result['expansion_prior_validation']={k:copy.deepcopy(original.get(k)) for k in ['triple_id','decision','evidence_level','evidence_validation','relation_type_validation','relation_entailment_validation','review_reasons','rejection_reasons','final_confidence']}
        for k in canon:
            if k.startswith(('head','tail','chinese_','terminology')) or k in ['relation','relation_label_zh','graph_display_language','eligible_for_chinese_graph']:
                result[k]=copy.deepcopy(canon[k])
        result.update(triple_id=sid('EXP-',[original['triple_id'],relation_key(result)]),decision='automatically_evidence_qualified_expansion',
            expansion_parent_triple_id=original['triple_id'],expansion_layer='new_recovered',expansion_mechanism=proof['mechanism'],
            expansion_source_witnesses=proof['source_witnesses'],conditions_source=proof['conditions_source'],modality=proof['modality'],
            expansion_changes={k:dict(before=original.get(k),after=result.get(k)) for k in ['head_surface','head_type','head_canonical_zh','relation','tail_surface','tail_type','tail_canonical_zh'] if original.get(k)!=result.get(k)},
            expansion_validation=dict(method='bounded native role proof v1',support_explanation=proof['support_explanation'],human_review=False,model_reverification=False,
                caveat='automatic contract qualification; quality evaluated by separate sample; old statuses in expansion_prior_validation'))
        accepted.append(result);decision['status']='added';decision['expanded_triple_id']=result['triple_id']
    write(OUT/'candidate_decisions.jsonl',decisions);write(OUT/'added_records.jsonl',accepted)
    base=[dict(copy.deepcopy(r),expansion_layer='baseline_reused') for r in baseline]
    combined=base+accepted;export(combined)
    base_relation_keys={relation_key(r) for r in baseline};new_keys={relation_key(r) for r in accepted}-base_relation_keys
    summary=dict(status='graph_built_quality_review_pending',input_records=8003,baseline=summarize(baseline),added=summarize(accepted),expanded=summarize(combined),
        genuinely_new_normalized_relations=len(new_keys),existing_relation_additional_evidence=sum(relation_key(r) in base_relation_keys for r in accepted),
        added_old_decisions=dict(Counter(r['expansion_prior_validation']['decision'] for r in accepted)),
        added_mechanisms=dict(Counter(r['expansion_mechanism'] for r in accepted)),decisions=dict(Counter(r['status'] for r in decisions)),
        added_by_document=dict(Counter(r['doc_id'] for r in accepted)),new_pages=len({(r['doc_id'],r['pdf_page_number']) for r in accepted}-{(r['doc_id'],r['pdf_page_number']) for r in baseline}),
        API_calls=0,canonical_language='Chinese',dedup='exact canonical type-label-relation keys; no claim of exhaustive semantic alias dedup',
        original_graphs_unchanged=True)
    write(OUT/'counts.json',summary)
    # Sampling occurs only after inclusion and graph files have been sealed.
    write(OUT/'graph_freeze.json',dict(sha256={str(p.relative_to(ROOT)):sha(p) for p in [*GRAPH.iterdir(),OUT/'added_records.jsonl',OUT/'counts.json',OUT/'candidate_decisions.jsonl']},AI_review_not_yet_started=True))
    sample=[]
    for cohort,population in [('baseline',base),('added',accepted)]:
        selected=sorted(population,key=lambda r:hashlib.sha256(('20261012|'+cohort+'|'+r['triple_id']).encode()).hexdigest())[:40]
        for i,r in enumerate(selected,1):
            key=f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}'
            original=next(x for x in records if x['triple_id']==r['expansion_parent_triple_id']) if cohort=='added' else None
            sample.append(dict(review_id=f'{cohort[0].upper()}{i:02d}',cohort=cohort,population_n=len(population),sample_n=len(selected),record=r,
                original_record=original,source_page=pages[key]))
    write(OUT/'quality_sample.jsonl',sample)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
