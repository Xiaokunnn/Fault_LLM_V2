"""Train-only frozen reference utility, labels sealed before new fitting."""
from collections import Counter,defaultdict
import torch
import numpy as np
from role_io import *
from contrast import load_parent,make_packs,forward_probe,task_margin


def main():
    torch.set_num_threads(2)
    while not (OUT/'data/freeze.json').exists():
        import time;time.sleep(2)
    rows=read(OUT/'data/role_pairs_unfiltered.jsonl');unique={}
    for row in rows:unique.setdefault(row['pair_id'],row)
    rows=list(unique.values());known={(r['h'],r['r']):r['tails'] for r in read(OUT/'data/train_positive_tails.json')}
    aliases=read(NEW/'administrative_entity_aliases.json');cat=read(RUN/'data/catalogue.json');n=cat['nbase']
    for seed in SEEDS:
        if (OUT/f'data/utility_{seed}.jsonl').exists():continue
        model,data,graph=load_parent(seed);model.eval();scored=[]
        for off in range(0,len(rows),64):
            batch=[]
            for raw in rows[off:off+64]:
                x=dict(raw);allgood=known[x['h'],x['r']];visible={t for t,_,_ in graph.entries(x['h'],x['training_id'])}
                good=[t for t in allgood if t not in visible and aliases[t]!=aliases[x['neighbor']] if t<len(aliases)]
                if not good:continue
                q=data['queries'][x['h'],x['r']];s=(data['entities'][:n]@q).detach().cpu().numpy()
                forbidden={aliases[t] for t in allgood}
                competitors=[int(t) for t in np.argsort(-s,kind='stable') if aliases[t] not in forbidden and t not in [x['neighbor'],x['negative_neighbor']]][:8]
                if len(competitors)<2:continue
                x['positive_tail_ids']=good;x['competitor_ids']=competitors;batch.append(x)
            if not batch:continue
            packs=make_packs(graph,batch);h=torch.tensor([x['h'] for x in batch],device='cuda');r=torch.tensor([x['r'] for x in batch],device='cuda');q=data['queries'][h,r]
            with torch.no_grad():
                vp,_=forward_probe(model,q,r,data['entities'],packs[0],packs[3],unit_gate=True)
                vm,_=forward_probe(model,q,r,data['entities'],packs[1],packs[3],unit_gate=True)
                vz=model(q,r,data['entities'],packs[2])
                up=task_margin(vp,data['entities'],batch)-task_margin(vz,data['entities'],batch)
                um=task_margin(vm,data['entities'],batch)-task_margin(vz,data['entities'],batch)
            for x,a,b in zip(batch,up.cpu().tolist(),um.cpu().tolist()):
                x.update(reference_u_plus=a,reference_u_minus=b,strong_contrast=bool(a>1e-5 and b<-1e-5),
                    reference_checkpoint_sha256=file_sha(checkpoint(seed)),reference_gate_for_selected_edge=1.,reference_is_automatic_task_teacher=True)
                scored.append(x)
        save(OUT/f'data/utility_{seed}.jsonl',scored)
        summary=dict(seed=seed,raw=len(rows),duplicates_removed=len(read(OUT/'data/role_pairs_unfiltered.jsonl'))-len(rows),scored=len(scored),
            strong_pairs=sum(x['strong_contrast'] for x in scored),strong_fit=sum(x['strong_contrast'] and x['split']=='fit' for x in scored),
            strong_probe=sum(x['strong_contrast'] and x['split']=='probe' for x in scored),positive_sources_not_universal_support=True,
            kinds=dict(Counter(x['negative_kind'] for x in scored if x['strong_contrast'])),
            source='No validation/test scores or targets used. Competitors are sampled unknowns, not factual negatives.')
        save(OUT/f'data/utility_{seed}.json',summary);print(DATASET,summary,flush=True)
        del model,data;torch.cuda.empty_cache()
    save(OUT/'data/utility_freeze.json',dict(files={p.name:file_sha(p) for p in sorted((OUT/'data').glob('utility_*'))},
        threshold=1e-5,used_train_labels_only=True,reference='Previous frozen full; no new teacher or LLM calls'))


if __name__=='__main__':main()
