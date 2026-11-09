"""Independent checks of RP1 audit sampling, joins, sealed reference and preservation."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'results/experiments/research_point_1/loss_page_audit_v1'
read=lambda p:[json.loads(x) for x in Path(p).open() if x.strip()]

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    checks={}
    before=json.loads((P/'preservation_before.json').read_text())
    # These two files were newly created by this task before inventory capture.
    # The preparation script received the explicitly archived ID-join correction.
    task_created={'scripts/audit_rp1_loss_pages.py','docs/research/RP1_LOSS_AND_PAGE_AUDIT_V1_PROTOCOL_20260929.md'}
    old={k:v for k,v in before.items() if k not in task_created}
    changes=[k for k,v in old.items() if not (ROOT/k).is_file() or digest(ROOT/k)!=v]
    assert not changes, changes
    checks['preexisting_files_byte_identical']=len(old)
    inputs=json.loads((P/'input_manifest.json').read_text())
    for k,v in inputs.items():
        if k=='scripts/audit_rp1_loss_pages.py':
            assert digest(P/'prepare_script_snapshot.py')==v
        else:assert digest(ROOT/k)==v,k
    supplemental=json.loads((P/'supplemental_input_manifest.json').read_text())
    assert all(digest(ROOT/k)==v for k,v in supplemental.items())
    checks['frozen_inputs_and_supplemental_inputs_unchanged']=True
    correction=json.loads((P/'membership_join_correction.json').read_text())
    assert correction['script_after_sha256']==digest(ROOT/'scripts/audit_rp1_loss_pages.py')
    assert correction['script_before_sha256']==digest(P/'prepare_script_snapshot.py')
    checks['join_fix_has_original_and_corrected_code_hashes']=True

    source=read(ROOT/'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl')
    docs={f'MP{i:03d}' for i in [*range(1,8),*range(15,23)]}
    assert {r['doc_id'] for r in source}==docs
    groups=defaultdict(list)
    dg={'silver_candidate':'qualified','candidate_needs_review':'quarantined','rejected':'rejected'}
    for r in source:groups[(r['doc_id'],dg[r['decision']])].append(r['triple_id'])
    expected=set()
    for key,ids in groups.items():
        expected.update(sorted(ids,key=lambda x:hashlib.sha256(f'20260929/record/{x}'.encode()).hexdigest())[:2])
    sample=read(P/'record_sample_manifest.jsonl')
    primary=[r for r in sample if r['sample_kind']=='probability']
    assert {r['triple_id'] for r in primary}==expected and len(primary)==90
    assert len(sample)==len({r['triple_id'] for r in sample})==97
    assert sum(r['weight'] for r in primary)==8003
    for r in primary:
        n=len(groups[tuple(r['stratum'])]);assert r['inclusion_probability']==2/n and r['weight']==n/2
    checks['probability_sample_reconstructed_and_weights_sum_to_8003']=True
    assert all(r['weight'] is None for r in sample if r['sample_kind']=='coverage_supplement')

    frames=defaultdict(list)
    for doc in sorted(docs):
        for r in read(ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl'):
            frames[(doc,'has_table' if r['tables'] else 'no_table')].append(f"{doc}:p{r['pdf_page_number']:04d}")
    assert sum(map(len,frames.values()))==1934
    expected_pages={min(ids,key=lambda x:hashlib.sha256(f'20260929/page/{x}'.encode()).hexdigest()) for ids in frames.values()}
    pages=read(P/'page_sample_manifest.jsonl')
    assert {r['page_key'] for r in pages}==expected_pages and len(pages)==30
    assert all(r['population_n']==len(frames[tuple(r['stratum'])]) for r in pages)
    checks['page_sample_reconstructed_from_all_1934_build_pages']=True

    seal=json.loads((P/'page_reference_seal.json').read_text())
    opened=json.loads((P/'comparison_opened.json').read_text())
    assert digest(P/'page_reference_annotations.jsonl')==seal['sha256']==opened['reference_sha256']
    assert seal['sealed_at']<=opened['opened_at']
    references=read(P/'page_reference_annotations.jsonl')
    assert len(references)==30 and sum(len(r['atoms']) for r in references)==245
    checks['source_first_reference_sealed_before_comparison_and_unchanged']=True

    fields=('doc_id','pdf_page_number','relation','head_surface','tail_surface','evidence_text')
    key=lambda r:tuple(r.get(k) for k in fields)
    indexed=defaultdict(list)
    for r in source:indexed[key(r)].append(r)
    memberships={r['triple_id']:r for r in read(P/'corrected_publication_membership.jsonl')}
    assert len(memberships)==8003
    for tier,n in [('strict',208),('conservative',620),('standard',1326)]:
        path=ROOT/'data/kg/marine_pump/triples/KG_v1_validated/source_records.jsonl' if tier=='strict' else ROOT/f'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/{tier}_graph/triples/KG_v1_validated/source_records.jsonl'
        graph=read(path);assert len(graph)==n
        ids=set()
        for r in graph:
            rs=indexed[key(r)];assert len(rs)==1 and dg[rs[0]['decision']]=='qualified'
            ids.add(rs[0]['triple_id'])
        assert ids=={i for i,m in memberships.items() if m['membership'][tier]} and len(ids)==n
    checks['publication_joins_independently_verified_208_620_1326']=True

    findings=read(P/'record_findings.jsonl')
    assert len(findings)==97 and {r['triple_id'] for r in findings}=={r['triple_id'] for r in sample}
    assert all(not r['human_expert_reviewed'] and not r['confirmed_false_rejection'] for r in findings)
    cidx={r['candidate_id']:r for r in read(P/'page_candidate_index.jsonl')}
    quality={r['candidate_id']:r for r in read(P/'page_candidate_semantic_annotations.jsonl')}
    assert len(cidx)==len(quality)==210
    matches=read(P/'page_match_findings.jsonl')
    atoms={a['atom_id'] for r in references for a in r['atoms']}
    assert len(matches)==len(atoms)==245 and {r['atom_id'] for r in matches}==atoms
    for r in matches:
        for cid in r['candidate_ids']:
            c=cidx[cid];assert f"{c['doc_id']}:p{c['pdf_page_number']:04d}"==r['page_key']
        if r['match_status']=='matched':
            assert r['candidate_ids'] and all(quality[c]['semantic_support']=='supported' for c in r['candidate_ids'])
        else:assert not r['matched_qualified'] and not any(r['matched_publication'].values())
    checks['review_coverage_97_records_210_candidates_245_references']=True
    checks['partial_matches_never_counted_as_full_recall']=True
    summary=json.loads((P/'summary.json').read_text())
    assert summary['reference_match_counts']==dict(Counter(r['match_status'] for r in matches))
    assert sum(summary['strict_path_stage_counts'].values())==245
    assert summary['complete_reference_matches_qualified']==sum(r['matched_qualified'] for r in matches)
    assert summary['complete_reference_matches_published']=={t:sum(r['matched_publication'][t] for r in matches) for t in ['strict','conservative','standard']}
    assert summary['new_teacher_or_extractor_calls']==0 and not summary['human_expert_reviewed']
    checks['summary_independently_recomputed']=True
    result={'status':'passed','checks':checks,'scope':'Structural, provenance and aggregation checks only; not validation of AI semantic truth.'}
    with (P/'verification.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
