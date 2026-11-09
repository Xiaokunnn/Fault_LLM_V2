#!/usr/bin/env python3
"""Read-only integrity, native provenance, graph linkage and sampling checks."""
import csv
import hashlib
import json
from collections import Counter
import xml.etree.ElementTree as ET
from build_rp1_graph_expansion_v1 import ROOT, OUT, GRAPH, rows, sha, write, old, REGISTRY


def key(r):
    return tuple(' '.join(str(r[k]).casefold().split()) for k in ['head_type','head_canonical_zh','relation','tail_type','tail_canonical_zh'])


def main():
    hash_checks=0
    for name in ['input_freeze.json','graph_freeze.json']:
        for path,expected in json.loads((OUT/name).read_text())['sha256'].items():
            assert sha(ROOT/path)==expected,path
            hash_checks+=1
    original=rows(old.SOURCE);by_id={r['triple_id']:r for r in original}
    baseline=rows(old.TIERS['standard']);combined=rows(GRAPH/'source_records.jsonl')
    added=combined[len(baseline):];pages,_=old.load_pages()
    assert len(combined)==1456 and len(added)==130
    for before,after in zip(baseline,combined):
        assert all(after[k]==v for k,v in before.items()),before['triple_id']
    decisions=rows(OUT/'candidate_decisions.jsonl')
    assert len(decisions)==8003 and {r['parent_triple_id'] for r in decisions}==set(by_id)
    assert sum(d['status']=='added' for d in decisions)==len(added)
    seen={(key(r),r['doc_id'],r['pdf_page_number']) for r in baseline}
    anchors=contexts=0
    for r in added:
        parent=by_id[r['expansion_parent_triple_id']]
        for k in ['source_url','document_sha256','page_text_sha256','evidence_text','doc_id','pdf_page_number','applicability_scope']:
            assert parent[k]==r[k],(r['triple_id'],k)
        assert r['doc_id'] in old.DOCS and r['document_split']=='build_train'
        assert 'dual_qwen_relation_not_entailed' not in parent.get('rejection_reasons',[])
        assert r['head_type'] in REGISTRY[r['relation']]['domain'] and r['tail_type'] in REGISTRY[r['relation']]['range']
        for side in ['head','tail']:
            assert any('\u4e00'<=c<='\u9fff' for c in r[side+'_canonical_zh'])
        item=(key(r),r['doc_id'],r['pdf_page_number']);assert item not in seen;seen.add(item)
        p=pages[f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}']
        units={u['block_id']:u for u in p['text_blocks']}
        units.update({u['cell_id']:u for t in p['tables'] for row in t['rows'] for u in row['cells']})
        for w in r['expansion_source_witnesses']:
            u=units[w.get('cell_id',w.get('block_id'))]
            assert u['text'][w['start']:w['end']]==w['text'] and u['bbox']==w['bbox']
            anchors+=1
        for c in r['conditions_source']:
            assert units[c.get('cell_id',c.get('unit_id'))]['text']==c['text']
            contexts+=1
    assert len({key(r) for r in combined})==1400
    assert len({key(r) for r in added}-{key(r) for r in baseline})==119
    assert len({(r['doc_id'],r['pdf_page_number']) for r in combined})==505
    claims={c['claim_id']:c for c in rows(GRAPH/'claims.jsonl')}
    entities={e['entity_id']:e for e in rows(GRAPH/'entities.jsonl')}
    assertions={a['assertion_id']:a for a in rows(GRAPH/'evidence_assertions.jsonl')}
    assert (len(claims),len(entities),len(assertions))==(1400,2150,1456)
    for r in combined:
        assert r['expanded_head_entity_id'] in entities and r['expanded_tail_entity_id'] in entities
        a=assertions[r['expanded_assertion_id']];c=claims[a['claim_id']]
        assert c['head_entity_id']==r['expanded_head_entity_id'] and c['tail_entity_id']==r['expanded_tail_entity_id']
        assert c['relation']==r['relation'] and a['original_evidence_text']==r['evidence_text']
    tree=ET.parse(GRAPH/'graph.graphml');ns={'g':'http://graphml.graphdrawing.org/xmlns'}
    assert len(tree.findall('.//g:node',ns))==2150 and len(tree.findall('.//g:edge',ns))==1400
    with (GRAPH/'triples.csv').open() as f:assert len(list(csv.DictReader(f)))==1456
    sample=rows(OUT/'quality_sample.jsonl');review=rows(OUT/'quality_review.jsonl')
    assert len(sample)==len(review)==80
    for cohort,population in [('baseline',combined[:1326]),('added',added)]:
        selected=sorted(population,key=lambda r:hashlib.sha256(('20261012|'+cohort+'|'+r['triple_id']).encode()).hexdigest())[:40]
        assert [s['record'] for s in sample if s['cohort']==cohort]==selected
    summary=json.loads((OUT/'quality_summary.json').read_text())
    for cohort in ['baseline','added']:
        for metric in ['source_support','context_qualified_usable']:
            assert dict(Counter(r[metric] for r in review if r['cohort']==cohort))==summary[cohort][metric]
    result=dict(status='PASS',frozen_file_hashes=hash_checks,baseline_records_preserved=1326,
        candidate_decisions=8003,added_provenance_records=130,native_anchor_roundtrips=anchors,
        source_context_roundtrips=contexts,entity_count=2150,claim_count=1400,assertion_count=1456,
        fixed_samples_reconstructed=80,AI_judgments_recounted=80,
        meaning='Integrity and provenance checks, not factual correctness or complete condition binding')
    write(OUT/'verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
