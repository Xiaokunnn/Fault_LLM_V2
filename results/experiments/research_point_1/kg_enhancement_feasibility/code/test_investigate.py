import copy
import pytest
import investigate as m

def test_source_keys_do_not_discard_evidence():
    r=dict(doc_id="MP001",pdf_page_number=1,head_surface="A",relation="causes",tail_surface="B",evidence_text="A causes B")
    assert m.source_key(r)!=m.source_key({**r,"evidence_text":"A may cause B"})

def test_canonical_relation_key_is_not_condition_equivalence():
    r=dict(head_type="Component",head_canonical_zh="轴承",relation="maintained_by",tail_type="MaintenanceAction",tail_canonical_zh="润滑",conditions=["cold"])
    assert m.relation_key(r)==m.relation_key({**r,"conditions":["hot"]})

def test_case_and_unicode_normalization():
    assert m.norm("  ＰＵＭＰ  ")=="pump"

def test_morphology_is_only_a_candidate_signal():
    assert m.morphological("wear rings")==m.morphological("wear ring")
    assert m.morphological("loss")=="loss"

def test_literal_qualification_cues_are_not_semantic_labels():
    assert "negation" in m.flags("There is no pressure.")
    assert "prohibition" not in m.flags("There is no pressure.",m.SOURCE_CUES)

def test_e1_exact_offsets():
    p={"page_text":"A causes B.","text_blocks":[],"tables":[]}
    r={"evidence_start":0,"evidence_end":11,"evidence_text":"A causes B.","evidence_level":"E1"}
    before=copy.deepcopy(p)
    result=m.locate_record(r,p)
    assert result["contiguous_offset_exact"] and result["some_address_verified"]
    assert not result["semantic_support_certified"] and p==before

def test_wrong_offsets_do_not_count_as_proof():
    r={"evidence_start":0,"evidence_end":5,"evidence_text":"invented","evidence_level":"E1"}
    assert not m.locate_record(r,{"page_text":"actual","tables":[]})["some_address_verified"]

def test_real_cell_and_bbox_are_preserved_without_fake_offsets():
    c={"cell_id":"c","text":"wear","bbox":{"x0":1,"top":2,"x1":3,"bottom":4}}
    p={"page_text":"","tables":[{"rows":[{"cells":[c]}]}]}
    r={"evidence_level":"E2","evidence_units":[{"cell_id":"c","text":"wear","bbox":[1,2,3,4],"start":-1,"end":-1}]}
    x=m.locate_record(r,p)
    assert x["nested_units_exact"]==1 and x["nested_bbox_exact"]==1
    assert not x["contiguous_offset_present"]

def test_unknown_unit_never_rescued():
    r={"expansion_source_witnesses":[{"block_id":"missing","start":0,"end":3,"text":"foo"}]}
    assert m.locate_record(r,{"page_text":"foo"})["native_witness_exact"]==0

def test_output_immutable_and_scoped(tmp_path,monkeypatch):
    monkeypatch.setattr(m,"TASK",tmp_path)
    p=tmp_path/"x.json";m.save(p,{"x":1});m.save(p,{"x":1})
    with pytest.raises(ValueError,match="Immutable"):m.save(p,{"x":2})
    with pytest.raises(ValueError,match="escaped"):m.save(tmp_path.parent/"outside.json",{})
