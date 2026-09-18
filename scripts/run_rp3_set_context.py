#!/usr/bin/env python3
"""Prespecified S0/S1 matched-capacity support experiment; reuse C0 read-only."""
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, _write_immutable
from src.research_point_3.ablations import seed_statistics
from src.research_point_3.diagnostics import mean
from src.research_point_3.experiment_io import prepare
from src.research_point_3.model import EvidenceControllerConfig, LightweightEvidenceController
from scripts.run_rp3_joint_contract import diagnose
from scripts.run_rp3_positive_guard import control, support_summary, comparison


def make_config(old, arm, seed, protocol):
    value = copy.deepcopy(old)
    value['experiment_id'] = f'rp3_set_context_v1_{arm}_seed_{seed}'
    value['model']['support_context'] = protocol['arms'][arm]
    a, b = copy.deepcopy(old), copy.deepcopy(value)
    a.pop('experiment_id'); b.pop('experiment_id'); b['model'].pop('support_context')
    assert a == b, 'undeclared configuration change'
    return value


def support_metrics(rows):
    result = support_summary(rows)
    for key, value in result.items():
        split, kind = key.split('_', 1)
        chosen = [r for r in rows if r['split'] == split and (kind == 'all' or (r['perturbation_id'] == 'original') == (kind == 'original'))]
        def negatives(items):
            p = [prob for r in items for label, prob in zip(r['support_labels'], r['support_probabilities']) if label == 0]
            return {'negative_count': len(p), 'negative_pass': sum(v >= .5 for v in p),
                    'negative_false_accept': sum(v >= .5 for v in p)/len(p) if p else None}
        value.update(negatives(chosen))
        for scenario, metric in value['by_scenario'].items():
            metric.update(negatives([r for r in chosen if r['scenario_id'] == scenario]))
        value['scenario_macro_negative_false_accept'] = mean(m['negative_false_accept'] for m in value['by_scenario'].values() if m['negative_count'])
    return result


def compare(reports, old, new, seeds):
    result = comparison(reports, old, new, seeds)
    rates = {arm: mean(reports[f'{arm}/{seed}']['support']['validation_original']['scenario_macro_negative_false_accept'] for seed in seeds)
             for arm in (old, new)}
    result['negative_false_accept_means'] = rates
    result['checks']['negative_false_accept_not_higher'] = rates[new] <= rates[old]
    result['improved_under_prespecified_rule'] = all(result['checks'].values())
    return result


def initialization(config, seed):
    import torch
    models = {}; states = {}; rng = {}
    for arm, mode in [('C0', 'pointwise'), ('S0', 'local_residual'), ('S1', 'set_residual')]:
        torch.manual_seed(seed)
        models[arm] = LightweightEvidenceController(EvidenceControllerConfig(**{**config['model'], 'support_context': mode}))
        states[arm] = models[arm].state_dict(); rng[arm] = torch.get_rng_state()
    assert torch.equal(rng['C0'], rng['S0']) and torch.equal(rng['C0'], rng['S1'])
    assert all(torch.equal(v, states[arm][k]) for k, v in states['C0'].items() for arm in ('S0', 'S1'))
    assert all(torch.equal(v, states['S1'][k]) for k, v in states['S0'].items())
    counts = {arm: model.parameter_count() for arm, model in models.items()}
    assert counts['S0'] == counts['S1'] < 50_000_000
    return {'parameter_counts': counts, 'base_initialization_equal': True, 'S0_S1_all_parameters_equal': True,
            'rng_stream_equal': True, 'S0_S1_initial_state_sha256': hashlib.sha256(b''.join(v.numpy().tobytes() for v in states['S0'].values())).hexdigest()}


def main():
    os.chdir(ROOT)
    path = Path('configs/research_point_3/set_context_v1.json'); protocol = json.loads(path.read_text())
    assert protocol['schema'] == 'rp3_set_context_protocol_v1' and protocol['seeds'] == [7042027, 7042028, 7042029]
    assert protocol['arms'] == {'S0': 'local_residual', 'S1': 'set_residual'} and protocol['support_threshold'] == .5
    assert not any(protocol[k] for k in ('development_attached', 'external_evaluation_allowed', 'deployment_allowed'))
    root = Path(protocol['output_root'])
    if root.exists(): raise FileExistsError('preserve completed or failed runs; no automatic rerun')
    controls = {}; directories = {}; init = {}
    import torch
    torch.set_num_threads(1)
    for seed in protocol['seeds']:
        directory = Path(protocol['reference_root'])/f'seed_{seed}/requested_balanced'
        directories[seed] = directory; controls[seed] = control(directory, seed)
        assert controls[seed][1]['runtime']['torch'] == torch.__version__
        init[str(seed)] = initialization(controls[seed][0], seed)
    prepared = prepare(directories[protocol['seeds'][0]]/'config.json', attach_development=False)
    for ds in (prepared.train_dataset, prepared.validation_dataset):
        assert all(not (ds[i]['availability_mask'] & ~ds[i]['requested_candidate_mask']).any() for i in range(len(ds)))
    root.mkdir(parents=True)
    for seed in protocol['seeds']:
        config, _, bindings = controls[seed]
        _write_immutable(root/f'seed_{seed}/C0/config.json', canonical_json_bytes(config))
        _write_immutable(root/f'seed_{seed}/C0/control_reference.json', canonical_json_bytes({'reused_without_training': True, 'files': bindings}))
        for arm in ('S0', 'S1'):
            _write_immutable(root/f'seed_{seed}/{arm}/config.json', canonical_json_bytes(make_config(config, arm, seed, protocol)))
    sources = [path, Path('docs/RP3_SET_CONTEXT_V1_PROTOCOL.md'), Path(protocol['diagnostic_protocol']), Path(__file__),
        Path('scripts/train_rp3_lec.py'), Path('scripts/run_rp3_positive_guard.py'), Path('scripts/run_rp3_joint_contract.py'),
        Path('scripts/audit_rp3_support_separability.py'), Path('tests/unit/test_research_point_3_set_context.py'),
        *Path('src/research_point_3').glob('*.py'), *root.glob('seed_*/*/config.json')]
    snapshot = {'protocol': protocol, 'files': {str(p): file_sha256(p) for p in sources},
        'control_files': {str(seed): values[2] for seed, values in controls.items()}, 'initialization': init,
        'environment': {'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'torch': torch.__version__}}
    _write_immutable(root/'protocol_snapshot.json', canonical_json_bytes(snapshot))
    with zipfile.ZipFile(root/'source_snapshot.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources: archive.write(source, source.resolve().relative_to(ROOT))
    reports = {}; env = {**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    diagnostic = json.loads(Path(protocol['diagnostic_protocol']).read_text())
    for seed in protocol['seeds']:
        identity = None
        for arm in ('C0', 'S0', 'S1'):
            directory = root/f'seed_{seed}/{arm}'
            bootstrap = (directories[seed] if arm == 'C0' else directory)/'bootstrap'
            elapsed = None
            if arm != 'C0':
                print(f'[set context] {arm} seed={seed}; C0 reused', flush=True)
                command = [sys.executable, '-u', 'scripts/train_rp3_lec.py', '--config', str(directory/'config.json'), '--output-dir', str(bootstrap)]
                start = time.perf_counter()
                with (directory/'execution.log').open('x') as log:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
                elapsed = time.perf_counter()-start
                if result.returncode:
                    _write_immutable(directory/'failure.json', canonical_json_bytes({'command': command, 'exit_code': result.returncode}))
                    raise RuntimeError(f'failed run preserved: {directory}')
            rows, report = diagnose(directory/'config.json', bootstrap, diagnostic)
            current = {r['trace_id']: (r['split'], r['scenario_id'], r['teacher_selected_ids'], r['available_ids'], r['target_cardinalities']) for r in rows}
            if identity is None: identity = current
            else: assert identity == current
            assert report['input_fingerprint'] == controls[seed][1]['input_fingerprint']
            if arm == 'C0':
                old = [json.loads(line) for line in (directories[seed]/'predictions.jsonl').read_text().splitlines()]
                # Original rows predate joint-diagnostic telemetry; verify all
                # fields they contain, including numerical head predictions.
                before = {r['trace_id']: r for r in old}
                assert all(all(r[k] == v for k, v in before[r['trace_id']].items()) for r in rows)
            _write_immutable(directory/'predictions.jsonl', canonical_jsonl_bytes(rows))
            report.update(arm=arm, seed=seed, support=support_metrics(rows), predictions_sha256=file_sha256(directory/'predictions.jsonl'),
                parameter_count=init[str(seed)]['parameter_counts'][arm], training_subprocess_seconds=elapsed,
                development_read=False, external_read=False, deployment_allowed=False, reused_control=arm == 'C0')
            _write_immutable(directory/'task_metrics.json', canonical_json_bytes(report)); reports[f'{arm}/{seed}'] = report
    for _, _, bindings in controls.values():
        assert all(file_sha256(name) == digest for name, digest in bindings.items())
    comparisons = {f'S1_vs_{arm}': compare(reports, arm, 'S1', protocol['seeds']) for arm in ('C0', 'S0')}
    aggregate = []
    for arm in ('C0', 'S0', 'S1'):
        for subset in next(iter(reports.values()))['metrics']:
            metrics = [reports[f'{arm}/{seed}']['metrics'][subset]['scenario_macro'] for seed in protocol['seeds']]
            aggregate.append({'arm': arm, 'subset': subset,
                'quality': {k: seed_statistics([m[k] for m in metrics]) for k in ('pointer_f1', 'pointer_precision', 'pointer_recall', 'requested_raw_cardinality_accuracy', 'requested_decoded_cardinality_accuracy')},
                'raw_zero': seed_statistics([m['nonempty_target_raw_zero']['mean'] for m in metrics]),
                'decoded_empty': seed_statistics([m['nonempty_target_decoded_empty']['mean'] for m in metrics]),
                'support': {k: seed_statistics([reports[f'{arm}/{seed}']['support'][subset][k] for seed in protocol['seeds']]) for k in ('scenario_macro_recall', 'scenario_macro_negative_false_accept')}})
    success = all(c['improved_under_prespecified_rule'] for c in comparisons.values())
    _write_immutable(root/'summary.json', canonical_json_bytes({'protocol': protocol, 'reports': reports, 'aggregate': aggregate,
        'comparisons': comparisons, 'context_increment_supported': success, 'architecture_search_stopped': not success, 'deployment_allowed': False}))
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerow(['arm','seed','best_epoch','subset','raw_zero_n','nonempty_n','decoded_empty_n','raw_cardinality_accuracy','decoded_cardinality_accuracy','pointer_f1','positive_recall','negative_false_accept','support_auc','support_ap','teacher_empty_false_n','teacher_empty_n','hard_empty_false_n','hard_empty_n'])
    lines = ['# 候选集合上下文三种子结果', '', '仅构建集内部诊断；C0未重训；S0/S1容量及初始化配对。', '',
        '| 臂 | seed | 最佳epoch | 原始val F1 | 非空最终为空 | 支持正例召回 | 负支持误接受 | 完整val空集误填 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for report in reports.values():
        for subset, m in report['metrics'].items():
            zero = m['nonempty_target_raw_zero']; empty = m['teacher_empty_false_fill']; hard = report['joint_metrics'][subset]['hard_empty_false_fill']; support = report['support'][subset]
            writer.writerow([report['arm'],report['seed'],report['best_epoch'],subset,zero['numerator'],zero['denominator'],m['nonempty_target_decoded_empty']['numerator'],
                m['requested_raw_cardinality_accuracy'],m['requested_decoded_cardinality_accuracy'],m['pointer_f1'],support['recall'],support['negative_false_accept'],support['roc_auc'],
                support['auprc_average_precision'],empty['numerator'],empty['denominator'],hard['numerator'],hard['denominator']])
        m = report['metrics']['validation_original']; support = report['support']['validation_original']
        zero = m['nonempty_target_decoded_empty']; empty = report['metrics']['validation_all']['teacher_empty_false_fill']
        lines.append(f"| {report['arm']} | {report['seed']} | {report['best_epoch']} | {m['pointer_f1']:.4f} | {zero['numerator']}/{zero['denominator']} | {support['recall']:.4f} | {support['negative_pass']}/{support['negative_count']} | {empty['numerator']}/{empty['denominator']} |")
    for name, value in comparisons.items(): lines += ['', f"{name}: 通过={value['improved_under_prespecified_rule']}，条件={value['checks']}。"]
    lines += ['', f'上下文增益整体判定={success}；停止本条架构试探={not success}。原始validation仅2个场景。']
    _write_immutable(root/'summary.csv', stream.getvalue().encode()); _write_immutable(root/'summary.md', ('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines), flush=True)


if __name__ == '__main__': main()
