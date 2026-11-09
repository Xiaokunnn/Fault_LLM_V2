#!/usr/bin/env python3
"""Supplement: distinguish frozen set agreement from exported display order."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / 'results/experiments/research_point_3/task_alignment_v1'
    target = out / 'export_order_audit.json'
    if target.exists():
        raise FileExistsError('preserve completed order audit')
    trace_path = ROOT / 'data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/augmented_training/teacher_traces.jsonl'
    aligned_path = out / 'trace_alignment.jsonl'
    traces = {t['trace_id']: t for t in map(json.loads, trace_path.read_text().splitlines())}
    aligned = [json.loads(s) for s in aligned_path.read_text().splitlines()]
    if len(traces) != len(aligned) or len(traces) != 165:
        raise ValueError('trace counts')
    mismatches = []
    for row in aligned:
        t = traces[row['trace_id']]
        pointer = [d['evidence_id'] for d in t['evidence_decisions'] if d['selected']]
        card = [eid for slot in t['diagnosis_card']['slots'] for item in slot['items'] for eid in item['evidence_ids']]
        teacher = row['selected_ids']
        if set(pointer) != set(teacher) or set(card) != set(teacher):
            raise ValueError('set mismatch: ' + row['trace_id'])
        score_order = [d['evidence_id'] for d in sorted(t['evidence_decisions'], key=lambda d: -d['teacher_score']) if d['selected']]
        if score_order != teacher:
            raise ValueError('teacher score order mismatch: ' + row['trace_id'])
        if pointer != teacher or card != teacher:
            mismatches.append({'trace_id': row['trace_id'], 'split': row['split'], 'kind': row['kind'],
                'teacher_run_order': teacher, 'exported_pointer_order': pointer, 'card_order': card,
                'teacher_score_order': score_order})
    result = {'schema': 'rp3_task_alignment_export_order_audit_v1', 'traces_checked': len(aligned),
        'all_exported_sets_match_teacher': True, 'all_teacher_score_orders_match_teacher': True,
        'exported_pointer_or_card_order_mismatches': len(mismatches),
        'mismatch_counts_by_split': dict(Counter(r['split'] for r in mismatches)),
        'mismatches': mismatches,
        'interpretation': 'derived candidate positions and decision.rank retain base order; teacher_score encodes new prefix. Set-based F1 is unaffected. Use actual run evidence order for future verifier inputs; do not rewrite frozen traces.',
        'bindings': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in [trace_path, aligned_path, Path(__file__)]}, 'model_calls': 0, 'labels_changed': False}
    with target.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('mismatches', 'bindings')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
