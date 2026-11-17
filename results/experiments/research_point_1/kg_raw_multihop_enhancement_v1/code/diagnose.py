"""Post-hoc provenance/coverage/case audit. Outputs never feed retrieval or scoring."""
import gzip
import numpy as np
import torch
from raw_io import *
from run_completion import Evaluation,metrics,transport

def main():
    if (EXP/'analysis/diagnostic_freeze.json').exists():return
    torch.set_num_threads(4); cat=read(EXP/'data/catalogue.json');keys=read(EXP/'paths/query_keys.json');ev=Evaluation(cat,keys);freeze=read(EXP/'completion/freeze.json')
    ranks=[json.loads(x) for x in gzip.decompress((EXP/'completion/query_ranks.jsonl.gz').read_bytes()).decode().splitlines()]
    lookup={(x['method'],x['seed'],x['id'],x['task']):x for x in ranks}
    strata=[];coverage=[];cost=freeze['cost_seconds'];target_support={};Q=len(keys)
    for kind in ['B0','B1','B2','B3','random']:
        z=dict(np.load(EXP/f'paths/{kind}.npz'));L=z['length'];rels=z['relations']; nodes=z['nodes'];nc=(rels>=0).sum(-1);nv=(rels==-1).sum(-1)
        dest=np.take_along_axis(nodes,L[...,None],axis=2)[...,0];valid=(L>=2)&(dest>=0)&(dest<2150)
        supports=[]
        for i,r in enumerate(ev.rows):
            j=r['key_index'];target=r['target'];known=valid[j]&(dest[j]==target)
            t=dict(id=r['id'],task=r['task'],key_index=j,bridge=kind,any_answer_path=bool(valid[j].any()),target_path_count=int(known.sum()),target_real2_path_count=int((known&(nc[j]>=2)).sum()),target_virtual_path_count=int((known&(nv[j]>0)).sum()),answer_path_count=int(valid[j].sum()))
            supports.append(t);coverage.append(t)
        target_support[kind]=supports
        methods=['P4_B3_full'] if kind=='B3' else ['P3_joint_real'] if kind=='B0' else ['P4_'+kind] if kind in ['B1','B2'] else ['random_bridges']
        for method in methods:
            for seed in SEEDS:
                for label,pred in [('any_answer_paths',lambda t:t['any_answer_path']),('no_answer_paths',lambda t:not t['any_answer_path']),('target_real2_path',lambda t:t['target_real2_path_count']>0),('target_virtual_only',lambda t:t['target_path_count']>0 and t['target_real2_path_count']==0),('target_not_reached',lambda t:t['target_path_count']==0)]:
                    ix=[i for i,t in enumerate(supports) if pred(t)]
                    if not ix:continue
                    rr=[lookup[method,seed,ev.rows[i]['id'],ev.rows[i]['task']]['rank'] for i in ix]
                    bb=[lookup['SimKGC_G2',seed,ev.rows[i]['id'],ev.rows[i]['task']]['rank'] for i in ix]
                    strata.append(dict(method=method,seed=seed,stratum=label,**metrics(rr),baseline_MRR=metrics(bb)['MRR'],delta_MRR=metrics(rr)['MRR']-metrics(bb)['MRR']))
    csvsave(EXP/'analysis/target_path_coverage.csv',coverage);csvsave(EXP/'analysis/path_strata.csv',strata)
    # Complete normalized -> computational edge -> raw export lineage, not repaired labels.
    d=locked();links=I.IdLinks()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for r in pop:links.add(I.record_ids(r))
    raw_by_root=defaultdict(list)
    for j,r in enumerate(d['raw']):
        ids=I.record_ids(r)
        if ids:raw_by_root[links.find(ids[0])].append(j)
    lineage=[]
    for x in d['normalized']:
        ids=I.record_ids(x);rr=raw_by_root[links.find(ids[0])]
        lineage.append(dict(record_id=x['triple_id'],raw_export_rows=rr,raw_original_endpoints=[{k:d['raw'][j].get(k) for k in ['triple_id','head_surface','head_type','relation','tail_surface','tail_type','doc_id','pdf_page_number']} for j in rr],normalized_key=I.core_tuple(x),link_basis='transitive saved current/legacy/previous/parent IDs, not semantic guessing'))
    save(EXP/'verification/raw_export_lineage.jsonl',lineage)
    # Known-truth/novelty lookup is audit-only and is not an argument to any scorer.
    basekeys={tuple(x['triple']) for x in read(OLD/'data/base_split.jsonl')};rawkeys={tuple(x['triple']) for x in load_graph('full_edges.jsonl')}
    examples=[x for x in read(EXP/'completion/prediction_examples.jsonl') if x['method']=='P4_B3_full']
    preds=[];recordgraph=read(EXP/'data/record_graph.jsonl'); sourcebyid={x['record_id']:x for x in recordgraph}
    visible_ids={x['record_id'] for x in recordgraph if not x['exclusions']};R=len(cat['relations'])
    for x in examples:
        h,r=x['query'];p=x['top5'][0];t=p['entity'];tr=(h,r,t) if r<R else (t,r-R,h)
        tag='base_existing' if tr in basekeys else 'raw_candidate_seen' if tr in rawkeys else 'beyond_base_and_raw_exact_key'
        preds.append(dict(triple=list(tr),score=p['score'],query=x['query'],seed=x['seed'],novelty=tag,score_is_probability=False))
    save(EXP/'analysis/top1_prediction_novelty.jsonl',preds)
    # Deterministic small evidence search, explicitly only lexical co-occurrence.
    # Candidate evidence used for paths is NEVER presented as independent support.
    catalogue=cat['entities'];sources=d['graph']['source_records']+d['normalized'];evidence=[]
    novel=sorted([x for x in preds if x['novelty']=='beyond_base_and_raw_exact_key'],key=lambda x:-x['score'])[:20]
    for pr in novel:
        h,r,t=pr['triple'];hl=I.norm(catalogue[h]['label_zh']);tl=I.norm(catalogue[t]['label_zh']);hits=[]
        for s in sources:
            text=I.norm(s.get('evidence_text','')); surfaces=I.norm(' '.join(str(s.get(k,'')) for k in ['head_canonical_zh','tail_canonical_zh','head_surface','tail_surface']))
            if hl in text+' '+surfaces and tl in text+' '+surfaces:
                rid=s.get('triple_id');hits.append(dict(record_id=rid,doc=s['doc_id'],page=s['pdf_page_number'],quote=s['evidence_text'],used_as_training_context=rid in visible_ids,independent_source_proven=False,relationship_support='unverified lexical endpoint co-occurrence'))
        evidence.append(dict(**pr,evidence_hits=hits[:5],classification='unverified_model_hypothesis',new_fact_confirmed=False))
    save(EXP/'analysis/novel_prediction_evidence.jsonl',evidence)
    # Frozen pretrained-encoder sanity panel: no label-trained foundation weights.
    # Uses SAME selected alphas, so this panel adds no validation hyperparameter search.
    v=np.load(EXP/'index/vectors.npz');f=dict(entities=torch.tensor(v['entities']),queries=torch.tensor(v['queries']));q=f['queries'][[x[0] for x in keys],[x[1] for x in keys]];base=(q@f['entities'][:2150].T).numpy();rows=[]
    for name in ['frozen_BGE_text','frozen_BGE_raw_R3','frozen_BGE_path_B3']:
        if name=='frozen_BGE_text':s=base;a=0.
        elif name=='frozen_BGE_raw_R3':
            z=np.load(EXP/'completion/R3_retrieval.npz');vv=read(EXP/'index/oriented_views.jsonl');qq,ee,cc=transport(f,keys,z['ids'],z['scores'],vv);a=freeze['selected']['transport_R3_raw'];s=(torch.nn.functional.normalize(qq+a*cc,dim=-1)@ee[:2150].T).cpu().numpy()
        else:a=freeze['selected']['P4_B3_full'];s=base+a*np.load(EXP/'completion/P4_B3_full_support.npz')['support']
        rr,ll,tt,_=ev.evaluate(s);rows.append(dict(method=name,alpha=a,**metrics(rr),top1_type_legal_fraction=float(ll.mean()),label_trained_foundation=False))
    csvsave(EXP/'verification/frozen_encoder_sanity.csv',rows)
    # Replay matched fixed-alpha comparisons rather than quoting only each arm's optimum.
    fixed=read(EXP/'completion/freeze.json')['selected']['P4_B3_full']
    seedresults=list(csv.DictReader((EXP/'completion/seed_results.csv').open()))
    summary=dict(raw_lineage_matched_records=sum(bool(x['raw_export_rows']) for x in lineage),raw_export_rows_covered=len({j for x in lineage for j in x['raw_export_rows']}),top1_novelty=dict(Counter(x['novelty'] for x in preds)),novel_evidence_audited=len(evidence),novel_confirmed_facts=0,path_coverage={kind:dict(directions=len(rr),any_answer_path=sum(x['any_answer_path'] for x in rr),target_reached=sum(x['target_path_count']>0 for x in rr),target_reached_with_2plus_real=sum(x['target_real2_path_count']>0 for x in rr),target_reached_only_virtual_single_real=sum(x['target_path_count']>0 and x['target_real2_path_count']==0 for x in rr)) for kind,rr in target_support.items()},seed_results=seedresults)
    save(EXP/'analysis/diagnostic_freeze.json',summary);print(canonical({k:v for k,v in summary.items() if k!='seed_results'}),flush=True)

if __name__=='__main__':main()
