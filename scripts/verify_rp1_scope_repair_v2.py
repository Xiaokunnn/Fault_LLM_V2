"""Independently verify mechanical evidence, reserved split and preserved assets."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/experiments/research_point_1/scope_repair_v2'
V1 = ROOT / 'results/experiments/research_point_1/loss_page_audit_v1'


def read(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def main():
    freeze = json.loads((OUT / 'experiment_freeze.json').read_text())
    for k, digest in freeze['inputs'].items():
        assert sha(ROOT / k) == digest, k
    before = json.loads((OUT / 'preservation_before.json').read_text())
    for k, digest in before.items():
        assert sha(ROOT / k) == digest, k
    v1_delivery = json.loads((V1 / 'delivery_manifest.json').read_text())['sha256']
    assert all(sha(ROOT / k) == v for k, v in v1_delivery.items())
    records = {r['triple_id']: r for r in read(OUT / 'development_candidates.jsonl')}
    pages = {r['page_key']: r for r in read(OUT / 'development_pages.jsonl')}
    rows = read(OUT / 'four_arm_probes.jsonl')
    assert len(rows) == len(records) == freeze['development_candidates']
    assert len({r['triple_id'] for r in rows}) == len(rows)
    checks = Counter()
    normalized = lambda s: ''.join(s.split())
    for result in rows:
        r = records[result['triple_id']]
        p = pages[f"{r['doc_id']}:p{r['pdf_page_number']:04d}"]
        text = p['page_text']
        assert hashlib.sha256(text.encode()).hexdigest() == p['page_text_sha256'] == r['page_text_sha256']
        w = result['witness']
        assert not w['automatically_qualified'] and not w['semantic_support_verified']
        assert result['new_qualification_decision'] is None
        baseline = bool(r.get('evidence_level') in {'E1', 'E2'} and r['evidence_validation'].get('valid')
                        and r['evidence_validation'].get('silver_eligible'))
        arms = result['technical_readiness']
        assert arms['A'] == baseline
        assert arms['B'] == (baseline or w['repair_proposed'])
        assert arms['C'] == (baseline and not result['relation_warnings'])
        assert arms['D'] == (arms['B'] and not result['relation_warnings'])
        if not w['repair_proposed']:
            continue
        if w['kind'] == 'page_span':
            assert w['source_text'] == text[w['start']:w['end']]
            assert w['end'] - w['start'] <= 1200
            for field, label in [('head_span', 'head_surface'), ('tail_span', 'tail_surface')]:
                start, end = w[field]
                assert w['start'] <= start < end <= w['end']
                assert normalized(text[start:end]) == normalized(r[label])
            assert not p['tables'] and r['evidence_level'] != 'E2'
            checks['exact_context_witnesses'] += 1
        else:
            assert w['kind'] == 'parser_cells'
            cells = {c['cell_id']: c for t in p['tables'] for row in t['rows'] for c in row['cells']}
            assert all(cells[c['cell_id']] == c for c in w['units'])
            h, t = cells[w['head_cell']], cells[w['tail_cell']]
            assert h['table_id'] == t['table_id'] and h['row_id'] == t['row_id']
            assert normalized(r['head_surface']) in normalized(h['text'])
            assert normalized(r['tail_surface']) in normalized(t['text'])
            for cell in w['units']:
                box = cell['bbox']
                assert 0 <= box['x0'] < box['x1'] <= p['page_width']
                assert 0 <= box['top'] < box['bottom'] <= p['page_height']
            assert min(h['bbox']['bottom'], t['bbox']['bottom']) > max(h['bbox']['top'], t['bbox']['top'])
            checks['native_same_row_witnesses'] += 1
    # Reconstruct reserved selection from original build page metadata and v1 exposure.
    docs = [f'MP{i:03d}' for i in [*range(1, 8), *range(15, 23)]]
    all_pages = {}
    for doc in docs:
        for p in read(ROOT / f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl'):
            assert p['doc_id'] == doc and p['document_split'] == 'build_train'
            all_pages[f"{doc}:p{p['pdf_page_number']:04d}"] = p
    seen_keys = {r['page_key'] for r in read(V1 / 'page_sample_manifest.jsonl')}
    seen_keys |= {f"{r['doc_id']}:p{r['pdf_page_number']:04d}" for r in read(V1 / 'record_findings.jsonl')}
    forbidden = set()
    for k in seen_keys:
        doc, number = k.split(':p')
        forbidden |= {f'{doc}:p{n:04d}' for n in range(int(number) - 1, int(number) + 2)}
    texts = {' '.join(all_pages[k]['page_text'].split()) for k in seen_keys}
    strata = defaultdict(list)
    for k, p in all_pages.items():
        if k not in forbidden and ' '.join(p['page_text'].split()) not in texts:
            strata[(p['doc_id'], 'has_table' if p['tables'] else 'no_table')].append(k)
    expected = {min(keys, key=lambda k: hashlib.sha256(f'20260930/holdout/{k}'.encode()).hexdigest())
                for keys in strata.values()}
    holdout = read(OUT / 'holdout_manifest.jsonl')
    assert {r['page_key'] for r in holdout} == expected
    assert not expected.intersection(pages)
    assert all(r['reference_status'] == 'not_opened_for_annotation'
               and r['candidate_comparison_status'] == 'not_executed' for r in holdout)
    assert len(all_pages) == 1934 and len(holdout) == 29
    summary = json.loads((OUT / 'summary.json').read_text())
    assert summary['technical_readiness'] == {a: sum(r['technical_readiness'][a] for r in rows) for a in 'ABCD'}
    assert summary['witness_status'] == dict(Counter(r['witness']['status'] for r in rows))
    assert summary['source_witness_proposals'] == sum(checks.values()) == 25
    completion = json.loads((OUT / 'probe_completion.json').read_text())
    assert freeze['frozen_at'] < completion['completed_at']
    assert completion['results_sha256'] == sha(OUT / 'four_arm_probes.jsonl')
    result = {'status': 'passed', 'preexisting_files_byte_identical': len(before),
              'v1_delivery_files_byte_identical': len(v1_delivery),
              'new_witnesses_reconstructed': dict(checks), 'four_arm_set_relations_verified': True,
              'holdout_reconstructed_from_build_only': len(holdout),
              'holdout_not_used_by_repair_probe': True, 'frozen_protocol_and_code_unchanged': True,
              'new_automatic_qualification': 0, 'semantic_truth_or_formal_recall_verified': False}
    with (OUT / 'verification.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
