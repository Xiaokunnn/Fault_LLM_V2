#!/usr/bin/env python3
"""Read-only delivery verification; no API calls and no output regeneration."""
import json
import re
from functools import lru_cache
from pathlib import Path
from rp1_offline_contract_v3 import ROOT, rows, sha, object_sha, channel
from run_rp1_ldc_new_pages import verify, OUT, PAGE
from run_rp1_targeted_v2_1 import request_state
from summarize_rp1_holdout_v1 import verify_sources
from summarize_rp1_ldc_new_pages import validate_witness

def main():
    requests=verify();old=verify_sources();target=OUT/'new_page_comparison'
    for f in ['execution_freeze.json','review_freeze.json','verification.json']:
        for rel,h in json.loads((target/f).read_text())['sha256'].items():assert sha(ROOT/rel)==h,rel
    for r in requests:assert request_state(OUT/'api_run_001',r) is not None
    assert not list((OUT/'api_run_001').glob('*.failed.json'))
    pages={p['page_key']:p for p in rows(PAGE/'source_only.jsonl')}
    assert {p['doc_id'] for p in pages.values()}=={'MP015','MP016','MP018','MP021'}
    used=set(json.loads((PAGE/'selection.json').read_text())['excluded_page_keys'])
    assert not used & pages.keys()
    refs=rows(PAGE/'references.jsonl');rv=rows(target/'source_quality_judgments.jsonl')
    lookup={(j['page_key'],j['payload_sha256']):j for j in rv}
    for r in refs+rv:
        for w in r['source_witnesses']:validate_witness(pages[r['page_key']],w)
    outputs=rows(target/'outputs.jsonl');metrics=json.loads((target/'metrics.json').read_text())
    page_metrics=rows(target/'page_metrics.jsonl');checked=0
    for stage in ['raw','B','L','D','C']:
        group=[r for r in outputs if r['stage']==stage and r['included']]
        ps=[p for p in page_metrics if p['stage']==stage]
        assert sum(p['all']['retained'] for p in ps)==metrics['stages'][stage]['all']['retained']
        assert sum(p['full_matches'] for p in ps)==metrics['stages'][stage]['full_matches']
        for key in pages:
            records=[r for r in group if r['page_key']==key and channel(r['payload'])=='core']
            pm=next(p for p in ps if p['page_key']==key)
            for grade in 'SEU':
                assert sum(lookup[key,object_sha(r['payload'])]['verdict']==grade for r in records)==pm['core'][grade]
            # Different algorithm from production augmenting paths.
            adj=[lookup[key,object_sha(r['payload'])]['reference_matches'] for r in records if lookup[key,object_sha(r['payload'])]['verdict']=='S']
            ref_ids=sorted({rid for a in adj for rid in a});bits={r:1<<i for i,r in enumerate(ref_ids)}
            @lru_cache(None)
            def best(i,mask):
                if i==len(adj):return 0
                return max([best(i+1,mask)]+[1+best(i+1,mask|bits[r]) for r in adj[i] if not mask&bits[r]])
            assert best(0,0)==pm['full_matches'];checked+=1
    # Every original is preserved exactly in the raw arm.
    raw={r['candidate_id']:r for r in outputs if r['stage']=='raw'}
    for r in requests:
        parsed=json.loads((OUT/'api_run_001'/(r['request_id']+'.parsed.json')).read_text())
        for i,a in enumerate(parsed['assertions'],1):assert raw[f'{r["page_key"]}:LDC:{i:03d}']['payload']==a
    assert len(raw)==141 and len(rv)==146 and len(outputs)==705 and len(refs)==45
    if (OUT/'delivery_manifest.json').exists():
        for rel,h in json.loads((OUT/'delivery_manifest.json').read_text())['sha256'].items():assert sha(ROOT/rel)==h,rel
    print(json.dumps(dict(status='passed',original_responses=8,original_candidates=141,unique_review_payloads=146,
        unchanged_old_frozen_files=len(old),independent_page_matching_checks=checked,reference_count=45,
        gate=metrics['comparison_gate']['status'],network_calls=0),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
