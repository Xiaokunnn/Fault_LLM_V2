#!/usr/bin/env python3
"""Read-only source-grounded query-family feasibility; never exports labels."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_json(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n')


def write_rows(path, rows):
    with Path(path).open('x') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def normalize(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def record_keys(row, claims, entities, *, aliases=False, source_family=False):
    claim = claims[row['claim_id']]
    p = row['provenance']
    keys = {('claim', row['claim_id']), ('page', p['doc_id'], p['physical_pdf_page'])}
    for side in ('head_entity_id', 'tail_entity_id'):
        e = entities[claim[side]]
        keys.add(('entity_id', e['entity_id']))
        surfaces = [e['canonical_label_zh']]
        if aliases:
            surfaces += e.get('source_surfaces', [])
        keys.update(('entity_surface', normalize(s)) for s in surfaces if normalize(s))
    if source_family:
        require(bool(p['source_family_id']), 'missing source family')
        keys.add(('source_family', p['source_family_id']))
    return keys


def components(rows, claims, entities, *, aliases=False, source_family=False):
    rows = sorted(rows, key=lambda r: r['evidence_id'])
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    edges = []
    for i, row in enumerate(rows):
        for key in sorted(record_keys(row, claims, entities, aliases=aliases, source_family=source_family)):
            if key in seen:
                j = seen[key]
                edges.append({'left': rows[j]['evidence_id'], 'right': row['evidence_id'], 'reason': list(key)})
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
            else:
                seen[key] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row)
    answer = []
    for members in groups.values():
        ids = sorted(r['evidence_id'] for r in members)
        eid = {claims[r['claim_id']][side] for r in members for side in ('head_entity_id', 'tail_entity_id')}
        faults = sorted(x for x in eid if entities[x]['entity_type'] == 'FaultMode')
        answer.append({'group_id': 'QFG-' + hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:20],
            'evidence_ids': ids, 'scope_entity_ids': faults,
            'doc_ids': sorted({r['provenance']['doc_id'] for r in members}),
            'source_family_ids': sorted({r['provenance']['source_family_id'] for r in members})})
    return sorted(answer, key=lambda g: g['group_id']), edges


def direction_anchor(row, claim, scope):
    role, relation = row['role'], claim['relation']
    if not row['metadata']['card_selectable']:
        return False
    side = {('cause_or_mechanism', 'causes'): 'tail_entity_id',
        ('symptom', 'indicates'): 'tail_entity_id',
        ('symptom', 'manifests_as'): 'head_entity_id',
        ('inspection', 'diagnosed_by'): 'head_entity_id',
        ('inspection', 'inspected_by'): 'head_entity_id',
        ('maintenance', 'maintained_by'): 'head_entity_id',
        ('maintenance', 'mitigated_by'): 'head_entity_id',
        ('maintenance', 'prevented_by'): 'head_entity_id'}.get((role, relation))
    return side is not None and claim[side] == scope


def propose_split(groups, seed, holdout):
    active = [g for g in groups if g['scope_entity_ids']]
    require(len(active) >= 2 * holdout + 1, 'too few dependency groups for proposal')
    # Size-based exception is specified before assignment; no teacher outcomes read.
    largest = min(active, key=lambda g: (-len(g['scope_entity_ids']), g['group_id']))
    rest = sorted((g for g in active if g != largest),
        key=lambda g: hashlib.sha256((seed + ':' + g['group_id']).encode()).hexdigest())
    result = {largest['group_id']: 'train'}
    for i, group in enumerate(rest):
        result[group['group_id']] = ('validation' if i < holdout else
            'build_confirmation' if i < 2 * holdout else 'train')
    return result


def concentration(groups):
    sizes = [len(g['scope_entity_ids']) for g in groups if g['scope_entity_ids']]
    n = sum(sizes)
    return (n * n / sum(s * s for s in sizes)) if n else None


def verify_location(row, source, page):
    """E1 has a contiguous span; E2 preserves existing cell units, never invents one."""
    p = row['provenance']
    require(source['evidence_text'] == row['evidence_text'], 'source evidence text binding')
    require(source['doc_id'] == p['doc_id'] and source['pdf_page_number'] == p['physical_pdf_page'], 'source location binding')
    level = row['metadata']['evidence_level']
    require(level == source['evidence_level'], 'source level binding')
    if level == 'E1':
        a, b = p['evidence_char_start'], p['evidence_char_end']
        require(isinstance(a, int) and isinstance(b, int), 'E1 missing offsets')
        require(0 <= a < b <= len(page['page_text']) and page['page_text'][a:b] == row['evidence_text'], 'verbatim offset')
        require(a == source['evidence_start'] and b == source['evidence_end'], 'source E1 offsets')
        return {'location_mode': 'E1_contiguous_span', 'contiguous_span_verified': True,
            'source_units': [], 'source_unit_ids': [], 'existing_table_bbox_verified': False,
            'cell_representation_differences': []}
    require(level == 'E2', 'unsupported source evidence level')
    require(p['evidence_char_start'] is None and p['evidence_char_end'] is None, 'unexpected E2 offset')
    cells = {cell['cell_id']: cell for table in page['tables'] for r in table['rows'] for cell in r['cells']}
    ids = source['evidence_unit_ids']
    units = source['evidence_validation']['units']
    require(len(ids) == len(units) and len(ids) > 0, 'E2 unit identity')
    require('\n--- CELL ---\n'.join(u['text'] for u in units) == row['evidence_text'], 'E2 cell concatenation')
    differences = []
    for uid, unit in zip(ids, units):
        cell = cells[uid]
        for key in ('table_id', 'row_id', 'row_group_id'):
            require(cell[key] == unit[key], 'E2 cell ' + key)
        require(re.sub(r'\s+', '', cell['text']) == re.sub(r'\s+', '', unit['text']), 'E2 cell nonwhitespace text')
        for key in ('text', 'column_name'):
            if cell[key] != unit[key]:
                differences.append({'unit_id': uid, 'field': key, 'parsed_page_value': cell[key],
                    'source_record_value': unit[key],
                    'interpretation': 'whitespace_only' if key == 'text' else 'column_annotation_difference_not_identity_key'})
        bbox = cell['bbox']
        require([bbox[k] for k in ('x0', 'top', 'x1', 'bottom')] == unit['bbox'], 'E2 existing cell bbox')
    return {'location_mode': 'E2_table_cells', 'contiguous_span_verified': False,
        'source_units': units, 'source_unit_ids': ids, 'existing_table_bbox_verified': True,
        'cell_representation_differences': differences}


def audit(config, root=ROOT):
    graph = root / config['graph_root']
    files = [root / config['memory_path'], graph / 'claims.jsonl', graph / 'entities.jsonl', graph / 'source_records.jsonl']
    memory = read_rows(files[0])
    claims = {r['claim_id']: r for r in read_rows(files[1])}
    entities = {r['entity_id']: r for r in read_rows(files[2])}
    sources = {r['evidence_id']: r for r in read_rows(files[3])}
    require(len(memory) == 208 and len(claims) == 203 and len(entities) == 281, 'frozen graph counts')
    require(len({r['evidence_id'] for r in memory}) == len(memory), 'duplicate evidence id')
    pages = {}
    for doc in config['build_documents']:
        path = root / config['pages_root'] / (doc + '.pages.v2.jsonl')
        files.append(path)
        for page in read_rows(path):
            require(page['doc_id'] == doc, 'unexpected document inside parsed file')
            key = (doc, page['pdf_page_number'])
            require(key not in pages, 'duplicate physical page')
            pages[key] = page
    provenance = []
    for row in memory:
        p, c = row['provenance'], claims[row['claim_id']]
        require(p['doc_id'] in config['build_documents'], 'nonbuild evidence')
        page = pages[(p['doc_id'], p['physical_pdf_page'])]
        text = page['page_text']
        require(hashlib.sha256(text.encode()).hexdigest() == p['page_sha256'].lower(), 'page SHA')
        require(page['page_text_sha256'].lower() == p['page_sha256'].lower(), 'stored page SHA')
        require(page['document_sha256'].lower() == p['document_sha256'].lower(), 'document binding SHA')
        require(page['source_family_id'] == p['source_family_id'], 'source family binding')
        location = verify_location(row, sources[row['evidence_id']], page)
        require(row['relation'] == c['relation'], 'Claim relation binding')
        for side in ('head', 'tail'):
            require(row[side + '_label_zh'] == entities[c[side + '_entity_id']]['canonical_label_zh'], 'entity binding')
        provenance.append({'evidence_id': row['evidence_id'], 'claim_id': row['claim_id'],
            'role': row['role'], 'head_entity_id': c['head_entity_id'], 'tail_entity_id': c['tail_entity_id'],
            'head_type': entities[c['head_entity_id']]['entity_type'],
            'tail_type': entities[c['tail_entity_id']]['entity_type'],
            'verbatim': row['evidence_text'], 'provenance': p,
            'applicability_scope': row['metadata']['applicability_scope'],
            'page_hash_verified': True, 'pdf_rehashed': False, **location})
    schemes, edges = {}, {}
    for name in config['dependency_schemes']:
        schemes[name], edges[name] = components(memory, claims, entities,
            aliases='alias' in name, source_family='source_family' in name)
    primary = schemes[config['primary_scheme']]
    assignments = propose_split(primary, config['split_seed'], config['proposal_holdout_groups_each'])
    scope_group = {s: g['group_id'] for g in primary for s in g['scope_entity_ids']}
    prompts = {'symptom': '症状或可观察表现', 'cause_or_mechanism': '原因或失效机理',
        'inspection': '检查方法', 'maintenance': '维护或缓解措施'}
    scopes, queries = [], []
    for scope in sorted(scope_group):
        e = entities[scope]
        incident = [r for r in memory if scope in (claims[r['claim_id']]['head_entity_id'], claims[r['claim_id']]['tail_entity_id'])]
        anchors = {role: sorted(r['evidence_id'] for r in incident
            if r['role'] == role and direction_anchor(r, claims[r['claim_id']], scope)) for role in config['roles']}
        group = scope_group[scope]
        scopes.append({'scope_entity_id': scope, 'canonical_label_zh': e['canonical_label_zh'],
            'entity_type': e['entity_type'], 'source_surfaces': e['source_surfaces'],
            'group_id': group, 'proposed_split': assignments[group],
            'incident_evidence_ids': sorted(r['evidence_id'] for r in incident),
            'directional_role_anchors': anchors,
            'applicability_scopes': sorted({r['metadata']['applicability_scope'] for r in incident}),
            'automatic_fault_class_ids': sorted({f for r in incident for f in r['fault_class_ids']}),
            'human_expert_validated': False})
        for role in config['roles']:
            queries.append({'query_id': 'QFD-' + scope.removeprefix('MPE-') + '-' + role,
                'scope_entity_id': scope, 'fault_name_zh': e['canonical_label_zh'], 'requested_role': role,
                'question': f'针对已给定的故障范围“{e["canonical_label_zh"]}”，资料中有哪些直接支持的{prompts[role]}？证据不足时留空。',
                'operating_context': None, 'group_id': group, 'proposed_split': assignments[group],
                'draft_source_anchor_ids': anchors[role], 'status': 'draft_requires_task_review',
                'review_reasons': ['scope_and_applicability', 'semantic_aliases_not_exhaustively_merged',
                    'source_anchor_is_not_teacher_label'] + ([] if anchors[role] else ['no_directional_role_anchor']),
                'eligible_for_training': False, 'teacher_label': None})
    summary = {'schema': config['schema'], 'status': 'coverage_audit_complete_query_drafts_not_training_data',
        'evidence_records': len(memory), 'claims': len(claims), 'entities': len(entities),
        'build_documents_scanned': len(config['build_documents']), 'physical_pages_scanned': len(pages),
        'evidence_documents': len({r['provenance']['doc_id'] for r in memory}),
        'source_families': len({r['provenance']['source_family_id'] for r in memory}),
        'all_evidence_locations_verified_by_native_mode': True,
        'E1_contiguous_spans_verified': sum(p['contiguous_span_verified'] for p in provenance),
        'E2_cell_record_locations_verified': sum(p['existing_table_bbox_verified'] for p in provenance),
        'E2_records_with_representation_differences': sum(bool(p['cell_representation_differences']) for p in provenance),
        'bbox_available_records': sum(bool(r['provenance'].get('bbox')) for r in memory),
        'unique_head_labels': len({r['head_label_zh'] for r in memory}),
        'head_type_record_counts': dict(Counter(p['head_type'] for p in provenance)),
        'fault_scope_candidates': len(scopes), 'query_drafts': len(queries), 'question_templates': len(prompts),
        'query_drafts_with_directional_anchors': sum(bool(q['draft_source_anchor_ids']) for q in queries),
        'query_drafts_without_directional_anchors': sum(not q['draft_source_anchor_ids'] for q in queries),
        'training_eligible_queries': 0, 'new_independent_field_cases': 0,
        'new_teacher_calls': 0, 'new_training_runs': 0, 'schemes': {}, 'proposed_splits': {}}
    for name, groups in schemes.items():
        active = [g for g in groups if g['scope_entity_ids']]
        summary['schemes'][name] = {'all_dependency_groups': len(groups), 'fault_scope_groups': len(active),
            'largest_evidence_group': max(len(g['evidence_ids']) for g in groups),
            'largest_scope_group': max(len(g['scope_entity_ids']) for g in groups),
            'scope_inverse_concentration_not_effective_sample_size': concentration(groups)}
    for split in ('train', 'validation', 'build_confirmation'):
        gs = [g for g in primary if assignments.get(g['group_id']) == split]
        qs = [q for q in queries if q['proposed_split'] == split]
        summary['proposed_splits'][split] = {'groups': len(gs), 'scopes': len(qs) // len(prompts),
            'queries': len(qs), 'with_directional_role_anchor': sum(bool(q['draft_source_anchor_ids']) for q in qs),
            'doc_ids': sorted({d for g in gs for d in g['doc_ids']}),
            'source_family_ids': sorted({f for g in gs for f in g['source_family_ids']})}
    summary['split_source_overlap'] = {}
    for a, b in [('train', 'validation'), ('train', 'build_confirmation'), ('validation', 'build_confirmation')]:
        summary['split_source_overlap'][a + '__' + b] = {k: sorted(set(summary['proposed_splits'][a][k]) & set(summary['proposed_splits'][b][k])) for k in ('doc_ids', 'source_family_ids')}
    summary['interpretation'] = {
        'internal_pilot_partition_structurally_possible': True,
        'independent_generalization_or_risk_certification_established': False,
        'source_disjoint_six_group_holdouts_possible': summary['schemes']['entity_alias_claim_page_source_family']['fault_scope_groups'] >= 13,
        'formal_new_benchmark_ready': False,
        'reason': 'Draft task scope and semantic families require review; dependency closure is not IID evidence. Shared frozen memory remains unchanged.'}
    return summary, schemes, edges, provenance, scopes, queries, assignments, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/research_point_3/query_family_feasibility_v1.json')
    parser.add_argument('--resume-incomplete', action='store_true', help='Only resume an identical protocol-only failed attempt; never overwrite results.')
    args = parser.parse_args()
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text())
    out = ROOT / config['output_root']
    if out.exists():
        require(args.resume_incomplete and sorted(p.name for p in out.iterdir()) == ['protocol_snapshot.json'],
            'refuse to overwrite existing query-family experiment')
        require(json.loads((out / 'protocol_snapshot.json').read_text()) == config, 'resume protocol mismatch')
    else:
        out.mkdir(parents=True)
        write_json(out / 'protocol_snapshot.json', config)
    result = audit(config)
    summary, schemes, edges, provenance, scopes, queries, assignments, files = result
    files += [config_path, Path(__file__), ROOT / 'docs/RP3_QUERY_FAMILY_FEASIBILITY_V1_PROTOCOL.md']
    write_json(out / 'input_bindings.json', {str(p.relative_to(ROOT)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files})
    for name, value in [('summary', summary), ('dependency_groups', schemes), ('dependency_edges', edges), ('proposed_assignments', assignments)]:
        write_json(out / (name + '.json'), value)
    for name, rows in [('source_audit', provenance), ('scope_inventory', scopes), ('query_drafts', queries)]:
        write_rows(out / (name + '.jsonl'), rows)
    md = ['# RP3 构建查询族覆盖可行性结果', '',
        f'核验 {len(provenance)} 条来源（E1连续跨度/E2表格单元），生成 {len(scopes)} 个自动故障范围的 {len(queries)} 条未标注草案。', '',
        '| 依赖规则 | 全部组 | 含故障范围组 | 最大证据组 | 最大故障范围组 | 范围逆集中度（非有效样本量） |',
        '|---|---:|---:|---:|---:|---:|']
    for name, s in summary['schemes'].items():
        md.append(f'| {name} | {s["all_dependency_groups"]} | {s["fault_scope_groups"]} | {s["largest_evidence_group"]} | {s["largest_scope_group"]} | {s["scope_inverse_concentration_not_effective_sample_size"]:.3f} |')
    md += ['', '这是来源覆盖和分组可行性实验，不是学生质量实验。查询草案全部禁止直接训练；无新标签、模型或证书。',
        '组数不等于独立现场病例数；内部pilot可划分不等于已建立独立泛化或风险保证。', '']
    with (out / 'summary.md').open('x') as f:
        f.write('\n'.join(md))
    artifacts = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
    write_json(out / 'manifest.json', {'schema': 'rp3_query_family_manifest_v1', 'artifacts': artifacts})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
