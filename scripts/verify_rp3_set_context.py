#!/usr/bin/env python3
"""Independent objective, artifact and intervention checks of saved S0/S1."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.dataset import collate_teacher_batch
from src.research_point_3.experiment_io import prepare
from src.research_point_3.training import load_controller_checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--inventory', required=True)
    args = parser.parse_args()
    import torch
    torch.set_num_threads(1)
    root = ROOT/'results/experiments/research_point_3/set_context_v1'
    snapshot = json.loads((root/'protocol_snapshot.json').read_text())
    inventory = json.loads(Path(args.inventory).read_text())
    assert all((ROOT/name).is_file() and file_sha256(ROOT/name) == h for name, h in inventory.items())
    assert all(file_sha256(ROOT/name) == h for name, h in snapshot['files'].items())
    with zipfile.ZipFile(root/'source_snapshot.zip') as archive:
        for name, h in snapshot['files'].items():
            assert hashlib.sha256(archive.read(str((ROOT/name).resolve().relative_to(ROOT)))).hexdigest() == h
    for bindings in snapshot['control_files'].values():
        assert all(file_sha256(ROOT/name) == h for name, h in bindings.items())
    prepared = prepare(root/'seed_7042027/C0/config.json', attach_development=False)
    datasets = {'train': prepared.train_dataset, 'validation': prepared.validation_dataset}
    batches = {key: collate_teacher_batch([ds[i] for i in range(len(ds))]) for key, ds in datasets.items()}
    aliases = json.loads((ROOT/'results/experiments/research_point_3/support_separability_v1/audit.json').read_text())['aliases']
    checks = []; mechanisms = {}
    for seed in snapshot['protocol']['seeds']:
        control_dir = ROOT/f'results/experiments/research_point_3/field_normalization_v1/seed_{seed}/requested_balanced'
        control = json.loads((control_dir/'bootstrap/training_manifest.json').read_text())
        old_predictions = {r['trace_id']: r for r in map(json.loads, (control_dir/'predictions.jsonl').read_text().splitlines())}
        for arm in ('C0', 'S0', 'S1'):
            directory = root/f'seed_{seed}/{arm}'
            bootstrap = (control_dir if arm == 'C0' else directory)/'bootstrap'
            m = json.loads((bootstrap/'training_manifest.json').read_text())
            assert stable_sha256({k: v for k, v in m.items() if k != 'logical_sha256'}) == m['logical_sha256']
            assert all(file_sha256(bootstrap/m[k+'_file']) == m[k+'_sha256'] for k in ('checkpoint', 'history'))
            assert not m['development_set']['attached'] and m['input_fingerprint'] == control['input_fingerprint'] and m['runtime'] == control['runtime']
            if arm != 'C0':
                config = dict(m['model_config']); assert config.pop('support_context') == snapshot['protocol']['arms'][arm]
                assert config == control['model_config']
                assert all(m['training_config'][key] == value for key, value in control['training_config'].items())
                assert m['training_config']['hard_negative_support_weight'] == m['training_config']['joint_contract_weight'] == 0
                assert not m['training_config']['positive_step_guard']
            history = list(map(json.loads, (bootstrap/m['history_file']).read_text().splitlines()))
            errors = []
            for epoch in history:
                for split in ('train', 'validation'):
                    metric = epoch[split]
                    total = sum(weight*metric['intervention_augmented_supervision' if name == 'intervention' else name]
                                for name, weight in m['training_config']['loss_weights'].items())
                    errors.append(abs(total-metric['total']))
            assert max(errors) < 1e-5
            assert min(history, key=lambda row: row['validation']['total'])['epoch'] == m['best_epoch']
            report = json.loads((directory/'task_metrics.json').read_text())
            assert file_sha256(directory/'predictions.jsonl') == report['predictions_sha256']
            rows = list(map(json.loads, (directory/'predictions.jsonl').read_text().splitlines()))
            selection_changes = {split: sum(r['selected_ids'] != old_predictions[r['trace_id']]['selected_ids'] for r in rows if r['split'] == split) for split in datasets}
            model, _ = load_controller_checkpoint(bootstrap/m['checkpoint_file'], expected_input_fingerprint=prepared.input_fingerprint)
            model.eval(); assert model.parameter_count() == snapshot['initialization'][str(seed)]['parameter_counts'][arm]
            mechanisms[f'{arm}/{seed}'] = {}
            for split, batch in batches.items():
                names = ('query_features', 'candidate_features', 'availability_mask', 'selection_budget')
                feed = {k: batch[k] for k in names}
                capture = {}
                hook = model.candidate_fusion.register_forward_hook(lambda module, inputs, output: capture.update(hidden=output.detach()))
                with torch.no_grad(): output = model(**feed)
                hook.remove(); hidden = capture['hidden']
                with torch.no_grad():
                    permutation = torch.arange(feed['candidate_features'].shape[1]-1, -1, -1)
                    permuted = model(feed['query_features'], feed['candidate_features'][:, permutation], feed['availability_mask'][:, permutation], feed['selection_budget'])
                    expected = output.support_logits[:, permutation]; valid = feed['availability_mask'][:, permutation]
                    permutation_error = float((permuted.support_logits[valid]-expected[valid]).abs().max())
                    assert permutation_error < 1e-5
                    altered = feed['candidate_features'].clone(); altered[~feed['availability_mask']] = 1000.
                    changed = model(feed['query_features'], altered, feed['availability_mask'], feed['selection_budget'])
                    assert torch.equal(output.support_logits, changed.support_logits)
                    features = model.support_residual.context_features(hidden, feed['availability_mask']) if arm != 'C0' else hidden
                indexes = {(t.trace_id, eid): (i, j) for i, t in enumerate(datasets[split].traces) for j, eid in enumerate(t.candidate_evidence_ids)}
                groups = []
                for group in aliases[split]['pointwise_key']['conflicts']:
                    positions = [indexes[(r['trace_id'], r['evidence_id'])] for r in group['occurrences']]
                    logits = [float(output.support_logits[i, j]) for i, j in positions]
                    keys = [hashlib.sha256(features[i, j].numpy().tobytes()).hexdigest() for i, j in positions]
                    groups.append({'pointwise_key': group['input_sha256'], 'distinct_residual_inputs': len(set(keys)), 'logit_spread': max(logits)-min(logits)})
                if arm != 'S1': assert all(g['logit_spread'] < 1e-6 for g in groups)
                mechanisms[f'{arm}/{seed}'][split] = {'permutation_max_abs_error': permutation_error,
                    'unavailable_input_change_no_effect': True, 'pointwise_conflict_groups': len(groups),
                    'groups_with_logit_spread_over_1e_6': sum(g['logit_spread'] > 1e-6 for g in groups),
                    'max_conflict_group_logit_spread': max(g['logit_spread'] for g in groups), 'groups': groups}
            checks.append({'arm': arm, 'seed': seed, 'epochs': len(history), 'best_epoch': m['best_epoch'],
                'max_objective_reconstruction_error': max(errors), 'parameter_count': model.parameter_count(),
                'selections_changed_from_C0': selection_changes, 'old_input_runtime_and_config_verified': True})
    output = {'preserved_existing_files': len(inventory), 'inventory': args.inventory, 'source_and_control_hashes_valid': True,
        'training_checks': checks, 'mechanism_checks': mechanisms, 'development_read': False, 'external_read': False, 'deployment_allowed': False}
    _write_immutable(root/'verification.json', canonical_json_bytes(output))
    print(json.dumps({k: v for k, v in output.items() if k != 'mechanism_checks'}, ensure_ascii=False, indent=2))
    print(json.dumps({key: {split: {k: v for k, v in values.items() if k != 'groups'} for split, values in record.items()} for key, record in mechanisms.items()}, indent=2))


if __name__ == '__main__': main()
