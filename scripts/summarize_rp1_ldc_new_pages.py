#!/usr/bin/env python3
"""Aggregate fixed source judgments, with one-to-one reference allocation."""
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from rp1_offline_contract_v3 import ROOT, BASE, rows, sha, write, object_sha, channel
from summarize_rp1_holdout_v1 import quality, ratio, match, losses, verify_sources
from run_rp1_ldc_new_pages import verify, OUT, PAGE

TARGET=OUT/'new_page_comparison'
STAGES=['raw','B','L','D','C']

def validate_witness(page,w):
    if w['kind']=='native_block_subspan':
        u=next(b for b in page['text_blocks'] if b['block_id']==w['block_id']);text=u['text']
        assert w['bbox']==u['bbox']
    elif w['kind']=='native_cell_subspan':
        u=next(c for t in page['tables'] for r in t['rows'] for c in r['cells'] if c['cell_id']==w['cell_id']);text=u['text']
        assert w['bbox']==u['bbox']
    else:
        assert w['kind']=='page_span';text=page['page_text']
    assert 0<=w['start']<w['end']<=len(text)
    assert text[w['start']:w['end']]==w['text']

def main():
    verify();old=verify_sources()
    for name in ['execution_freeze.json','review_freeze.json']:
        for rel,h in json.loads((TARGET/name).read_text())['sha256'].items():assert sha(ROOT/rel)==h,rel
    pages={p['page_key']:p for p in rows(PAGE/'source_only.jsonl')}
    refs={r['reference_id']:r for r in rows(PAGE/'references.jsonl')}
    judgments=rows(TARGET/'source_quality_judgments.jsonl')
    lookup={(j['page_key'],j['payload_sha256']):j for j in judgments}
    packets=rows(TARGET/'review_packets.jsonl')
    assert len(lookup)==len(judgments)==len(packets)
    n_witness=0
    for p in packets:
        j=lookup[p['page_key'],p['payload_sha256']]
        assert p['review_id']==j['review_id'] and object_sha(p['payload'])==p['payload_sha256']
        assert j['verdict'] in ['S','E','U'] and j['reason_zh']
        if j['verdict']!='S':assert not j['reference_matches']
        for rid in j['reference_matches']+j['partial_reference_matches']:assert refs[rid]['page_key']==j['page_key']
        for w in j['source_witnesses']:validate_witness(pages[p['page_key']],w);n_witness+=1
    for r in refs.values():
        for w in r['source_witnesses']:validate_witness(pages[r['page_key']],w);n_witness+=1
    outputs=rows(TARGET/'outputs.jsonl')
    for r in outputs:
        r['judgment']=lookup[r['page_key'],object_sha(r['payload'])]
        for w in r.get('source_witnesses',[]):validate_witness(pages[r['page_key']],w);n_witness+=1
    arms={s:[r for r in outputs if r['stage']==s] for s in STAGES}
    ids={r['candidate_id']:r for r in arms['raw']}
    for s,group in arms.items():
        assert len(group)==len(ids) and {r['candidate_id'] for r in group}==set(ids)
        for r in group:assert r['original_sha256']==object_sha(ids[r['candidate_id']]['payload'])
    summary={};page_metrics=[];allocations=[];loss_records=[]
    for s,group in arms.items():
        kept=[r for r in group if r['included']];core=[r for r in kept if channel(r['payload'])=='core']
        current={r['candidate_id']:r for r in group}
        raw_loss=losses(arms['raw'],current,True)
        raw_loss_all=losses(arms['raw'],current,False)
        baseline_loss=losses([r for r in arms['B'] if r['included']],current,True)
        allocation=match(core)
        assert len(set(allocation.values()))==len(allocation)
        for rid,cid in allocation.items():assert refs[rid]['page_key']==current[cid]['page_key']
        full_all=match(kept)
        summary[s]=dict(all=quality(kept),core=quality(core),
            channels={c:quality([r for r in kept if channel(r['payload'])==c]) for c in ['core','noncore','auxiliary','background']},
            full_matches=len(allocation),reference_total=len(refs),reference_coverage=ratio(len(allocation),len(refs)),
            full_matches_all_channels=len(full_all),raw_supported_core_lost=len(raw_loss),raw_supported_all_lost=len(raw_loss_all),
            baseline_supported_core_lost=len(baseline_loss),core_errors=dict(Counter(r['judgment']['error_category'] for r in core if r['judgment']['verdict']=='E')))
        loss_records += [dict(stage=s,**r) for r in raw_loss_all]
        for key in pages:
            subset=[r for r in kept if r['page_key']==key];core_subset=[r for r in subset if channel(r['payload'])=='core']
            refset={rid for rid,r in refs.items() if r['page_key']==key}
            selected={rid:cid for rid,cid in allocation.items() if rid in refset}
            partial={rid for r in subset for rid in r['judgment']['partial_reference_matches'] if rid in refset and rid not in selected}
            one=dict(page_key=key,stage=s,all=quality(subset),core=quality(core_subset),
                original_assertions=sum(r['page_key']==key for r in arms['raw']),references=len(refset),full_matches=len(selected),
                reference_coverage=ratio(len(selected),len(refset)),unmatched_with_partial_only=len(partial))
            page_metrics.append(one)
            allocations.append(dict(page_key=key,stage=s,allocations=selected,partial_only_references=sorted(partial),unmatched_references=sorted(refset-set(selected))))
        values=[p for p in page_metrics if p['stage']==s]
        cov=[p['reference_coverage'] for p in values if p['references']]
        lower=[p['core']['lower'] for p in values if p['core']['lower'] is not None]
        summary[s]['page_macro']=dict(reference_coverage=mean(cov),reference_pages=len(cov),support_lower=mean(lower) if lower else None,support_pages=len(lower))
        summary[s]['pages_with_supported_core']=sum(p['core']['S']>0 for p in values)
        summary[s]['pages_with_reference_match']=sum(p['full_matches']>0 for p in values)
    b,c=summary['B'],summary['C'];pair={(p['page_key'],p['stage']):p for p in page_metrics}
    gains=[k for k in pages if pair[k,'C']['core']['S']>pair[k,'B']['core']['S'] or pair[k,'C']['full_matches']>pair[k,'B']['full_matches']]
    checks=dict(core_S_non_decreasing=c['core']['S']>=b['core']['S'],matches_non_decreasing=c['full_matches']>=b['full_matches'],
        core_E_U_non_increasing=c['core']['E']+c['core']['U']<=b['core']['E']+b['core']['U'],
        all_E_U_non_increasing=c['all']['E']+c['all']['U']<=b['all']['E']+b['all']['U'],
        raw_good_core_loss_non_increasing=c['raw_supported_core_lost']<=b['raw_supported_core_lost'],
        raw_good_all_loss_non_increasing=c['raw_supported_all_lost']<=b['raw_supported_all_lost'],
        no_new_baseline_good_core_loss=c['baseline_supported_core_lost']==0,at_least_one_page_gain=bool(gains))
    completion=[json.loads(p.read_text()) for p in (OUT/'api_run_001').glob('*.completed.json')]
    assert len(completion)==8
    usage={k:sum(x['usage'].get(k,0) for x in completion) for k in ['prompt_tokens','completion_tokens','total_tokens']}
    usage.update(response_elapsed_sum_seconds=sum(x['elapsed_seconds'] for x in completion),model=sorted({x['returned_model'] for x in completion}),requests=8,additional_postprocess_API_calls=0)
    metric=dict(status='completed',pages=8,reference_total=45,reference_pages=6,original_assertions=len(ids),unique_payloads=len(packets),stages=summary,
        comparison_gate=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,strict_gain_pages=gains),usage=usage,
        scope='AI source review; same-document new pages; finite English rules; two pages actually French/German despite en metadata',
        reference_or_method_changed_after_outputs=False,partial_matches_in_full_count=False)
    write(TARGET/'metrics.json',metric);write(TARGET/'page_metrics.jsonl',page_metrics)
    write(TARGET/'reference_allocations.jsonl',allocations);write(TARGET/'correct_knowledge_losses.jsonl',loss_records)
    write(TARGET/'verification.json',dict(status='passed',frozen_old_dependency_files=len(old),source_witnesses_checked=n_witness,
        all_payloads_reviewed=len(packets),decisions_checked=len(outputs),matching_injective=True,page_count=8,
        source_first_references=45,sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),TARGET/'metrics.json',TARGET/'page_metrics.jsonl',TARGET/'reference_allocations.jsonl',TARGET/'correct_knowledge_losses.jsonl']}))
    print(json.dumps(metric,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
