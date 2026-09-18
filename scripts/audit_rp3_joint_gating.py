#!/usr/bin/env python3
"""Read-only, build-only audit of joint gating; oracle substitutions are diagnostic."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, _write_immutable
from src.research_point_3.ablations import ablation_row
from src.research_point_3.contracts import CARD_SLOT_ROLES
from src.research_point_3.experiment_io import prepare, onnx_feed
from src.research_point_3.field_audit import grouped_field_metrics
from src.research_point_3.training import load_controller_checkpoint


def main():
    import torch
    torch.set_num_threads(1)
    out = ROOT / 'results/experiments/research_point_3/joint_gating_audit_v1'
    if out.exists():
        raise FileExistsError('preserve existing audit')
    controls = ROOT / 'results/experiments/research_point_3/field_normalization_v1'
    protocol = json.loads((ROOT / 'configs/research_point_3/diagnostics_v1.json').read_text())
    results, bindings, all_rows = {}, {}, []
    for seed in (7042027, 7042028, 7042029):
        base = controls / f'seed_{seed}/requested_balanced'
        config = base / 'config.json'
        prepared = prepare(config, attach_development=False)
        manifest_path = base / 'bootstrap/training_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        checkpoint = base / 'bootstrap' / manifest['checkpoint_file']
        assert file_sha256(checkpoint) == manifest['checkpoint_sha256']
        model, _ = load_controller_checkpoint(checkpoint, expected_input_fingerprint=prepared.input_fingerprint)
        model.eval()
        for path in (config, manifest_path, checkpoint, base / 'predictions.jsonl'):
            bindings[str(path.relative_to(ROOT))] = file_sha256(path)
        old = {r['trace_id']: r for r in map(json.loads, (base / 'predictions.jsonl').read_text().splitlines())}
        variants = {key: [] for key in ('unchanged', 'oracle_assessed_support', 'oracle_field', 'oracle_cardinality')}
        counts = {}
        for ds in (prepared.train_dataset, prepared.validation_dataset):
            c = Counter()
            for i, trace in enumerate(ds.traces):
                row = ds[i]
                j = CARD_SLOT_ROLES.index(trace.query.requested_role)
                eligible = [bool(a) and ds.records[e].role == trace.query.requested_role
                            for e, a in zip(trace.candidate_evidence_ids, trace.availability_mask)]
                eligible += [False] * (len(row['availability_mask']) - len(eligible))
                mask = torch.tensor(eligible)
                labels = row['support_labels']
                n = int(row['cardinality_labels'][j])
                supported = int(((labels == 1) & mask).sum())
                unknown = int(((labels == -100) & mask).sum())
                hard = n == 0 and bool(mask.any()) and bool((labels[mask] == 0).all())
                c['rows'] += 1
                c['no_eligible_candidates'] += not bool(mask.any())
                c['teacher_empty_with_candidates'] += n == 0 and bool(mask.any())
                c['fully_assessed_hard_empty'] += hard
                c['teacher_empty_with_positive_support'] += n == 0 and supported > 0
                c['teacher_count_exceeds_positive_support'] += n > supported
                with torch.no_grad():
                    output = model(**{k: torch.from_numpy(v) for k, v in onnx_feed(ds, i).items()})
                logits = [getattr(output, k).numpy() for k in
                          ('rank_logits','support_logits','field_state_logits','cardinality_logits','route_logits')]
                decisions = {}
                for name in variants:
                    values = [a.copy() for a in logits]
                    if name == 'oracle_assessed_support':
                        for k in range(len(labels)):
                            if labels[k] != -100:
                                values[1][0, k] = 40.0 if labels[k] == 1 else -40.0
                    if name in ('oracle_field', 'oracle_cardinality'):
                        k, target = (2, row['field_state_labels']) if name == 'oracle_field' else (3, row['cardinality_labels'])
                        values[k].fill(-40.0)
                        for f, label in enumerate(target.tolist()):
                            values[k][0, f, label] = 40.0
                    pred = ablation_row(trace, ds.records, values, protocol, 'full_local')
                    variants[name].append(pred)
                    decisions[name] = pred['selected_ids']
                current = variants['unchanged'][-1]
                assert current['selected_ids'] == old[trace.trace_id]['selected_ids']
                probabilities = torch.sigmoid(output.support_logits[0]).detach().tolist()
                all_rows.append({**current, 'seed': seed, 'fully_assessed_hard_empty': hard,
                    'eligible_candidates': int(mask.sum()), 'eligible_supported_teacher': supported,
                    'eligible_unassessed_teacher': unknown,
                    'requested_state_probabilities': torch.softmax(output.field_state_logits[0,j], -1).detach().tolist(),
                    'requested_count_probabilities': torch.softmax(output.cardinality_logits[0,j], -1).detach().tolist(),
                    'candidate_audit': [{'id': e, 'eligible': eligible[k], 'label': int(labels[k]), 'probability': probabilities[k]}
                                        for k, e in enumerate(trace.candidate_evidence_ids)],
                    'oracle_selected_ids': decisions})
            counts[ds.traces[0].split.value] = dict(c)
        results[str(seed)] = {'counts': counts, 'oracle_metrics': {k: grouped_field_metrics(v) for k,v in variants.items()}}
    _write_immutable(out / 'rows.jsonl', canonical_jsonl_bytes(all_rows))
    _write_immutable(out / 'audit.json', canonical_json_bytes({'schema':'rp3_joint_gating_audit_v1',
        'results':results,'input_bindings':bindings,'rows_sha256':file_sha256(out/'rows.jsonl'),
        'development_read':False,'external_read':False,'oracle_boundary':'label substitution for localization only; never an inference algorithm'}))
    lines = ['# 联合门控审计', '', '只读构建集；oracle替换只定位错误，不能作为可部署成绩。', '',
             '| seed | split | rows | 无候选 | 有候选教师空集 | 全部已核验为负 | 数量超过支持数 |', '|---|---|---:|---:|---:|---:|---:|']
    for seed,r in results.items():
        for split,c in r['counts'].items():
            lines.append(f"| {seed} | {split} | {c['rows']} | {c['no_eligible_candidates']} | {c['teacher_empty_with_candidates']} | {c['fully_assessed_hard_empty']} | {c['teacher_count_exceeds_positive_support']} |")
    lines += ['', '| seed | 诊断替换 | 原始validation F1 | 完整validation教师空集误填 |', '|---|---|---:|---:|']
    for seed,r in results.items():
        for name,metrics in r['oracle_metrics'].items():
            e = metrics['validation_all']['teacher_empty_false_fill']
            lines.append(f"| {seed} | {name} | {metrics['validation_original']['pointer_f1']:.4f} | {e['numerator']}/{e['denominator']} |")
    _write_immutable(out/'audit.md', ('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
