"""Contract failure modes and immutable offline evidence, not expert-quality tests."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from rp1_offline_contract_v3 import (OUT, SOURCE, REVIEW, bind, filter_flags,
    rows, sha, object_sha, type_valid, maximum_matching, exact_key)


def test_locator_does_not_join_disjoint_evidence():
    page={'page_text':'alpha beta gamma','tables':[]}
    assert bind(page,'alpha gamma') is None
    assert bind(page,'alpha\n beta')['text']=='alpha beta'
    assert bind(page,'alpha!') is None


def test_native_subspan_offsets_and_geometry_are_not_fabricated():
    cell={'text':'Poor\nlubrication.','cell_id':'c1','bbox':{'x0':1,'top':2,'x1':4,'bottom':5}}
    page={'page_text':'unrelated','tables':[{'rows':[{'cells':[cell]}]}]}
    w=bind(page,'Poor lubrication.')
    assert w['kind']=='native_cell_subspan'
    assert cell['text'][w['start']:w['end']]==w['text']
    assert w['bbox']==cell['bbox']
    assert bind(page,'Poor lubrication!') is None


def inputs():
    candidates={a['candidate_review_id']:a for p in rows(REVIEW/'arm_masked_review_packets.jsonl') for a in p['assertions']}
    pages={p['page_key']:p for p in rows(SOURCE/'pilot_sources.jsonl')}
    return candidates,pages


def test_filter_is_invariant_to_labels_identifiers_and_arm_names():
    candidates,pages=inputs()
    a=copy.deepcopy(candidates['VR11:A013']);p=pages['MP007:p0012']
    flags=filter_flags(a,p)
    a.update(candidate_review_id='unseen-id',expert_label='correct',arm='E0',mechanical={'type_direction_valid':True})
    assert filter_flags(a,p)==flags
    assert 'instrument_not_inspection_target' in flags


def test_checklist_whether_is_not_conditional_antecedent():
    candidates,pages=inputs()
    a=copy.deepcopy(candidates['VR11:A009'])
    a['conditions']=[];a['applicability']='pump'
    assert 'conditional_context_not_explicit' not in filter_flags(a,pages['MP007:p0012'])


def test_negative_maintenance_requirements_do_not_become_prohibitions():
    ledger={x['candidate_review_id']:x for x in rows(OUT/'candidate_adjudications.jsonl')}
    for cid in ['VR01:A003','VR01:A004','VR01:A005','VR10:A004','VR10:A005','VR10:A007']:
        a=ledger[cid]
        assert a['original']['polarity']=='negative'
        assert a['proposal']['record_kind']=='maintenance_requirement'
        assert a['proposal']['requirement']=='not_required'
    assert ledger['VR06:A013']['proposal']['requirement']=='prohibited'


def test_ambiguous_source_is_not_silently_repaired():
    ledger={x['candidate_review_id']:x for x in rows(OUT/'candidate_adjudications.jsonl')}
    for cid in ['VR06:A027','VR08:A026','VR11:A014','VR04:A011','VR04:A012','VR12:A006']:
        assert ledger[cid]['proposal'] is None
        assert ledger[cid]['original_contract_status']=='unresolved'


def test_procedure_purpose_does_not_remain_prevented_event():
    ledger={x['candidate_review_id']:x for x in rows(OUT/'candidate_adjudications.jsonl')}
    assert ledger['VR10:A024']['proposal']['record_kind']=='operating_procedure'
    for cid in ['VR10:A025','VR10:A026']:
        a=ledger[cid]['proposal']
        assert a['relation']=='maintained_by' and a['head_surface']=='drainage valve'
        assert any('shut off' in x for x in a['conditions'])


def test_table_modal_and_scope_inheritance_respects_column():
    ledger={x['candidate_review_id']:x for x in rows(OUT/'candidate_adjudications.jsonl')}
    assert ledger['VR03:A002']['proposal']['modality']=='descriptive'
    assert ledger['VR03:A003']['proposal']['modality']=='probable'
    assert ledger['VR03:A003']['proposal']['scope']=='primary'
    assert '非船舶' in ledger['VR03:A003']['proposal']['applicability']
    assert ledger['VR02:A001']['proposal']['scope']=='background'


def test_duplicate_and_composite_candidates_cannot_inflate_full_coverage():
    a=maximum_matching({'r1':['c1'],'r2':['c1']})
    assert len(a)==1
    b=maximum_matching({'r1':['c1','c2'],'r2':['c1']})
    assert len(b)==2 and len(set(b.values()))==2


def test_every_source_witness_round_trips_to_saved_page_or_native_cell():
    _,pages=inputs()
    ledger=rows(OUT/'candidate_adjudications.jsonl')
    assert len(ledger)==233
    for a in ledger:
        assert object_sha(a['original'])==a['original_sha256']
        page=pages[a['page_key']]
        assert page['page_text_sha256']==a['source_page_sha256']
        cells={c['cell_id']:c for t in page['tables'] for row in t['rows'] for c in row['cells']}
        for w in a['source_witnesses']:
            source=page['page_text'] if w['kind']=='page_span' else cells[w['cell_id']]['text']
            assert source[w['start']:w['end']]==w['text']
            if w['kind']=='native_cell_subspan':assert w['bbox']==cells[w['cell_id']].get('bbox')
        if a['proposal'] and not a['proposal'].get('record_kind'):assert type_valid(a['proposal'])


def test_raw_arm_immutable_and_filter_never_changes_payload():
    candidates,_=inputs()
    decisions=rows(OUT/'arm_decisions.jsonl')
    assert len(decisions)==699
    for d in decisions:
        if d['stage']=='C_source_edit':continue
        raw={k:v for k,v in candidates[d['candidate_review_id']].items() if k not in ['candidate_review_id','mechanical']}
        assert d['payload']==raw
    for stage in ['A_raw','B_filter','C_source_edit']:
        assert len({d['candidate_review_id'] for d in decisions if d['stage']==stage})==233


def test_matching_capacity_and_unresolved_denominator():
    refs=rows(OUT/'reference_overlay.jsonl')
    assert len(refs)==85 and sum(x['v3_evaluation_channel']=='core' for x in refs)==79
    matches=rows(OUT/'reference_matches_510.jsonl')
    assert len(matches)==510
    for stage in ['A_raw','B_filter','C_source_edit']:
        for arm in ['E0','E1']:
            full=[m['allocated_candidate_id'] for m in matches if m['stage']==stage and m['prompt_arm']==arm and m['state']=='full']
            assert len(full)==len(set(full))
    assert all(m['state']!='full' for m in matches if m['reference_channel']=='unresolved')


def test_freezes_and_expert_queues_unchanged():
    freeze=json.loads((OUT/'adjudication_freeze.json').read_text())
    for p,digest in freeze['sha256'].items():assert sha(ROOT/p)==digest
    before=json.loads((OUT/'preservation_before.json').read_text())['sha256']
    for name in ['candidate_expert_review_queue.jsonl','reference_match_review_queue.jsonl']:
        p=REVIEW/name
        assert sha(p)==before[str(p.relative_to(ROOT))]
