"""Validation-only full-universe selection; preserve early top200 diagnostics."""
from common import RUN,read,save,file_sha
from run_anyburl import apply,parse
from eval_core import Evaluator
import numpy as np


def main():
    cat=read(RUN/'data/catalogue.json');validation=Evaluator.validation(cat)
    for folder in sorted((RUN/'models').glob('anyburl_*')):
        if not (folder/'complete.json').exists() or (folder/'selection_full.json').exists():continue
        best=-1;chosen=None;results=[]
        for snapshot in [10,30]:
            output=folder/f'valid_full_{snapshot}.predictions'
            if output.exists():scores=parse(output,cat);cost=0.
            else:scores,cost=apply(folder,folder/'train.tsv',folder/f'rules-{snapshot}',[q['triple'] for q in validation.targets],f'valid_full_{snapshot}',cat)
            def predict(h,r,t,task):return np.zeros(len(cat['relations'])) if task=='relation' else scores.get(((h,r,t),task),np.zeros(cat['nbase']))
            predict.symbolic=True
            metrics,rows=validation.score(predict)
            results.append(dict(snapshot=snapshot,validation=metrics,application_seconds=cost))
            save(folder/f'validation_full_{snapshot}.jsonl',rows)
            if metrics['link_MRR']>best:best=metrics['link_MRR'];chosen=snapshot
        save(folder/'selection_full.json',dict(best_snapshot=chosen,validation_link_MRR=best,results=results,
             reason='Full entity universe output, no top200 censoring; validation only; earlier raw predictions retained',
             rules_sha256=file_sha(folder/f'rules-{chosen}')))
        print(folder.name,'full validation',best,flush=True)


if __name__=='__main__':main()
