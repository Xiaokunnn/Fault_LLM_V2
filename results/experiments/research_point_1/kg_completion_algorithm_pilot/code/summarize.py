"""Aggregate every frozen run, including negative outcomes; no selection by test."""
from collections import defaultdict
import csv
import io
import numpy as np
from common import RUN,read,save


def table(name,rows):
    stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);save(RUN/'tables'/name,stream.getvalue())


def main():
    assert (RUN/'evaluation/complete.json').exists()
    metrics=[]
    for p in sorted((RUN/'evaluation').glob('*/test/metrics.json')):
        m=read(p);cfg=read(RUN/'models'/m['model']/'config.json')
        family=m['model'].split('_')[0]
        view=m['view'];prototype=m.get('prototype','none')
        metrics.append(dict(model=m['model'],algorithm=family,view=view,seed=m['seed'],fraction=cfg.get('fraction',1.),noise=cfg.get('noise',0.),prototype=prototype,
            head_MRR=m['head']['all']['MRR'],tail_MRR=m['tail']['all']['MRR'],link_MRR=m['link_MRR'],relation_MRR=m['relation']['all']['MRR'],
            link_Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,
            link_Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2,
            typed_link_MRR=(m['head']['typed_MRR']+m['tail']['typed_MRR'])/2,
            tie_randomized_link_MRR=(m['head']['tie_randomized_MRR']+m['tail']['tie_randomized_MRR'])/2,
            alias_sensitivity_link_MRR=m['automatic_alias_filter_sensitivity']['link_MRR'],
            top1_schema_violation=(m['head']['top1_schema_violation_rate']+m['tail']['top1_schema_violation_rate'])/2,
            discriminative_coverage=(m['head']['all']['coverage']+m['tail']['all']['coverage'])/2,
            rule_target_support_coverage=(m['head']['target_rule_support_coverage']+m['tail']['target_rule_support_coverage'])/2 if family=='anyburl' else '',
            training_seconds=m['train_seconds'],evaluation_seconds=m['evaluation_seconds'],
            checkpoint=m['source_checkpoint_sha256']))
    assert len(metrics)==78,len(metrics)
    table('all_frozen_models.csv',metrics)
    groups=defaultdict(list)
    for r in metrics:groups[r['algorithm'],r['view'],r['fraction'],r['noise'],r['prototype']].append(r)
    summaries=[]
    for key,rr in sorted(groups.items()):
        row=dict(algorithm=key[0],view=key[1],fraction=key[2],noise=key[3],prototype=key[4],seeds=len(rr))
        for field in ['link_MRR','relation_MRR','link_Hits1','link_Hits10','typed_link_MRR','tie_randomized_link_MRR','alias_sensitivity_link_MRR','top1_schema_violation','discriminative_coverage']:
            row[field+'_mean']=float(np.mean([r[field] for r in rr]));row[field+'_sd']=float(np.std([r[field] for r in rr]))
        summaries.append(row)
    table('grouped_metrics.csv',summaries)
    save(RUN/'tables/grouped_metrics.json',summaries)
    # Predeclared paired contrast: anchor minus identical-initialization continuation.
    base_rows=read(RUN/'data/base_split.jsonl');group={r['claim_id']:r['group_id'] for r in base_rows}
    comparisons=[]
    for alternative in ['anchor','anchor_uniform']:
        by_group=defaultdict(list)
        for seed in [14112026,14112027,14112028]:
            a=read(RUN/'evaluation'/f'simkgc_G3_s{seed}_{alternative}'/'test/rankings.jsonl')
            b=read(RUN/'evaluation'/f'simkgc_G3_s{seed}_continue'/'test/rankings.jsonl')
            lookup={(r['id'],r['task']):r for r in b}
            for row in a:
                if row['task']=='relation':continue
                old=lookup[row['id'],row['task']]
                by_group[group[row['id']]].append(1/row['rank']-1/old['rank'])
        values=np.array([np.mean(v) for v in by_group.values()]);rng=np.random.default_rng(14112026)
        draws=np.array([np.mean(rng.choice(values,size=len(values),replace=True)) for _ in range(2000)])
        # Point estimate weights each query equally; CI resamples observed fact groups.
        all_values=[x for v in by_group.values() for x in v]
        comparisons.append(dict(contrast=alternative+' minus continue',query_weighted_delta=float(np.mean(all_values)),
             group_macro_delta=float(np.mean(values)),group_bootstrap_CI95=[float(x) for x in np.quantile(draws,[.025,.975])],
             groups=len(values),bootstrap_replicates=2000,interpretation='Internal automatic-label recovery, conditional on fixed split; not independent factual risk certificate'))
    save(RUN/'tables/prototype_paired_comparisons.json',comparisons)
    main_rows=[]
    for r in summaries:
        if r['fraction']!=1 or r['noise']!=0 or r['prototype']!='none':continue
        if r['algorithm']=='anyburl':
            display={'G1':'G1','G2':'G2','G3_bridge':'G3','G4_bridge':'G4'}.get(r['view'])
        else:display=r['view'] if r['view'] in ['G1','G2','G3','G4'] else None
        if display:main_rows.append(dict(r,display_view=display))
    table('baseline_G1_G4.csv',main_rows)
    table('candidate_scale_noise.csv',[r for r in summaries if r['fraction']!=1 or r['noise']!=0])
    table('prototype_ablation.csv',[r for r in summaries if r['prototype']!='none'])
    table('candidate_merge_ablation.csv',[r for r in summaries if r['view'] in ['G3','G3_bridge','G3_flat','G3_flat_filtered','G3_uniform','G3_labels','G4','G4_bridge'] and r['fraction']==1 and r['noise']==0 and r['prototype']=='none'])
    save(RUN/'tables/summary_complete.json',dict(models=len(metrics),groups=len(summaries),all_three_seed_rows_preserved=True,models_selected_by_validation_only=True))
    print('Summarized',len(metrics),'models',flush=True)


if __name__=='__main__':main()
