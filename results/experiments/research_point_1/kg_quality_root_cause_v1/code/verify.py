"""Independent consistency checks and preservation, no old gate/model runs."""
import ast
from common import *


def main():
    checked=[]
    def ok(name,cond):
        if not cond:raise AssertionError(name)
        checked.append(name)
    names=['EXTRACTION_ATTRIBUTION.md','CANDIDATE_LINEAGE.csv','ONTOLOGY_ASSESSMENT.md','ENTITY_RELATION_CASEBOOK.md','DOCUMENT_KNOWLEDGE_AUDIT.md','SOURCE_UNIT_AUDIT.jsonl','COUNTERFACTUAL_VIEWS.md','QUALITY_METRICS.csv','ROOT_CAUSE_ANALYSIS.md','RP1_NEXT_STEP.md','REPRODUCE.md','QUALITY_EVALUATION_FRAMEWORK.md','local_llm/run_optional.py']
    ok('required deliverables',all((OUT/n).is_file() for n in names))
    for f in [*(OUT/'code').glob('*.py'),*(OUT/'local_llm').glob('*.py')]:ast.parse(f.read_text(),filename=str(f))
    ok('Python syntax',True)
    d,E,C,S=dataset();scope=d['inputs'].hashes
    ok('locked snapshot repeated',scope==read(OUT/'lineage/input_hashes.json')==read(OUT/'source_sample/input_hashes.json'))
    for p,h in scope.items():ok('unchanged input '+p,(ROOT/p).is_file() and sha(ROOT/p)==h)
    ok('15 build manuals only',set(doc for doc,page in d['pages'])==I.BUILD)
    lineage=list(csv.DictReader((OUT/'CANDIDATE_LINEAGE.csv').open()));l=read(OUT/'lineage/complete.json')
    ok('8003 unique normalized rows',len(lineage)==8003==len({r['record_id'] for r in lineage}))
    ok('raw identity count corrected',len(d['raw'])==8007 and len({r['triple_id'] for r in d['raw']})==l['raw_unique_ids']==8004)
    ok('primary classes partition',dict(Counter(r['primary_attribution'] for r in lineage))==l['primary_counts'])
    ok('preserved original status',Counter(r['original_status'] for r in lineage)==Counter(r['decision'] for r in d['normalized']))
    ok('old audit explicit lineage resolved',all(r['prior_audit_record_ids'] for r in lineage))
    ok('6387 direct current IDs',len({r['triple_id'] for r in d['audit']}&{r['triple_id'] for r in d['normalized']})==6387)
    linked={cid for r in lineage for cid in r['published_claim_ids'].split('|') if cid}
    ok('all 1400 final Claims have candidate lineage',linked==set(C))
    raw=list(csv.DictReader((OUT/'lineage/raw_export_links.csv').open()));ok('raw 8007 link rows',len(raw)==8007 and sum(r['explicit_ID_link']=='True' for r in raw)==l['raw_rows_linked'])
    units=read(OUT/'source_sample/selected_units.jsonl');sf=read(OUT/'SOURCE_SAMPLE_FREEZE.json');rf=read(OUT/'source_sample/REFERENCE_FREEZE.json')
    ok('frozen sample hash',sha(OUT/'source_sample/selected_units.jsonl')==sf['sample_sha256'])
    ok('source sample 15 x 3',len(units)==45 and Counter(u['doc_id'] for u in units)==Counter({doc:3 for doc in I.BUILD}))
    ok('separate physical pages',len({(u['doc_id'],u['pdf_page_number']) for u in units})==45)
    for u in units:
        p=d['pages'][u['doc_id'],u['pdf_page_number']];native=I.native_units(p)
        ok('native source '+u['sample_id'],u['page_text_sha256']==p['page_text_sha256'] and all(z==native[z.get('block_id',z.get('cell_id'))] for z in u['native_fragments']))
    ok('frozen questions unchanged',sha(OUT/'source_sample/fixed_questions.jsonl')==rf['question_sha256'])
    ok('source judgments unchanged since reference freeze',sha(OUT/'SOURCE_UNIT_AUDIT.jsonl')==rf['source_audit_sha256'])
    audit=read(OUT/'SOURCE_UNIT_AUDIT.jsonl');ok('A-U partition 45',dict(Counter(u['primary_source_judgment'] for u in audit))==rf['judgment_counts'] and len(audit)==45)
    ga=read(OUT/'lineage/GA_eligible_records.jsonl');ok('GA records retain automatic uncertainty',len(ga)==276 and all(x['saved_semantic_status']=='entailed' and x['old_locator_contract']['locator_contract_pass'] and x['automatic_proxy_only'] and not x['scope_and_conditions_complete_confirmed'] for x in ga))
    N={r['triple_id']:r for r in d['normalized']}
    for a in ga:
        n=N[a['record_id']];addr=I.address_check(n,d['pages'][n['doc_id'],n['pdf_page_number']])
        ok('GA literal evidence '+a['record_id'],addr['metadata_hashes_match'] and (addr['exact_contiguous_offset'] or addr['all_provided_cells_match'] or addr['all_native_witnesses_match']))
        ok('GA no old veto '+a['record_id'],not n.get('rejection_reasons'))
    views={v:read(OUT/'counterfactual'/f'{v}_business_claims.jsonl') for v in ['G0','GA','GB','GAB','GC']};cat={v:{x['entity_id']:x for x in read(OUT/'counterfactual'/f'{v}_entities.jsonl')} for v in views}
    ok('G0/GB exact business invariance',views['G0']==views['GB'] and {c['claim_id']:c for c in views['G0']}==C)
    ok('G0 entity catalog unchanged',cat['G0']==E and cat['GB']==E)
    ok('GA/GAB business invariance',views['GA']==views['GAB'] and len(views['GA'])==1671)
    ok('GC is evaluation source subset',len(views['GC'])==18 and len(cat['GC'])==36)
    graphstats={}
    for view,cc in views.items():
        g=nx.Graph();g.add_nodes_from(cat[view])
        for c in cc:
            rule=d['schema']['relation_registry'][c['relation']];h,t=c['head_entity_id'],c['tail_entity_id'];ok('schema '+view+c['claim_id'],cat[view][h]['entity_type'] in rule['domain'] and cat[view][t]['entity_type'] in rule['range']);g.add_edge(h,t)
        parts=list(nx.connected_components(g));graphstats[view]=dict(nodes=g.number_of_nodes(),claims=len(cc),components=len(parts),largest=max(map(len,parts)))
        expected=next(x for x in read(OUT/'counterfactual/view_summary.json') if x['view']==view)
        ok('independent view recount '+view,graphstats[view]==dict(nodes=expected['semantic_entities'],claims=expected['business_claims'],components=expected['components'],largest=expected['largest_component']))
    ga_claim={c['claim_id']:c for c in views['GA']};novel_sources=[s for s in read(OUT/'counterfactual/GA_business_sources.jsonl') if s['claim_id'].startswith('AQC-')]
    for s in novel_sources:
        n=N[s['source']['diagnostic_record_id']];c=ga_claim[s['claim_id']];h,t=cat['GA'][c['head_entity_id']],cat['GA'][c['tail_entity_id']]
        ok('unchanged candidate tuple '+s['source']['diagnostic_record_id'],(h['entity_type'],I.norm(h['label_zh']),c['relation'],t['entity_type'],I.norm(t['label_zh']))==key(n))
    metrics=list(csv.DictReader((OUT/'QUALITY_METRICS.csv').open()));ok('180 typed metric rows',len(metrics)==180 and sum(r['value']=='NA' for r in metrics)==30)
    answers=read(OUT/'counterfactual/question_results.jsonl')
    for view in views:
        q=[r for r in answers if r['view']==view and r['kind']=='atomic_relation_retrieval'];ok('fixed 18 answers '+view,len(q)==18 and sum(r['atomic_exact_source_scoped_answer'] for r in q)==(18 if view=='GC' else 4))
    ok('complex references distinct from assertion metrics',not any(r['view']=='GC' and r['projection']=='complex_source_access' for r in metrics))
    navigation=read(OUT/'navigation/paths.jsonl');ok('inverse traversal is not fact',all(r['inverse_labels_are_traversal_only'] and not r['new_business_fact'] and not r['conditions_jointly_verified'] for r in navigation))
    # Protect all three preceding studies by their delivered content manifests.
    prior=[]
    for dirname,mname in [('kg_query_aware_completion_v1','verification/delivery_manifest.json'),('kg_structure_cross_document_audit_v1','delivery_manifest.json'),('kg_enhancement_document_gap_v1','delivery_manifest.json')]:
        root=PARENT/dirname;m=root/mname;files=read(m)['files']
        for r in files:ok('preserve '+dirname+'/'+r['path'],(root/r['path']).is_file() and sha(root/r['path'])==r['sha256'])
        prior.append(dict(study=dirname,files_checked=len(files),manifest_sha256=sha(m),unchanged=True))
    runner=OUT/'local_llm/run_optional.py';guards=[]
    for flags in [[],['--enable-external-llm','--confirm-local-machine']]:
        out=subprocess.check_output([sys.executable,str(runner),'--check-only',*flags],text=True);guard=json.loads(out);ok('external API guard '+str(flags),not guard['allowed'] and guard['network_calls']==0);guards.append(guard)
    environment=dict(python=sys.version.split()[0],numpy=np.__version__,networkx=nx.__version__,device='server CPU',CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),new_training_runs=0,new_model_inference=0,new_external_LLM_API_calls=0)
    save('verification/input_hashes.json',dict(locked_domain_object=I.REV,domain_inputs=scope,parent_studies=prior,parent_inputs=read(OUT/'details/parent_input_hashes.json')))
    save('verification/environment.json',environment)
    save('verification/checks.json',dict(checks_passed=len(checked),old_study_files_preserved=sum(r['files_checked'] for r in prior),source_sample_units=45,frozen_atomic_references=18,frozen_complex_references=16,quality_metric_rows=len(metrics),independent_graph_recounts=graphstats,old_semantic_labels_changed=False,formal_graph_changes=0,RP2_RP3_changes=0,old_publication_gate_runs=0,full_document_reextractions=0,new_completion_training=0,external_LLM_API_calls=0,expert_Gold=False,independent_semantic_reference=False,API_guard_checks=guards))
    print(canon(read(OUT/'verification/checks.json')),flush=True)


if __name__=='__main__':main()
