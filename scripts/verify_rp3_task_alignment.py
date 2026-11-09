#!/usr/bin/env python3
"""Independently reconcile the alignment audit and preserve pre-existing bytes."""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def check(ok, message):
    if not ok:
        raise ValueError(message)


def verify(out, inventory_path):
    manifest = read(out / 'manifest.json')
    for name, artifact in manifest['artifacts'].items():
        check(digest(out / name) == artifact['sha256'], 'output hash: ' + name)
        check((out / name).stat().st_size == artifact['bytes'], 'output bytes: ' + name)
    bindings = read(out / 'input_bindings.json')
    for name, artifact in bindings.items():
        check(digest(ROOT / name) == artifact['sha256'], 'input hash: ' + name)
    inventory = read(inventory_path)
    for name, artifact in inventory.items():
        check((ROOT / name).is_file() and digest(ROOT / name) == artifact['sha256'], 'preserved asset: ' + name)
    summary = read(out / 'summary.json')
    candidates = lines(out / 'candidate_alignment.jsonl')
    traces = {t['trace_id']: t for t in lines(out / 'trace_alignment.jsonl')}
    runs = {r['run_id']: r for r in lines(out / 'verifier_runs.jsonl')}
    calls = lines(out / 'cache_calls.jsonl')
    conflicts = read(out / 'conflicts.json')
    check(len(traces) == 165 and len(runs) == 317 and len(calls) == 519, 'artifact counts')
    check(len({c['cache_path'] for c in calls}) == len(calls), 'cache reused as independent call')
    for r in candidates:
        origin = runs[r['origin_run_id']]
        i = origin['evidence_ids'].index(r['evidence_id'])
        check(r['label'] == (origin['final_mask'][i] if origin['valid'] else None), 'origin label')
        check(r['selected'] == (r['evidence_id'] in traces[r['trace_id']]['selected_ids']), 'selection mapping')
        if r['selected']:
            check(r['eligible'] and r['label'] == 1 and r['in_current_prefix'], 'selection contract')
    for subset, counts in summary['counts'].items():
        split, kind = subset.split('_', 1)
        rows = [r for r in candidates if r['split'] == split and (kind == 'all' or r['kind'] == kind)]
        eligible = [r for r in rows if r['eligible'] and r['label'] is not None]
        table = Counter((r['label'], r['selected']) for r in eligible)
        for name, cell in [('positive_selected', (1, True)), ('positive_unselected', (1, False)),
                           ('negative_selected', (0, True)), ('negative_unselected', (0, False))]:
            check(table[cell] == counts[name], 'contingency table ' + subset + '/' + name)
        check(len(eligible) == counts['assessed_slots'], 'denominator ' + subset)

    # Independently reconstruct each empirical pointwise disagreement group.
    grouped = defaultdict(list)
    for r in candidates:
        if r['eligible'] and r['label'] is not None:
            grouped[(r['split'], r['pair_key'])].append(r)
    actual_conflicts = {key for key, rows in grouped.items() if len({r['label'] for r in rows}) == 2}
    check(actual_conflicts == {(c['split'], c['pair_key']) for c in conflicts}, 'conflict coverage')
    pathways = []
    for c in conflicts:
        rows = grouped[(c['split'], c['pair_key'])]
        events = {(r['origin_run_id'], r['evidence_id']): r for r in rows}.values()
        events = list(events)
        positives = [r for r in events if r['label'] == 1]
        negatives = [r for r in events if r['label'] == 0]
        pathways.append({'query_id': c['query_id'], 'evidence_id': c['evidence_id'], 'split': c['split'],
            'positive_events': len(positives), 'negative_events': len(negatives),
            'all_positive_first_stage_one': all(r['first_bit'] == 1 and not r['reviewed'] for r in positives),
            'all_negative_first_and_review_zero': all(r['first_bit'] == 0 and r['reviewed'] and r['review_bit'] == 0 for r in negatives),
            'origin_kinds': sorted({runs[r['origin_run_id']]['kind'] for r in events})})
    on_policy = {}
    for split in ('train', 'validation'):
        rows = [r for r in runs.values() if r['split'] == split and r['kind'] != 'base_singleton_tail']
        on_policy[split] = {'runs': len(rows), 'nonempty_input_runs': sum(bool(r['evidence_ids']) for r in rows),
            'mask_bits': sum(len(r['final_mask']) for r in rows), 'positive_bits': sum(sum(r['final_mask']) for r in rows),
            'unique_nonempty_precision_prompts': len({r['precision_user_prompt_sha256'] for r in rows if r['evidence_ids']})}
    aliases = defaultdict(list)
    for r in candidates:
        if r['eligible'] and r['label'] is not None:
            aliases[r['legacy_feature_key']].append(r)
    multiple_ids = []
    for key, rows in aliases.items():
        if len({r['pair_key'] for r in rows}) > 1:
            multiple_ids.append({'legacy_feature_key': key,
                'query_evidence_labels': sorted({(r['query_id'], r['evidence_id'], r['label']) for r in rows}),
                'semantic_pair_keys': sorted({r['semantic_pair_key'] for r in rows})})
    cached_prompt_conflicts = {}
    for stage in ('precision_mask', 'recall_review'):
        by_prompt = defaultdict(list)
        for c in calls:
            if c['stage'] == stage:
                raw = read(ROOT / c['cache_path'])
                prompt = raw['cache_payload']['prompt']
                check(hashlib.sha256(prompt.encode()).hexdigest() == c['user_prompt_sha256'], 'prompt byte hash')
                check(raw['answer'] == c['response'], 'response copy')
                by_prompt[prompt].append(json.dumps(raw['answer'], sort_keys=True))
        cached_prompt_conflicts[stage] = sum(len(set(v)) > 1 for v in by_prompt.values())
        check(cached_prompt_conflicts[stage] == summary['prompt_consistency'][stage]['different_response_groups'], 'prompt conflict count')
    return {'schema': 'rp3_task_alignment_verification_v1', 'all_checks_passed': True,
        'output_artifacts_verified': len(manifest['artifacts']), 'input_files_verified': len(bindings),
        'preserved_prior_files': len(inventory), 'preserved_prior_bytes': sum(a['bytes'] for a in inventory.values()),
        'inventory_path': str(inventory_path.relative_to(ROOT)), 'inventory_sha256': digest(inventory_path),
        'all_old_hashes_unchanged': True, 'contingency_tables_recomputed': True,
        'conflict_membership_recomputed': True, 'conflict_pathways': pathways,
        'on_policy_k3_supervision': on_policy, 'legacy_feature_aliases_with_multiple_evidence_ids': multiple_ids,
        'cached_identical_user_prompt_conflicts': cached_prompt_conflicts,
        'verification_source_sha256': digest(Path(__file__)),
        'model_calls': 0, 'development_external_access': 'byte hashes only for preservation; no semantic analysis'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='results/experiments/research_point_3/task_alignment_v1')
    parser.add_argument('--inventory', required=True)
    args = parser.parse_args()
    out = ROOT / args.output
    target = out / 'verification.json'
    check(not target.exists(), 'preserve prior verification')
    result = verify(out, ROOT / args.inventory)
    with target.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('conflict_pathways', 'legacy_feature_aliases_with_multiple_evidence_ids')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
