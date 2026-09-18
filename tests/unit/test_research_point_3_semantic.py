from types import SimpleNamespace
import pytest
import torch

from src.research_point_3.contracts import CARD_SLOT_ROLES
from src.research_point_3.features import evidence_vector, query_vector, hash_text
from src.research_point_3.semantic_features import query_text, evidence_text, evidence_metadata, optimistic_break_even, FrozenSemanticEncoder, QUERY_INSTRUCTION
from scripts.benchmark_rp3_semantic import assemble_inputs


def test_feature_text_excludes_ids_split_and_labels_and_preserves_metadata():
    query = SimpleNamespace(question_zh='泵异常如何处理', fault_name_zh='汽蚀', requested_role=CARD_SLOT_ROLES[0],
                            scenario_id='train-sensitive', query_id='label-derived')
    assert hash_text(query_text(query)) == query_vector(query)
    before = query_text(query); query.scenario_id='validation'; query.query_id='different'
    assert query_text(query) == before
    r = SimpleNamespace(head_label_zh='泵',relation='表现',tail_label_zh='异常',evidence_text='原始证据',
                        role=CARD_SLOT_ROLES[1],fault_class_ids=['F1'],evidence_contract_confidence=.8,
                        doc_id='MP001',evidence_id='private-id',teacher_score=.99)
    assert hash_text(evidence_text(r)) == evidence_vector(r)[:256]
    assert evidence_metadata(r) == evidence_vector(r)[256:]
    text, meta = evidence_text(r), evidence_metadata(r)
    r.teacher_score=.01; r.doc_id='different'; r.evidence_id='new-id'
    assert (evidence_text(r), evidence_metadata(r)) == (text,meta)


def test_encoder_uses_cls_l2_prefix_and_declared_truncation_without_gradients():
    calls = []
    class Tokenizer:
        def __call__(self, texts, **kw):
            calls.append((texts,kw)); return {'input_ids':torch.zeros(len(texts),3,dtype=torch.long)}
    class Model:
        def __call__(self, **kw):
            assert not torch.is_grad_enabled()
            return SimpleNamespace(last_hidden_state=torch.tensor([[[3.,4.],[100.,0.],[100.,0.]]]).expand(kw['input_ids'].shape[0],-1,-1))
    encoder = FrozenSemanticEncoder.__new__(FrozenSemanticEncoder)
    encoder.tokenizer=Tokenizer();encoder.model=Model()
    assert torch.allclose(torch.tensor(encoder.encode(['问题','另一个'],query=True,batch_size=1)), torch.tensor([[.6,.8],[.6,.8]]))
    assert calls[0][0]==[QUERY_INSTRUCTION+'问题']
    assert calls[0][1]==dict(padding=True,truncation=True,max_length=512,return_tensors='pt')
    encoder.encode(['原文']);assert calls[-1][0]==['原文']


def test_runtime_assembly_does_not_read_unavailable_evidence_and_pads_closed():
    batch=assemble_inputs([.1,.2],['valid','unavailable-not-in-memory'],[True,False],2,{'valid':torch.tensor([1.,2.,3.])},width=4)
    assert batch['availability_mask'].tolist()==[[True,False,False,False]]
    assert torch.equal(batch['candidate_features'][0,1:],torch.zeros(3,3))
    with pytest.raises(KeyError):assemble_inputs([0.],['unknown'],[True],1,{'known':torch.ones(3)})
    with pytest.raises(ValueError):assemble_inputs([0.],['known'],[],1,{'known':torch.ones(3)})


def test_break_even_matches_two_oracle_costs_and_exposes_no_call_saving():
    result=optimistic_break_even(queries=8,delta_correct=2,delta_local_ms=3.)
    threshold=result['teacher_cost_threshold_ms'];assert threshold==12.
    for teacher_ms in (5.,12.,20.):
        old=1+teacher_ms*(7-2)/8
        new=4+teacher_ms*(7-4)/8
        assert (new<old)==(teacher_ms>threshold)
    for dg in (0,-1):
        assert optimistic_break_even(queries=8,delta_correct=dg,delta_local_ms=3.)['dominated_in_homogeneous_oracle_model']
    with pytest.raises(ValueError):optimistic_break_even(queries=0,delta_correct=1,delta_local_ms=1.)
