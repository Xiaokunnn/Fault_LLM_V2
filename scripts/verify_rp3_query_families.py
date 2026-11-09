#!/usr/bin/env python3
"""Independently verify connected components, draft boundaries and preserved bytes."""
import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def check(value, message):
    if not value:
        raise ValueError(message)


def norm(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).casefold()).strip()


def verify(out, inventory):
    for name, data in read(out / 'manifest.json')['artifacts'].items():
        check(digest(out / name) == data['sha256'], 'artifact hash: ' + name)
    bindings = read(out / 'input_bindings.json')
    for name, data in bindings.items():
        check(digest(ROOT / name) == data['sha256'], 'input hash: ' + name)
    original = read(inventory)
    for name, data in original.items():
        check((ROOT / name).is_file() and digest(ROOT / name) == data['sha256'], 'preservation: ' + name)
    cfg = read(out / 'protocol_snapshot.json')
    mem = lines(ROOT / cfg['memory_path'])
    claims = {x['claim_id']: x for x in lines(ROOT / cfg['graph_root'] / 'claims.jsonl')}
    ent = {x['entity_id']: x for x in lines(ROOT / cfg['graph_root'] / 'entities.jsonl')}
    saved_groups = read(out / 'dependency_groups.json')
    all_ids = {r['evidence_id'] for r in mem}
    # Independent pairwise adjacency + breadth-first search, not the audit's DSU.
    for scheme, groups in saved_groups.items():
        keys = {}
        for row in mem:
            c, p = claims[row['claim_id']], row['provenance']
            ks = {('claim', row['claim_id']), ('page', p['doc_id'], p['physical_pdf_page'])}
            for side in ('head_entity_id', 'tail_entity_id'):
                e = ent[c[side]]
                ks.add(('entity_id', e['entity_id']))
                names = [e['canonical_label_zh']] + (e['source_surfaces'] if 'alias' in scheme else [])
                ks.update(('entity_surface', norm(x)) for x in names if norm(x))
            if 'source_family' in scheme:
                ks.add(('source_family', p['source_family_id']))
            keys[row['evidence_id']] = ks
        adjacency = {a: {b for b in all_ids if keys[a] & keys[b]} for a in all_ids}
        unvisited = set(all_ids)
        actual = set()
        while unvisited:
            queue, found = deque([min(unvisited)]), set()
            while queue:
                a = queue.popleft()
                if a in found:
                    continue
                found.add(a)
                queue.extend(adjacency[a] - found)
            unvisited -= found
            actual.add(frozenset(found))
        check(actual == {frozenset(g['evidence_ids']) for g in groups}, 'independent component reconstruction: ' + scheme)
        check(sum(len(g['evidence_ids']) for g in groups) == len(mem), 'duplicate or missing group membership')
    summary = read(out / 'summary.json')
    scopes = lines(out / 'scope_inventory.jsonl')
    queries = lines(out / 'query_drafts.jsonl')
    assignments = read(out / 'proposed_assignments.json')
    eligible_faults = {x for r in mem for c in [claims[r['claim_id']]] for x in (c['head_entity_id'], c['tail_entity_id']) if ent[x]['entity_type'] == cfg['scope_entity_type']}
    check({s['scope_entity_id'] for s in scopes} == eligible_faults, 'scope coverage')
    check(len(queries) == 4 * len(scopes) == summary['query_drafts'], 'query counts')
    check(len({q['query_id'] for q in queries}) == len(queries), 'query ID uniqueness')
    per_scope = defaultdict(set)
    for q in queries:
        check(q['eligible_for_training'] is False and q['teacher_label'] is None, 'new labels or unintended training admission')
        check(q['proposed_split'] == assignments[q['group_id']], 'split assignment')
        per_scope[q['scope_entity_id']].add(q['requested_role'])
    check(all(roles == set(cfg['roles']) for roles in per_scope.values()), 'role enumeration')
    with_anchors = 0
    for s in scopes:
        for role, anchors in s['directional_role_anchors'].items():
            expected = []
            for row in mem:
                if not row['metadata']['card_selectable'] or row['role'] != role:
                    continue
                c = claims[row['claim_id']]
                target = (c['tail_entity_id'] if c['relation'] in ('causes', 'indicates') else c['head_entity_id'])
                if target == s['scope_entity_id']:
                    expected.append(row['evidence_id'])
            check(sorted(expected) == anchors, 'independent directional role anchor reconstruction')
            with_anchors += bool(anchors)
    check(with_anchors == summary['query_drafts_with_directional_anchors'], 'anchored count')
    locations = lines(out / 'source_audit.jsonl')
    check(len(locations) == 208 and {r['evidence_id'] for r in locations} == all_ids, 'location coverage')
    check(sum(r['contiguous_span_verified'] for r in locations) == 145, 'E1 count')
    check(sum(r['existing_table_bbox_verified'] for r in locations) == 63, 'E2 count')
    for r in locations:
        if r['location_mode'] == 'E2_table_cells':
            check('\n--- CELL ---\n'.join(u['text'] for u in r['source_units']) == r['verbatim'], 'saved E2 reconstruction')
            check(r['provenance']['evidence_char_start'] is None, 'fabricated E2 span')
    return {'all_checks_passed': True, 'dependency_schemes_reconstructed_independently': len(saved_groups),
        'input_files_verified': len(bindings), 'prior_files_preserved': len(original),
        'prior_bytes_preserved': sum(x['bytes'] for x in original.values()),
        'query_count': len(queries), 'training_eligible_queries': 0, 'new_teacher_calls': 0,
        'inventory_path': str(inventory.relative_to(ROOT)), 'inventory_sha256': digest(inventory),
        'verification_source_sha256': digest(Path(__file__))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default='results/experiments/research_point_3/query_family_feasibility_v1')
    p.add_argument('--inventory', required=True)
    args = p.parse_args()
    out = ROOT / args.output
    check(not (out / 'verification.json').exists(), 'refuse to replace existing verification')
    result = verify(out, ROOT / args.inventory)
    with (out / 'verification.json').open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
