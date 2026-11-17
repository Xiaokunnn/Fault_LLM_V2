"""Admin-only controlled split and candidate/evidence features; no models."""
from collections import Counter,defaultdict
import numpy as np
from collab_io import *


def main():
    if (RUN/'data/collab_freeze.json').exists():print('REUSE',RUN);return
    oldsplit=read(OLD/'data/base_split.jsonl');cat=read(OLD/'data/catalogue.json')
    candidates=read(OLD/'data/training_candidate_edges.jsonl');sources=read(OLD/'audit_only/base_source_records.jsonl')
    src=defaultdict(list)
    for r in sources:src[r['expanded_claim_id']].append(r)
    d=I.load();norm={r['triple_id']:r for r in d['normalized']};audit={k:r for r in d['audit'] for k in I.record_ids(r)}
    aliases=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],sources]:
        for r in pop:
            for side in ['head','tail']:aliases.join('L|'+r[side+'_type']+'|'+I.norm(r[side+'_canonical_zh']),'S|'+I.norm(r[side+'_surface']))
    ea=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities']]
    def pair(t):return tuple(sorted([ea[t[0]],ea[t[2]]]))
    groups=defaultdict(list)
    for r in oldsplit:
        if r['fold']=='train':groups[r['group_id']].append(r)
    quotegrams={cid:set().union(*(shingles(s['evidence_text']) for s in ss)) for cid,ss in src.items()}
    candgrams={rid:shingles(norm[rid]['evidence_text']) for e in candidates for rid in e['occurrences']}
    def sanitized(held_groups):
        targets=[r for g in held_groups for r in groups[g]]
        bp={pair(r['triple']) for r in targets};pages={tuple(p) for r in targets for p in r['source_pages']}
        grams=set().union(*(quotegrams[r['claim_id']] for r in targets)) if targets else set()
        result=[]
        for e in candidates:
            if pair(e['triple']) in bp:continue
            ids=[rid for rid in e['occurrences'] if (norm[rid]['doc_id'],norm[rid]['pdf_page_number']) not in pages and not candgrams[rid]&grams]
            if ids:
                row=dict(e,occurrences=ids,pages=sorted({(norm[rid]['doc_id'],norm[rid]['pdf_page_number']) for rid in ids}),
                         source_families=sorted({norm[rid]['source_family_id'] for rid in ids}))
                result.append(row)
        return result
    def support(held,cc):
        base=Counter(e for g,rr in groups.items() if g not in held for r in rr for e in [r['triple'][0],r['triple'][2]])
        all_deg=base.copy()
        for e in cc:
            if e['legal'] and e['weight']>0:
                all_deg.update([e['triple'][0],e['triple'][2]])
        return base,all_deg
    selection=[]
    if DATASET=='cold':
        split=oldsplit;cc=candidates
    else:
        potential=[];strict=[]
        for g,rr in groups.items():
            b,a=support({g},sanitized({g}))
            if all(a[e]>0 for r in rr for e in [r['triple'][0],r['triple'][2]]):
                potential.append(g)
                if all(b[e]>0 for r in rr for e in [r['triple'][0],r['triple'][2]]):strict.append(g)
        held=set()
        for g in sorted(potential,key=lambda x:(x not in strict,digest(['structured-14112026',x]))):
            if len(held)>=24:break
            trial=held|{g};clean=sanitized(trial);b,a=support(trial,clean)
            if all(a[e]>0 for gg in trial for r in groups[gg] for e in [r['triple'][0],r['triple'][2]]):held=trial
        assert len(held)>=8,'Insufficient leakage-safe supported groups; do not relax blocking'
        ordered=sorted(held,key=lambda g:digest(['valid-test-14112026',g]));valid=set(ordered[::3]);test=held-valid
        cc=sanitized(held);b,a=support(held,cc)
        split=[]
        for r in oldsplit:
            fold='valid' if r['group_id'] in valid else 'test' if r['group_id'] in test else 'train' if r['fold']=='train' else 'excluded_previous_holdout'
            split.append(dict(r,fold=fold))
        for g in sorted(held):
            for r in groups[g]:selection.append(dict(claim_id=r['claim_id'],group_id=g,fold='valid' if g in valid else 'test',
                base_degrees=[b[e] for e in [r['triple'][0],r['triple'][2]]],context_degrees=[a[e] for e in [r['triple'][0],r['triple'][2]]],
                support_kind='base_supported' if all(b[e]>0 for e in [r['triple'][0],r['triple'][2]]) else 'candidate_assisted',
                original_fold='train',old_finetuned_checkpoint_forbidden=True))
        save(RUN/'audit_only/structure_selection.json',dict(potential_groups=len(potential),strict_leave_group_base_supported=len(strict),selected=selection,
             selection='fixed hashes and joint postmask positive-degree feasibility only, never model performance',
             independence='new task from previous training groups; fresh pretrained initialization required; not independent documents or expert facts'))
    train=[r for r in split if r['fold']=='train'];seen={e for r in train for e in [r['triple'][0],r['triple'][2]]}
    def clean(r):
        h,rel,t=r['triple'];return dict(id=r['claim_id'],triple=r['triple'],endpoint_status='warm' if h in seen and t in seen else 'one_cold' if h in seen or t in seen else 'both_cold')
    for name,value in [('catalogue.json',cat),('base_split.jsonl',split),('train_base.jsonl',[clean(r) for r in train]),
                       ('validation_targets.jsonl',[clean(r) for r in split if r['fold']=='valid']),('validation_truth.json',[r['triple'] for r in split if r['fold'] in ['train','valid']]),
                       ('training_candidate_edges.jsonl',cc),('filter_entity_aliases.json',read(OLD/'data/filter_entity_aliases.json')),
                       ('training_entity_text.jsonl',[dict(r,text=r['label'],context_ids=[]) for r in read(OLD/'data/training_entity_text.jsonl')])]:save(RUN/'data'/name,value)
    save(RUN/'audit_only/test_targets.jsonl',[clean(r) for r in split if r['fold']=='test'])
    save(RUN/'audit_only/test_truth.json',read(OLD/'audit_only/test_truth.json'))
    save(RUN/'audit_only/base_source_records.jsonl',sources)
    # Evidence features, never AI source-review S/E/U or testing rank values.
    edges=[]
    for r in train:
        edges.append(dict(edge_id=r['claim_id'],triple=r['triple'],is_base=True,group_id=r['group_id'],pages=r['source_pages'],pair=list(pair(r['triple'])),
            legal=True,fixed_weight=1.,features=[1.,1.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.]))
    for j,e in enumerate(cc):
        linked=[norm[rid] for rid in e['occurrences']]
        aa=[next((audit[k] for k in I.record_ids(r) if k in audit),r) for r in linked]
        located=any(a.get('evidence_validation',{}).get('valid') for a in aa)
        entailed=any(a.get('relation_entailment_validation',{}).get('status')=='entailed' for a in aa)
        text=' '.join(r['evidence_text'] for r in linked).lower()
        f=[float(e['legal']),float(located),float(entailed),float(e['conservative']),float(e['bucket']=='quarantine'),float(e['bucket']=='rejected'),
           float(e['bucket']=='schema_invalid'),0.,min(1.,np.log1p(len(e['occurrences']))/3),min(1.,len(e['source_families'])/3),
           float(any(w in text for w in [' if ',' when ',' unless ',' after ',' before '])),float(any(w in text for w in [' not ',' never ',' do not ']))]
        if e['already_base_train'] and tuple(e['triple']) not in {tuple(r['triple']) for r in train}:continue
        if any(tuple(e['triple'])==tuple(r['triple']) for r in train):continue
        edges.append(dict(edge_id='C-'+digest(e['triple'])[:20],triple=e['triple'],is_base=False,group_id=None,pages=e['pages'],pair=list(pair(e['triple'])),
            legal=e['legal'],fixed_weight=e['weight'],features=f,conservative=e['conservative'],simple_filter=bool(e['legal'] and located),bucket=e['bucket'],
            occurrences=e['occurrences'],source_families=e['source_families']))
    save(RUN/'data/context_edges.jsonl',edges)
    # Training-only target contexts for true leave-evidence-family-out fitting.
    train_groups={g:rr for g,rr in groups.items() if all(r['claim_id'] in {x['claim_id'] for x in train} for r in rr)}
    meta={g:dict(pairs=sorted({pair(r['triple']) for r in rr}),pages=sorted({tuple(p) for r in rr for p in r['source_pages']})) for g,rr in train_groups.items()}
    save(RUN/'data/train_group_context.json',meta)
    info=dict(dataset=DATASET,folds=dict(Counter(r['fold'] for r in split)),context_edges=len(edges),legal_candidate_contexts=sum(not r['is_base'] and r['legal'] for r in edges),
         original_pilot_inputs_preserved=True,previous_test_score_used_for_selection=False,source_object=I.REV,features='12 declared executable evidence/structure features, not semantic truth labels',
         old_checkpoint_allowed=DATASET=='cold',source_files=d['inputs'].hashes)
    save(RUN/'data/freeze.json',info)
    save(RUN/'data/collab_freeze.json',dict(summary=info,files={str(p.relative_to(RUN)):file_sha(p) for p in sorted((RUN/'data').glob('*')) if p.name!='collab_freeze.json'}))
    print(info['dataset'],info['folds'],'contexts',info['context_edges'],'legal candidates',info['legal_candidate_contexts'],flush=True)


if __name__=='__main__':main()
