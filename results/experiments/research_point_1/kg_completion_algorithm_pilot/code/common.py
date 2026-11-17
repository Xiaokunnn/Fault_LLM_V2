"""Shared isolated pilot IO and ranking, with no graph publication side effects."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import os
import sys
import numpy as np
sys.dont_write_bytecode=True

PILOT=Path(__file__).resolve().parents[1]
ROOT=PILOT.parents[3]
RUN=PILOT/'runs'/os.environ.get('RP1_KGC_RUN','20261114_controlled_v1')
assert RUN.resolve().is_relative_to((PILOT/'runs').resolve())
SEEDS=[14112026,14112027,14112028]


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def read(path):
    p=Path(path)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.suffix=='.jsonl' else json.loads(p.read_text())


def save(path,value,replace=False):
    p=Path(path)
    if not p.resolve().is_relative_to(PILOT.resolve()):raise ValueError('Output escaped pilot')
    data=value if isinstance(value,str) else ''.join(canonical(x)+'\n' for x in value) if p.suffix=='.jsonl' else json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if p.exists() and not replace:
        if p.read_text()!=data:raise ValueError('Preserve existing output: '+str(p))
        return
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)


def seed_all(seed):
    import torch
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(2)


def truths(triples):
    tail=defaultdict(set);head=defaultdict(set);rel=defaultdict(set)
    for h,r,t in triples:
        tail[h,r].add(t);head[r,t].add(h);rel[h,t].add(r)
    return tail,head,rel


def rank(scores,target,filtered=(),allowed=None):
    """Average rank over exact/numerically equal score ties, target retained."""
    scores=np.asarray(scores,dtype=np.float64).copy()
    if not np.isfinite(scores).all():raise ValueError('Nonfinite model score')
    keep=np.ones(len(scores),dtype=bool)
    if allowed is not None:
        keep[:]=False;keep[list(allowed)]=True
    keep[list(filtered)]=False;keep[target]=True
    target_score=scores[target]
    equal=np.isclose(scores,target_score,rtol=0,atol=1e-8)&keep
    greater=(scores>target_score+1e-8)&keep
    return float(1+greater.sum()+(equal.sum()-1)/2),int(equal.sum())


def rank_summary(rows):
    if not rows:return dict(n=0,MRR=None,Hits1=None,Hits3=None,Hits10=None,coverage=None)
    ranks=np.array([r['rank'] for r in rows])
    return dict(n=len(rows),MRR=float(np.mean(1/ranks)),Hits1=float(np.mean(ranks<=1)),
                Hits3=float(np.mean(ranks<=3)),Hits10=float(np.mean(ranks<=10)),
                mean_rank=float(np.mean(ranks)),coverage=float(np.mean([r['covered'] for r in rows])),
                tied_queries=int(sum(r['ties']>1 for r in rows)))


def aggregate(rows):
    return {task:{'all':rank_summary([r for r in rows if r['task']==task]),
                  'warm':rank_summary([r for r in rows if r['task']==task and r['endpoint_status']=='warm']),
                  'one_cold':rank_summary([r for r in rows if r['task']==task and r['endpoint_status']=='one_cold']),
                  'both_cold':rank_summary([r for r in rows if r['task']==task and r['endpoint_status']=='both_cold'])}
            for task in ['head','tail','relation']}
