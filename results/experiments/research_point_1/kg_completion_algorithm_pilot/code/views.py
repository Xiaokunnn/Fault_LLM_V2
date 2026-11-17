"""Training-safe view assembly. Never read audit_only or test/graph source files."""
import numpy as np
from common import RUN,read,digest


def build(view='G1',fraction=1.,noise=0.,seed=14112026):
    cat=read(RUN/'data/catalogue.json')
    base=np.array([r['triple'] for r in read(RUN/'data/train_base.jsonl')],dtype=np.int64)
    selected=[]
    candidates=[] if view=='G1' else read(RUN/'data/training_candidate_edges.jsonl')
    for row in candidates:
        if row['already_base_train'] and view not in ['G3_bridge','G4_bridge']:continue
        if view=='G1':continue
        if view=='G2' and not row['conservative']:continue
        if int(digest(['scale',seed,row['triple']])[:12],16)/16**12>fraction:continue
        selected.append(row.copy())
    injected=0
    if noise:
        noise_map={tuple(r['original_triple']):r for r in read(RUN/f'data/noise_{seed}_{noise}.jsonl')}
        for row in selected:
            perturb=noise_map[tuple(row['triple'])];row['triple']=perturb['triple'];row['synthetic_corruption']=perturb['synthetic_corruption'];injected+=int(perturb['synthetic_corruption'])
    aux=np.array([r['triple'] for r in selected],dtype=np.int64).reshape(-1,3)
    weights=np.array([1. if view in ['G2','G3_flat','G3_flat_filtered','G3_uniform'] else r['weight'] for r in selected],dtype=np.float32)
    legal=np.array([r['legal'] for r in selected],dtype=bool)
    if view in ['G3_flat','G3_flat_filtered']:legal[:]=True
    active={int(e) for t in np.concatenate([base,aux],axis=0) for e in [t[0],t[2]]}
    return dict(catalogue=cat,base=base,aux=aux,weights=weights,legal=legal,aux_rows=selected,
                summary=dict(view=view,base_edges=len(base),aux_edges=len(aux),schema_invalid_contexts=int((~legal).sum()),
                             fraction=fraction,noise=noise,injected_corruptions=injected,active_entities=len(active),
                             negative_definition='sampled unknowns, not verified false facts; synthetic corruptions are not original errors'))
