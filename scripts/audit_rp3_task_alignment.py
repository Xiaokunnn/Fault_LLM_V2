#!/usr/bin/env python3
"""Audit existing build supervision and saved prompts; never load a model."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.augment_rp3_interventions import reselect
from src.research_point_2.dataset import EvidenceCandidate, SilverQuery
from src.research_point_2.generation import (
    apply_evidence_coverage_guard, build_generation_prompt,
    build_recall_review_prompt, expand_compact_evidence_mask,
    parse_single_recall_review,
)
from src.research_point_3.artifacts import (
    canonical_json_bytes, canonical_jsonl_bytes, file_sha256,
    normalized_text_sha256, read_compact_evidence_memory_bundle,
    read_teacher_trace_bundle, stable_sha256,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def answer_ids(run):
    return [eid for point in run['answer']['answer_points'] for eid in point['evidence_ids']]


def label_from_run(run, eid):
    """Malformed auxiliary output is missing supervision, even if a bit is 0."""
    ids = [r['evidence_id'] for r in run['expanded_model_answer']['evidence_assessments']]
    if not run['cascade_contract_valid']:
        return None
    return run['final_mask'][ids.index(eid)]


def origin_for(eid, current_prefix, base_prefix, derived):
    if derived and eid in current_prefix:
        return 'fresh_intervention_k3'
    base = 'base_k3' if eid in base_prefix else 'base_singleton_tail'
    return ('inherited_' if derived else '') + base


def alias_summary(rows, key):
    """Empirical contradictions, not a population-risk estimate."""
    groups = defaultdict(list)
    for row in rows:
        if row['eligible'] and row['label'] is not None:
            groups[row[key]].append(row)
    conflicts = []
    errors = 0
    for identity, items in sorted(groups.items()):
        counts = Counter(r['label'] for r in items)
        errors += min(counts.get(0, 0), counts.get(1, 0))
        if len(counts) == 2:
            conflicts.append({'key': identity, 'positive': counts[1], 'negative': counts[0],
                              'occurrences': items})
    return {'occurrences': sum(map(len, groups.values())), 'unique_inputs': len(groups),
            'conflicting_inputs': len(conflicts), 'minimum_empirical_errors': errors,
            'conflicts': conflicts}


def prompt_summary(calls):
    result = {}
    for stage in ('precision_mask', 'recall_review'):
        groups = defaultdict(list)
        for call in calls:
            if call['stage'] == stage:
                groups[call['user_prompt_sha256']].append(call)
        conflicts = [items for items in groups.values()
                     if len({stable_sha256(r['response']) for r in items}) > 1]
        result[stage] = {'calls': sum(map(len, groups.values())), 'unique_user_prompts': len(groups),
                         'repeated_prompt_groups': sum(len(v) > 1 for v in groups.values()),
                         'different_response_groups': len(conflicts), 'conflicts': conflicts}
    return result


def template_for(query):
    name = query['fault_name_zh']
    require(name and name in query['question_zh'], 'fault name missing from controlled query')
    return query['question_zh'].replace(name, '{fault_scope}')


class Inputs:
    def __init__(self, root):
        self.root = root
        self.bindings = {}

    def bind(self, path):
        path = Path(path)
        path = path if path.is_absolute() else self.root / path
        rel = str(path.relative_to(self.root))
        self.bindings[rel] = {'sha256': file_sha256(path), 'bytes': path.stat().st_size}
        return path

    def json(self, path):
        return json.loads(self.bind(path).read_text(encoding='utf-8-sig'))

    def rows(self, path):
        return [json.loads(s) for s in self.bind(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def coverage(traces, memory):
    report = {}
    evidence_sets = {}
    for split in ('train', 'validation'):
        originals = [t for t in traces if t['split'] == split and t['perturbation_id'] == 'original']
        all_rows = [t for t in traces if t['split'] == split]
        candidates = {e for t in originals for e in t['candidate_evidence_ids']}
        selected = {d['evidence_id'] for t in originals for d in t['evidence_decisions'] if d['selected']}
        scenarios = sorted({t['query']['scenario_id'] for t in originals})
        report[split] = {'original_queries': len(originals), 'all_traces': len(all_rows),
            'derived_traces': len(all_rows) - len(originals), 'fault_scenarios': scenarios,
            'scenario_count': len(scenarios),
            'question_texts': len({t['query']['question_zh'] for t in originals}),
            'fault_masked_templates': sorted({template_for(t['query']) for t in originals}),
            'roles': dict(Counter(t['query']['requested_role'] for t in originals)),
            'nonempty_operating_contexts': sum(bool(t['query']['operating_context']) for t in originals),
            'families': [{'scenario_id': s,
                'query_ids': [t['query']['query_id'] for t in originals if t['query']['scenario_id'] == s],
                'derived_count': sum(t['query']['scenario_id'] == s and t['perturbation_id'] != 'original' for t in all_rows)} for s in scenarios]}
        evidence_sets[split] = {'candidate_evidence': candidates, 'selected_evidence': selected}
        for kind, ids in (('candidate', candidates), ('selected', selected)):
            evidence_sets[split].update({kind + '_claims': {memory[e]['claim_id'] for e in ids},
                kind + '_documents': {memory[e]['provenance']['doc_id'] for e in ids},
                kind + '_source_families': {memory[e]['provenance']['source_family_id'] for e in ids}})
    report['overlap'] = {kind: {'train_count': len(ids), 'validation_count': len(evidence_sets['validation'][kind]),
        'intersection_count': len(ids & evidence_sets['validation'][kind]),
        'intersection': sorted(ids & evidence_sets['validation'][kind]),
        'validation_only': sorted(evidence_sets['validation'][kind] - ids)}
        for kind, ids in evidence_sets['train'].items()}
    report['template_overlap'] = sorted(set(report['train']['fault_masked_templates']) & set(report['validation']['fault_masked_templates']))
    report['scenario_overlap'] = sorted(set(report['train']['fault_scenarios']) & set(report['validation']['fault_scenarios']))
    return report


def aggregate(rows, trace_rows):
    result = {}
    for split in ('train', 'validation'):
        for kind in ('original', 'derived', 'all'):
            ts = [t for t in trace_rows if t['split'] == split and (kind == 'all' or t['kind'] == kind)]
            ids = {t['trace_id'] for t in ts}
            rs = [r for r in rows if r['trace_id'] in ids]
            eligible = [r for r in rs if r['eligible']]
            assessed = [r for r in eligible if r['label'] is not None]
            result[split + '_' + kind] = {
                'traces': len(ts), 'candidate_slots': len(rs), 'available_requested_slots': len(eligible),
                'assessed_slots': len(assessed), 'not_assessed_slots': sum(r['label'] is None for r in eligible),
                'positive_selected': sum(r['label'] == 1 and r['selected'] for r in assessed),
                'positive_unselected': sum(r['label'] == 1 and not r['selected'] for r in assessed),
                'negative_selected': sum(r['label'] == 0 and r['selected'] for r in assessed),
                'negative_unselected': sum(r['label'] == 0 and not r['selected'] for r in assessed),
                'unavailable_slots': sum(not r['available'] for r in rs),
                'unavailable_positive_labels': sum(not r['available'] and r['label'] == 1 for r in rs),
                'unavailable_selected': sum(not r['available'] and r['selected'] for r in rs),
                'label_origin_counts': dict(Counter(r['origin'] for r in assessed)),
                'unique_label_events': len({(r['origin_run_id'], r['evidence_id']) for r in assessed}),
                'inherited_origin_contains_removed_evidence': sum(r['origin_context_contains_unavailable'] for r in assessed),
                'teacher_empty': sum(not t['selected_ids'] for t in ts),
                'teacher_empty_with_available': sum(not t['selected_ids'] and t['available_count'] > 0 for t in ts),
                'teacher_empty_with_positive_tail': sum(not t['selected_ids'] and t['tail_positive_count'] > 0 for t in ts),
                'positive_unselected_reasons': dict(Counter(r['nonselection_reason'] for r in assessed if r['label'] == 1 and not r['selected'])),
                'all_pool_positive_top3_set_disagreements': sum(not t['all_pool_positive_top3_set_match'] for t in ts),
                'all_pool_positive_top3_order_disagreements': sum(not t['all_pool_positive_top3_order_match'] for t in ts),
                'negative_prefix_with_positive_tail_traces': sum(t['prefix_negative_count'] > 0 and t['tail_positive_count'] > 0 for t in ts),
                'prefix_guard_exact_matches': sum(t['prefix_guard_exact_match'] for t in ts),
            }
    return result


def run_audit(root, protocol_path):
    inputs = Inputs(root)
    protocol = inputs.json(protocol_path)
    trace_root = root / protocol['trace_root']
    raw_dir = root / protocol['raw_teacher_dir']
    memory_dir = root / protocol['memory_dir']
    config = inputs.json(protocol['teacher_config'])
    freeze = inputs.json(protocol['teacher_freeze'])
    base_manifest = inputs.json(trace_root / 'training/manifest.json')
    aug_manifest = inputs.json(trace_root / 'augmented_training/manifest.json')
    mem_manifest = inputs.json(memory_dir / 'manifest.json')
    base_traces = inputs.rows(trace_root / 'training/teacher_traces.jsonl')
    traces = inputs.rows(trace_root / 'augmented_training/teacher_traces.jsonl')
    memory = {r['evidence_id']: r for r in inputs.rows(memory_dir / 'evidence_memory.jsonl')}
    # Existing readers enforce purpose, hash, memory and corpus boundaries.
    read_teacher_trace_bundle(trace_root / 'training', purpose='training')
    read_teacher_trace_bundle(trace_root / 'augmented_training', purpose='training')
    read_compact_evidence_memory_bundle(memory_dir, purpose='training')
    for manifest in (base_manifest, aug_manifest, mem_manifest):
        require(manifest['teacher_system_identity_sha256'] == freeze['teacher_system_identity_sha256'], 'teacher identity')
    raw = {r['query_id']: r for r in inputs.rows(raw_dir / 'teacher_candidate_traces.jsonl')}
    raw_manifest = inputs.json(raw_dir / 'manifest.json')
    require(normalized_text_sha256(raw_dir / 'teacher_candidate_traces.jsonl') == base_manifest['candidate_trace']['data_sha256'], 'candidate hash')
    require(normalized_text_sha256(raw_dir / 'manifest.json') == base_manifest['candidate_trace']['manifest_sha256'], 'candidate manifest hash')
    require(raw_manifest['base_query_count'] == len(raw) == len(base_traces) == 40, '40 originals required')
    for artifact in freeze['teacher_trace_artifacts']:
        require(normalized_text_sha256(inputs.bind(artifact['path'])) == artifact['sha256'], 'frozen raw teacher binding')
    interventions = {r['trace_id']: r for r in inputs.rows(trace_root / 'augmented_training/intervention_audit.jsonl')}
    lineage = inputs.json(trace_root / 'augmented_training/lineage.json')
    require(file_sha256(trace_root / 'training/manifest.json') == lineage['base_manifest_sha256'], 'lineage base manifest')
    require(file_sha256(trace_root / 'augmented_training/intervention_audit.jsonl') == lineage['intervention_audit_sha256'], 'lineage audit hash')
    originals = {t['trace_id']: t for t in base_traces}
    require(len(traces) == 165 and len(interventions) == 125 and len({t['trace_id'] for t in traces}) == 165, 'trace counts')
    require({t['trace_id']: t for t in traces if t['perturbation_id'] == 'original'} == originals, 'original rows changed')
    allowed_docs = {f'MP{i:03}' for i in [*range(1, 8), *range(15, 23)]}
    require({r['provenance']['doc_id'] for r in memory.values()} <= allowed_docs, 'nonbuild memory')
    candidates = {r['evidence_id']: EvidenceCandidate(**{**r, 'fault_class_ids': tuple(r['fault_class_ids'])})
                  for r in inputs.rows(Path(config['benchmark_dir']) / 'evidence_candidates.jsonl')}
    require(set(candidates) == set(memory) and len(memory) == 208, 'strict208 closure')
    caches = defaultdict(list)
    for folder in (raw_dir / 'model_cache', trace_root / 'augmented_training/verifier_cache'):
        for path in sorted(folder.glob('*.json')):
            row = inputs.json(path)
            payload = row['cache_payload']
            expected_name = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            require(path.stem == expected_name, 'cache filename mismatch: ' + str(path))
            caches[(payload['fingerprint'], payload['query_id'])].append((str(path.relative_to(root)), row))

    run_records = {}
    calls = []
    used_cache_paths = set()
    scenario = next(s for s in config['scenarios'] if s['id'] == 'Ours_v6_k3_equal')

    def register(run, run_id, ids, q, split, kind, source):
        query = SilverQuery(run['query_id'], q['question_zh'], q['fault_id'], q['fault_name_zh'], q['requested_role'], ())
        evidence = [candidates[e] for e in ids]
        require(ids == [r['evidence_id'] for r in run['expanded_model_answer']['evidence_assessments']], 'run evidence order')
        _, first_audit = expand_compact_evidence_mask(run['first_payload'], evidence)
        first = first_audit['normalized_mask']
        first = first if first is not None else [0] * len(ids)
        require(first == run['first_mask'] and first_audit == run['first_audit'], 'first mask reconstruction')
        final = list(first)
        reviews = {r['candidate_index']: r for r in run['review_rows']}
        require(set(reviews) == {i for i, bit in enumerate(first) if bit == 0}, 'conditional review coverage')
        for i, review in reviews.items():
            require(review['evidence_id'] == ids[i], 'review ID mapping')
            bit, audit = parse_single_recall_review(review['payload'])
            require(audit == review['audit'], 'review audit reconstruction')
            final[i] = bit if audit['contract_valid'] else 0
        valid = first_audit['mask_contract_valid'] and all(r['audit']['contract_valid'] for r in reviews.values())
        require(final == run['final_mask'] and valid == run['cascade_contract_valid'], 'cascade reconstruction')
        expanded, _ = expand_compact_evidence_mask({'direct': final}, evidence)
        guarded, guard = apply_evidence_coverage_guard(expanded, query, evidence, config['generation_contract'],
            minimum_fault_affinity=float(scenario.get('minimum_visible_fault_affinity', 0)))
        require(guarded == run['answer'], 'guard answer mismatch')
        require({k:v for k,v in guard.items() if k != 'elapsed_ms'} ==
                {k:v for k,v in run['faithfulness_guard'].items() if k != 'elapsed_ms'}, 'guard audit mismatch')
        matched = caches.get((run['protocol_fingerprint'], run['query_id']), [])
        require(len(matched) == (int(bool(ids)) + len(reviews)), 'cache call count: ' + run_id)
        precision_sha = None
        review_shas = {}
        paths = []
        for path, row in matched:
            payload = row['cache_payload']
            stage = payload['stage']
            if stage == 'precision_mask':
                expected_prompt = build_generation_prompt(query, evidence, strategy='evidence_mask_v3')
                expected_answer = run['first_payload']
                candidate_index = None
                max_tokens = config['generator']['stage1_max_new_tokens']
            else:
                require(stage == 'recall_review', 'unknown cache stage')
                candidate_index = payload['candidate_index']
                expected_prompt = build_recall_review_prompt(query, evidence[candidate_index])
                expected_answer = reviews[candidate_index]['payload']
                max_tokens = config['generator']['review_max_new_tokens']
            require(expected_prompt == payload['prompt'] and expected_answer == row['answer'], 'saved prompt/response mismatch: ' + path)
            require(row['generation_metrics']['do_sample'] is False and row['generation_metrics']['requested_max_new_tokens'] == max_tokens, 'generation settings')
            sha = hashlib.sha256(payload['prompt'].encode()).hexdigest()
            if stage == 'precision_mask':
                require(precision_sha is None, 'duplicate precision cache')
                precision_sha = sha
            else:
                require(candidate_index not in review_shas, 'duplicate review cache')
                review_shas[candidate_index] = sha
            calls.append({'run_id': run_id, 'split': split, 'stage': stage, 'candidate_index': candidate_index,
                'user_prompt_sha256': sha, 'response': row['answer'], 'cache_path': path,
                'cache_model_identity': payload['model'], 'requested_max_new_tokens': max_tokens,
                'do_sample': False, 'protocol_fingerprint': payload['fingerprint']})
            paths.append(path)
            used_cache_paths.add(path)
        require(bool(precision_sha) == bool(ids), 'missing precision cache')
        record = {'run_id': run_id, 'kind': kind, 'split': split, 'source': source,
            'query_id': q['query_id'], 'actual_run_query_id': run['query_id'], 'evidence_ids': ids,
            'first_mask': first, 'final_mask': final, 'valid': bool(valid), 'selected_ids': answer_ids(run),
            'guard_drops': guard['dropped_points'], 'protocol_fingerprint': run['protocol_fingerprint'],
            'precision_user_prompt_sha256': precision_sha, 'review_prompt_sha256_by_index': review_shas,
            'review_bits': {i: final[i] for i in reviews}, 'cache_paths': sorted(paths)}
        require(run_id not in run_records, 'duplicate run_id')
        run_records[run_id] = record
        return record

    by_query = {t['query']['query_id']: t for t in base_traces}
    for query_id, row in sorted(raw.items()):
        t = by_query[query_id]
        require(row['query_id'] == t['query']['query_id'], 'query identity')
        recovered = inputs.json(raw_dir / 'checkpoints' / (query_id + '.json'))
        require(recovered['row'] == row, 'raw checkpoint mismatch')
        register(row['base_verifier_run'], 'base:' + query_id, row['rp2_selected_before_verifier'],
                 t['query'], t['split'], 'base_k3', f"{protocol['raw_teacher_dir']}/teacher_candidate_traces.jsonl#{query_id}/base_verifier_run")
        for eid, run in sorted(row['auxiliary_tail_verifier_runs'].items()):
            register(run, 'tail:' + query_id + ':' + eid, [eid], t['query'], t['split'], 'base_singleton_tail',
                f"{protocol['raw_teacher_dir']}/teacher_candidate_traces.jsonl#{query_id}/auxiliary_tail_verifier_runs/{eid}")

    rows = []
    trace_rows = []
    for t in traces:
        tid, q = t['trace_id'], t['query']
        require(t['split'] in ('train', 'validation'), 'nonbuild split')
        base = raw[q['query_id']]
        derived = t['perturbation_id'] != 'original'
        removed = {eid for eid, ok in zip(t['candidate_evidence_ids'], t['availability_mask']) if not ok}
        prefix = [e.evidence_id for e, _ in reselect(base['candidates'], removed, candidates, config['retrieval'])]
        if derived:
            intervention = interventions[tid]
            parent = originals[intervention['parent']]
            require(parent['query'] == q and parent['split'] == t['split'] and t['metadata']['parent_trace_id'] == parent['trace_id'], 'parent grouping')
            require(removed == set(intervention['removed']), 'removed mask')
            checkpoint = inputs.json(trace_root / 'augmented_training/checkpoints' / (tid + '.json'))
            require(checkpoint['run'] == intervention['verifier'], 'intervention checkpoint')
            current = register(intervention['verifier'], 'intervention:' + tid, prefix, q, t['split'], 'fresh_intervention_k3',
                f"{protocol['trace_root']}/augmented_training/intervention_audit.jsonl#{tid}/verifier")
        else:
            require(prefix == base['rp2_selected_before_verifier'], 'base bounded selection')
            current = run_records['base:' + q['query_id']]
        require(current['valid'], 'invalid on-policy verifier')
        decisions = {d['evidence_id']: d for d in t['evidence_decisions']}
        require(list(decisions) == t['candidate_evidence_ids'], 'decision positions')
        expected_order = prefix + [r['evidence_id'] for r in base['candidates'] if r['evidence_id'] not in prefix]
        require(sorted(decisions, key=lambda e: -decisions[e]['teacher_score']) == expected_order, 'ranking target reconstruction')
        selected = [e for e in prefix if decisions[e]['selected']]
        require(set(selected) == {e for e,d in decisions.items() if d['selected']} and selected == current['selected_ids'], 'selected mapping')
        card_ids = [e for slot in t['diagnosis_card']['slots'] for item in slot['items'] for e in item['evidence_ids']]
        require(set(card_ids) == set(selected), 'card pointers')
        current_drops = {r['evidence_id']: r['reason'] for r in current['guard_drops']}
        current_rows = []
        for eid, available in zip(t['candidate_evidence_ids'], t['availability_mask']):
            origin = origin_for(eid, prefix, base['rp2_selected_before_verifier'], derived)
            origin_id = (current['run_id'] if origin == 'fresh_intervention_k3' else
                         'base:' + q['query_id'] if origin.endswith('base_k3') else 'tail:' + q['query_id'] + ':' + eid)
            event = run_records[origin_id]
            position = event['evidence_ids'].index(eid)
            label = event['final_mask'][position] if event['valid'] else None
            expected_support = 'not_assessed' if label is None else 'direct' if label else 'irrelevant'
            require(decisions[eid]['support'] == expected_support, 'exported label differs from origin')
            # Current prefix supplies new labels; outside it the original map is retained.
            if origin != 'fresh_intervention_k3':
                require(base['final_support_by_evidence_id'].get(eid) == label, 'original label map')
            if decisions[eid]['selected']:
                require(available and label == 1 and memory[eid]['role'] == q['requested_role'], 'selected contract')
            point_input = [q['question_zh'], q['requested_role'], q['fault_name_zh'], eid]
            semantic_input = point_input[:3] + [memory[eid][key] for key in ('head_label_zh', 'relation', 'tail_label_zh', 'evidence_text', 'role')]
            r = {'trace_id': tid, 'query_id': q['query_id'], 'scenario_id': q['scenario_id'], 'split': t['split'],
                'kind': 'derived' if derived else 'original', 'role': q['requested_role'], 'evidence_id': eid,
                'available': available, 'eligible': available and memory[eid]['role'] == q['requested_role'],
                'label': label, 'selected': decisions[eid]['selected'], 'in_current_prefix': eid in prefix,
                'teacher_rank_score': decisions[eid]['teacher_score'], 'origin': origin, 'origin_run_id': origin_id,
                'origin_position': position, 'origin_context_ids': event['evidence_ids'],
                'origin_context_contains_unavailable': bool(removed & set(event['evidence_ids'])) if available else False,
                'first_bit': event['first_mask'][position], 'reviewed': position in event['review_bits'],
                'review_bit': event['review_bits'].get(position),
                'precision_prompt_sha256': event['precision_user_prompt_sha256'],
                'review_prompt_sha256': event['review_prompt_sha256_by_index'].get(position),
                'pair_key': stable_sha256(point_input), 'semantic_pair_key': stable_sha256(semantic_input),
                'origin_prompt_position_key': stable_sha256([event['precision_user_prompt_sha256'], position]),
                'nonselection_reason': None if decisions[eid]['selected'] else 'unavailable' if not available else
                    'outside_current_k3' if eid not in prefix else current_drops.get(eid, 'negative_or_not_assessed')}
            rows.append(r)
            current_rows.append(r)
        positives = sorted([r for r in current_rows if r['eligible'] and r['label'] == 1], key=lambda r: -r['teacher_rank_score'])
        naive = [r['evidence_id'] for r in positives[:t['selection_budget']]]
        trace_rows.append({'trace_id': tid, 'query_id': q['query_id'], 'scenario_id': q['scenario_id'], 'split': t['split'],
            'kind': 'derived' if derived else 'original', 'role': q['requested_role'],
            'candidate_count': len(current_rows), 'available_count': sum(r['available'] for r in current_rows),
            'prefix_ids': prefix, 'selected_ids': selected, 'final_mask': current['final_mask'],
            'prefix_negative_count': sum(bit == 0 for bit in current['final_mask']),
            'tail_positive_count': sum(r['eligible'] and r['label'] == 1 and not r['in_current_prefix'] for r in current_rows),
            'all_pool_positive_top3_ids': naive, 'all_pool_positive_top3_set_match': set(naive) == set(selected),
            'all_pool_positive_top3_order_match': naive == selected, 'prefix_guard_exact_match': True,
            'run_id': current['run_id']})

    previous = inputs.json(protocol['previous_alias_audit'])
    legacy_rows = inputs.rows(Path(protocol['previous_alias_audit']).parent / 'candidate_rows.jsonl')
    legacy = {(r['trace_id'], r['evidence_id']): r for r in legacy_rows if r['arm'] == 'C0' and r['seed'] == 7042027}
    for row in rows:
        old_row = legacy.get((row['trace_id'], row['evidence_id']))
        if row['eligible'] and row['label'] is not None:
            require(old_row is not None and old_row['label'] == row['label'], 'previous candidate label identity')
        row['legacy_feature_key'] = old_row['pointwise_key'] if old_row else None
    aliases = {split: {key: alias_summary([r for r in rows if r['split'] == split], key)
        for key in ('pair_key', 'semantic_pair_key', 'legacy_feature_key', 'origin_prompt_position_key')} for split in ('train', 'validation')}
    for split in ('train', 'validation'):
        new = aliases[split]['pair_key']
        old = previous['aliases'][split]['pointwise_key']
        def signature(groups):
            return {frozenset((r['trace_id'], r['evidence_id'], r['label']) for r in c['occurrences']) for c in groups}
        require(signature(new['conflicts']) == signature(old['conflicts']), 'previous feature conflict membership')
        feature = aliases[split]['legacy_feature_key']
        require((feature['occurrences'], feature['unique_inputs'], feature['minimum_empirical_errors']) ==
                (old['occurrences'], old['unique_inputs'], old['empirical_minimum_01_errors']), 'previous alias counts')
    conflicts = []
    for split in ('train', 'validation'):
        for group in aliases[split]['pair_key']['conflicts']:
            events = {r['origin_run_id']: r for r in group['occurrences']}
            event_rows = list(events.values())
            negative_reviews = {r['review_bit'] for r in event_rows if r['label'] == 0}
            positive_paths = Counter('first_stage_positive_skip_review' if r['first_bit'] == 1 else 'review_positive' for r in event_rows if r['label'] == 1)
            conflicts.append({'split': split, 'query_id': event_rows[0]['query_id'], 'evidence_id': event_rows[0]['evidence_id'],
                'pair_key': group['key'], 'positive_occurrences': group['positive'], 'negative_occurrences': group['negative'],
                'unique_origin_runs': len(events), 'positive_paths': dict(positive_paths),
                'negative_review_bits': sorted(negative_reviews),
                'distinct_precision_prompts': len({r['precision_prompt_sha256'] for r in event_rows}),
                'origin_kinds': sorted({run_records[r['origin_run_id']]['kind'] for r in event_rows}),
                'occurrences': group['occurrences'],
                'canonical_claim': f"{memory[event_rows[0]['evidence_id']]['head_label_zh']} --{memory[event_rows[0]['evidence_id']]['relation']}--> {memory[event_rows[0]['evidence_id']]['tail_label_zh']}"})
    call_groups = prompt_summary(calls)
    for path in ('scripts/augment_rp3_interventions.py', 'scripts/run_rp3_teacher.py',
                 'src/research_point_3/teacher_runner.py', 'src/research_point_3/trace_export.py',
                 'src/research_point_3/dataset.py', 'src/research_point_2/generation.py',
                 'src/research_point_2/retrieval.py', 'scripts/run_rp2_equal_budget_v6.py',
                 'scripts/audit_rp3_task_alignment.py', 'docs/RP3_TASK_ALIGNMENT_AUDIT_V1_PROTOCOL.md'):
        inputs.bind(path)
    summary = {'schema': 'rp3_task_alignment_audit_v1', 'counts': aggregate(rows, trace_rows),
        'coverage': coverage(traces, memory),
        'aliases': {split: {key: {k:v for k,v in value.items() if k != 'conflicts'} for key,value in stats.items()} for split,stats in aliases.items()},
        'verifier_runs': len(run_records), 'run_kinds': dict(Counter(r['kind'] for r in run_records.values())),
        'validity_by_run_kind': {kind: dict(Counter('valid' if r['valid'] else 'invalid' for r in run_records.values() if r['kind'] == kind)) for kind in sorted({r['kind'] for r in run_records.values()})},
        'matched_cache_calls': len(calls), 'prompt_consistency': call_groups,
        'cache_model_identities_by_run_kind': {kind: sorted({c['cache_model_identity'] for c in calls if run_records[c['run_id']]['kind'] == kind}) for kind in sorted({r['kind'] for r in run_records.values()})},
        'unused_cache_files': sorted(path for group in caches.values() for path,_ in group if path not in used_cache_paths),
        'checks': {'manifest_hashes': True, 'original_rows_preserved': True, 'parent_split_inheritance': True,
            'bounded_selector_reconstruction': True, 'saved_prompts_and_responses': True, 'two_stage_mask_reconstruction': True,
            'guard_reconstruction': True, 'support_origin_reconstruction': True, 'previous_alias_membership': True},
        'boundary': {'development_content_read': False, 'external_content_read': False, 'model_calls': 0,
            'model_loads': 0, 'features_regenerated': False, 'labels_changed': False, 'thresholds_fit': False,
            'deployment_certificate_created': False, 'teacher_agreement_is_factual_accuracy': False,
            'same_user_prompt_scope': 'saved user prompt and stage only; system prompt source is bound, not duplicated inside old cache; runtime identity is not fully observed',
            'full_pool_positive_filter': 'label-semantic counterfactual using saved teacher labels; not an executable student or a new method score'}}
    return summary, rows, trace_rows, list(run_records.values()), calls, conflicts, inputs.bindings


def render_summary(summary, conflicts):
    lines = ['# RP3 构建集任务—监督对齐审计', '',
        '只读既有教师记录；没有模型调用、训练、特征重算或阈值拟合。完整解释见独立结果报告。', '',
        '| 子集 | 轨迹 | 可用已评估候选 | 正且入选 | 正但未选 | 负但入选 | 未评估 | 全池正标签取前3集合不一致 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, c in summary['counts'].items():
        lines.append(f"| {name} | {c['traces']} | {c['assessed_slots']} | {c['positive_selected']} | {c['positive_unselected']} | {c['negative_selected']} | {c['not_assessed_slots']} | {c['all_pool_positive_top3_set_disagreements']} |")
    lines += ['', '“全池正标签取前3”使用已保存教师标签，仅用于说明支持与选集目标的区别，不是新模型成绩。', '',
        '| split | 点式输入冲突组 | 最少经验错误/出现项 | 原标签产生的提示词+位置冲突组 |', '|---|---:|---:|---:|']
    for split, a in summary['aliases'].items():
        v = a['pair_key']
        lines.append(f"| {split} | {v['conflicting_inputs']} | {v['minimum_empirical_errors']}/{v['occurrences']} | {a['origin_prompt_position_key']['conflicting_inputs']} |")
    lines += ['', '| 查询 | 证据ID | split | 正/负出现 | 不同第一阶段提示 | 正标签生成路径 |', '|---|---|---|---:|---:|---|']
    for c in conflicts:
        lines.append(f"| {c['query_id']} | {c['evidence_id']} | {c['split']} | {c['positive_occurrences']}/{c['negative_occurrences']} | {c['distinct_precision_prompts']} | {c['positive_paths']} |")
    lines += ['', f"核验记录{summary['verifier_runs']}份，匹配模型响应缓存{summary['matched_cache_calls']}份。",
        '相同已保存用户提示词的检查不证明所有运行环境下教师确定性，亦不是因果实验。', '',
        '| split | 原始查询 | 派生轨迹 | 故障类别场景 | 故障名替换后模板 | 非空运行上下文 |', '|---|---:|---:|---:|---:|---:|']
    for split in ('train', 'validation'):
        c = summary['coverage'][split]
        lines.append(f"| {split} | {c['original_queries']} | {c['derived_traces']} | {c['scenario_count']} | {len(c['fault_masked_templates'])} | {c['nonempty_operating_contexts']} |")
    lines += ['', '故障类别场景不是独立现场病例；四种表面模板不是四个经过独立采样的临床/工程任务族。',
        '仍采用固定共享证据记忆；文档/来源族交集见summary.json，不能声称未见语料泛化。']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', default='configs/research_point_3/task_alignment_audit_v1.json')
    parser.add_argument('--output', help='new directory only; defaults to protocol output_dir')
    args = parser.parse_args()
    protocol_path = ROOT / args.protocol
    protocol = json.loads(protocol_path.read_text())
    out = ROOT / (args.output or protocol['output_dir'])
    require(out.resolve().is_relative_to(ROOT), 'output must be within repository')
    if out.exists():
        raise FileExistsError('preserve completed audit: ' + str(out))
    summary, rows, traces, runs, calls, conflicts, bindings = run_audit(ROOT, protocol_path)
    # Verify every bound byte again before creating outputs.
    require(all(file_sha256(ROOT / p) == v['sha256'] for p,v in bindings.items()), 'input changed during audit')
    out.mkdir(parents=True, exist_ok=False)
    artifacts = {'summary.json': canonical_json_bytes(summary), 'candidate_alignment.jsonl': canonical_jsonl_bytes(rows),
        'trace_alignment.jsonl': canonical_jsonl_bytes(traces), 'verifier_runs.jsonl': canonical_jsonl_bytes(runs),
        'cache_calls.jsonl': canonical_jsonl_bytes(calls), 'conflicts.json': canonical_json_bytes(conflicts),
        'input_bindings.json': canonical_json_bytes(bindings), 'protocol_snapshot.json': canonical_json_bytes(protocol),
        'summary.md': render_summary(summary, conflicts).encode()}
    stream = io.StringIO(newline='')
    simple = [{k:v for k,v in c.items() if not isinstance(v, dict)} | {'subset': name} for name,c in summary['counts'].items()]
    writer = csv.DictWriter(stream, fieldnames=list(simple[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(simple)
    artifacts['summary.csv'] = stream.getvalue().encode()
    for name, payload in artifacts.items():
        with (out / name).open('xb') as handle:
            handle.write(payload)
    manifest = {'schema': 'rp3_task_alignment_output_manifest_v1', 'artifacts': {
        name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)} for name,data in artifacts.items()},
        'input_count': len(bindings), 'model_calls': 0, 'old_inputs_byte_verified': True}
    (out / 'manifest.json').write_bytes(canonical_json_bytes(manifest))
    print(render_summary(summary, conflicts))
    print('Saved:', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
