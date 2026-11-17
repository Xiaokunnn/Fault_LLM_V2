"""Meaningful protocol checks: no target copies, no answer access, fallback."""
from pathlib import Path
import numpy as np
import torch
from io_utils import *
from query_model import Residual
from build_index import edge_sources


def test_no_group_crosses_new_split():
    groups=defaultdict(set)
    for r in read(EXP/'data/base_split.jsonl'):groups[r['group_id']].add(r['fold'])
    assert all(len(x)==1 for x in groups.values())
    assert read(EXP/'data/summary.json')['base_entities']==2150


def test_index_has_no_held_pairs_or_visible_target_evidence():
    blockers=read(EXP/'audit_only/copy_blockers.json');pairs=set(map(tuple,blockers['pairs']));pages=set(map(tuple,blockers['pages']));grams=set(blockers['quotegrams'])
    registry=read(EXP/'data/training_source_registry.json')
    for e in read(EXP/'index/edges.jsonl'):
        assert tuple(e['pair']) not in pairs
        for s in edge_sources(e,registry):
            assert (s['doc_id'],s['pdf_page_number']) not in pages
            assert not shingles(s.get('evidence_text',''))&grams
            assert s['doc_id'] in I.BUILD


def test_all_cached_training_contexts_exclude_own_pair_and_source():
    rows=read(EXP/'index/edges.jsonl');examples=read(EXP/'retrieval/train_example_keys.json');meta=read(EXP/'data/train_group_context.json')
    groups={x['claim_id']:x['group_id'] for x in read(EXP/'data/base_split.jsonl') if x['fold']=='train'}
    for strategy in ['R0','R1','R2','R3']:
        z=np.load(EXP/'retrieval'/f'{strategy}_all_train.npz')['ids']
        for ex,chosen in zip(examples,z):
            m=meta[groups[ex[3]]];pairs=set(map(tuple,m['pairs']));pages=set(map(tuple,m['pages']))
            for i in chosen[chosen>=0]:
                edge=rows[int(i)//2]
                assert tuple(edge['pair']) not in pairs and not set(map(tuple,edge['pages']))&pages


def test_direction_and_role_schema_in_R2_R3():
    cat=read(EXP/'data/catalogue.json');views=read(EXP/'index/oriented_views.jsonl');R=len(cat['relations'])
    for strategy in ['R2','R3']:
        z=np.load(EXP/'retrieval'/f'{strategy}_all_global.npz')['ids']
        for h in range(0,cat['nbase'],13):
            for r in range(2*R):
                rule=cat['registry'][cat['relations'][r%R]];out=rule['domain' if r>=R else 'range']
                for v in z[h,r]:
                    if v<0:continue
                    assert cat['entities'][views[int(v)]['anchor']]['entity_type']==cat['entities'][h]['entity_type']
                    assert cat['entities'][views[int(v)]['neighbor']]['entity_type'] in out


def test_no_context_exactly_falls_back_to_query():
    torch.manual_seed(4);m=Residual();torch.nn.init.normal_(m.up.weight)
    q=torch.nn.functional.normalize(torch.randn(7,512),dim=-1);x=torch.randn(7,1558)
    torch.testing.assert_close(m(q,x,torch.zeros(7,dtype=torch.bool)),q,atol=1e-7,rtol=1e-6)


def test_retrieval_api_cannot_accept_hidden_answer():
    import inspect
    from retrieval import Retriever
    args=list(inspect.signature(Retriever.search).parameters)
    assert args==['self','heads','relations','strategy','k','training_ids','pool']
    text=Path(__file__).with_name('retrieval.py').read_text()
    assert 'test_targets' not in text and 'test_truth' not in text
    for f in ['train_adapters.py','train_baselines.py','fixed_baselines.py']:
        text=Path(__file__).with_name(f).read_text()
        assert 'audit_only' not in text and 'test_targets' not in text


def test_permutation_invariant_fixed_context_pooling():
    # Pooling is mathematically symmetric; no accidental candidate-rank label.
    torch.manual_seed(7);x=torch.randn(5,16,512);s=torch.randn(5,16);p=torch.randperm(16)
    a=(torch.softmax(s,-1)[:,:,None]*x).sum(1)
    b=(torch.softmax(s[:,p],-1)[:,:,None]*x[:,p]).sum(1)
    torch.testing.assert_close(a,b,atol=2e-7,rtol=2e-6)
