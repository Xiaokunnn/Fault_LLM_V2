"""Frozen, additive RP1 repair feasibility comparison on previously reviewed data."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import audit_rp1_loss_pages as old
from research_point_1_graph_evidence.stage03_schema_validation.repair_probe_v2 import probe

OUT = ROOT / 'results/experiments/research_point_1/scope_repair_v2'
V1 = old.OUT
PROTOCOL = ROOT / 'docs/research/RP1_SCOPE_AND_EVALUATION_V2_20260930.md'
ENGINE = ROOT / 'src/research_point_1_graph_evidence/stage03_schema_validation/repair_probe_v2.py'
CREATED = {str(p.relative_to(ROOT)) for p in [PROTOCOL, ENGINE, Path(__file__).resolve(),
           ROOT / 'scripts/run_rp1_v2_blind_second_opinion.py',
           ROOT / 'tests/unit/test_rp1_repair_probe_v2.py']}


def read(name):
    return old.read_rows(OUT / name)


def write_json(name, value):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def write_rows(name, records):
    with (OUT / name).open('x', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def write_csv(name, records):
    with (OUT / name).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


def priority(namespace, key):
    return hashlib.sha256(f'20260930/{namespace}/{key}'.encode()).hexdigest()


def prepare():
    pages, files = old.load_pages()
    packets = old.read_rows(V1 / 'record_review_packets.jsonl')
    candidates = {r['record']['triple_id']: r['record'] for r in packets}
    for r in old.read_rows(V1 / 'page_candidate_comparison_packets.jsonl'):
        if r['triple_id'] in candidates:
            assert r == candidates[r['triple_id']]
        candidates[r['triple_id']] = r
    used = {s['page_key'] for s in old.read_rows(V1 / 'page_sample_manifest.jsonl')}
    used.update(f"{p['record']['doc_id']}:p{p['record']['pdf_page_number']:04d}" for p in packets)
    excluded = set()
    for key in used:
        doc, n = key.split(':p')
        excluded.update(f'{doc}:p{i:04d}' for i in range(int(n) - 1, int(n) + 2))
    seen = {' '.join(pages[k]['page_text'].split()) for k in used}
    strata = defaultdict(list)
    eligible_frame = []
    for key, page in pages.items():
        if key in excluded or ' '.join(page['page_text'].split()) in seen:
            continue
        stratum = (page['doc_id'], 'has_table' if page['tables'] else 'no_table')
        strata[stratum].append(key)
        eligible_frame.append({'page_key': key, 'stratum': list(stratum),
                               'page_text_sha256': page['page_text_sha256']})
    holdout = []
    missing = []
    for doc in old.DOCS:
        for mode in ['has_table', 'no_table']:
            keys = strata[(doc, mode)]
            if not keys:
                missing.append([doc, mode])
                continue
            key = min(keys, key=lambda k: priority('holdout', k))
            holdout.append({'page_key': key, 'stratum': [doc, mode], 'population_n': len(keys),
                            'inclusion_probability_conditional_on_exclusion': 1 / len(keys),
                            'page_text_sha256': pages[key]['page_text_sha256'],
                            'reference_status': 'not_opened_for_annotation',
                            'candidate_comparison_status': 'not_executed'})
    assert not {r['page_key'] for r in holdout}.intersection(used)
    write_rows('holdout_eligible_frame.jsonl', eligible_frame)
    write_rows('holdout_manifest.jsonl', holdout)
    write_json('holdout_sampling_report.json', {
        'seed': 20260930, 'target': 30, 'selected': len(holdout),
        'reviewed_pages': len(used), 'eligible_pages': len(eligible_frame),
        'empty_strata': missing, 'replacement_or_relaxed_exclusion': False,
        'interpretation': 'Internal reserved pages; not document-disjoint or globally unseen by historical extraction.',
        'protocol_execution_deviation': 'One-per-stratum target is infeasible for empty strata; retain shortfall instead of relaxing exclusions.',
    })
    write_rows('development_candidates.jsonl', sorted(candidates.values(), key=lambda r: r['triple_id']))
    used_for_candidates = {f"{r['doc_id']}:p{r['pdf_page_number']:04d}" for r in candidates.values()}
    write_rows('development_pages.jsonl', [{'page_key': k, **pages[k]} for k in sorted(used_for_candidates)])
    write_rows('reference_scope_overlay.jsonl', [
        {'atom_id': r['atom_id'], 'v1_status_unchanged': r['match_status'],
         'v2_scope': 'background' if r['page_key'] in {'MP001:p0014', 'MP002:p0121'} else 'requires_v2_scope_adjudication',
         'not_a_performance_change': True}
        for r in old.read_rows(V1 / 'page_match_findings.jsonl')])
    protected = set()
    for directory in ('docs', 'papers', 'configs', 'src', 'scripts', 'tests', 'results', 'logs'):
        protected.update(p for p in (ROOT / directory).rglob('*') if p.is_file()
                         and not p.is_relative_to(OUT) and '__pycache__' not in p.parts
                         and str(p.relative_to(ROOT)) not in CREATED)
    protected.update(ROOT / k for k in json.loads((V1 / 'input_manifest.json').read_text())
                     if str(k) not in CREATED)
    protected.add(ROOT / 'AGENTS.md')
    write_json('preservation_before.json', {str(p.relative_to(ROOT)): old.sha(p) for p in sorted(protected)})
    inputs = [PROTOCOL, ENGINE, Path(__file__).resolve(), *files,
              OUT / 'development_candidates.jsonl', OUT / 'development_pages.jsonl',
              OUT / 'holdout_manifest.jsonl', V1 / 'record_findings.jsonl',
              V1 / 'page_candidate_findings.jsonl', V1 / 'page_match_findings.jsonl']
    write_json('experiment_freeze.json', {
        'frozen_at': datetime.now(timezone.utc).isoformat(), 'seed': 20260930,
        'development_candidates': len(candidates), 'development_pages': len(used_for_candidates),
        'holdout_pages': len(holdout), 'inputs': {str(p.relative_to(ROOT)): old.sha(p) for p in inputs},
        'semantic_ground_truth': False, 'new_automatic_qualification_permitted': False,
    })
    (OUT / 'engine_snapshot.py').write_bytes(ENGINE.read_bytes())
    (OUT / 'experiment_runner_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'candidate_n': len(candidates), 'reserved_pages': len(holdout), 'missing_strata': missing}))


def check_frozen():
    freeze = json.loads((OUT / 'experiment_freeze.json').read_text())
    for path, digest in freeze['inputs'].items():
        assert old.sha(ROOT / path) == digest, path
    return freeze


def run():
    check_frozen()
    pages = {r['page_key']: r for r in read('development_pages.jsonl')}
    rows = [probe(r, pages[f"{r['doc_id']}:p{r['pdf_page_number']:04d}"])
            for r in read('development_candidates.jsonl')]
    write_rows('four_arm_probes.jsonl', rows)
    write_json('probe_completion.json', {'n': len(rows), 'completed_at': datetime.now(timezone.utc).isoformat(),
                                        'results_sha256': old.sha(OUT / 'four_arm_probes.jsonl')})
    print(json.dumps({'n': len(rows), 'technical_readiness': {a: sum(r['technical_readiness'][a] for r in rows) for a in 'ABCD'},
                      'witness_status': dict(Counter(r['witness']['status'] for r in rows))}))


def summarize():
    check_frozen()
    rows = read('four_arm_probes.jsonl')
    by_id = {r['triple_id']: r for r in rows}
    records = old.read_rows(V1 / 'record_findings.jsonl')
    page_candidates = old.read_rows(V1 / 'page_candidate_findings.jsonl')
    cohorts = {'records_probability': [r for r in records if r['sample_kind'] == 'probability'],
               'records_supplement': [r for r in records if r['sample_kind'] == 'coverage_supplement'],
               'page_candidates': page_candidates}
    tables = []
    for name, cohort in cohorts.items():
        for arm in 'ABCD':
            selected = [r for r in cohort if by_id[r['triple_id']]['technical_readiness'][arm]]
            tables.append({'cohort': name, 'arm': arm, 'cohort_n': len(cohort), 'technical_ready_n': len(selected),
                           **{f'v1_ai_{s}': sum(r['semantic_support'] == s for r in selected)
                              for s in ['supported', 'unsupported', 'unresolved']},
                           'expert_accuracy': 'NA', 'formal_recall': 'NA'})
    write_csv('four_arm_diagnostic_summary.csv', tables)
    flagged_old = [r for r in rows if r['original_qualified'] and r['relation_warnings']]
    write_rows('old_qualified_recheck_queue.jsonl', flagged_old)
    novel = [r for r in rows if r['witness']['repair_proposed']]
    write_rows('new_source_witnesses.jsonl', novel)
    refs = old.read_rows(V1 / 'page_match_findings.jsonl')
    cidx = {r['candidate_id']: r['triple_id'] for r in old.read_rows(V1 / 'page_candidate_index.jsonl')}
    reference_table = []
    for arm in 'ABCD':
        ready = [r for r in refs if r['match_status'] == 'matched'
                 and any(by_id[cidx[c]]['technical_readiness'][arm] for c in r['candidate_ids'])]
        reference_table.append({'arm': arm, 'fixed_v1_reference_count': len(refs),
                                 'v1_explicitly_matched_reference_count': 93,
                                 'matched_refs_with_technical_ready_candidate': len(ready),
                                 'formal_recall': None, 'new_semantic_matches_generated': 0})
    write_json('reference_readiness_diagnostic.json', reference_table)
    result = {'version': 'scope_repair_v2', 'experiment': 'technical_locator_and_warning_probe',
              'n_unique_candidates': len(rows), 'four_arm': tables,
              'technical_readiness': {a: sum(r['technical_readiness'][a] for r in rows) for a in 'ABCD'},
              'witness_status': dict(Counter(r['witness']['status'] for r in rows)),
              'warning_counts_overlapping': dict(Counter(f for r in rows for f in r['relation_warnings'])),
              'original_qualified_in_probe': sum(r['original_qualified'] for r in rows),
              'original_qualified_flagged_for_recheck': len(flagged_old),
              'source_witness_proposals': len(novel), 'new_automatically_qualified': 0,
              'reference_diagnostic': reference_table,
              'holdout': json.loads((OUT / 'holdout_sampling_report.json').read_text()),
              'expert_adjudication': 'pending', 'complete_extractor_comparison': 'not_executed',
              'limitation': 'Same development cases used to design rules; v1 AI labels are provisional; structural readiness is not source truth or automatic qualification.'}
    write_json('summary.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'run', 'summarize'])
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'summarize': summarize}[args.stage]()
