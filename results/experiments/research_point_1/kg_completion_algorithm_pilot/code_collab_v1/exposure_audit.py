"""Actual training/evaluation neighbor exposure, never used to select models."""
from collections import Counter
import numpy as np
from collab_io import *
from model import Neighborhood


def main():
    assert (RUN/'evaluation/complete.json').exists()
    graph=Neighborhood('full',SEEDS[0]);results={};used=set()
    for fold,path in [('train',RUN/'data/train_base.jsonl'),('valid',RUN/'data/validation_targets.jsonl'),('test',RUN/'audit_only/test_targets.jsonl')]:
        records=read(path);counts=[];candidates=[];base=[]
        for x in records:
            for h in [x['triple'][0],x['triple'][2]]:
                entries=graph.entries(h,x['id'] if fold=='train' else None)
                counts.append(len(entries));candidates.append(sum(not e['is_base'] for _,_,e in entries));base.append(sum(e['is_base'] for _,_,e in entries))
                if fold=='train':used.update(e['edge_id'] for _,_,e in entries if not e['is_base'])
        results[fold]=dict(head_tail_queries=len(counts),any_context_fraction=float(np.mean(np.array(counts)>0)),candidate_context_fraction=float(np.mean(np.array(candidates)>0)),
            base_context_fraction=float(np.mean(np.array(base)>0)),mean_context_count=float(np.mean(counts)),mean_candidate_count=float(np.mean(candidates)))
    all_candidates=[e for e in graph.rows if not e['is_base']]
    results['candidate_training_exposure']=dict(legal_pool=len(all_candidates),distinct_used=len(used),unused=len(all_candidates)-len(used),
        unused_reason='Not incident to a supervised base query, or source/self exclusion, or max16 cap; not a semantic rejection')
    save(RUN/'analysis/exposure_audit.json',results)
    print(DATASET,results,flush=True)


if __name__=='__main__':main()
