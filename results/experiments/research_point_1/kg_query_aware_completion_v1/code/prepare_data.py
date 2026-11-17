"""Pretraining administrative split/copy blocking, no result-driven selection."""
from collections import Counter, defaultdict
import re
import numpy as np
from io_utils import *


def main():
    if (EXP/'data/freeze.json').exists():
        print('REUSE immutable new split'); return
    d = I.load(); graph = d['graph']; reg = d['schema']['relation_registry']
    aliases = UF(); groups = UF()
    def lkey(typ, label): return 'L|'+typ+'|'+I.norm(label)
    for pop in [d['raw'], d['audit'], d['normalized'], graph['source_records']]:
        for x in pop:
            for s in ['head', 'tail']:
                aliases.join(lkey(x[s+'_type'], x[s+'_canonical_zh']), 'S|'+I.norm(x[s+'_surface']))
    entities = [dict(x, index=i, source='expanded1456') for i,x in enumerate(sorted(graph['entities'], key=lambda x:x['entity_id']))]
    ei = {x['entity_id']:i for i,x in enumerate(entities)}
    labels = {(e['entity_type'], I.norm(e['label_zh'])):e['index'] for e in entities}
    nbase = len(entities); rels = sorted(reg); ri = {r:i for i,r in enumerate(rels)}
    sources = defaultdict(list)
    for x in graph['source_records']: sources[x['expanded_claim_id']].append(x)
    def cpair(c): return tuple(sorted(aliases.find(lkey(entities[ei[c[s+'_entity_id']]]['entity_type'],entities[ei[c[s+'_entity_id']]]['label_zh'])) for s in ['head','tail']))
    def rpair(x): return tuple(sorted(aliases.find(lkey(x[s+'_type'],x[s+'_canonical_zh'])) for s in ['head','tail']))
    by_pair = defaultdict(list); by_unit = defaultdict(list); by_quote = defaultdict(list)
    for c in graph['claims']:
        cid=c['claim_id']; groups.find(cid); by_pair[cpair(c)].append(cid)
        for x in sources[cid]:
            by_quote[I.norm(x['evidence_text'])].append(cid)
            units=set(x.get('evidence_unit_ids') or [])
            units.update(u.get('cell_id') or u.get('block_id') for u in x.get('expansion_source_witnesses',[]) or [])
            for u in units:
                if u: by_unit[u].append(cid)
    for mapping in [by_pair, by_unit, by_quote]:
        for ids in mapping.values(): groups.join(*ids)
    split=[]
    for c in sorted(graph['claims'],key=lambda x:x['claim_id']):
        g=groups.find(c['claim_id']); z=int(digest(['query-aware-split-20261116',g])[:12],16)%100
        fold='train' if z<75 else 'valid' if z<87 else 'test'
        split.append(dict(claim_id=c['claim_id'],group_id=g,fold=fold,
            triple=[ei[c['head_entity_id']],ri[c['relation']],ei[c['tail_entity_id']]],
            source_pages=sorted({(x['doc_id'],x['pdf_page_number']) for x in sources[c['claim_id']]})))
    assert all(sum(x['fold']==f for x in split)>=20 for f in ['train','valid','test'])
    held={x['claim_id'] for x in split if x['fold']!='train'}
    held_pairs={cpair(c) for c in graph['claims'] if c['claim_id'] in held}
    held_pages={(x['doc_id'],x['pdf_page_number']) for cid in held for x in sources[cid]}
    held_grams=set().union(*(shingles(x['evidence_text']) for cid in held for x in sources[cid]))
    held_units={u for u,ids in by_unit.items() if set(ids)&held}
    audit={k:x for x in d['audit'] for k in I.record_ids(x)}
    ledger=[]; surviving=[]
    for x in d['normalized']:
        reasons=[]
        if rpair(x) in held_pairs: reasons.append('held_alias_unordered_pair_any_relation')
        if (x['doc_id'],x['pdf_page_number']) in held_pages: reasons.append('held_source_page')
        if shingles(x['evidence_text'])&held_grams: reasons.append('held_quote_20gram')
        if set(x.get('evidence_unit_ids') or [])&held_units: reasons.append('held_native_unit')
        # Long endpoint text may itself copy a held quote, even on another page.
        if any(shingles(x[s+'_canonical_zh'])&held_grams or shingles(x[s+'_surface'])&held_grams for s in ['head','tail']): reasons.append('held_quote_in_endpoint')
        a=next((audit[k] for k in I.record_ids(x) if k in audit),x)
        ledger.append(dict(record_id=x['triple_id'],doc=x['doc_id'],page=x['pdf_page_number'],reasons=reasons,automatic_status=a.get('decision')))
        if not reasons: surviving.append((x,a))
    def endpoint(x,s):
        key=(x[s+'_type'],I.norm(x[s+'_canonical_zh']))
        if key not in labels:
            labels[key]=len(entities); entities.append(dict(index=len(entities),entity_id='CTX-'+digest(key)[:24],entity_type=key[0],label_zh=x[s+'_canonical_zh'],source='visible_initial_candidate'))
        return labels[key]
    train=[x for x in split if x['fold']=='train']; traintriples={tuple(x['triple']) for x in train}
    cc={}; registry={}; fieldcounts=Counter()
    for x,a in surviving:
        if x['relation'] not in ri: continue
        tr=(endpoint(x,'head'),ri[x['relation']],endpoint(x,'tail')); rule=reg[x['relation']]
        legal=x['head_type'] in rule['domain'] and x['tail_type'] in rule['range']
        located=bool(a.get('evidence_validation',{}).get('valid'))
        entailed=a.get('relation_entailment_validation',{}).get('status')=='entailed'
        conservative=legal and located and entailed and a.get('decision') in ['accepted_silver','silver_candidate']
        bucket='qualified' if conservative else 'quarantine' if a.get('decision')=='candidate_needs_review' else 'rejected' if legal else 'schema_invalid'
        weight=.5 if conservative else .15 if bucket=='quarantine' else .05 if legal and located else .02 if legal else 0.
        row=cc.setdefault(tr,dict(triple=tr,legal=legal,conservative=conservative,weight=weight,bucket=bucket,occurrences=[],pages=[],source_families=[],located=False,entailed=False))
        row['occurrences'].append(x['triple_id']);row['pages'].append((x['doc_id'],x['pdf_page_number']));row['source_families'].append(x['source_family_id'])
        row['located']|=located;row['entailed']|=entailed
        if weight>row['weight']:row.update(weight=weight,bucket=bucket)
        row['conservative']|=conservative
        registry[x['triple_id']]=dict(I.source_pointer(x),automatic_status=a.get('decision'),rejection_reasons=a.get('rejection_reasons',[]),location_contract=located,semantic_contract=entailed,
            native_address=I.address_check(x,d['pages'][x['doc_id'],x['pdf_page_number']]))
    candidates=[]
    for tr,e in sorted(cc.items()):
        e['pages']=sorted(set(e['pages'])); e['source_families']=sorted(set(e['source_families']));e['already_base_train']=tr in traintriples
        candidates.append(e)
    edges=[]
    for x in train:
        cid=x['claim_id']; pointer=[]
        for s in sources[cid]:
            # Never pass a held source page/quote through a different training edge.
            if (s['doc_id'],s['pdf_page_number']) in held_pages or shingles(s['evidence_text'])&held_grams: continue
            pointer.append(dict(I.source_pointer(s),location_contract=True,semantic_contract=True))
        registry[cid]=pointer
        edges.append(dict(edge_id=cid,triple=x['triple'],is_base=True,group_id=x['group_id'],pages=x['source_pages'],pair=cpair(next(c for c in graph['claims'] if c['claim_id']==cid)),
            legal=True,conservative=True,simple_filter=True,bucket='base',fixed_weight=1.,features=[1.,1.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.],source_keys=[cid]))
    norm={x['triple_id']:x for x in d['normalized']}
    for e in candidates:
        if e['already_base_train']: continue
        text=' '.join(norm[rid]['evidence_text'] for rid in e['occurrences']).lower()
        f=[float(e['legal']),float(e['located']),float(e['entailed']),float(e['conservative']),float(e['bucket']=='quarantine'),float(e['bucket']=='rejected'),float(e['bucket']=='schema_invalid'),0.,min(1.,np.log1p(len(e['occurrences']))/3),min(1.,len(e['source_families'])/3),float(any(w in text for w in [' if ',' when ',' unless ',' after ',' before '])),float(any(w in text for w in [' not ',' never ',' do not ']))]
        edges.append(dict(edge_id='C-'+digest(e['triple'])[:20],triple=e['triple'],is_base=False,group_id=None,pages=e['pages'],pair=rpair(norm[e['occurrences'][0]]),legal=e['legal'],conservative=e['conservative'],simple_filter=e['legal'] and e['located'],bucket=e['bucket'],fixed_weight=e['weight'],features=f,occurrences=e['occurrences'],source_keys=e['occurrences'],source_families=e['source_families']))
    ea=[aliases.find(lkey(e['entity_type'],e['label_zh'])) for e in entities]
    # Actual train identity closure is available only to administrative blocking.
    metas={}
    for x in train:
        meta=metas.setdefault(x['group_id'],dict(pairs=[],pages=[],edge_ids=[],quotegrams=[]))
        meta['pairs'].append(tuple(sorted([ea[x['triple'][0]],ea[x['triple'][2]]])));meta['pages']+=x['source_pages'];meta['edge_ids'].append(x['claim_id'])
        meta['quotegrams']+=sorted(set().union(*(shingles(s['evidence_text']) for s in sources[x['claim_id']])))
    for meta in metas.values():
        meta['pairs']=sorted(set(meta['pairs']));meta['pages']=sorted(set(map(tuple,meta['pages'])));meta['quotegrams']=sorted(set(meta['quotegrams']))
    seen={i for x in train for i in [x['triple'][0],x['triple'][2]]}
    def target(x):
        h,r,t=x['triple'];return dict(id=x['claim_id'],triple=x['triple'],endpoint_status='warm' if h in seen and t in seen else 'one_cold' if h in seen or t in seen else 'both_cold')
    cat=dict(entities=entities,relations=rels,registry=reg,nbase=nbase)
    for name,value in [('catalogue.json',cat),('base_split.jsonl',split),('train_base.jsonl',[target(x) for x in train]),('validation_targets.jsonl',[target(x) for x in split if x['fold']=='valid']),('validation_truth.json',[x['triple'] for x in split if x['fold']!='test']),('training_candidate_edges.jsonl',candidates),('context_edges.jsonl',edges),('train_group_context.json',metas),('training_source_registry.json',registry),('filter_entity_aliases.json',[str(i) for i in range(nbase)]),('entity_alias_closure.json',ea),('training_entity_text.jsonl',[dict(entity_index=e['index'],label=e['label_zh'],text=e['label_zh'],context_ids=[]) for e in entities])]:save(EXP/'data'/name,value)
    save(EXP/'audit_only/test_targets.jsonl',[target(x) for x in split if x['fold']=='test']);save(EXP/'audit_only/test_truth.json',[x['triple'] for x in split])
    save(EXP/'audit_only/source_records.jsonl',graph['source_records']);save(EXP/'audit_only/candidate_exclusions.jsonl',ledger)
    save(EXP/'audit_only/copy_blockers.json',dict(pairs=sorted(held_pairs),pages=sorted(held_pages),quotegrams=sorted(held_grams),units=sorted(held_units)))
    save(EXP/'audit_only/full_initial_keys.jsonl',[dict(key=I.core_tuple(x),record_id=x['triple_id'],source=I.source_pointer(x)) for x in d['normalized']])
    summary=dict(assertions=len(graph['evidence_assertions']),claims=len(split),base_entities=nbase,total_visible_entities=len(entities),raw_records=len(d['raw']),normalized_records=len(d['normalized']),folds=dict(Counter(x['fold'] for x in split)),groups=len(set(x['group_id'] for x in split)),candidate_edges=len(candidates),legal_candidates=sum(x['legal'] and not x['already_base_train'] for x in candidates),candidate_occurrences=len(surviving),candidate_buckets=dict(Counter(x['bucket'] for x in candidates)),blocked_source_pages=len(held_pages),split_key='query-aware-split-20261116',scope='15 build manuals only; expanded1456 only',independence='New internal frozen partition from repeatedly examined corpus, not independent external documents or expert truth',domain_git_object=I.REV)
    save(EXP/'data/summary.json',summary)
    save(EXP/'data/freeze.json',dict(inputs=d['inputs'].hashes,summary=summary,files={str(p.relative_to(EXP)):file_sha(p) for p in sorted((EXP/'data').glob('*')) if p.name!='freeze.json'}))
    print(summary,flush=True)


if __name__=='__main__': main()
