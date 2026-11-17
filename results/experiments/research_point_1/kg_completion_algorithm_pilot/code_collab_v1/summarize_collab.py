"""Report all predeclared conditions and paired uncertainty, not best seeds."""
from collections import defaultdict
import csv
import io
import numpy as np
from collab_io import *


def table(name,rows):
    stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    save(STUDY/'tables'/name,stream.getvalue())


def main():
    allrows=[];groups=defaultdict(list);scenarios=[]
    for dataset in ['cold','structured']:
        root=STUDY/dataset;assert (root/'evaluation/complete.json').exists()
        split={r['claim_id']:r for r in read(root/'data/base_split.jsonl')}
        for p in sorted((root/'evaluation').glob('*/metrics.json')):
            m=read(p);name=p.parent.name;seed=int(name.rsplit('_s',1)[1]);variant=name.rsplit('_s',1)[0]
            folder=root/'models'/name
            if not folder.exists():folder=OLD/'models'/name
            comp=read(folder/'complete.json');cfg=read(folder/'config.json')
            row=dict(dataset=dataset,model=name,variant=variant,seed=seed,link_MRR=m['link_MRR'],
                Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2,
                relation_MRR=m['relation']['all']['MRR'],schema_legal_top1=1-(m['head']['top1_schema_violation_rate']+m['tail']['top1_schema_violation_rate'])/2,
                best_epoch=comp['best_epoch'],train_seconds=comp['seconds'],parameters=cfg['parameters'],peak_cuda_bytes=comp.get('peak_cuda_bytes',0),
                extra_candidates=cfg.get('legal_candidates',cfg.get('view',{}).get('aux_edges',0)),synthetic_contexts=cfg.get('synthetic_contexts',0))
            allrows.append(row);groups[dataset,variant].append(row)
            if dataset=='structured':
                tags={x['claim_id']:x['support_kind'] for x in read(root/'audit_only/structure_selection.json')['selected']}
                ranks=read(p.parent/'rankings.jsonl')
                for tag in ['base_supported','candidate_assisted']:
                    values=[r['rank'] for r in ranks if r['task']!='relation' and tags[r['id']]==tag]
                    scenarios.append(dict(model=name,variant=variant,seed=seed,support_kind=tag,head_tail_queries=len(values),MRR=float(np.mean(1/np.array(values)))))
        assert sum(r['dataset']==dataset for r in allrows)==48
    table('all96_models.csv',allrows);table('structured_support_subgroups.csv',scenarios)
    grouped=[]
    for (dataset,variant),rr in sorted(groups.items()):
        assert len(rr)==3
        row=dict(dataset=dataset,variant=variant,seeds=3)
        for metric in ['link_MRR','Hits1','Hits10','relation_MRR','schema_legal_top1','train_seconds']:
            row[metric+'_mean']=float(np.mean([r[metric] for r in rr]));row[metric+'_sd']=float(np.std([r[metric] for r in rr]))
        grouped.append(row)
    table('grouped_metrics.csv',grouped);save(STUDY/'tables/grouped_metrics.json',grouped)
    comparisons=[]
    for dataset in ['cold','structured']:
        root=STUDY/dataset;mapping={r['claim_id']:r['group_id'] for r in read(root/'data/base_split.jsonl')}
        for control in ['simkgc_G2','simkgc_filter','collab_lan','collab_no_dynamic','collab_fixed','collab_no_relation','collab_no_neighbor','collab_no_null']:
            deltas=defaultdict(list);seed_deltas=[]
            for seed in SEEDS:
                full=read(root/'evaluation'/f'collab_full_s{seed}'/'rankings.jsonl')
                other=read(root/'evaluation'/f'{control}_s{seed}'/'rankings.jsonl');lookup={(r['id'],r['task']):r for r in other}
                vals=[]
                for r in full:
                    if r['task']=='relation':continue
                    delta=1/r['rank']-1/lookup[r['id'],r['task']]['rank'];deltas[mapping[r['id']]].append(delta);vals.append(delta)
                seed_deltas.append(float(np.mean(vals)))
            group_values=np.array([np.mean(v) for v in deltas.values()]);rng=np.random.default_rng(SEEDS[0]);draws=[np.mean(rng.choice(group_values,len(group_values),replace=True)) for _ in range(2000)]
            comparisons.append(dict(dataset=dataset,contrast='collab_full minus '+control,seed_deltas=seed_deltas,
                query_weighted_delta=float(np.mean(seed_deltas)),group_macro_delta=float(np.mean(group_values)),
                group_bootstrap_CI95=[float(x) for x in np.quantile(draws,[.025,.975])],groups=len(group_values),
                caution='Conditional fixed split automatic-label proxy; not factual accuracy or document-level generalization certificate; multiple comparisons exploratory'))
    save(STUDY/'tables/paired_comparisons.json',comparisons)
    save(STUDY/'tables/complete.json',dict(evaluated=96,new_neural_foundations=15,reused_cold_models=9,adapters=72,all_conditions_reported=True))
    print('Summarized all96 evaluations',flush=True)


if __name__=='__main__':main()
