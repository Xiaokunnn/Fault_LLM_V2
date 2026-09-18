#!/usr/bin/env python3
"""Prespecified E1 versus H512; C0 is only read, never trained."""
import copy
import hashlib
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
from src.research_point_3.dataset import ExplicitFeatureStore
from src.research_point_3.experiment_io import prepare
from src.research_point_3.features import ENCODER_MANIFEST, hash_text, evidence_vector
from src.research_point_3.model import EvidenceControllerConfig, LightweightEvidenceController
from src.research_point_3.semantic_features import (MODEL_ID, REVISION, QUERY_INSTRUCTION,
    FrozenSemanticEncoder, model_bindings, query_text, evidence_text, evidence_metadata, optimistic_break_even)
from src.research_point_3.ablations import seed_statistics
from scripts.run_rp3_joint_contract import diagnose
from scripts.run_rp3_positive_guard import control
from scripts.run_rp3_set_context import support_metrics, compare
from scripts.audit_rp3_scope_feasibility import oracle_frontier


def make_config(old, arm, seed, protocol):
    new = copy.deepcopy(old)
    new['experiment_id'] = f'rp3_semantic_v1_{arm}_seed_{seed}'
    new['model'].update(query_dim=512, evidence_dim=544)
    new['feature_bundle_path'] = str(Path(protocol['output_root'])/'features'/f'{arm}.json')
    a, b = copy.deepcopy(old), copy.deepcopy(new)
    for key in ('experiment_id', 'feature_bundle_path'):
        a.pop(key); b.pop(key)
    b['model'].update(query_dim=256, evidence_dim=288)
    assert a == b, 'undeclared configuration change'
    return new


def export_features(data, protocol, bindings, root):
    traces = (*data.train_dataset.traces, *data.validation_dataset.traces)
    records = list(data.train_dataset.records.values())
    qtexts = sorted({query_text(t.query) for t in traces})
    etexts = [evidence_text(r) for r in records]
    assert len(traces) == 165 and len(records) == 208 and len(qtexts) == 40
    encoder = FrozenSemanticEncoder(protocol['encoder_directory'], bindings)
    query_embeddings = dict(zip(qtexts, encoder.encode(qtexts, query=True, batch_size=16)))
    evidence_embeddings = encoder.encode(etexts, batch_size=16)
    assert all(evidence_metadata(r) == evidence_vector(r)[256:] for r in records)
    manifest = {'id': MODEL_ID, 'revision': REVISION, 'file_sha256': bindings,
        'query_dimension': 512, 'evidence_dimension': 544, 'pooling': 'last_hidden_state_CLS_L2',
        'query_instruction': QUERY_INSTRUCTION, 'maximum_tokens': 512, 'dtype': 'float32', 'device': 'cpu',
        'learned_parameters': encoder.parameter_count, 'finetuned_parameters': 0,
        'requires_online_bge': True, 'purpose': 'training',
        'trace_manifest_sha256': data.trace_manifest['logical_sha256'],
        'memory_manifest_sha256': data.memory_manifest['logical_sha256'],
        'text_fields_identical_to_hash_baseline': True, 'metadata_identical_to_hash_baseline': True}
    for arm in ('H512', 'E1'):
        qm = {t.trace_id: (hash_text(query_text(t.query), 512) if arm == 'H512' else query_embeddings[query_text(t.query)]) for t in traces}
        em = {r.evidence_id: tuple(hash_text(evidence_text(r), 512) if arm == 'H512' else evidence_embeddings[i])+evidence_metadata(r)
              for i, r in enumerate(records)}
        m = (dict(ENCODER_MANIFEST, id='rp3_signed_char_ngram_h512_v1', query_dimension=512, evidence_dimension=544,
                  purpose='training', trace_manifest_sha256=data.trace_manifest['logical_sha256'],
                  memory_manifest_sha256=data.memory_manifest['logical_sha256']) if arm == 'H512' else manifest)
        payload = ExplicitFeatureStore.build_payload(query_features=qm, evidence_features=em,
            query_dimension=512, evidence_dimension=544, encoder_manifest=m)
        ExplicitFeatureStore.from_dict(payload)
        _write_immutable(root/'features'/f'{arm}.json', canonical_json_bytes(payload))
    audit = {'encoder_parameter_count': encoder.parameter_count, 'encoder_fp32_parameter_bytes': encoder.weight_bytes,
        'query_count': len(qtexts), 'trace_count': len(traces), 'evidence_count': len(records),
        'query_text_audit': encoder.text_audit(qtexts, query=True), 'evidence_text_audit': encoder.text_audit(etexts),
        'all_encoder_parameters_frozen': all(not p.requires_grad for p in encoder.model.parameters()),
        'metadata_exactly_equal': True, 'development_read': False, 'external_read': False}
    _write_immutable(root/'features/audit.json', canonical_json_bytes(audit))
    return audit


def main():
    os.chdir(ROOT)
    path = Path('configs/research_point_3/semantic_v1.json'); p = json.loads(path.read_text())
    assert p['schema'] == 'rp3_semantic_protocol_v1' and p['seeds'] == [7042027,7042028,7042029]
    assert p['arms'] == ['H512', 'E1'] and p['encoder_id'] == MODEL_ID and p['encoder_revision'] == REVISION
    assert not any(p[k] for k in ('development_attached','external_evaluation_allowed','deployment_allowed'))
    root = Path(p['output_root'])
    if root.exists(): raise FileExistsError('preserve existing runs; no automatic rerun')
    import torch
    torch.set_num_threads(1)
    directories = {seed: Path(p['reference_root'])/f'seed_{seed}/requested_balanced' for seed in p['seeds']}
    controls = {seed: control(d, seed) for seed, d in directories.items()}
    assert all(c[1]['runtime']['torch'] == torch.__version__ for c in controls.values())
    prepared = prepare(directories[p['seeds'][0]]/'config.json', attach_development=False)
    for ds in (prepared.train_dataset, prepared.validation_dataset):
        assert all(not (ds[i]['availability_mask'] & ~ds[i]['requested_candidate_mask']).any() for i in range(len(ds)))
    bindings = model_bindings(p['encoder_directory'])
    root.mkdir(parents=True); init = {}
    for seed in p['seeds']:
        old, _, refs = controls[seed]
        _write_immutable(root/f'seed_{seed}/C0/config.json', canonical_json_bytes(old))
        _write_immutable(root/f'seed_{seed}/C0/control_reference.json', canonical_json_bytes({'reused_without_training': True, 'files': refs}))
        states = []
        for arm in p['arms']:
            config = make_config(old, arm, seed, p)
            _write_immutable(root/f'seed_{seed}/{arm}/config.json', canonical_json_bytes(config))
            torch.manual_seed(seed)
            model = LightweightEvidenceController(EvidenceControllerConfig(**config['model']))
            states.append({k:v.clone() for k,v in model.state_dict().items()})
        assert all(torch.equal(v, states[1][k]) for k,v in states[0].items())
        init[str(seed)] = {'H512_E1_initialization_equal': True, 'controller_parameters': model.parameter_count(),
            'initial_state_sha256': hashlib.sha256(b''.join(v.numpy().tobytes() for v in states[0].values())).hexdigest()}
    sources = [path, Path('docs/RP3_SEMANTIC_V1_PROTOCOL.md'), Path(p['diagnostic_protocol']),
        *Path('src/research_point_3').glob('*.py'), *Path('scripts').glob('*rp3*.py'),
        Path('tests/unit/test_research_point_3_semantic.py'), *root.glob('seed_*/*/config.json')]
    snapshot = {'protocol': p, 'files': {str(f): file_sha256(f) for f in sources},
        'encoder_files': bindings, 'initialization': init, 'control_files': {str(s): c[2] for s,c in controls.items()},
        'environment': {'torch': torch.__version__, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}}
    _write_immutable(root/'protocol_snapshot.json', canonical_json_bytes(snapshot))
    with zipfile.ZipFile(root/'source_snapshot.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources: archive.write(source, source.resolve().relative_to(ROOT))
    print('[semantic] protocol and source frozen; generating independent H512/E1 features', flush=True)
    feature_audit = export_features(prepared, p, bindings, root)
    assert feature_audit['encoder_parameter_count']+model.parameter_count() < p['maximum_total_parameters']
    del prepared, model, states
    reports = {}; rows_by_arm = {}; diagnostic = json.loads(Path(p['diagnostic_protocol']).read_text())
    env = {**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'TOKENIZERS_PARALLELISM': 'false'}
    for seed in p['seeds']:
        identity = None
        for arm in ('C0', *p['arms']):
            d = root/f'seed_{seed}/{arm}'; bootstrap = (directories[seed] if arm == 'C0' else d)/'bootstrap'
            elapsed = None
            if arm != 'C0':
                print(f'[semantic] train {arm} seed={seed}; C0 reused', flush=True)
                command = [sys.executable, '-u', 'scripts/train_rp3_lec.py', '--config', str(d/'config.json'), '--output-dir', str(bootstrap)]
                start = time.perf_counter()
                with (d/'execution.log').open('x') as log:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
                elapsed = time.perf_counter()-start
                if result.returncode:
                    _write_immutable(d/'failure.json', canonical_json_bytes({'command': command, 'exit_code': result.returncode}))
                    raise RuntimeError(f'failed run preserved: {d}')
            rows, report = diagnose(d/'config.json', bootstrap, diagnostic)
            current = {r['trace_id']: (r['split'],r['scenario_id'],r['teacher_selected_ids'],r['available_ids'],r['target_cardinalities']) for r in rows}
            if identity is None: identity = current
            else: assert identity == current
            if arm == 'C0':
                before = {r['trace_id']: r for r in map(json.loads, (directories[seed]/'predictions.jsonl').read_text().splitlines())}
                assert all(all(r[k] == v for k,v in before[r['trace_id']].items()) for r in rows)
            _write_immutable(d/'predictions.jsonl', canonical_jsonl_bytes(rows))
            report.update(arm=arm, seed=seed, support=support_metrics(rows),
                oracle={split: oracle_frontier([r for r in rows if r['split'] == split and r['perturbation_id'] == 'original']) for split in ('train','validation')},
                predictions_sha256=file_sha256(d/'predictions.jsonl'), training_subprocess_seconds=elapsed,
                development_read=False, external_read=False, deployment_allowed=False, reused_control=arm == 'C0')
            _write_immutable(d/'task_metrics.json', canonical_json_bytes(report)); reports[f'{arm}/{seed}'] = report
            rows_by_arm[f'{arm}/{seed}'] = rows
            print(f"[semantic] {arm}/{seed} best_epoch={report['best_epoch']} original_val_F1={report['metrics']['validation_original']['pointer_f1']:.6f}", flush=True)
    comparisons = {}
    for arm in ('C0','H512'):
        c = compare(reports, arm, 'E1', p['seeds'])
        g = {a: [reports[f'{a}/{s}']['oracle']['validation']['correct_nonempty_local'] for s in p['seeds']] for a in (arm,'E1')}
        c['oracle_correct'] = g
        c['checks']['oracle_correct_mean_strictly_improved'] = sum(g['E1']) > sum(g[arm])
        c['checks']['oracle_correct_each_seed_not_lower'] = all(b>=a for a,b in zip(g[arm],g['E1']))
        assert set(c['checks']) == set(p['quality_checks'])
        c['improved_under_prespecified_rule'] = all(c['checks'].values())
        comparisons[f'E1_vs_{arm}'] = c
    aggregate = []
    for arm in ('C0', *p['arms']):
        for subset in next(iter(reports.values()))['metrics']:
            ms = [reports[f'{arm}/{s}']['metrics'][subset]['scenario_macro'] for s in p['seeds']]
            aggregate.append({'arm': arm, 'subset': subset,
                'quality': {k:seed_statistics([m[k] for m in ms]) for k in ('pointer_f1','pointer_precision','pointer_recall','requested_raw_cardinality_accuracy','requested_decoded_cardinality_accuracy')},
                'raw_zero': seed_statistics([m['nonempty_target_raw_zero']['mean'] for m in ms]),
                'decoded_empty': seed_statistics([m['nonempty_target_decoded_empty']['mean'] for m in ms]),
                'support': {k:seed_statistics([reports[f'{arm}/{s}']['support'][subset][k] for s in p['seeds']]) for k in ('scenario_macro_recall','scenario_macro_negative_false_accept')}})
    summary = {'protocol': p, 'reports': reports, 'aggregate': aggregate, 'comparisons': comparisons,
        'semantic_feasibility_gate_passed': all(c['improved_under_prespecified_rule'] for c in comparisons.values()),
        'deployment_allowed': False, 'feature_audit': feature_audit}
    _write_immutable(root/'summary.json', canonical_json_bytes(summary))
    for arm in ('C0', *p['arms']):
        print(f'[semantic] component CPU benchmark {arm}', flush=True)
        subprocess.run([sys.executable, '-u', 'scripts/benchmark_rp3_semantic.py', '--arm', arm], check=True, env=env)
    costs = {arm: json.loads((root/f'cost_{arm}.json').read_text()) for arm in ('C0', *p['arms'])}
    cost_comparisons = {}
    for arm in ('C0','H512'):
        for split in ('train','validation'):
            delta_cost = costs['E1']['by_split'][split]['mean_ms']-costs[arm]['by_split'][split]['mean_ms']
            for seed in p['seeds']:
                a, b = [reports[f'{v}/{seed}']['oracle'][split] for v in (arm,'E1')]
                dg = b['correct_nonempty_local']-a['correct_nonempty_local']
                cost_comparisons[f'E1_vs_{arm}/{seed}/{split}'] = dict(
                    optimistic_break_even(queries=a['queries'], delta_correct=dg, delta_local_ms=delta_cost),
                    delta_local_ms=delta_cost, delta_correct=dg, queries=a['queries'])
    _write_immutable(root/'cost_feasibility.json', canonical_json_bytes({'costs': costs, 'oracle_comparisons': cost_comparisons,
        'boundary': 'homogeneous oracle comparison only; no realized routing/system savings claim', 'deployment_allowed': False}))
    for _, _, refs in controls.values():
        assert all(file_sha256(name) == digest for name,digest in refs.items())
    print(json.dumps({'comparisons': comparisons, 'semantic_feasibility_gate_passed': summary['semantic_feasibility_gate_passed']}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__': main()
