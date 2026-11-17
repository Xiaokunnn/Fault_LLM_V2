"""Observed contribution/structure checks after all frozen evaluations."""
from collections import defaultdict,Counter
import numpy as np
import torch
from collab_io import *
from summarize_collab import table
from model import Collaboration


def main():
    rows=[];sensitivity=[]
    for dataset in ['cold','structured']:
        root=STUDY/dataset;assert (root/'evaluation/complete.json').exists();cat=read(root/'data/catalogue.json');R=len(cat['relations'])
        targets=read(root/'audit_only/test_targets.jsonl');actual={(h,r) for q in targets for h,r in [(q['triple'][0],q['triple'][1]),(q['triple'][2],q['triple'][1]+R)]}
        for p in sorted((root/'evaluation').glob('collab*/context_contributions.jsonl')):
            name=p.parent.name;model=root/'models'/name;cfg=read(model/'config.json');contrib=read(p)
            chosen=[c for c in contrib if (c['head'],c['directed_relation']) in actual]
            candidate=[x for c in chosen for x in c['contexts'] if not x['is_base']]
            byedge=defaultdict(list)
            for c in contrib:
                for edge in c['contexts']:
                    if not edge['is_base']:byedge[c['head'],edge['edge_id']].append(edge['task_gate'])
            seed_all(cfg['seed']);initial=Collaboration(R,variant=cfg['variant']);state=torch.load(model/'best.pt',map_location='cpu',weights_only=True)
            delta=float(sum(((v-state[k])**2).sum() for k,v in initial.state_dict().items() if k.startswith('trust.'))**.5)
            rows.append(dict(dataset=dataset,model=name,variant=cfg['variant'],seed=cfg['seed'],queries=len(chosen),
                query_context_coverage=float(np.mean([bool(c['contexts']) for c in chosen])),candidate_query_coverage=float(np.mean([any(not x['is_base'] for x in c['contexts']) for c in chosen])),
                mean_null=float(np.mean([c['null'] for c in chosen])),mean_residual_norm=float(np.mean([c['residual_norm'] for c in chosen])),
                candidate_gate_mean=float(np.mean([x['task_gate'] for x in candidate])) if candidate else None,
                candidate_gate_sd=float(np.std([x['task_gate'] for x in candidate])) if candidate else None,
                mean_cross_relation_gate_sd=float(np.mean([np.std(v) for v in byedge.values() if len(v)>1])) if any(len(v)>1 for v in byedge.values()) else None,
                selected_trust_parameter_change_L2=delta,best_epoch=read(model/'complete.json')['best_epoch']))
        for variant in ['drop_candidates','drop_all','shuffle_edge_relations']:
            for seed in SEEDS:
                m=read(root/'interventions'/f'{variant}_s{seed}'/'metrics.json')
                sensitivity.append(dict(dataset=dataset,intervention=variant,seed=seed,MRR=m['link_MRR'],
                    Hits1=(m['head']['all']['Hits1']+m['tail']['all']['Hits1'])/2,Hits10=(m['head']['all']['Hits10']+m['tail']['all']['Hits10'])/2))
    table('contribution_diagnostics.csv',rows);table('frozen_weight_interventions.csv',sensitivity)
    print('Saved learned-gate and frozen-weight intervention diagnostics',flush=True)


if __name__=='__main__':main()
