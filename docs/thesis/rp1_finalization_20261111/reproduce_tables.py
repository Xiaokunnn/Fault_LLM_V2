#!/usr/bin/env python3
"""Read existing RP1 assets and export thesis tables. No model/graph writers."""
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
EXP='results/experiments/research_point_1/'
PATHS={
 'raw_cache':'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl',
 'audit':'data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl',
 'expansion_input':'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl',
 'strict208':'data/kg/marine_pump/triples/KG_v1_validated',
 'standard1326':'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/standard_graph/triples/KG_v1_validated',
 'expanded1456':'data/kg/marine_pump/versions/expanded_v1_20261012',
}
SOURCES={}

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def source(path):
    p=ROOT/path;SOURCES[path]={'sha256':sha(p),'bytes':p.stat().st_size};return p

def read(path):
    p=source(path)
    with p.open(encoding='utf-8-sig') as f:
        return [json.loads(s) for s in f if s.strip()] if p.suffix=='.jsonl' else json.load(f)

def write(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    value=obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False,indent=2)+'\n'
    if p.exists() and p.read_bytes()!=value.encode('utf-8') and (OUT/'source_manifest.json').exists():raise RuntimeError('Preserve differing sealed output: '+str(p))
    p.write_text(value)

def table(name,rows,fields=None):
    buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows);write('tables/'+name+'.csv',buf.getvalue())

def csv_source(path):
    return list(csv.DictReader(source(path).open(encoding='utf-8-sig')))

def collect():
    raw=read(PATHS['raw_cache']);audit=read(PATHS['audit']);expansion_input=read(PATHS['expansion_input'])
    qualified=[r for r in audit if r.get('decision') in ['silver_candidate','accepted_silver']]
    versions={};layers={}
    for name in ['strict208','standard1326','expanded1456']:
        root=PATHS[name];versions[name]=read(root+'/source_records.jsonl')
        layers[name]={k:read(root+'/'+k+'.jsonl') for k in ['entities','claims','evidence_assertions']}
        for extra in ['claim_evidence_links.jsonl','graph.graphml','triples.csv','README.md']:
            if (ROOT/root/extra).exists():source(root+'/'+extra)
    populations={'raw_cache':raw,'audit':audit,'audit_expansion_input':expansion_input,'qualified1698':qualified,**versions}
    counts=[];distributions=[]
    for name,rr in populations.items():
        entities={(r[side+'_type'],r.get(side+'_surface',r.get(side,''))) for r in rr for side in ['head','tail']}
        row=dict(population=name,records=len(rr),actual_serialized_claims=len(layers[name]['claims']) if name in layers else '',actual_serialized_entities=len(layers[name]['entities']) if name in layers else '',typed_exact_source_surface_entities=len(entities),documents=len({r['doc_id'] for r in rr}),pages=len({(r['doc_id'],r['pdf_page_number']) for r in rr}),source_families=len({r.get('source_family_id') for r in rr if r.get('source_family_id')}))
        if name=='audit':
            row['actual_serialized_claims']=len(read('data/kg/marine_pump/triples/KG_v1_raw/claims.jsonl'));row['actual_serialized_entities']=len(read('data/kg/marine_pump/triples/KG_v1_raw/entities.jsonl'))
        if name=='qualified1698':
            row['actual_serialized_claims']='';row['actual_serialized_entities']='' # historical ID-based 1650/2613 recorded separately
        counts.append(row)
        for kind,field in [('record_relation','relation'),('record_document','doc_id'),('record_source_family','source_family_id'),('record_head_type','head_type'),('record_tail_type','tail_type')]:
            for value,n in sorted(Counter(r.get(field,'missing') for r in rr).items()):distributions.append(dict(population=name,unit=kind,value=value,count=n))
        if name in layers:
            for typ,n in sorted(Counter(r['entity_type'] for r in layers[name]['entities']).items()):distributions.append(dict(population=name,unit='serialized_entity_type',value=typ,count=n))
            for rel,n in sorted(Counter(r['relation'] for r in layers[name]['claims']).items()):distributions.append(dict(population=name,unit='serialized_claim_relation',value=rel,count=n))
    table('graph_scale',counts);table('entity_relation_source_distribution',distributions)
    run=read('data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/extraction_run_summary.json')
    stage=read(EXP+'six_checks_final_v1_20261110/inventory/stage_counts.json')
    write('tables/counting_units.json',dict(raw_API_proposals=run['raw_proposals'],serialized_raw_cache=len(raw),normalization_rejected=run['rejected_proposals'],audited=len(audit),audit_decisions=dict(Counter(r['decision'] for r in audit)),historical_ID_based_qualified=dict(claims=1650,entities=2613,source=EXP+'b0_ours_ablation_v1/b0_ours_comparison.csv'),non_equivalence='8071 proposals -> 8007 cached records; 8007 and 8003 are different processing populations, not an asserted four-record-only set subtraction',frozen_inventory=stage))
    def source_key(r):return tuple(r.get(k) for k in ['doc_id','pdf_page_number','relation','head_surface','tail_surface','evidence_text'])
    strict={source_key(r):r for r in versions['strict208']};std={r['triple_id']:r for r in versions['standard1326']};au={r['triple_id']:r for r in expansion_input}
    source_index=defaultdict(list)
    for r in expansion_input:source_index[source_key(r)].append(r)
    crosswalk=[];baseline=[];added=[];missing=[]
    for r in versions['expanded1456']:
        origin=std.get(r['triple_id']) if r['expansion_layer']=='baseline_reused' else None
        if origin:
            matched=source_index[source_key(origin)];assert len(matched)==1
            parent=matched[0]['triple_id']
        else:parent=r['expansion_parent_triple_id']
        if r['expansion_layer']=='baseline_reused':
            assert origin is not None
            for k,v in origin.items():assert r[k]==v,(parent,k)
            baseline.append(r)
        else:added.append(r)
        if parent not in au:missing.append(parent)
        crosswalk.append(dict(parent_triple_id=parent,parent_source=PATHS['expansion_input'],publication_record_id=origin['triple_id'] if origin else '',expanded_record_id=r['triple_id'],expanded_entity_head_id=r['expanded_head_entity_id'],expanded_entity_tail_id=r['expanded_tail_entity_id'],expanded_claim_id=r['expanded_claim_id'],expanded_assertion_id=r['expanded_assertion_id'],standard_claim_id=origin.get('claim_id','') if origin else '',strict_claim_id=strict.get(source_key(origin),{}).get('claim_id','') if origin else '',layer=r['expansion_layer'],old_decision=au.get(parent,{}).get('decision','missing')))
    assert not missing
    assert len(raw)==8007 and len(audit)==8003 and len(qualified)==1698
    assert [(len(versions[n]),len(layers[n]['claims']),len(layers[n]['entities'])) for n in versions]==[(208,203,281),(1326,1281,2022),(1456,1400,2150)]
    assert len(baseline)==1326 and len(added)==130
    for name,ls in layers.items():
        es={e['entity_id'] for e in ls['entities']};cs={c['claim_id'] for c in ls['claims']}
        assert len(cs)==len(ls['claims']) and len(es)==len(ls['entities'])
        assert all(c['head_entity_id'] in es and c['tail_entity_id'] in es for c in ls['claims'])
        if name=='expanded1456':assert all(a['claim_id'] in cs for a in ls['evidence_assertions'])
    table('version_record_id_crosswalk',crosswalk)
    lineage=dict(baseline_reused=len(baseline),new_recovered=len(added),new_recovered_old_decisions=dict(Counter(r['expansion_prior_validation']['decision'] for r in added)),expanded_intersection_historical_qualified=sum(au[x['parent_triple_id']]['decision']=='silver_candidate' for x in crosswalk),baseline_all_original_fields_preserved=True,records_with_explicit_conditions_source=sum(r.get('conditions_source') is not None for r in versions['expanded1456']),legacy_unspecified_modality=sum(a['modality']=='legacy_unspecified' for a in layers['expanded1456']['evidence_assertions']),expanded_assertion_file_has_family_column=any('source_family_id' in a for a in layers['expanded1456']['evidence_assertions']),mixed_root_claim_id_count=sum(r['claim_id']!=r['expanded_claim_id'] for r in versions['expanded1456']))
    write('tables/version_lineage.json',lineage)
    api=read(EXP+'api_prompt_comparison_v1/comparison_analysis.json');table('api20_prompt_comparison',api['rows']);write('tables/api20_bootstrap.json',api['paired_ours_minus_baseline_ci95'])
    for filename in ['b0_ours_comparison','incremental_gate_ablation','specific_module_ablation']:
        table(filename,csv_source(EXP+'b0_ours_ablation_v1/'+filename+'.csv'))
    table('source_family_replication',csv_source(EXP+'source_family_replication_pressure_v1/replication_pressure.csv'))
    for key in ['all_candidate_audit_summary','fault_injection_summary']:write('tables/'+key+'.json',read(EXP+'evidence_contract_validation_v1/'+key+'.json'))
    for key,path in {'graph_constraints':EXP+'constraint_report_v1/graph_constraint_report.json','terminology':EXP+'full_terminology_governance_v1_summary.json','expansion_counts':EXP+'graph_expansion_v1_20261012/counts.json','expansion_quality':EXP+'graph_expansion_v1_20261012/quality_summary.json','expansion_verification':EXP+'graph_expansion_v1_20261012/verification.json','complex_binding':EXP+'complex_binding_controlled_20261110/formal/pipeline_aligned/failure_attribution/summary.json'}.items():write('tables/'+key+'.json',read(path))
    cq=read(EXP+'cq_v1/cq_v1_evaluation.json');write('tables/cq_historical_strict208.json',cq['aggregate'])
    # Persist existing larger-tier CQ results only where explicitly stored.
    cqrows=[dict(graph='strict208',tasks=40,covered=34,mean_answers=5.075,mean_evidence=6.15,source=EXP+'cq_v1/cq_v1_evaluation.json'),dict(graph='standard1326',tasks=40,covered=34,mean_answers=6.4,mean_evidence=7.7,source=EXP+'full_terminology_governance_v1_summary.json'),dict(graph='expanded1456',tasks=40,covered='',mean_answers='',mean_evidence='',source='Not evaluated under a frozen expanded1456 CQ reference; do not copy strict/standard numbers')]
    table('cq_version_boundaries',cqrows)
    complexroot=EXP+'complex_binding_controlled_20261110/formal/pipeline_aligned/'
    delivery=read(complexroot+'delivery.json');write('tables/complex_binding_delivery.json',delivery)
    table('complex_binding_metrics',read(delivery['snapshot']+'/trial_comparison.jsonl'))
    schema=read('data/kg/marine_pump/schema/provenance_schema_v3.json')
    table('ontology_entities',[dict(type=k,definition=v) for k,v in schema['node_type_registry'].items()])
    table('ontology_relations',[dict(relation=k,label_zh=v['label_zh'],domain=';'.join(v['domain']),range=';'.join(v['range']),direction=v['canonical_direction'],evidence_roles=';'.join(v['evidence_roles']),core_diagnostic=v['core_diagnostic_relation']) for k,v in schema['relation_registry'].items()])
    # Mechanism explanations are pinned to readable current code, NOT a claim
    # that the current checkout is the historical execution commit.
    for directory in ['src/research_point_1_graph_evidence','papers/ICSMD_2026']:
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and p.suffix in ['.py','.tex','.bib']:source(str(p.relative_to(ROOT)))
    for n in ['build_rp1_graph_expansion_v1.py','build_versioned_knowledge_graph.py','run_local_full_terminology_experiment.py','run_silver_terminology_governance.py','run_rp1_api_prompt_comparison.py','evaluate_cq_v1.py']:
        source('scripts/'+n)
    for p in ['configs/rp1_b0_ours_experiment_v1.json','configs/competency_questions_marine_pump_v1.json',EXP+'api_prompt_comparison_v1/comparison.json',EXP+'api_prompt_comparison_v1/Ours/extraction_run_summary.json',EXP+'graph_expansion_v1_20261012/input_freeze.json',EXP+'graph_expansion_v1_20261012/graph_freeze.json',EXP+'graph_expansion_v1_20261012/completion.json',EXP+'source_family_support_v1/source_family_support_summary.json',EXP+'b0_ours_ablation_v1/artifact_manifest.json',EXP+'evidence_contract_validation_v1/run_manifest.json']:
        source(p)
    for p,meta in SOURCES.items():assert sha(ROOT/p)==meta['sha256'],p
    existing_manifest=OUT/'source_manifest.json'
    captured_commit=json.loads(existing_manifest.read_text())['checkout_commit'] if existing_manifest.exists() else subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    write('source_manifest.json',dict(date='2026-11-11',checkout_commit=captured_commit,code_snapshot_not_historical_execution_commit=True,new_model_calls=0,graph_or_frozen_experiment_modified=False,inputs=SOURCES))
    write('verification.json',dict(status='PASS',input_files=len(SOURCES),all_input_hashes_preserved=True,scale_checks_passed=True,baseline1326_fields_preserved=True,parent_links_resolved=1456,graph_entity_claim_links_closed=True,new_model_calls=0,RP2_RP3_migration_executed=False))
    print(json.dumps(dict(output=str(OUT),files=len(SOURCES),lineage=lineage),ensure_ascii=False))

def verify():
    manifest=json.loads((OUT/'source_manifest.json').read_text())
    for p,d in manifest['inputs'].items():assert sha(ROOT/p)==d['sha256'],p
    print('All',len(manifest['inputs']),'source hashes preserved; no model calls.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    verify() if args.verify else collect()
