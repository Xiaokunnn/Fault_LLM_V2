"""Regression guard for the actual source schema, not assumed field names."""
from io_utils import *
from build_index import edge_sources
import torch


def test_native_role_feature_matches_actual_evidence_units_role():
    rows=read(EXP/'index/edges.jsonl');registry=read(EXP/'data/training_source_registry.json')
    corrected=torch.load(EXP/'native_role_correction/vectors.pt',map_location='cpu',weights_only=True)
    positive=0
    for i,e in enumerate(rows):
        roles=[u.get('role') for s in edge_sources(e,registry) for u in s.get('evidence_units') or []]
        expected=float(any(r and r!='unclassified' for r in roles))
        assert float(corrected['flags'][2*i,5])==expected
        assert float(corrected['flags'][2*i+1,5])==expected
        positive+=int(expected)
    assert positive==220


def test_corrected_encoder_outputs_keep_index_and_answer_dimensions():
    original=torch.load(EXP/'index/vectors.pt',map_location='cpu',weights_only=True)
    corrected=torch.load(EXP/'native_role_correction/vectors.pt',map_location='cpu',weights_only=True)
    assert corrected['semantic'].shape==original['semantic'].shape==(9320,512)
    assert torch.isfinite(corrected['semantic']).all()
    assert read(EXP/'data/catalogue.json')['nbase']==2150
    assert read(EXP/'native_role_correction/verification.json')['identical_no_evidence_features']
