import numpy as np
import torch
from common import rank,read,RUN
from train_complex import Complex,callback


def test_complex_all_queries_equal_scalar_score():
    model=Complex(7,3,dim=4,seed=11);model.eval()
    predict=callback(model,{'nbase':7})
    for task,n in [('tail',7),('head',7),('relation',3)]:
        h,r,t=1,2,3;expected=[]
        for i in range(n):
            q=[h,r,t];q[{'head':0,'relation':1,'tail':2}[task]]=i
            expected.append(float(model(*[torch.tensor([v]) for v in q]).detach()))
        np.testing.assert_allclose(predict(h,r,t,task),expected,atol=1e-7)


def test_average_ties_and_filtering():
    assert rank([0.,0.,0.,0.],1)==(2.5,4)
    assert rank([2.,1.,1.,0.],1,filtered=[0,2])==(1.,1)
    assert rank([2.,1.,1.,0.],1)==(2.5,2)


def test_no_duplicate_base_across_folds():
    rows=read(RUN/'data/base_split.jsonl');seen={}
    for r in rows:
        if r['group_id'] in seen:assert seen[r['group_id']]==r['fold']
        seen[r['group_id']]=r['fold']


def test_train_validation_targets_separated():
    train={r['id'] for r in read(RUN/'data/train_base.jsonl')}
    valid={r['id'] for r in read(RUN/'data/validation_targets.jsonl')}
    test={r['id'] for r in read(RUN/'audit_only/test_targets.jsonl')}
    assert not train&valid and not train&test and not valid&test


def test_text_source_pages_are_blocked_and_document_independent():
    blocked={tuple(p) for p in read(RUN/'audit_only/blocked_text_pages.json')}
    for row in read(RUN/'data/training_safe_context_units.jsonl'):
        assert row['doc_id']!='MP022'
        assert (row['doc_id'],row['page']) not in blocked


def test_schema_negative_rows_never_have_positive_weight():
    for row in read(RUN/'data/training_candidate_edges.jsonl'):
        if not row['legal']:assert row['weight']==0


def test_training_modules_do_not_access_test_or_provenance_files():
    from pathlib import Path
    for name in ['train_complex.py','train_simkgc.py','views.py']:
        code=Path(__file__).with_name(name).read_text()
        for forbidden in ["RUN/'audit_only'",'test_targets.jsonl','base_split.jsonl','base_source_records.jsonl','independent_document.jsonl']:
            assert forbidden not in code


def test_reference_prototype_anchor_matches_same_seed_base():
    from common import SEEDS,file_sha
    for seed in SEEDS:
        expected=file_sha(RUN/'models'/f'simkgc_G1_s{seed}'/'best.pt')
        for variant in ['continue','anchor','anchor_uniform']:
            path=RUN/'models'/f'simkgc_G3_s{seed}_{variant}'/'complete.json'
            if path.exists():assert read(path)['reference_checkpoint_sha256']==expected
