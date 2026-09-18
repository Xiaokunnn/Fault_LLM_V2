#!/usr/bin/env python3
"""Comparable CPU component timings; no teacher calls and no model fitting."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, _write_immutable
from src.research_point_3.experiment_io import prepare, decode_row
from src.research_point_3.features import hash_text
from src.research_point_3.semantic_features import FrozenSemanticEncoder, query_text
from src.research_point_3.training import load_controller_checkpoint


def assemble_inputs(query_features, candidate_ids, availability, budget, cache, *, width=32):
    """Only observable request/ID-addressed evidence inputs, no teacher labels."""
    import torch
    dim = next(iter(cache.values())).numel()
    if len(candidate_ids) != len(availability) or len(candidate_ids) > width:
        raise ValueError('invalid candidate request')
    features = torch.zeros((1, width, dim), dtype=torch.float32)
    mask = torch.zeros((1, width), dtype=torch.bool)
    for i, (eid, available) in enumerate(zip(candidate_ids, availability)):
        if available:
            features[0,i] = cache[eid]
            mask[0,i] = True
    return {'query_features': torch.tensor([query_features], dtype=torch.float32),
        'candidate_features': features, 'availability_mask': mask,
        'selection_budget': torch.tensor([budget], dtype=torch.long)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--arm', required=True, choices=['C0','H512','E1'])
    arm = parser.parse_args().arm; os.chdir(ROOT)
    import torch
    import numpy as np
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    p = json.loads(Path('configs/research_point_3/semantic_v1.json').read_text()); root = Path(p['output_root'])
    seed = p['cost']['seed']; d = root/f'seed_{seed}/{arm}'
    if (root/f'cost_{arm}.json').exists(): raise FileExistsError('preserve measured results')
    config = json.loads((d/'config.json').read_text())
    rss_before_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    data = prepare(d/'config.json', attach_development=False)
    bootstrap = (Path(p['reference_root'])/f'seed_{seed}/requested_balanced' if arm == 'C0' else d)/'bootstrap'
    manifest = json.loads((bootstrap/'training_manifest.json').read_text())
    model, _ = load_controller_checkpoint(bootstrap/manifest['checkpoint_file'], expected_input_fingerprint=data.input_fingerprint)
    model.eval()
    encoder = (FrozenSemanticEncoder(p['encoder_directory'], json.loads((root/'protocol_snapshot.json').read_text())['encoder_files']) if arm == 'E1' else None)
    cache = {eid: torch.tensor(v, dtype=torch.float32) for eid,v in data.feature_store.evidence_features.items()}
    reference = {r['trace_id']:r for r in map(json.loads, (d/'predictions.jsonl').read_text().splitlines())}
    traces = [t for ds in (data.train_dataset,data.validation_dataset) for t in ds.traces if t.perturbation_id == 'original']
    records = data.train_dataset.records
    feature_error = 0.0; measurements = []
    for trace in traces:
        samples = []; components = []
        # Warm up every query; encoding always runs, including measured repeats.
        with torch.inference_mode():
            for repeat in range(p['cost']['warmup']+p['cost']['repeats']):
                start = time.perf_counter_ns()
                text = query_text(trace.query)
                q = encoder.encode([text], query=True, batch_size=1)[0] if encoder else hash_text(text, config['model']['query_dim'])
                encoded = time.perf_counter_ns()
                inputs = assemble_inputs(q, trace.candidate_evidence_ids, trace.availability_mask, trace.selection_budget, cache)
                assembled = time.perf_counter_ns()
                output = model(**inputs)
                forwarded = time.perf_counter_ns()
                logits = [getattr(output,k).numpy() for k in ('rank_logits','support_logits','field_state_logits','cardinality_logits','route_logits')]
                decision = decode_row(logits, trace, records, support_threshold=.5, minimum_route_confidence=0.)
                end = time.perf_counter_ns()
                if repeat >= p['cost']['warmup']:
                    samples.append((end-start)/1e6)
                    components.append([(encoded-start)/1e6,(assembled-encoded)/1e6,(forwarded-assembled)/1e6,(end-forwarded)/1e6])
                # Correctness checks excluded from latency samples.
                error = float(np.max(np.abs(np.asarray(q)-data.feature_store.query_features[trace.trace_id])))
                feature_error = max(feature_error,error)
                assert error < 1e-5
                assert set(decision.selected_evidence_ids) == set(reference[trace.trace_id]['selected_ids'])
        measurements.append({'trace_id': trace.trace_id, 'split': trace.split.value,
            'mean_ms': float(np.mean(samples)), 'p50_ms': float(np.median(samples)), 'p95_ms': float(np.percentile(samples,95)),
            'samples_ms': samples, 'component_mean_ms': dict(zip(('query_encoding','candidate_assembly','controller','decode'),np.mean(components,axis=0).tolist()))})
    parameters = model.parameter_count()+(encoder.parameter_count if encoder else 0)
    result = {'arm': arm, 'seed': seed, 'scope': p['cost']['scope'], 'cost_protocol': p['cost'],
        'measurements': measurements, 'by_split': {split: {'mean_ms': float(np.mean([r['mean_ms'] for r in measurements if r['split']==split]))} for split in ('train','validation')},
        'controller_parameters': model.parameter_count(), 'encoder_parameters': encoder.parameter_count if encoder else 0,
        'total_parameters': parameters, 'under_50M_including_encoder': parameters < 50_000_000,
        'encoder_parameter_bytes': encoder.weight_bytes if encoder else 0,
        'controller_parameter_bytes': sum(v.numel()*v.element_size() for v in model.parameters()),
        'static_evidence_fp32_bytes': sum(v.numel()*v.element_size() for v in cache.values()),
        'feature_bundle_json_bytes_including_offline_query_table': Path(config['feature_bundle_path']).stat().st_size,
        'encoder_safetensors_bytes': (Path(p['encoder_directory'])/'model.safetensors').stat().st_size if encoder else 0,
        'process_peak_rss_before_loading_kib': rss_before_kib, 'process_peak_rss_after_benchmark_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'rss_boundary': 'whole Python process including libraries, corpus objects and feature JSON; not model-only or edge memory',
        'max_online_offline_feature_abs_error': feature_error, 'all_40_predictions_equal_offline': True,
        'environment': {'platform': platform.platform(), 'cpu': Path('/proc/cpuinfo').read_text().split('model name')[1].splitlines()[0].strip(': \t'),
            'torch': torch.__version__, 'device': 'cpu', 'dtype': 'float32', 'intraop_threads': torch.get_num_threads(), 'interop_threads': torch.get_num_interop_threads()},
        'checkpoint_sha256': file_sha256(bootstrap/manifest['checkpoint_file']), 'target_edge_measurement': False,
        'teacher_or_network_measured': False, 'deployment_allowed': False}
    _write_immutable(root/f'cost_{arm}.json', canonical_json_bytes(result))
    print(json.dumps({'arm':arm, 'by_split':result['by_split'], 'total_parameters':parameters}), flush=True)


if __name__ == '__main__': main()
