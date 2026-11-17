"""All new models sealed before scoring; reuse all old strong comparison results."""
import time
import gc
import torch
import numpy as np
from role_io import *
from contrast import load_parent,make_packs,forward_probe,task_margin
from train import ARMS
from fit_collab import query_scores
from eval_core import Evaluator

OLD_METHODS=['simkgc_G1','simkgc_G2','simkgc_G3','simkgc_filter','collab_full','collab_lan','collab_no_dynamic','collab_no_neighbor']


def probe(model,data,graph,seed):
    allpairs=read(OUT/f'data/utility_{seed}.jsonl');rows=[]
    for off in range(0,len(allpairs),64):
        pairs=allpairs[off:off+64];pp,pm,pz,slots=make_packs(graph,pairs)
        h=torch.tensor([p['h'] for p in pairs],device='cuda');r=torch.tensor([p['r'] for p in pairs],device='cuda');q=data['queries'][h,r]
        with torch.no_grad():
            ep,lp=forward_probe(model,q,r,data['entities'],pp,slots);em,lm=forward_probe(model,q,r,data['entities'],pm,slots)
            ez=model(q,r,data['entities'],pz);baseline=task_margin(ez,data['entities'],pairs)
            up=task_margin(ep,data['entities'],pairs)-baseline;um=task_margin(em,data['entities'],pairs)-baseline
        for p,a,b,c,d in zip(pairs,lp.cpu().tolist(),lm.cpu().tolist(),up.cpu().tolist(),um.cpu().tolist()):
            rows.append(dict(pair_id=p['pair_id'],split=p['split'],strong_contrast=p['strong_contrast'],kind=p['negative_kind'],
                logit_plus=a,logit_minus=b,gate_plus=float(torch.sigmoid(torch.tensor(a))),gate_minus=float(torch.sigmoid(torch.tensor(b))),
                contribution_plus=c,contribution_minus=d))
    subsets={}
    for name,predicate in [('fit_strong',lambda p:p['split']=='fit' and p['strong_contrast']),('probe_strong',lambda p:p['split']=='probe' and p['strong_contrast']),('probe_all',lambda p:p['split']=='probe')]:
        rr=[r for r in rows if predicate(r)]
        subsets[name]=dict(n=len(rr),logit_order=sum((x['logit_plus']>x['logit_minus'])+.5*(x['logit_plus']==x['logit_minus']) for x in rr)/len(rr) if rr else None,
            score_contribution_order=sum((x['contribution_plus']>x['contribution_minus'])+.5*(x['contribution_plus']==x['contribution_minus']) for x in rr)/len(rr) if rr else None,
            mean_gate_plus=float(np.mean([x['gate_plus'] for x in rr])) if rr else None,mean_gate_minus=float(np.mean([x['gate_minus'] for x in rr])) if rr else None,
            saturation_rate=float(np.mean([v>.95 for x in rr for v in [x['gate_plus'],x['gate_minus']]])) if rr else None)
    # Natural candidates on validation queries; no use of labels/grades to classify truth.
    valid=read(RUN/'data/validation_targets.jsonl');R=graph.R;keys=sorted({k for x in valid for k in [(x['triple'][0],x['triple'][1]),(x['triple'][2],x['triple'][1]+R)]});gates=[]
    for off in range(0,len(keys),128):
        kk=keys[off:off+128];h=[k[0] for k in kk];r=torch.tensor([k[1] for k in kk],device='cuda');p=graph.pack(h)
        with torch.no_grad():_,details=model(data['queries'][torch.tensor(h,device='cuda'),r],r,data['entities'],p,True)
        g=details['gates'][p['mask']&~p['base']].cpu().tolist();gates+=g
    subsets['natural_validation_candidate_gates']=dict(n=len(gates),mean=float(np.mean(gates)) if gates else None,std=float(np.std(gates)) if gates else None,
        saturation_rate=float(np.mean(np.array(gates)>.95)) if gates else None,low_rate=float(np.mean(np.array(gates)<.05)) if gates else None,
        gate_is_not_truth_probability=True)
    return subsets,rows


def main():
    torch.set_num_threads(2);deadline=time.monotonic()+7200
    folders=[OUT/'models'/f'role_{arm}_s{s}' for s in SEEDS for arm in ARMS]
    while not all((f/'complete.json').exists() for f in folders):
        if time.monotonic()>deadline:raise TimeoutError('Keep complete models; unfinished fitting')
        time.sleep(3)
    save(OUT/'test_release.json',dict(checkpoints={f.name:file_sha(f/'best.pt') for f in folders},protocol_sha256=file_sha(NEW/'PROTOCOL.md'),no_more_model_selection=True))
    targets=read(RUN/'audit_only/test_targets.jsonl');cat=read(RUN/'data/catalogue.json');R=len(cat['relations']);n=cat['nbase']
    ev=Evaluator(targets,read(RUN/'audit_only/test_truth.json'),cat,list(range(n)))
    for s in SEEDS:
        for method in OLD_METHODS:
            name=f'{method}_s{s}';src=RUN/'evaluation'/name
            save(OUT/'evaluation'/name/'metrics.json',dict(read(src/'metrics.json'),reused_frozen_previous=True))
            save(OUT/'evaluation'/name/'rankings.jsonl',read(src/'rankings.jsonl'))
            save(OUT/'evaluation'/name/'reuse.json',dict(source=str(src.relative_to(PILOT)),metrics_sha256=file_sha(src/'metrics.json')))
    for folder in folders:
        name=folder.name;out=OUT/'evaluation'/name;cfg=read(folder/'config.json');seed=cfg['seed']
        if (out/'complete.json').exists():continue
        model,data,graph=load_parent(seed);model.load_state_dict(torch.load(folder/'best.pt',map_location='cuda',weights_only=True));model.eval()
        keys=sorted({k for x in targets for k in [(x['triple'][2],x['triple'][1]+R)]+[(x['triple'][0],j) for j in range(R)]});idx={k:i for i,k in enumerate(keys)}
        scores=query_scores(model,data,graph,keys)
        def predict(h,r,t,task):
            if task=='relation':return np.array([scores[idx[h,j],t] for j in range(R)])
            return scores[idx[(h,r) if task=='tail' else (t,r+R)]]
        matrices={task:np.stack([predict(*x['triple'],task) for x in targets]) for task in ['head','tail','relation']}
        metrics,rankings=ev.score(predict);save(out/'metrics.json',dict(metrics,model=name,seed=seed,arm=cfg['arm'],proxy_only=True,checkpoint_sha256=file_sha(folder/'best.pt')))
        save(out/'rankings.jsonl',rankings);np.savez_compressed(out/'scores.npz',**matrices)
        for which in ['best','last_diagnostic']:
            model.load_state_dict(torch.load(folder/(which+'.pt'),map_location='cuda',weights_only=True));model.eval()
            summary,rows=probe(model,data,graph,seed)
            save(out/(which+'_probe_summary.json'),summary);save(out/(which+'_probe_rows.jsonl'),rows)
        save(out/'complete.json',dict(test_scored_best_only=True,last_only_mechanism_diagnostic=True))
        print(DATASET,name,metrics['link_MRR'],flush=True)
        del model,data;gc.collect();torch.cuda.empty_cache()
    save(OUT/'evaluation/complete.json',dict(new_models=len(folders),reused_models=3*len(OLD_METHODS),total=len(folders)+3*len(OLD_METHODS),all_conditions_reported=True))


if __name__=='__main__':main()
