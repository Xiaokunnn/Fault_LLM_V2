"""Separate training/validation inputs from sealed test and audit-only metadata."""
from collections import defaultdict,Counter
from common import RUN,save,read,digest,file_sha
from prepare import I,UF


def main():
    rows=read(RUN/'data/base_split.jsonl');cat=read(RUN/'data/catalogue.json')
    train=[r for r in rows if r['fold']=='train'];seen={e for r in train for e in [r['triple'][0],r['triple'][2]]}
    def clean(r):
        h,rel,t=r['triple']
        return dict(id=r['claim_id'],triple=r['triple'],endpoint_status='warm' if h in seen and t in seen else 'one_cold' if h in seen or t in seen else 'both_cold')
    save(RUN/'data/train_base.jsonl',[clean(r) for r in train])
    save(RUN/'data/validation_targets.jsonl',[clean(r) for r in rows if r['fold']=='valid'])
    save(RUN/'audit_only/test_targets.jsonl',[clean(r) for r in rows if r['fold']=='test'])
    save(RUN/'audit_only/document_holdout_targets.jsonl',[clean(r) for r in rows if r['fold']=='evidence_holdout'])
    save(RUN/'data/validation_truth.json',[r['triple'] for r in rows if r['fold'] in ['train','valid']])
    save(RUN/'audit_only/test_truth.json',[r['triple'] for r in rows])
    # Metadata for filtered synonym answers; used only by evaluators, never as training edges.
    d=I.load();aliases=UF()
    for population in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for r in population:
            for side in ['head','tail']:
                aliases.join('L|'+r[side+'_type']+'|'+I.norm(r[side+'_canonical_zh']), 'S|'+I.norm(r[side+'_surface']))
    entity_alias=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities'][:cat['nbase']]]
    save(RUN/'data/filter_entity_aliases.json',entity_alias)
    save(RUN/'data/task_exports_freeze.json',dict(files={str(p.relative_to(RUN)):file_sha(p) for p in (RUN/'data').glob('*') if p.name in ['train_base.jsonl','validation_targets.jsonl','validation_truth.json','filter_entity_aliases.json']},
        admin_only='Test targets and source provenance remain in audit_only; training runner must not access them',
        no_new_graphs=True,source_object=I.REV))
    print('Task separation exported; train',len(train),'valid',sum(r['fold']=='valid' for r in rows),'test',sum(r['fold']=='test' for r in rows),flush=True)


if __name__=='__main__':main()
