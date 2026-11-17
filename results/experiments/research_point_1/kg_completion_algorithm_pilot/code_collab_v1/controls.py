"""Precompute context scale/quality and noise without training target access."""
import numpy as np
from collections import defaultdict
from collab_io import *


def main():
    if (RUN/'data/controls_freeze.json').exists():return
    cat=read(RUN/'data/catalogue.json');d=I.load();a=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for x in pop:
            for side in ['head','tail']:a.join('L|'+x[side+'_type']+'|'+I.norm(x[side+'_canonical_zh']),'S|'+I.norm(x[side+'_surface']))
    ea=[a.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities']]
    forbidden={tuple(sorted([ea[x['triple'][0]],ea[x['triple'][2]]])) for x in read(RUN/'data/base_split.jsonl') if x['fold']!='train'}
    edges=read(RUN/'data/context_edges.jsonl');known={tuple(e['triple']) for e in edges}
    bytype=defaultdict(list)
    for e in cat['entities']:bytype[e['entity_type']].append(e['index'])
    for seed in SEEDS:
        rng=np.random.default_rng(seed+1411);rows=[]
        for e in edges:
            if e['is_base']:continue
            h,r,t=e['triple'];pool=[i for typ in cat['registry'][cat['relations'][r]]['range'] for i in bytype[typ]];draw=float(rng.random());new=None
            for _ in range(200):
                tt=int(rng.choice(pool))
                if (h,r,tt) not in known and tuple(sorted([ea[h],ea[tt]])) not in forbidden:
                    new=[h,r,tt];break
            rows.append(dict(edge_id=e['edge_id'],draw=draw,replacement=new))
        save(RUN/f'data/noise_context_{seed}.jsonl',rows)
    save(RUN/'data/controls_freeze.json',dict(files={str(p.relative_to(RUN)):file_sha(p) for p in sorted((RUN/'data').glob('noise_context_*'))},
        generation='admin before adapter fitting; type-compatible unknown tail, no held alias pair, not guaranteed false under OWA',flags_not_model_inputs=True))
    print('Frozen context controls',DATASET,flush=True)


if __name__=='__main__':main()
