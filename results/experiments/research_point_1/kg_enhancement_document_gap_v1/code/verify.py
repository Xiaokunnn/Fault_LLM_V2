"""Verify delivered results and preservation without retraining or API calls."""
import ast
import subprocess
from common_local import *


def main():
    checked=[]
    def ok(label,condition):
        if not condition:raise AssertionError(label)
        checked.append(label)
    required=['POTENTIAL_RELATIONS.jsonl','COMPLETION_OPPORTUNITIES.md','KNOWLEDGE_GAPS.csv','DOCUMENT_PRIORITIES.md','TRANSPORT_COMPARISON.csv','CASEBOOK.md','EXPERIMENT_PROTOCOL.md','FINAL_DECISION.md','REPRODUCE.md','local_llm/run_optional.py']
    ok('all required deliverables exist',all((OUT/f).is_file() for f in required))
    for py in sorted((OUT/'code').glob('*.py'))+sorted((OUT/'local_llm').glob('*.py')):ast.parse(py.read_text(),filename=str(py))
    ok('all Python files parse',True)
    original=[]
    for root,m in [(STUDY,STUDY/'verification/delivery_manifest.json'),(AUDIT,AUDIT/'delivery_manifest.json')]:
        files=read(m)['files']
        for f in files:
            p=root/f['path'];ok('preserve '+str(p.relative_to(ROOT)),p.is_file() and sha(p)==f['sha256'])
        original.append(dict(root=str(root.relative_to(ROOT)),manifest_sha256=sha(m),verified_files=len(files),all_hashes_match=True))
    d,cat,entities,ei,claims,src,uf=load_domain()
    input_hashes=d['inputs'].hashes
    ok('locked domain inputs retain prior snapshot hashes',input_hashes==read(OUT/'gaps/input_hashes.json')==read(OUT/'potential/input_hashes.json')['domain_inputs'])
    current=[]
    for path,h in input_hashes.items():
        same=(ROOT/path).is_file() and sha(ROOT/path)==h
        current.append(dict(path=path,locked_sha256=h,current_matches_locked=same))
    ok('working copy input files match locked domain blobs',all(x['current_matches_locked'] for x in current))
    ok('domain corpus boundary',set(doc for doc,page in d['pages'])==I.BUILD)
    predictions=read(OUT/'POTENTIAL_RELATIONS.jsonl');summary=read(OUT/'potential/complete.json')
    ok('potential category counts',dict(Counter(x['primary_category'] for x in predictions))==summary['categories'])
    ok('unique potential triples',len({tuple(x['triple_indices']) for x in predictions})==len(predictions)==161)
    for x in predictions:
        rule=cat['registry'][x['relation']]
        ok('schema '+x['relation_id'],x['head']['entity_type'] in rule['domain'] and x['tail']['entity_type'] in rule['range'])
        ok('unpublished '+x['relation_id'],not x['published'] and not x['confirmed_new_fact'] and not x['already_base'])
        if x['primary_category']=='B':
            ok('B preserves 3 real premises '+x['relation_id'],not x['already_initial_candidate'] and all(len(p['premises'])==3 and all(c['claim_id'] in claims for c in p['premises']) for p in x['pattern_support']))
            ok('B is conditional analogy '+x['relation_id'],all(p['logical_entailment'] is False and p['local_conditions_fully_verified'] is False for p in x['pattern_support']))
        if x['primary_category']=='C':ok('C remains unknown '+x['relation_id'],'insufficient' in x['support_grade'])
    keys=[tuple(x) for x in read(OUT/'mechanism/query_keys.json')];index_edges=read(STUDY/'index/edges.jsonl');views=read(STUDY/'index/oriented_views.jsonl');anchor_docs=defaultdict(set)
    for e in index_edges:
        for a in [e['triple'][0],e['triple'][2]]:anchor_docs[a].update(x[0] for x in e['pages'])
    cached=np.load(STUDY/'retrieval/R3_all_global.npz')
    for k in [8,16,32]:
        ids={m:np.load(OUT/'mechanism'/f'{m}_k{k}_selection.npz')['ids'] for m in ['T0','T1','T2','T3','T4','T5']}
        ok('T0 original retrieval K'+str(k),all(np.array_equal(ids['T0'][j],cached['ids'][h,r,:k]) for j,(h,r) in enumerate(keys)))
        ok('T4 records zero effective conflict blocking K'+str(k),np.array_equal(ids['T3'],ids['T4']))
        for method in ['T1','T2']:
            for j,(h,r) in enumerate(keys):
                selected=[int(v) for v in ids[method][j] if v>=0]
                if not anchor_docs[h]:ok(method+' unknown fallback '+str((j,k)),not selected)
                else:ok(method+' source side '+str((j,k)),all(bool(anchor_docs[h]&{p[0] for p in index_edges[views[v]['edge_index']]['pages']})==(method=='T1') for v in selected))
    allseed=list(csv.DictReader((OUT/'mechanism/ALL_SEED_RESULTS.csv').open()));agg=list(csv.DictReader((OUT/'TRANSPORT_COMPARISON.csv').open()))
    ok('54 actual settings',len([x for x in allseed if x['subset']=='all_validation'])==54)
    for x in allseed:
        rows=read(OUT/'mechanism'/f"{x['method']}_k{x['k']}_s{x['seed']}_ranks.jsonl")
        if x['subset']!='all_validation':rows=[q for q in rows if q['source_observable']==(x['subset']=='source_observable_directions')]
        ok('recompute metric '+str([x['method'],x['k'],x['seed'],x['subset']]),len(rows)==int(x['query_directions']) and abs(float(np.mean([1/q['rank'] for q in rows]))-float(x['MRR']))<1e-12)
    for x in agg:
        rr=[q for q in allseed if all(q[k]==x[k] for k in ['method','k','subset'])]
        ok('aggregate '+str([x['method'],x['k'],x['subset']]),len(rr)==3 and abs(np.mean([float(q['MRR']) for q in rr])-float(x['MRR']))<1e-12)
    ok('three baseline CPU exact replays',all(x['delta']==0 and x['within_1e_5'] for x in read(OUT/'mechanism/reference_replay.json')))
    gaps=list(csv.DictReader((OUT/'KNOWLEDGE_GAPS.csv').open()));gg=read(OUT/'gaps/complete.json')
    ok('gap ledger denominators',len(gaps)==886==len(read(OUT/'gaps/gap_sources.jsonl')) and dict(Counter(x['gap_class'] for x in gaps))==gg['gap_classes'])
    for q in read(OUT/'gaps/document_requests.jsonl'):
        p=d['pages'][q['doc'],q['page']]
        ok('exact document request '+q['request_id'],p['page_text'][q['context_start']:q['context_end']]==q['exact_context'] and p['page_text_sha256']==q['page_text_sha256'])
    runner=OUT/'local_llm/run_optional.py';guards=[]
    for flags in [[],['--enable-external-llm','--confirm-local-machine']]:
        out=subprocess.check_output([sys.executable,str(runner),'--check-only',*flags],text=True);q=json.loads(out);ok('API guard '+str(flags),not q['allowed'] and q['network_calls']==0);guards.append(q)
    save(OUT/'verification/input_hashes.json',dict(locked_git_object=I.REV,domain_inputs=input_hashes,parent_files=original,current_domain_files=current))
    save(OUT/'verification/checks.json',dict(checks_passed=len(checked),original_files_preserved=sum(x['verified_files'] for x in original),parent_experiments=original,CPU_replay_exact=True,formal_graph_changes=0,RP2_RP3_changes=0,new_extractions=0,new_training_runs=0,new_GPU_work=0,external_LLM_calls=0,api_guard_checks=guards,new_independent_evaluation=False,expert_Gold=False))
    print(canonical(read(OUT/'verification/checks.json')),flush=True)
    manifest=OUT/'delivery_manifest.json'
    # The verifier never edits a sealed report. Seal only when no manifest
    # exists; on subsequent runs verify that manifest, including saved logs.
    if manifest.exists():
        for f in read(manifest)['files']:
            p=OUT/f['path'];assert p.exists() and sha(p)==f['sha256'],f['path']
    else:
        files=[dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery_manifest.json']
        save(manifest,dict(files=files,source_revision=I.REV,formal_graph_changes=0,RP2_RP3_changes=0,external_LLM_calls=0,CPU_only=True))


if __name__=='__main__':main()
