"""Post-fit diagnostics only; never used by fitting or model selection.

Compare proxy/native gate covariates, selected-vs-last behavior, cost and
validation selection. No new source truth labels or graph modifications.
"""
from collections import Counter
import csv
import io
import numpy as np
from role_io import *
from train import ARMS


def main():
    rows = []
    for dataset in ['cold', 'structured']:
        root = NEW / dataset
        parent = PARENT / dataset
        edges = {x['edge_id']: x for x in read(parent / 'data/context_edges.jsonl')}
        # These are the five declared executable status flags, not truth labels.
        indices = [2, 3, 4, 5, 6]
        native = Counter(tuple(e['features'][i] for i in indices)
                         for e in edges.values() if e['legal'] and not e['is_base'])
        shift = []
        for seed in SEEDS:
            pairs = [p for p in read(root / f'data/utility_{seed}.jsonl')
                     if p['strong_contrast'] and p['split'] == 'fit']
            shift.append(dict(
                seed=seed, pairs=len(pairs),
                base_reference_pairs=sum(edges[p['edge_id']]['is_base'] for p in pairs),
                proxy_status_flags_in_native_candidate_support=sum(
                    tuple(edges[p['edge_id']]['features'][i] for i in indices) in native
                    for p in pairs)))
        save(root / 'analysis/proxy_feature_shift.json', dict(
            status_indices=indices,
            status_names=['entailed', 'conservative', 'quarantine', 'rejected', 'schema_invalid'],
            natural_status_patterns=[dict(pattern=list(k), edges=v) for k, v in sorted(native.items())],
            results=shift,
            caveat='Post-hoc covariate diagnostic. Nonoverlap is not proof of failed generalization; '
                   'overlap is not proof of correct source support. Full continuous features can also shift.'))
        for seed in SEEDS:
            for arm in ARMS:
                name = f'role_{arm}_s{seed}'
                c = read(root / 'models' / name / 'complete.json')
                cfg = read(root / 'models' / name / 'config.json')
                summary = read(root / 'evaluation' / name / 'best_probe_summary.json')
                all_probe = summary['probe_all']
                strong = summary['probe_strong']
                rows.append(dict(dataset=dataset, arm=arm, seed=seed,
                    train_pairs=cfg['pairs'], kgc_examples=cfg['kgc_examples'],
                    trainable_parameters=cfg['trainable_parameters'],
                    best_epoch=c['best_epoch'], executed_epochs=c['executed_epochs'],
                    train_seconds=c['seconds'], peak_cuda_bytes=c['peak_cuda_bytes'],
                    probe_all_n=all_probe['n'], probe_all_logit_order=all_probe['logit_order'],
                    probe_all_contribution_order=all_probe['score_contribution_order'],
                    probe_strong_n=strong['n'], probe_strong_logit_order=strong['logit_order'],
                    probe_strong_contribution_order=strong['score_contribution_order']))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    save(NEW / 'tables/cost_and_probe.csv', out.getvalue())
    save(NEW / 'tables/cost_summary.json', dict(
        trained_models=len(rows), summed_worker_train_seconds=sum(r['train_seconds'] for r in rows),
        max_peak_cuda_bytes=max(r['peak_cuda_bytes'] for r in rows),
        epoch_zero_selections=sum(r['best_epoch'] == 0 for r in rows),
        maximum_executed_epochs=max(r['executed_epochs'] for r in rows),
        note='Worker fitting times sum across two concurrent dataset jobs; not wall clock. '
             'CUDA peak excludes unrelated server models and full encoder training. '
             'Frozen text-cache generation and the historical model costs are not charged as new runs.'))
    print('Saved post-hoc distribution, cost and probe diagnostics; no fitting performed.')


if __name__ == '__main__':
    main()
