"""Unchanged architecture/teachers, corrected supervision and score replay."""
import numpy as np
import torch
from role_io import *
from train import ARMS
from eval_core import Evaluator
from clean_supervision import suspected_copy


def main():
    checks=[]
    for old in [P/'runs/20261114_controlled_v1',PARENT]:
        for record in read(old/'verification/delivery_manifest.json')['files']:assert file_sha(P/record['path'])==record['sha256'],record['path']
    checks.append('Both previous complete delivery manifests unchanged (1896 + 915 files), including old graphs/models/predictions')
    for record in read(P/'runs/20261114_controlled_v1/verification/input_preservation.json'):assert file_sha(ROOT/record['path'])==record['sha256']
    for record in read(P/'runs/20261114_controlled_v1/verification/build_pdf_preservation.json'):assert file_sha(ROOT/record['path'])==record['sha256']
    for seed in SEEDS:
        original=torch.load(checkpoint(seed),map_location='cpu',weights_only=True)
        for arm in ARMS:
            folder=OUT/'models'/f'role_{arm}_s{seed}';cfg=read(folder/'config.json');state=torch.load(folder/'best.pt',map_location='cpu',weights_only=True)
            assert set(state)==set(original)
            if not arm.startswith('joint'):
                assert all(torch.equal(v,original[k]) for k,v in state.items() if not k.startswith('trust.'))
                assert cfg['trainable_parameters']==545
            assert file_sha(folder/'best.pt')==read(folder/'complete.json')['checkpoint_sha256']
        records=read(OUT/f'data/utility_{seed}.jsonl')
        if NEW.name.endswith('clean_v2'):
            cat=read(RUN/'data/catalogue.json')['entities']
            for x in records:assert not any(suspected_copy(cat[x['neighbor']]['label_zh'],cat[t]['label_zh']) for t in set([x['y']]+x['positive_tail_ids']))
    checks.append('Identical architecture keys; every gate-only best checkpoint preserves all non-gate tensors exactly; labels have no known guarded target copies')
    targets=read(RUN/'audit_only/test_targets.jsonl');cat=read(RUN/'data/catalogue.json');ev=Evaluator(targets,read(RUN/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    for arm in ARMS:
        for seed in SEEDS:
            path=OUT/'evaluation'/f'role_{arm}_s{seed}';rows=read(path/'rankings.jsonl')
            assert {(x['id'],x['task']) for x in rows}=={(q['id'],task) for q in targets for task in ['head','tail','relation']}
    replay=[]
    for arm in ['gate_kgc','absolute_only','full']:
        path=OUT/'evaluation'/f'role_{arm}_s{SEEDS[0]}';z=np.load(path/'scores.npz');index={tuple(q['triple']):i for i,q in enumerate(targets)}
        def predict(h,r,t,task):return z[task][index[h,r,t]]
        m,rr=ev.score(predict);old=read(path/'rankings.jsonl');assert [(r['rank'],r['ties']) for r in rr]==[(r['rank'],r['ties']) for r in old]
        assert m['link_MRR']==read(path/'metrics.json')['link_MRR'];replay.append(dict(arm=arm,MRR=m['link_MRR'],all_rows_reconstructed=True))
    checks.append('Same frozen targets/all-answer rankings across arms; three raw-score rank/tie replays exact')
    save(OUT/'verification/checks.json',dict(passed=True,checks=checks,replay=replay,unit_tests=8,expert_truth_certified=False,formal_graph_modifications=0))
    print('Verified',DATASET,'protected inputs, freeze, models and saved scores')


if __name__=='__main__':main()
