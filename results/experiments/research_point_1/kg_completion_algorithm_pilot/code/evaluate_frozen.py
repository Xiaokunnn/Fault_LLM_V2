"""Test-only release after all selected training jobs are sealed. Never fits models."""
import argparse
import time
import numpy as np
import torch
from common import RUN,read,save,file_sha
from eval_core import Evaluator


def eval_folder(folder,fold='test'):
    out=RUN/'evaluation'/folder.name/fold
    if (out/'metrics.json').exists():return read(out/'metrics.json')
    config=read(folder/'config.json');cat=read(RUN/'data/catalogue.json');view=config['view']['view']
    targets=read(RUN/'audit_only'/('test_targets.jsonl' if fold=='test' else 'document_holdout_targets.jsonl'))
    known=read(RUN/'audit_only/test_truth.json')
    # Blocking aliases are deliberately overinclusive; they are not semantic Gold.
    # Primary test filtering therefore uses only exact serialized entity identities.
    ev=Evaluator(targets,known,cat,list(range(cat['nbase'])))
    alias_sensitivity=Evaluator(targets,known,cat,read(RUN/'data/filter_entity_aliases.json'))
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2)
    start=time.perf_counter()
    if folder.name.startswith('complex_'):
        from train_complex import Complex,callback
        state=torch.load(folder/'best.pt',map_location=device,weights_only=True)
        model=Complex(len(cat['entities']),len(cat['relations']),config['dim'],state.get('text'),config['seed']).to(device)
        model.load_state_dict(state);model.eval();predict=callback(model,cat)
    elif folder.name.startswith('simkgc_'):
        from train_simkgc import setup,callback
        model,tokenizer,descriptions,_=setup(view,cat);model=model.to(device)
        model.load_state_dict(torch.load(folder/'best.pt',map_location=device,weights_only=True));model.eval()
        predict=callback(model,tokenizer,descriptions,cat,targets,device)
    else:
        from run_anyburl import apply,parse
        selection=read(folder/'selection_full.json');rules=folder/f'rules-{selection["best_snapshot"]}'
        link_scores,_=apply(folder,folder/'train.tsv',rules,[q['triple'] for q in targets],fold+'_full',cat)
        queries=[(q['triple'][0],r,q['triple'][2]) for q in targets for r in range(len(cat['relations']))]
        relation_scores,_=apply(folder,folder/'train.tsv',rules,queries,fold+'_relation_queries',cat)
        def predict(h,r,t,task):
            if task=='relation':
                return np.array([max(relation_scores.get(((h,j,t),'tail'),np.zeros(cat['nbase']))[t],
                                         relation_scores.get(((h,j,t),'head'),np.zeros(cat['nbase']))[h]) for j in range(len(cat['relations']))])
            return link_scores.get(((h,r,t),task),np.zeros(cat['nbase']))
        predict.symbolic=True
    # Preserve every raw score for exact offline ranking reproduction.
    scores={task:np.stack([predict(*q['triple'],task) for q in targets]) for task in ['head','tail','relation']}
    symbolic=getattr(predict,'symbolic',False)
    index={tuple(q['triple']):i for i,q in enumerate(targets)}
    def frozen(h,r,t,task):return scores[task][index[h,r,t]]
    frozen.symbolic=symbolic
    metrics,rows=ev.score(frozen)
    alias_metrics,alias_rows=alias_sensitivity.score(frozen)
    metrics['automatic_alias_filter_sensitivity']=alias_metrics
    for exact_row,alias_row in zip(rows,alias_rows):exact_row['automatic_alias_rank']=alias_row['rank']
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'scores.npz',**scores)
    save(out/'rankings.jsonl',rows)
    complete=read(folder/'complete.json')
    metrics.update(model=folder.name,view=view,seed=config['seed'],fold=fold,evaluation_seconds=time.perf_counter()-start,
         train_seconds=complete['seconds'] if not complete.get('learn_wall_unavailable') else None,
         prototype=config.get('prototype','none'),proxy_only=True,
         ranking='Primary: same 2150 exact base entity IDs/15 relations; exact known-base filtering; average 1e-8 tied rank. Automatic blocking-alias filtering is sensitivity only. Validation selection retained its predeclared automatic-alias proxy.',
         relation_score='AnyBURL: max of author head/tail target scores across 15 predicate queries; neural: raw original scoring function',
         source_checkpoint_sha256=file_sha(folder/'best.pt') if (folder/'best.pt').exists() else read(folder/'selection_full.json')['rules_sha256'])
    save(out/'metrics.json',metrics)
    print(folder.name,fold,'link_MRR',metrics['link_MRR'],flush=True)
    return metrics


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--fold',default='test');args=p.parse_args()
    assert (RUN/'configs/test_release.json').exists(),'Test gate not released'
    eval_folder(RUN/'models'/args.folder,args.fold)
