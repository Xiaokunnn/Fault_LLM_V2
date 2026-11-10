"""Evidence-interface regressions without treating an address pass as truth."""
import copy

from src.research_point_1_graph_evidence.stage03_schema_validation.native_evidence_binding_v2 import (
    exact_witness_roundtrip, screen_with_native_binding,
)


def page():
    return {"page_text":"Alpha other\n causes words\n damage text.", "page_width":600,
            "tables":[], "text_blocks":[
                {"block_id":"b1","text":"Alpha causes", "bbox":{"x0":30,"x1":200,"top":10,"bottom":20}},
                {"block_id":"b2","text":"damage.", "bbox":{"x0":30,"x1":200,"top":22,"bottom":32}},
            ]}


def assertion(quote="Alpha causes damage."):
    return {"evidence_text":quote,"evidence_unit_ids":[]}


def test_later_screen_accepts_the_same_native_quote_proof():
    p=page();before=copy.deepcopy(p)
    result=screen_with_native_binding(assertion(),p,lambda *_:["unbound_quote"])
    assert result["screen_flags"]==[]
    assert result["unique_native_proof_valid"]
    assert result["removed_flags"]==["unbound_quote"]
    assert p==before
    assert not result["semantic_support_certified"]


def test_non_quote_vetoes_survive_a_valid_native_proof():
    result=screen_with_native_binding(assertion(),page(),lambda *_:["unbound_quote","schema_type_direction","unknown_native_unit"])
    assert result["screen_flags"]==["schema_type_direction","unknown_native_unit"]


def test_changed_proposal_cannot_reuse_an_old_layout_pass():
    result=screen_with_native_binding(assertion("Alpha causes invented failure."),page(),lambda *_:["unbound_quote"])
    assert result["screen_flags"]==["unbound_quote"]
    assert not result["unique_native_proof_valid"]


def test_repeated_native_quote_is_not_a_unique_proof():
    p=page();p["text_blocks"].append({"block_id":"b3","text":"Alpha causes damage.",
            "bbox":{"x0":30,"x1":200,"top":34,"bottom":44}})
    result=screen_with_native_binding(assertion(),p,lambda *_:["unbound_quote"])
    assert result["native_path_count"]==2
    assert result["screen_flags"]==["unbound_quote"]


def test_empty_quote_cannot_be_rescued():
    assert not screen_with_native_binding(assertion(""),page(),lambda *_:["unbound_quote"])["unique_native_proof_valid"]


def test_native_addresses_are_real_not_reconstructed_page_offsets():
    result=screen_with_native_binding(assertion(),page(),lambda *_:["unbound_quote"])
    assert [w["block_id"] for w in result["source_witnesses"]]==["b1","b2"]
    assert all(exact_witness_roundtrip(page(),w) for w in result["source_witnesses"])
    bad={**result["source_witnesses"][0],"start":-1}
    assert not exact_witness_roundtrip(page(),bad)
