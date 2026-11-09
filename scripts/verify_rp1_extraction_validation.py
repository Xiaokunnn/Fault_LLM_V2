#!/usr/bin/env python3
"""Verify frozen requests, complete received responses, native positions and counts."""
import json
from collections import Counter
from validate_rp1_extraction import OUT, ROOT, rows, sha, write, verify, priority, digest, classify, DOCS
from research_point_1_graph_evidence.stage02_triple_extraction.contextual_extraction import units_of, compile_records
from rp1_offline_contract_v3 import REGISTRY


def main():
    requests=verify();sources=rows(OUT/'sources.jsonl');source_map={s['page_key']:s for s in sources}
    selection=json.loads((OUT/'selection.json').read_text());excluded=set(selection['excluded_page_keys'])
    assert len(sources)==10 and len(source_map)==10 and not (set(source_map)&excluded)
    # Independent reconstruction of the fixed metadata/text sampling frame.
    eligible=[]
    for doc in DOCS:
        pp=rows(ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl');pm={p['pdf_page_number']:p for p in pp}
        for p in pp:
            k=f'{doc}:p{p["pdf_page_number"]:04d}';tag=classify(p,pm.get(p['pdf_page_number']-1))
            if tag and k not in excluded:eligible.append((priority(k),k,tag,p))
    chosen=[];counts=Counter()
    for kind,needed in [('fault_table',1),('maintenance',4),('prose',5)]:
        for _,key,tag,p in sorted(eligible):
            if tag!=kind or counts[p['doc_id']]>=3:continue
            chosen.append(key);counts[p['doc_id']]+=1
            if sum(source_map[k]['stratum']==kind for k in chosen)==needed:break
    assert chosen==[s['page_key'] for s in sources]
    records=rows(OUT/'candidates.jsonl');anchors=0;regenerated=[];response_tokens=Counter()
    for item in requests:
        s=source_map[item['page_key']];target=s['target'];run=OUT/'api';code=item['request_id']
        meta=json.loads((run/(code+'.completed.json')).read_text());raw=run/(code+'.response.bin')
        assert meta['response_sha256']==sha(raw) and meta['payload_sha256']==item['payload_sha256']
        response=json.loads(raw.read_bytes());choice=response['choices'][0]
        assert response['model']==meta['returned_model']=='qwen3.8-max' and choice['finish_reason']=='stop'
        parsed=json.loads((run/(code+'.parsed.json')).read_text());assert parsed==json.loads(choice['message']['content'])
        assert len(parsed['records'])==meta['records']
        units=units_of([target,*s['context_pages']])
        for p in [target,*s['context_pages']]:
            assert p['document_split']=='build_train' and p['doc_id']==target['doc_id']
            assert digest(p['page_text'].encode())==p['page_text_sha256']
        current=compile_records(parsed,target,s['context_pages'],REGISTRY)
        for a in current:
            a.update(candidate_id=f'{code}:{a["index"]:03d}',page_key=item['page_key'],stratum=item['stratum'])
            for w in a.get('source_witnesses',[]):
                u=units[w['unit_id']]
                assert u['text'][w['start']:w['end']]==w['text'] and u.get('bbox')==w['bbox']
                assert u['doc_id']==w['doc_id'] and u['page']==w['pdf_page_number'];anchors+=1
        regenerated+=current
        response_tokens.update({k:meta.get('usage',{}).get(k,0) for k in ['prompt_tokens','completion_tokens','total_tokens']})
    assert regenerated==records and len(records)==224
    sample=rows(OUT/'review_sample.jsonl');assert [r['candidate_id'] for r in sample]==[r['candidate_id'] for r in sorted(records,key=lambda a:priority(a['candidate_id']))[:60]]
    review=rows(OUT/'source_review.jsonl');assert {r['candidate_id'] for r in review}=={r['candidate_id'] for r in sample}
    for p,h in json.loads((OUT/'output_freeze.json').read_text())['sha256'].items():assert sha(ROOT/p)==h,p
    metric=json.loads((OUT/'metrics.json').read_text());by_id={a['candidate_id']:a for a in records}
    assert metric['automatic_pass']==sum(a['automatic_pass'] for a in records)==129
    assert metric['source_review']['S']==sum(r['grade']=='S' for r in review)==25
    assert metric['source_review']['joint_source_supported_and_automatic_pass']==sum(r['grade']=='S' and by_id[r['candidate_id']]['automatic_pass'] for r in review)==23
    assert metric['source_review']['defects_automatically_released']==sum(r['grade']=='E' and by_id[r['candidate_id']]['automatic_pass'] for r in review)==16
    assert metric['successful_response_usage']==dict(response_tokens)
    coverage=rows(OUT/'coverage_review.jsonl');inventory=rows(OUT/'source_inventory.jsonl')
    assert {r['reference_id'] for r in coverage}=={r['reference_id'] for r in inventory} and len(coverage)==65
    assert dict(Counter(r['status'] for r in coverage))==metric['coverage']['statuses']
    for r in coverage:assert set(r['candidate_ids'])<=set(by_id)
    # Old graphs remain byte-identical to the previous, pre-existing expansion input freeze.
    old=json.loads((ROOT/'results/experiments/research_point_1/graph_expansion_v1_20261012/input_freeze.json').read_text())['sha256']
    preserved=[]
    for path,h in old.items():
        if path.endswith('/source_records.jsonl'):
            assert sha(ROOT/path)==h,path;preserved.append(path)
    assert len(preserved)==3
    result=dict(status='PASS',target_pages_reconstructed=10,successful_response_payloads=10,all_output_candidates_recompiled=224,
        native_position_roundtrips=anchors,fixed_review_samples_reconstructed=60,AI_judgments_recounted=60,
        checklist_matches_recounted=65,old_graph_source_files_preserved=preserved,network_attempts=metric['network_attempts'],
        source_semantic_correctness='not proven by this verifier; labels are unblinded single-AI judgments',
        protocol_changes='Disclosed pre-API sampling feasibility amendment, post-response native-block compiler correction and one explicit timeout retry; not claimed as unchanged pre-API code')
    write(OUT/'verification.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
