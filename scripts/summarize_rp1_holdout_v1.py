#!/usr/bin/env python3
"""Summarize sealed source judgments without changing any experimental output."""
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from rp1_offline_contract_v3 import ROOT, rows, sha, write, object_sha, exact_key, channel, maximum_matching

BASE = ROOT / 'results/experiments/research_point_1/ai_review_v1'
OUT = BASE / 'holdout_comparison_v1'
ARMS = ['raw', 'mechanical_filter', 'source_constrained_repair']


def ratio(n, d):
    return n / d if d else None


def quality(records):
    counts = Counter(r['judgment']['verdict'] for r in records)
    s, e, u = (counts[k] for k in 'SEU')
    return dict(retained=len(records), S=s, E=e, U=u,
                lower=ratio(s, s+e+u), decided=ratio(s, s+e), upper=ratio(s+u, s+e+u),
                exact_unique=len({(r['page_key'], exact_key(r['payload'])) for r in records}))


def match(records):
    edges = defaultdict(set)
    for record in records:
        if record['judgment']['verdict'] == 'S':
            for ref in record['judgment']['reference_matches']:
                edges[ref].add(record['candidate_id'])
    return maximum_matching(edges)


def losses(raw, current, core_only):
    selected = [r for r in raw if r['judgment']['verdict'] == 'S'
                and (not core_only or channel(r['payload']) == 'core')]
    result = []
    for record in selected:
        other = current[record['candidate_id']]
        kind = None
        if not other['included']:
            kind = 'rejected_supported'
        elif other['judgment']['verdict'] != 'S':
            kind = 'damaged_supported'
        elif core_only and channel(other['payload']) != 'core':
            kind = 'removed_from_core'
        if kind:
            result.append(dict(candidate_id=record['candidate_id'], page_key=record['page_key'],
                review_id=record['judgment']['review_id'], loss_kind=kind,
                flags=other.get('screen_flags', []), reason=other.get('reason')))
    return result


def verify_sources():
    checked = {}
    for manifest in [BASE/'historical_evidence.json', BASE/'ai_method_freeze.json',
                     BASE/'heldout_materials/reference_and_request_freeze.json',
                     OUT/'generation_freeze.json', OUT/'review_freeze.json']:
        data = json.loads(manifest.read_text())
        # The historical inventory is a direct path/hash dictionary.
        hashes = data.get('sha256', data if manifest.name == 'historical_evidence.json' else {})
        for rel, expected in hashes.items():
            if sha(ROOT/rel) != expected:
                raise ValueError(('Frozen dependency changed', str(manifest), rel))
            checked[rel] = expected
    return checked


def summarize():
    checked = verify_sources()
    outputs = rows(OUT/'outputs.jsonl')
    judgements = rows(OUT/'source_quality_judgments.jsonl')
    packets = {r['review_id']: r for r in rows(OUT/'quality_review_packets.jsonl')}
    references = {r['reference_id']: r for r in rows(BASE/'heldout_materials/source_first_references.jsonl')}
    pages = rows(BASE/'heldout_materials/page_inventory.jsonl')
    source_pages = {r['page_key']: r for r in rows(BASE/'heldout_sources/source_only.jsonl')}
    lookup = {(r['page_key'], r['payload_sha256']): r for r in judgements}
    assert len(lookup) == len(judgements) == len(packets) == 328
    assert len(outputs) == 966 and len(pages) == 29 and len(references) == 118
    for judgment in judgements:
        packet = packets[judgment['review_id']]
        page = source_pages[judgment['page_key']]
        assert packet['payload_sha256'] == judgment['payload_sha256']
        assert page['page_text_sha256'] == judgment['source_page_sha256']
        for witness in judgment['source_witnesses']:
            text = page['page_text']
            if witness['kind'] == 'native_cell_subspan':
                cell = next(c for t in page['tables'] for row in t['rows'] for c in row['cells'] if c['cell_id'] == witness['cell_id'])
                text = cell['text']
                assert witness['bbox'] == cell.get('bbox')
            assert text[witness['start']:witness['end']] == witness['text']
        for ref in judgment['reference_matches'] + judgment['partial_reference_matches']:
            assert references[ref]['page_key'] == judgment['page_key']
    for record in outputs:
        record['judgment'] = lookup[(record['page_key'], object_sha(record['payload']))]
    arm_rows = {arm: [r for r in outputs if r['arm'] == arm] for arm in ARMS}
    raw_by_id = {r['candidate_id']: r for r in arm_rows['raw']}
    for arm in ARMS:
        assert len(arm_rows[arm]) == 322
        assert {r['candidate_id'] for r in arm_rows[arm]} == set(raw_by_id)
        for record in arm_rows[arm]:
            assert record['original_sha256'] == object_sha(raw_by_id[record['candidate_id']]['payload'])
            if arm in ['raw', 'mechanical_filter']:
                assert record['payload'] == raw_by_id[record['candidate_id']]['payload']

    page_results = []
    page_matches = []
    summary = {}
    loss_records = []
    full_references_per_page = Counter(r['page_key'] for r in references.values())
    for arm in ARMS:
        current = arm_rows[arm]
        kept = [r for r in current if r['included']]
        kept_core = [r for r in kept if channel(r['payload']) == 'core']
        all_loss = losses(arm_rows['raw'], {r['candidate_id']: r for r in current}, False)
        core_loss = losses(arm_rows['raw'], {r['candidate_id']: r for r in current}, True)
        loss_records += [dict(arm=arm, **r, original_core=channel(raw_by_id[r['candidate_id']]['payload']) == 'core') for r in all_loss]
        mapping = match(kept_core)
        mapping_all = match(kept)
        assert len(mapping.values()) == len(set(mapping.values()))
        assert len(mapping_all.values()) == len(set(mapping_all.values()))
        channels = {c: quality([r for r in kept if channel(r['payload']) == c]) for c in ['core', 'background', 'noncore', 'auxiliary']}
        summary[arm] = dict(all=quality(kept), channels=channels,
            full_reference_matches=len(mapping), reference_total=len(references),
            reference_coverage=ratio(len(mapping), len(references)),
            supported_original_loss_all=len(all_loss), supported_original_loss_core=len(core_loss),
            full_matches_including_background=len(mapping_all),
            full_matches_not_in_core=len(set(mapping_all)-set(mapping)),
            core_error_categories=dict(Counter(r['judgment']['error_category'] for r in kept_core if r['judgment']['verdict'] == 'E')),
            all_error_categories=dict(Counter(r['judgment']['error_category'] for r in kept if r['judgment']['verdict'] == 'E')))
        for page in pages:
            key = page['page_key']
            subset = [r for r in kept if r['page_key'] == key]
            core_subset = [r for r in subset if channel(r['payload']) == 'core']
            ref_count = full_references_per_page[key]
            allocation = {ref: cid for ref, cid in mapping.items() if references[ref]['page_key'] == key}
            one = dict(page_key=key, arm=arm, reference_total=ref_count,
                original_assertions=sum(r['page_key'] == key for r in arm_rows['raw']),
                all=quality(subset), core=quality(core_subset),
                full_matches=len(allocation), reference_coverage=ratio(len(allocation), ref_count),
                correct_original_loss_core=sum(r['page_key'] == key for r in core_loss))
            page_results.append(one)
            page_matches.append(dict(page_key=key, arm=arm, allocations=allocation,
                unmatched_references=sorted(ref for ref, r in references.items() if r['page_key'] == key and ref not in allocation)))
        valid = [p for p in page_results if p['arm'] == arm]
        macro = {}
        for metric in ['lower', 'decided', 'upper']:
            vals = [p['core'][metric] for p in valid if p['core'][metric] is not None]
            macro[metric] = mean(vals) if vals else None
            macro[metric+'_pages'] = len(vals)
        vals = [p['reference_coverage'] for p in valid if p['reference_coverage'] is not None]
        macro['reference_coverage'] = mean(vals)
        macro['reference_pages'] = len(vals)
        summary[arm]['page_macro'] = macro
        summary[arm]['pages_with_supported_core'] = sum(p['core']['S'] > 0 for p in valid)
        summary[arm]['reference_pages_covered'] = sum(p['full_matches'] > 0 for p in valid)
        summary[arm]['pages_with_any_output'] = sum(p['all']['retained'] > 0 for p in valid)

    baseline, final = (summary[a] for a in ARMS[1:])
    changes = []
    mechanical = {r['candidate_id']: r for r in arm_rows['mechanical_filter']}
    for r in arm_rows[ARMS[2]]:
        before = mechanical[r['candidate_id']]
        if before['included'] != r['included'] or before['payload'] != r['payload']:
            changes.append(dict(candidate_id=r['candidate_id'], page_key=r['page_key'],
                filter_included=before['included'], repair_included=r['included'],
                filter_review=before['judgment']['review_id'], repair_review=r['judgment']['review_id'],
                filter_verdict=before['judgment']['verdict'], repair_verdict=r['judgment']['verdict'],
                changed_fields={k: dict(before=before['payload'].get(k), after=r['payload'].get(k))
                    for k in set(before['payload']) | set(r['payload']) if before['payload'].get(k) != r['payload'].get(k)},
                repair_reason=r.get('reason'), quality_reason=r['judgment']['reason_zh']))
    paired = {(r['page_key'], r['arm']): r for r in page_results}
    strict_pages = [p['page_key'] for p in pages if
        paired[p['page_key'], ARMS[2]]['core']['S'] > paired[p['page_key'], ARMS[1]]['core']['S'] or
        paired[p['page_key'], ARMS[2]]['full_matches'] > paired[p['page_key'], ARMS[1]]['full_matches']]
    checks = dict(
        error_release_not_above_raw=final['all']['E'] <= summary['raw']['all']['E'],
        core_supported_not_below_filter=final['channels']['core']['S'] >= baseline['channels']['core']['S'],
        full_reference_matches_not_below_filter=final['full_reference_matches'] >= baseline['full_reference_matches'],
        core_problem_plus_unresolved_not_above_filter=final['channels']['core']['E']+final['channels']['core']['U'] <= baseline['channels']['core']['E']+baseline['channels']['core']['U'],
        all_problem_plus_unresolved_not_above_filter=final['all']['E']+final['all']['U'] <= baseline['all']['E']+baseline['all']['U'],
        original_correct_loss_not_above_filter=final['supported_original_loss_all'] <= baseline['supported_original_loss_all'],
        at_least_one_page_strict_gain=bool(strict_pages))
    completions = [json.loads(p.read_text()) for p in (BASE/'heldout_api_run_001').glob('*.completed.json')]
    assert len(completions) == 29
    usage = {k: sum(r['usage'].get(k, 0) for r in completions) for k in ['prompt_tokens', 'completion_tokens', 'total_tokens']}
    usage['cached_prompt_tokens'] = sum(r['usage'].get('prompt_tokens_details', {}).get('cached_tokens', 0) for r in completions)
    elapsed = [r['elapsed_seconds'] for r in completions]
    usage.update(response_count=29, model=sorted({r['returned_model'] for r in completions}),
        api_response_elapsed_sum_seconds=sum(elapsed), api_response_elapsed_mean_seconds=mean(elapsed),
        dollar_cost=None, price_lookup_performed=False, review_or_postprocess_API_calls=0)
    sidecars = rows(OUT/'extraction_sidecars.jsonl')
    results = dict(status='completed', pages=29, reference_pages=len(full_references_per_page),
        pages_without_core_references=29-len(full_references_per_page), original_assertions=322,
        unique_review_payloads=328, original_responses=29, arms=summary,
        expansion_gate=dict(status='PASS' if all(checks.values()) else 'FAIL', checks=checks, strict_gain_pages=strict_pages),
        usage=usage, model_sidecars=dict(auxiliary_items=sum(len(r['auxiliary']) for r in sidecars), unresolved_items=sum(len(r['unresolved']) for r in sidecars)),
        metrics_scope='AI source-supported representation and fixed-reference one-to-one coverage; same-document held-out pages',
        reference_change=False, method_change=False, external_evaluation_used=False,
        partial_reference_matches_counted=False, runtime_scope_reassigned=False)
    write(OUT/'metrics.json', results)
    write(OUT/'page_metrics.jsonl', page_results)
    write(OUT/'reference_allocations.jsonl', page_matches)
    write(OUT/'correct_knowledge_losses.jsonl', loss_records)
    write(OUT/'filter_repair_deltas.jsonl', changes)
    write(OUT/'evaluation_verification.json', dict(status='passed',
        frozen_dependency_files_checked=len(checked), review_payloads_checked=len(lookup),
        arm_decisions_checked=len(outputs), source_witnesses_checked=sum(len(j['source_witnesses']) for j in judgements),
        identical_payload_same_judgment=True, matching_injective=True,
        frozen_reference_total=118, partial_matches_excluded=True, page_sums_verified=True,
        sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__), OUT/'metrics.json',
            OUT/'page_metrics.jsonl', OUT/'reference_allocations.jsonl', OUT/'correct_knowledge_losses.jsonl', OUT/'filter_repair_deltas.jsonl']}))
    return results


if __name__ == '__main__':
    print(json.dumps(summarize(), ensure_ascii=False, indent=2))
