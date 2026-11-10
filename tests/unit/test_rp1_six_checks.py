"""Audit helpers: conservative classification, literal addresses, immutable output."""
import copy
import pytest
from run_rp1_six_checks import blocking_endpoint_reasons,save,source_anchor,summarize


def test_dictionary_override_is_not_a_publication_failure():
    r={"chinese_canonicalization":{
        "head":{"graph_ready":True,"reasons":["model_terminology_id_overridden_by_dictionary"]},
        "tail":{"graph_ready":False,"reasons":["translation_status_not_graph_eligible"]}}}
    before=copy.deepcopy(r)
    assert blocking_endpoint_reasons(r)=={"tail":["translation_status_not_graph_eligible"]}
    assert r==before


def test_fully_eligible_endpoints_have_no_blocking_reasons():
    r={"chinese_canonicalization":{s:{"graph_ready":True,"reasons":[]} for s in ["head","tail"]}}
    assert blocking_endpoint_reasons(r)=={}


def test_literal_page_witness_roundtrips():
    p={"page_text":"Check  alignment\nafter piping.","tables":[],"text_blocks":[]}
    w=source_anchor(p,"alignment after piping.")
    assert p["page_text"][w["start"]:w["end"]]==w["text"]


def test_native_multiline_source_is_not_given_fake_page_offsets():
    p={"doc_id":"X","pdf_page_number":1,"page_text":"Alpha other causes words damage.","page_width":600,"tables":[],
       "text_blocks":[{"block_id":"b1","text":"Alpha causes","bbox":{"x0":30,"x1":200,"top":10,"bottom":20}},
                      {"block_id":"b2","text":"damage.","bbox":{"x0":30,"x1":200,"top":22,"bottom":32}}]}
    w=source_anchor(p,"Alpha causes damage.")
    assert w["kind"]=="native_multiline_path"
    assert "start" not in w
    assert [x["block_id"] for x in w["witnesses"]]==["b1","b2"]


def test_an_invented_source_quote_fails_closed():
    p={"doc_id":"X","pdf_page_number":1,"page_text":"Alpha.","page_width":600,"tables":[],"text_blocks":[]}
    with pytest.raises(ValueError,match="Not a source-bound quote"):
        source_anchor(p,"invented failure")


def test_generated_records_are_immutable(tmp_path):
    p=tmp_path/"record.json"
    save(p,{"x":1});save(p,{"x":1})
    before=p.read_bytes()
    with pytest.raises(ValueError,match="Refuse overwrite"):save(p,{"x":2})
    assert p.read_bytes()==before


def test_dedup_inventory_does_not_imply_semantic_equivalence():
    r={"head_type":"Component","head_surface":"Bearing","head_canonical_zh":"轴承","relation":"maintained_by",
       "tail_type":"MaintenanceAction","tail_surface":"lubricate","tail_canonical_zh":"润滑",
       "doc_id":"MP001","pdf_page_number":1}
    data=summarize([{**r,"conditions":["cold"]},{**r,"conditions":["hot"]}])
    assert data["evidence_records"]==2
    assert data["distinct_source_relation_keys"]==1
    assert data["explicit_conditions_field"]==2
    assert data["explicit_modality_field"]==0
