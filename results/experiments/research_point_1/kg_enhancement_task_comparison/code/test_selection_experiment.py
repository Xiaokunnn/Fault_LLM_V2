"""Contracts and negative controls, not tests of real-world diagnostic truth."""
from collections import Counter
import copy
import json
from pathlib import Path
import sys

import pytest

from inputs import Inputs,GRAPH,load,native_units,digest
from selection_screen import OUT,OLD,read,schema_view,frozen_validators
from selection_discovery import topology_candidates
from selection_join import reference_join
from selection_overlay import SANDBOX


@pytest.fixture(scope="module")
def data():return load()


def assert_proof(p,d):
    page=d["pages"][p["doc_id"],p["page"]]
    assert p["document_sha256"].lower()==page["document_sha256"].lower()
    assert p["page_text_sha256"]==page["page_text_sha256"]
    s=p["proof"]
    if s["kind"]=="native_multiunit_quote":
        witnesses=s["witnesses"]
    else:witnesses=[s]
    for w in witnesses:
        text=page["page_text"] if w["kind"]=="page_span" else native_units(page)[w.get("cell_id") or w.get("block_id")]["text"]
        assert 0<=w["start"]<w["end"]<=len(text)
        assert text[w["start"]:w["end"]]==w["text"]


def test_all_delta_source_addresses_roundtrip(data):
    rows=read(SANDBOX/"delta_assertions.jsonl")
    assert len(rows)==22
    for r in rows:
        assert r["source_proofs"]
        for p in r["source_proofs"]:assert_proof(p,data)


def test_all_qualifier_addresses_roundtrip(data):
    for r in read(SANDBOX/"qualifier_overlays.jsonl"):
        for p in r["source_proofs"]:assert_proof(p,data)


def test_all_auxiliary_frame_addresses_roundtrip(data):
    for r in read(SANDBOX/"auxiliary_source_frames.jsonl"):
        for p in r["source_proofs"]:assert_proof(p,data)


def test_topology_addresses_and_no_direct_admission(data):
    rows=read(OUT/"review/topology_decisions.jsonl")
    assert len(rows)==6 and all(not r["trusted_direct_edge_added"] for r in rows)
    assert Counter(r["verdict"] for r in rows)=={"source_supported_mediated_chain_not_new_direct_relation":3,"insufficient_evidence_for_direct_relation":3}
    for r in rows:
        for p in r["source_proofs"]:assert_proof(p,data)


@pytest.mark.parametrize("mutation",["text","offset","hash","page"])
def test_source_integrity_negative_controls(data,mutation):
    p=copy.deepcopy(read(SANDBOX/"delta_assertions.jsonl")[0]["source_proofs"][0])
    if mutation=="text":p["proof"]["text"]+=" fabricated"
    elif mutation=="offset":p["proof"]["end"]+=1
    elif mutation=="hash":p["page_text_sha256"]="0"*64
    else:p["page"]+=1
    with pytest.raises((AssertionError,KeyError)):assert_proof(p,data)


def test_no_other_graph_or_heldout_data_reads():
    m=read(OUT/"input_manifest.json")
    assert m["base_graph"]=="expanded1456" and m["no_other_graphs_loaded"]
    assert all(not any(x in p for x in ["MP008.","MP009.","MP010.","MP011.","MP012.","MP013.","MP014."]) for p in m["data_hashes"])
    for path in ["data/kg/marine_pump/triples/KG_v1_validated/triples.jsonl","data/interim/parsed_pages/corpus_v2/MP008.pages.v2.jsonl"]:
        with pytest.raises(ValueError):Inputs().raw(path)


def test_old_run_immutable_hashes():
    m=read(Path(__file__).resolve().parents[1]/"completion_manifest.json")
    assert all(digest((Path(__file__).resolve().parents[1]/p).read_bytes())==sha for p,sha in m["file_hashes_sha256"].items())


def test_original_base_assertions_preserved(data):
    base=data["graph"]["evidence_assertions"]
    assert read(SANDBOX/"evidence_assertions_additive.jsonl")[:1456]==base
    assert len(base)==1456


def test_claims_and_entities_closed_no_new_orphans(data):
    es=read(SANDBOX/"entities.jsonl");cs=read(SANDBOX/"claims.jsonl");ass=read(SANDBOX/"evidence_assertions_additive.jsonl")
    eids={x["entity_id"] for x in es};cids={x["claim_id"] for x in cs}
    assert all(c[side+"_entity_id"] in eids for c in cs for side in ["head","tail"])
    assert all(a["claim_id"] in cids for a in ass)
    new={x["entity_id"] for x in es if x["entity_id"].startswith("TE-")}
    used={c[side+"_entity_id"] for c in cs for side in ["head","tail"]}
    assert new<=used
    assert len(cids)==len(cs)==1419


def test_no_duplicate_core_or_assertion_ids():
    cs=read(SANDBOX/"claims.jsonl");ass=read(SANDBOX/"evidence_assertions_additive.jsonl")
    assert len({(c['head_entity_id'],c['relation'],c['tail_entity_id']) for c in cs})==len(cs)
    assert len({a['assertion_id'] for a in ass})==len(ass)==1478


def test_A_semantic_duplicate_sources_not_multiple_facts():
    a=[r for r in read(SANDBOX/"delta_assertions.jsonl") if r["case_id"] in ["A-RAW-03430","A-RAW-03881"]]
    assert len(a)==2 and len({r['sandbox_claim_id'] for r in a})==1
    assert len({r['source_family_id'] for r in a})==1
    assert a[0]['qualifiers']['equipment']!=a[1]['qualifiers']['equipment']


def test_source_additions_existing_claims_not_new_facts():
    a=[r for r in read(SANDBOX/"delta_assertions.jsonl") if not r['new_claim_relative_to_base']]
    assert len(a)==2
    assert all(r['existing_claim_override'] for r in a)


def test_no_schema_relaxation(data):
    for r in read(SANDBOX/"delta_assertions.jsonl"):
        s=data['schema']['relation_registry'][r['relation']]
        assert r['head_type'] in s['domain'] and r['tail_type'] in s['range']


def test_no_unverified_direct_or_schema_invented_edges():
    delta=read(SANDBOX/"delta_assertions.jsonl")
    assert all(not r['inferred_edge'] and not r['formal_release_permitted'] for r in delta)
    assert all(r['relation'] not in ['made_of','precedes','before_reuse'] for r in delta)
    frames=read(SANDBOX/"auxiliary_source_frames.jsonl")
    assert len(frames)==22 and all(not r['new_claim_counted'] for r in frames)


def test_no_expert_or_independent_reference_claim():
    p=read(OUT/'review/protocol.json')
    assert not p['human_expert'] and not p['independent_model'] and not p['blind']


def test_quarantine_fail_closed_and_false_positives_kept():
    q=read(SANDBOX/'quarantine_overlay.jsonl');kept=read(SANDBOX/'evidence_assertions_scope_filtered.jsonl')
    ids={x['assertion_id'] for x in kept};blocked={x['assertion_id'] for x in q}
    assert len(blocked)==9 and not(ids&blocked)
    assert {'EXA-0e3a98f3dbe8dd694efd4244','EXA-3c06f91ad198d5f65d435522'}<=ids


def test_reference_join_is_explicit_not_causal_transitivity(data):
    r=reference_join(data['pages']['MP015',31],data['pages']['MP015',32])
    assert len(r)==91
    for x in r:
        assert len(x['proof_cells'])==4
        assert str(x['source_reference_number'])==x['proof_cells'][2]['text']
        assert x['head_surface']==x['proof_cells'][3]['text']


def test_reference_join_negative_without_reference(data):
    p=copy.deepcopy(data['pages']['MP015',31]);p['tables'][0]['rows'][0]['cells'][1]['text']='unrelated table'
    with pytest.raises(ValueError):reference_join(p,data['pages']['MP015',32])


def test_source_records_not_corrupted_by_normalization(data):
    records=read(SANDBOX/'original_candidate_provenance.jsonl')
    assert len(records)==17
    for r in records:assert r['original_raw_record_unchanged'] in data['raw']


def test_current_gate_retains_rejection_and_review_states():
    mods,_=frozen_validators()
    fn=mods['confidence_policy'].decide_confidence
    ev={'valid':True,'evidence_level':'E1','silver_eligible':True};typ={'valid':True}
    for status in ['undetermined','not_entailed']:
        out=fn(model_confidence=.99,evidence_validation=ev,relation_type_validation=typ,
               relation_entailment_validation={'status':status,'silver_eligible':False})
        assert not out.silver_eligible


def test_topology_scan_does_not_mutate_adjacency(data):
    rows=topology_candidates(data)
    assert len(rows)==6 and all(not r['trusted_fact'] for r in rows)


def test_publication_loss_is_not_mislabeled_as_generation_omission():
    r=read(OUT/'evaluation/publication_loss_summary.json')
    assert r['A_restored_previously_evidence_qualified_but_term_blocked']==11
    assert r['A_restored_previously_evidence_quarantined']==2
    assert r['A_restored_previously_evidence_rejected']==4
    assert r['repaired_candidates_have_not_passed_original_chinese_publication_gate']


def test_stronger_simple_matching_control_not_claimed_as_innovation():
    r=read(OUT/'evaluation/endpoint_control_summary.json')
    assert r['executed_unpublished_queries']==6562
    for p in r['three_reviewed_nonduplicate_probes']:
        assert p['whole_record_top1']['combined']>.95
        assert p['endpoint_separated_top1']['score_min_head_tail']<.3


def test_no_leakage_free_masked_recovery_claim_without_experiment():
    r=read(OUT/'evaluation/quantitative_snapshot.json')
    assert not r['known_relation_masked_recovery_experiment_run']
    assert r['no_masked_recovery_generalization_claim']
