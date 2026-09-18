#!/usr/bin/env python3
"""Read-only post-run checks of G1 updates, checkpoint selection and controls."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.dataset import collate_teacher_batch
from src.research_point_3.experiment_io import prepare
from src.research_point_3.positive_guard import positive_reference_loss
from src.research_point_3.training import load_controller_checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True)
    args = parser.parse_args()
    import torch
    torch.set_num_threads(1)
    root = ROOT / 'results/experiments/research_point_3/positive_guard_v1'
    inventory = json.loads(Path(args.inventory).read_text())
    changed = [name for name, h in inventory.items() if not (ROOT/name).is_file() or file_sha256(ROOT/name) != h]
    snapshot = json.loads((root/'protocol_snapshot.json').read_text())
    mismatches = [name for name, h in snapshot['files'].items() if file_sha256(ROOT/name) != h]
    assert not changed and not mismatches, (changed, mismatches)
    with zipfile.ZipFile(root/'source_snapshot.zip') as archive:
        for name, h in snapshot['files'].items():
            member = str((ROOT/name).resolve().relative_to(ROOT))
            assert hashlib.sha256(archive.read(member)).hexdigest() == h
    for bindings in snapshot['control_files'].values():
        assert all(file_sha256(ROOT/name) == h for name, h in bindings.items())
    old_snapshot = json.loads((ROOT/'results/experiments/research_point_3/joint_contract_v1/protocol_snapshot.json').read_text())
    unchanged = {name: file_sha256(ROOT/name) == old_snapshot['files'][name]
                 for name in ('src/research_point_3/model.py', 'src/research_point_3/decoding.py', 'src/research_point_3/losses.py')}
    assert all(unchanged.values())
    checks = []; scores = {}
    for seed in snapshot['protocol']['seeds']:
        directory = root/f'seed_{seed}/G1'
        bootstrap = directory/'bootstrap'
        m = json.loads((bootstrap/'training_manifest.json').read_text())
        c = json.loads((ROOT/f'results/experiments/research_point_3/joint_contract_v1/seed_{seed}/W1/bootstrap/training_manifest.json').read_text())
        assert stable_sha256({k: v for k, v in m.items() if k != 'logical_sha256'}) == m['logical_sha256']
        assert all(file_sha256(bootstrap/m[k+'_file']) == m[k+'_sha256'] for k in ('checkpoint', 'history'))
        assert not m['development_set']['attached']
        assert all(m[k] == c[k] for k in ('model_config', 'runtime', 'input_fingerprint'))
        config = m['training_config']
        previous = dict(config)
        for k, value in snapshot['protocol']['treatment'].items():
            assert previous.pop(k) == value
        assert previous == c['training_config']
        prepared = prepare(directory/'config.json', attach_development=False)
        reference = collate_teacher_batch([prepared.train_dataset[i] for i in range(len(prepared.train_dataset))])
        positive_count = int((reference['availability_mask'] & reference['requested_candidate_mask'] & (reference['support_labels'] == 1)).sum())
        assert len(prepared.train_dataset) == 129 and len(prepared.validation_dataset) == 36 and positive_count == 415
        history = [json.loads(line) for line in (bootstrap/m['history_file']).read_text().splitlines()]
        errors = []
        for row in history:
            for split in ('train', 'validation'):
                saved = row[split]
                total = sum(weight*saved['intervention_augmented_supervision' if key == 'intervention' else key]
                            for key, weight in config['loss_weights'].items())
                total += config['hard_negative_support_weight']*saved['hard_negative_support'] + config['joint_contract_weight']*saved['joint_contract']
                errors.append(abs(total-saved['total']))
            assert 'positive_guard_steps' not in row['validation']
            assert len(row['train']['positive_guard_steps']) == math.ceil(129/config['batch_size'])
        best = min(history, key=lambda row: row['validation']['total'])['epoch']
        assert max(errors) < 1e-5 and best == m['best_epoch']
        steps = [step for row in history for step in row['train']['positive_guard_steps']]
        chain_errors = []; previous_loss = None; feasibility_errors = []
        for step in steps:
            assert step['positive_reference_count'] == positive_count and step['tolerance'] == 1e-7
            assert 1 <= step['trial_count'] <= 9 and len(step['trials']) == step['trial_count']
            assert step['reference_forward_calls'] == 1+step['trial_count']
            assert math.isfinite(step['positive_loss_before']) and math.isfinite(step['positive_loss_after'])
            assert abs(step['positive_loss_after']-step['positive_loss_before']-step['positive_loss_change']) < 1e-12
            bound = -.1*step['gradient_norm']*step['proposal_norm']
            assert abs(bound-step['halfspace_bound']) < 1e-12
            feasibility_errors.append(max(0., step['projected_dot']-bound))
            # d-c*g uses FP32 scalar conversion, multiplication and subtraction.
            # Cauchy-Schwarz gives a norm-scaled rounding allowance; a fixed
            # relative tolerance on the small residual bound ignores cancellation.
            epsilon = torch.finfo(torch.float32).eps
            gamma3 = 3*epsilon/(1-3*epsilon)
            rounding_bound = gamma3*(step['gradient_norm']*step['proposal_norm']
                + abs(step['projection_coefficient'])*step['gradient_norm']**2)
            assert feasibility_errors[-1] <= rounding_bound+1e-15
            expected_coefficient = max(step['proposal_dot']-bound, 0.)/step['gradient_norm']**2 if step['gradient_norm'] else 0.
            assert math.isclose(expected_coefficient, step['projection_coefficient'], rel_tol=1e-10, abs_tol=1e-12)
            assert step['projected'] == (expected_coefficient > 0.)
            for index, trial in enumerate(step['trials']):
                assert trial['scale'] == 2.**(-index)
                if index < step['trial_count']-1 or not step['accepted']:
                    assert trial['positive_loss'] is None or trial['positive_loss'] > step['positive_loss_before']+1e-7
            if step['accepted']:
                assert not step['optimizer_state_restored']
                assert step['scale'] == step['trials'][-1]['scale']
                assert step['positive_loss_after'] == step['trials'][-1]['positive_loss']
                assert step['positive_loss_change'] <= 1e-7
            else:
                assert step['optimizer_state_restored'] and step['scale'] == 0 and step['trial_count'] == 9
                assert step['positive_loss_after'] == step['positive_loss_before']
            if previous_loss is not None:
                chain_errors.append(abs(previous_loss-step['positive_loss_before']))
            previous_loss = step['positive_loss_after']
        assert max(chain_errors, default=0.) < 1e-6
        model, _ = load_controller_checkpoint(bootstrap/m['checkpoint_file'], expected_input_fingerprint=prepared.input_fingerprint)
        model.eval()
        with torch.no_grad():
            checkpoint_loss = float(positive_reference_loss(model, reference))
        selected_row = next(row for row in history if row['epoch'] == best)
        saved_loss = selected_row['train']['positive_guard_steps'][-1]['positive_loss_after']
        assert abs(checkpoint_loss-saved_loss) < 1e-6
        checks.append({'seed': seed, 'epochs': len(history), 'best_epoch': best,
            'max_objective_reconstruction_error': max(errors), 'same_inputs_model_runtime': True,
            'guard_steps': len(steps), 'projected_steps': sum(s['projected'] for s in steps),
            'backtracked_steps': sum(s['trial_count'] > 1 for s in steps), 'rejected_steps': sum(not s['accepted'] for s in steps),
            'reference_forward_calls': sum(s['reference_forward_calls'] for s in steps),
            'guard_region_seconds': sum(s['seconds'] for s in steps),
            'timing_boundary': 'guard-region includes AdamW proposal and copies; not incremental overhead against a timed W1 rerun',
            'positive_reference_count': positive_count, 'initial_positive_loss': steps[0]['positive_loss_before'],
            'selected_checkpoint_positive_loss': checkpoint_loss, 'final_epoch_positive_loss': steps[-1]['positive_loss_after'],
            'max_positive_loss_change': max(s['positive_loss_change'] for s in steps),
            'max_positive_loss_chain_error': max(chain_errors), 'max_halfspace_violation': max(feasibility_errors),
            'checkpoint_positive_loss_recompute_error': abs(checkpoint_loss-saved_loss)})
        for arm in ('C0', 'W1', 'G1'):
            d = root/f'seed_{seed}/{arm}'
            report = json.loads((d/'task_metrics.json').read_text())
            assert file_sha256(d/'predictions.jsonl') == report['predictions_sha256']
            assert not any(report[k] for k in ('development_read', 'external_read', 'deployment_allowed'))
            rows = [json.loads(line) for line in (d/'predictions.jsonl').read_text().splitlines()]
            scores[f'{arm}/{seed}'] = {}
            for split in ('train', 'validation'):
                for kind in ('original', 'derived', 'all'):
                    subset = split+'_'+kind
                    chosen = [r for r in rows if r['split'] == split and (kind == 'all' or (r['perturbation_id'] == 'original') == (kind == 'original'))]
                    positives = [p for r in chosen for p, label in zip(r['support_probabilities'], r['support_labels']) if label == 1]
                    negatives = [p for r in chosen for p, label in zip(r['support_probabilities'], r['support_labels']) if label == 0]
                    positive_pass = sum(p >= .5 for p in positives); negative_pass = sum(p >= .5 for p in negatives)
                    assert math.isclose(report['support'][subset]['recall'], positive_pass/len(positives))
                    empty = [r for r in chosen if not r['teacher_selected_ids']]
                    assert report['metrics'][subset]['teacher_empty_false_fill']['numerator'] == sum(bool(r['selected_ids']) for r in empty)
                    scores[f'{arm}/{seed}'][subset] = {'positive_pass': positive_pass, 'positive_count': len(positives),
                        'negative_pass': negative_pass, 'negative_count': len(negatives),
                        'negative_false_positive_rate': negative_pass/len(negatives) if negatives else None,
                        'teacher_empty_false_fill': sum(bool(r['selected_ids']) for r in empty), 'teacher_empty_count': len(empty)}
    output = {'inventory': args.inventory, 'preserved_existing_files': len(inventory), 'changed_or_missing_files': changed,
        'frozen_source_mismatches': mismatches, 'source_archive_and_control_hashes_valid': True,
        'model_decoder_base_loss_unchanged': unchanged, 'training_checks': checks,
        'geometry_check': 'FP32 gamma3*(||g||||d||+|coefficient|*||g||^2)+1e-15 rounding bound; actual loss acceptance tolerance unchanged at 1e-7',
        'support_gate_checks': scores, 'development_read': False, 'external_read': False, 'deployment_allowed': False}
    _write_immutable(root/'verification.json', canonical_json_bytes(output))
    print(json.dumps({k: v for k, v in output.items() if k != 'support_gate_checks'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
