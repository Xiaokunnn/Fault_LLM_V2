"""Administrative second pass: exhaustive quote shingles and sealed noise views.

This adds derived training files; the initial freeze and its logs are preserved.
It runs before candidate/text training, never inside a model's training process.
"""
from collections import defaultdict,Counter
import re
import numpy as np
from common import RUN,SEEDS,read,save,digest,file_sha
from prepare import I,UF


def shingles(text):
    s=re.sub(r'\s+','',I.norm(text));return {s[i:i+20] for i in range(max(0,len(s)-19))}


def main():
    if (RUN/'data/safety_refinement_freeze.json').exists():print('REUSE safety refinement');return
    d=I.load();cat=read(RUN/'data/catalogue.json');split=read(RUN/'data/base_split.jsonl')
    held={r['claim_id'] for r in split if r['fold']!='train'}
    target_shingles=set()
    for r in d['graph']['source_records']:
        if r['expanded_claim_id'] in held:target_shingles.update(shingles(r['evidence_text']))
    normalized={r['triple_id']:r for r in d['normalized']}
    bad_ids={r['triple_id'] for r in d['normalized'] if shingles(r['evidence_text'])&target_shingles}
    ledger=defaultdict(list)
    for r in read(RUN/'data/candidate_ledger.jsonl'):
        if not r['exclusions']:ledger[r['record_id']].append(r)
    clean=[];removed=[]
    for e in read(RUN/'data/candidate_edges.jsonl'):
        ids=[rid for rid in e['occurrences'] if rid not in bad_ids]
        if not ids:removed.append(dict(triple=e['triple'],reason='all_surviving_occurrences_overlap_target_quote_20gram'));continue
        oo=[r for rid in ids for r in ledger[rid]];best=max(oo,key=lambda r:r['weight'])
        row=dict(e,occurrences=ids,pages=sorted({(r['doc_id'],r['page']) for r in oo}),
                 source_families=sorted({normalized[rid]['source_family_id'] for rid in ids}),
                 weight=best['weight'],conservative=best['conservative'],bucket=best['bucket'])
        clean.append(row)
    save(RUN/'data/training_candidate_edges.jsonl',clean)
    units=read(RUN/'data/safe_context_units.jsonl');safe={i for i,u in enumerate(units) if not shingles(u['text'])&target_shingles}
    safe_units=[dict(units[i],original_context_index=i) for i in sorted(safe)]
    descriptions=[]
    for item in read(RUN/'data/entity_text.jsonl'):
        ids=[i for i in item['context_ids'] if i in safe]
        descriptions.append(dict(item,context_ids=ids,text=item['label']+'\n'+'\n'.join(units[i]['text'][:800] for i in ids)))
    save(RUN/'data/training_safe_context_units.jsonl',safe_units)
    save(RUN/'data/training_entity_text.jsonl',descriptions)
    # Derive train-safe, type-preserving corruptions, with admin target-copy blockers.
    aliases=UF()
    for population in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for r in population:
            for side in ['head','tail']:aliases.join('L|'+r[side+'_type']+'|'+I.norm(r[side+'_canonical_zh']),'S|'+I.norm(r[side+'_surface']))
    ent_alias=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities']]
    forbidden={tuple(sorted([ent_alias[r['triple'][0]],ent_alias[r['triple'][2]]])) for r in split if r['fold']!='train'}
    known={tuple(r['triple']) for r in clean}|{tuple(r['triple']) for r in split if r['fold']=='train'}
    by_type=defaultdict(list)
    for e in cat['entities']:by_type[e['entity_type']].append(e['index'])
    noise_stats=[]
    for seed in SEEDS:
        rng=np.random.default_rng(seed+101);draws=[]
        for e in clean:
            h,r,t=e['triple'];pool=[j for typ in cat['registry'][cat['relations'][r]]['range'] for j in by_type[typ]]
            replacement=None
            for _ in range(200):
                tt=int(rng.choice(pool))
                if (h,r,tt) not in known and tuple(sorted([ent_alias[h],ent_alias[tt]])) not in forbidden:
                    replacement=[h,r,tt];break
            draws.append((float(rng.random()),replacement))
        for rate in [.25,.5]:
            noise_rows=[]
            for e,(draw,replacement) in zip(clean,draws):
                noise_rows.append(dict(original_triple=e['triple'],triple=replacement if draw<rate and replacement is not None else e['triple'],synthetic_corruption=bool(draw<rate and replacement is not None)))
            save(RUN/f'data/noise_{seed}_{rate}.jsonl',noise_rows)
            noise_stats.append(dict(seed=seed,rate=rate,injected=sum(r['synthetic_corruption'] for r in noise_rows)))
    summary=dict(initial_candidate_edges=len(read(RUN/'data/candidate_edges.jsonl')),training_candidate_edges=len(clean),
                 removed_edges=len(removed),initial_units=len(units),final_units=len(safe_units),
                 description_entities_with_context=sum(bool(t['context_ids']) for t in descriptions),
                 candidate_strata=dict(Counter(e['bucket'] for e in clean)),
                 G2_extra_edges=sum(e['conservative'] and not e['already_base_train'] for e in clean),
                 final_extra_edges=sum(not e['already_base_train'] for e in clean),noise=noise_stats,
                 no_target_overlap_under_frozen_blockers=True,caveat='No exhaustive semantic-paraphrase guarantee; aliases and exact shared text are conservative finite proxies')
    save(RUN/'audit_only/safety_removed_edges.jsonl',removed)
    save(RUN/'data/safety_refinement_summary.json',summary)
    save(RUN/'data/safety_refinement_freeze.json',dict(summary=summary,input_freeze=file_sha(RUN/'data/freeze.json'),
       files={str(p.relative_to(RUN)):file_sha(p) for p in (RUN/'data').glob('*') if p.name.startswith(('training_','noise_'))},
       decision_time='before any candidate/text model is trained; G1 structural baselines unaffected',training_does_not_read_heldout_files=True))
    print(summary,flush=True)


if __name__=='__main__':main()
