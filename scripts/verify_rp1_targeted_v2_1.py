#!/usr/bin/env python3
"""Read-only independent reconstruction of RP1 v2.1 witnesses and preserved assets."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/experiments/research_point_1'
OUT = BASE / 'adjudication_targeted_v2_1'


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def filehash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify():
    snapshots = [json.loads((OUT/'preservation_before.json').read_text())['sha256'], json.loads((BASE/'scope_repair_v2/preservation_before.json').read_text())]
    for version in ['loss_page_audit_v1', 'scope_repair_v2']:
        snapshots.append(json.loads((BASE/version/'delivery_manifest.json').read_text())['sha256'])
    expectations = {}
    for snapshot in snapshots:
        for path, expected in snapshot.items():
            if path in expectations:
                assert expectations[path] == expected, ('Incompatible prior preservation manifests', path)
            expectations[path] = expected
    for path, expected in expectations.items():
        assert filehash(ROOT/path) == expected, ('Prior asset changed', path)
    sources = {}
    for name in ['adjudication_sources.jsonl', 'pilot_sources.jsonl']:
        for page in rows(OUT/name):
            assert hashlib.sha256(page['page_text'].encode()).hexdigest() == page['page_text_sha256']
            if page['page_key'] in sources:
                assert sources[page['page_key']] == page
            sources[page['page_key']] = page
    documents = {p['local_file']: p['document_sha256'] for p in sources.values()}
    for path, expected in documents.items():
        assert filehash(ROOT/path).lower() == expected.lower(), ('Original PDF hash', path)
    span_count = 0
    cell_count = 0

    def witness(page, evidence):
        nonlocal span_count, cell_count
        cells = {c['cell_id']: c for t in page['tables'] for r in t['rows'] for c in r['cells']}
        for e in evidence:
            if e['kind'] == 'page_span':
                assert 0 <= e['start'] < e['end'] <= len(page['page_text'])
                assert page['page_text'][e['start']:e['end']] == e['text']
                span_count += 1
            elif e['kind'] == 'native_table_cells':
                for c in e['cells']:
                    assert c == cells[c['cell_id']]
                    assert c['table_id'] == e['table_id']
                    assert c['row_id'] == e['row_id'] or c['row_index'] == 0
                    b = c['bbox']
                    assert 0 <= b['x0'] < b['x1'] <= page['page_width']
                    assert 0 <= b['top'] < b['bottom'] <= page['page_height']
                    cell_count += 1
            else:
                raise AssertionError('Unknown witness kind')

    schema = json.loads((ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json').read_text())
    refs = rows(OUT/'page_reference_v2_1.jsonl')
    assert len({x['reference_id'] for x in refs}) == len(refs)
    for x in refs:
        p = sources[x['page_key']]
        assert x['source_page_sha256'] == p['page_text_sha256']
        rule = schema['relation_registry'][x['relation']]
        assert rule['core_diagnostic_relation']
        assert x['head_type'] in rule['domain'], x['reference_id']
        assert x['tail_type'] in rule['range'], x['reference_id']
        assert x['conditions_zh'] and x['expert_review'] == 'pending'
        witness(p,x['evidence'])
    disputes = rows(OUT/'dispute_resolutions.jsonl')
    old = rows(BASE/'scope_repair_v2/second_opinion/adjudication_packets.jsonl')
    assert {x['audit_id'] for x in disputes} == {x['audit_id'] for x in old if not x['agreement']}
    for x in disputes:
        p = sources[x['page_key']]
        assert x['source_page_sha256'] == p['page_text_sha256']
        assert x['expert_adjudication'] == 'pending' and x['automatic_qualification'] is False
        witness(p,x['source_witnesses'])
    aux = rows(OUT/'auxiliary_and_unresolved.jsonl')
    for x in aux:
        witness(sources[x['page_key']],x['evidence'])
    pilot = rows(OUT/'pilot_sources.jsonl')
    holdout = rows(BASE/'scope_repair_v2/holdout_manifest.jsonl')
    assert not {x['page_key'] for x in pilot} & {x['page_key'] for x in holdout}
    assert all(p['doc_id'] in {f'MP{i:03d}' for i in [1,2,3,4,5,6,7,15,16,17,18,19,20,21,22]} for p in pilot)
    assert not any(x['page_key']=='MP002:p0089' for x in refs)
    lineage = rows(OUT/'v1_reference_lineage.jsonl')
    oldrefs = [a for p in rows(BASE/'loss_page_audit_v1/page_reference_annotations.jsonl') for a in p['atoms']]
    assert {x['old_reference_id'] for x in lineage} == {a['atom_id'] for a in oldrefs}
    assert len([x for x in refs if x.get('supersedes_reference_id')]) == 30
    for filename in ['expert_dispute_queue.jsonl', 'expert_page_queue.jsonl']:
        for x in rows(OUT/filename):
            assert x['status']=='pending' and x['reviewer_id'] is None and x['reviewed_at'] is None
    for key, value in json.loads((OUT/'request_freeze.json').read_text())['sha256'].items():
        assert filehash(ROOT/key)==value, ('Request freeze modified',key)
    return {'status':'passed','preserved_prior_files':len(expectations),'original_pdf_hashes_verified':len(documents),'source_pages_reconstructed':len(sources),'span_witnesses_verified':span_count,'native_cell_occurrences_verified':cell_count,'disputes':len(disputes),'provisional_reference_items':len(refs),'auxiliary_or_unresolved':len(aux),'reference_by_page':dict(Counter(x['page_key'] for x in refs)),'reserved_page_ids_only_checked':len(holdout),'reserved_content_opened':0,'new_model_calls':0,'expert_review':'pending','formal_accuracy_recall':'not_computed'}


if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
