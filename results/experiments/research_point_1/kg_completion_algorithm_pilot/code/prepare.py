"""Freeze fact-family masking and sanitized G1--G4 views from locked Git inputs."""
from collections import Counter,defaultdict
import importlib.util
import json
import re
import sys
from common import RUN,ROOT,save,digest,canonical,file_sha

SPEC=importlib.util.spec_from_file_location('locked_inputs',ROOT/'results/experiments/research_point_1/kg_enhancement_task_comparison/code/inputs.py')
I=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(I)


class UF:
    def __init__(self):self.p={}
    def find(self,x):
        self.p.setdefault(x,x)
        if self.p[x]!=x:self.p[x]=self.find(self.p[x])
        return self.p[x]
    def join(self,*xs):
        roots=sorted({self.find(x) for x in xs})
        for x in roots[1:]:self.p[x]=roots[0]


def grams(text,n=20):
    value=re.sub(r'\s+','',I.norm(text))
    return {value[j:j+n] for j in range(0,max(0,len(value)-n+1),5)}


def main():
    if (RUN/'data/freeze.json').exists():raise ValueError('Completed data freeze preserved; use another run directory')
    d=I.load();graph=d['graph'];registry=d['schema']['relation_registry']
    aliases=UF();families=UF()
    def lkey(typ,label):return 'L|'+typ+'|'+I.norm(label)
    for rows in [d['raw'],d['audit'],d['normalized'],graph['source_records']]:
        for r in rows:
            for side in ['head','tail']:
                aliases.join(lkey(r[side+'_type'],r.get(side+'_canonical_zh',r[side+'_surface'])),
                             'S|'+I.norm(r[side+'_surface']))
    entities=sorted(graph['entities'],key=lambda r:r['entity_id'])
    entity_index={r['entity_id']:j for j,r in enumerate(entities)}
    labels={(r['entity_type'],I.norm(r['label_zh'])):j for j,r in enumerate(entities)}
    relations=sorted(registry);relation_index={r:j for j,r in enumerate(relations)}
    def pair_record(r):
        return tuple(sorted(aliases.find(lkey(r[s+'_type'],r[s+'_canonical_zh'])) for s in ['head','tail']))
    def pair_claim(c):
        return tuple(sorted(aliases.find(lkey(entities[entity_index[c[s+'_entity_id']]]['entity_type'],entities[entity_index[c[s+'_entity_id']]]['label_zh'])) for s in ['head','tail']))
    sources=defaultdict(list)
    for r in graph['source_records']:sources[r['expanded_claim_id']].append(r)
    claim_lookup={c['claim_id']:c for c in graph['claims']}
    same_pair=defaultdict(list);same_unit=defaultdict(list);same_quote=defaultdict(list)
    for c in graph['claims']:
        cid=c['claim_id'];families.find(cid);same_pair[pair_claim(c)].append(cid)
        for r in sources[cid]:
            same_quote[I.norm(r['evidence_text'])].append(cid)
            units=list(r.get('evidence_unit_ids') or [])
            units += [w.get('cell_id') or w.get('block_id') for w in r.get('expansion_source_witnesses',[]) or []]
            for unit in units:
                if unit:same_unit[unit].append(cid)
    for collection in [same_pair,same_unit,same_quote]:
        for ids in collection.values():families.join(*ids)
    grouped=defaultdict(list)
    for cid in claim_lookup:grouped[families.find(cid)].append(cid)
    split={};group_manifest=[]
    for group,cids in sorted(grouped.items()):
        docs={r['doc_id'] for cid in cids for r in sources[cid]}
        number=int(digest(['split-14112026',group])[:12],16)%100
        fold='evidence_holdout' if 'MP022' in docs else 'train' if number<70 else 'valid' if number<85 else 'test'
        for cid in cids:split[cid]=fold
        group_manifest.append(dict(group_id=group,claims=sorted(cids),documents=sorted(docs),fold=fold))
    assert all(sum(v==fold for v in split.values())>=20 for fold in ['train','valid','test'])
    masked={cid for cid,fold in split.items() if fold!='train'}
    blocked_pairs={pair_claim(claim_lookup[cid]) for cid in masked}
    blocked_units={u for u,cids in same_unit.items() if any(c in masked for c in cids)}
    blocked_pages={(r['doc_id'],r['pdf_page_number']) for cid in masked for r in sources[cid]}
    held_shingles=set()
    for cid in masked:
        for r in sources[cid]:held_shingles.update(grams(r['evidence_text']))
    audit_by_id={k:r for r in d['audit'] for k in I.record_ids(r)}
    candidate_records=[];dropped=Counter();candidate_copy_pages=set()
    for j,r in enumerate(d['normalized']):
        a=next((audit_by_id[k] for k in I.record_ids(r) if k in audit_by_id),r)
        why=[]
        if r['doc_id']=='MP022':why.append('independent_document')
        if pair_record(r) in blocked_pairs:why.append('masked_alias_or_reverse_pair')
        units=set(r.get('evidence_unit_ids') or [])
        if units&blocked_units:why.append('masked_native_unit')
        if why:
            dropped.update(why);candidate_copy_pages.add((r['doc_id'],r['pdf_page_number']))
        candidate_records.append((r,a,why))
    # Full target-source pages and pages of candidate copies are unavailable to G4.
    blocked_pages.update(candidate_copy_pages)
    all_entities=[dict(r,index=j,source='base_inventory') for j,r in enumerate(entities)]
    def endpoint(r,side):
        k=(r[side+'_type'],I.norm(r[side+'_canonical_zh']))
        if k not in labels:
            labels[k]=len(all_entities)
            all_entities.append(dict(entity_id='CTX-'+digest(k)[:24],entity_type=k[0],label_zh=r[side+'_canonical_zh'],index=labels[k],source='sanitized_candidate_vocabulary'))
        return labels[k]
    base=[]
    for c in sorted(graph['claims'],key=lambda c:c['claim_id']):
        base.append(dict(claim_id=c['claim_id'],triple=[entity_index[c['head_entity_id']],relation_index[c['relation']],entity_index[c['tail_entity_id']]],
                         group_id=families.find(c['claim_id']),fold=split[c['claim_id']],
                         source_pages=sorted({(r['doc_id'],r['pdf_page_number']) for r in sources[c['claim_id']]})))
    base_train={tuple(c['triple']) for c in base if c['fold']=='train'}
    edges={};ledger=[]
    for j,(r,a,why) in enumerate(candidate_records):
        item=dict(occurrence=j,record_id=r['triple_id'],doc_id=r['doc_id'],page=r['pdf_page_number'],
                  status=a.get('decision'),rejection_reasons=a.get('rejection_reasons',[]),exclusions=why)
        if why:ledger.append(item);continue
        triple=(endpoint(r,'head'),relation_index[r['relation']],endpoint(r,'tail'))
        rule=registry[r['relation']]
        legal=r['head_type'] in rule['domain'] and r['tail_type'] in rule['range']
        located=bool(a.get('evidence_validation',{}).get('valid')) and a.get('evidence_level') in ['E1','E2']
        entailed=a.get('relation_entailment_validation',{}).get('status')=='entailed'
        conservative=legal and located and entailed and a.get('decision') in ['silver_candidate','accepted_silver']
        weight=.5 if conservative else .15 if legal and a.get('decision')=='candidate_needs_review' else .05 if legal and located else .02 if legal else 0.
        bucket='qualified' if conservative else 'quarantine' if a.get('decision')=='candidate_needs_review' else 'rejected' if legal else 'schema_invalid'
        item.update(triple=triple,legal=legal,located=located,conservative=conservative,bucket=bucket,weight=weight)
        ledger.append(item)
        e=edges.setdefault(triple,dict(triple=triple,weight=weight,legal=legal,conservative=conservative,bucket=bucket,occurrences=[],pages=[],source_families=[]))
        e['occurrences'].append(r['triple_id']);e['pages'].append((r['doc_id'],r['pdf_page_number']));e['source_families'].append(r['source_family_id'])
        if weight>e['weight']:e.update(weight=weight,conservative=conservative,bucket=bucket)
    candidate_edges=[]
    for triple,e in sorted(edges.items()):
        e['pages']=sorted(set(e['pages']));e['source_families']=sorted(set(e['source_families']))
        e['already_base_train']=triple in base_train
        candidate_edges.append(e)
    source_forms=defaultdict(set)
    for r,a,why in candidate_records:
        if why:continue
        for side in ['head','tail']:source_forms[endpoint(r,side)].add(I.norm(r[side+'_surface']))
    for c in base:
        if c['fold']=='train':
            for r in sources[c['claim_id']]:
                for side,pos in [('head',0),('tail',2)]:source_forms[c['triple'][pos]].add(I.norm(r[side+'_surface']))
    contexts=[];text_exclusions=Counter();inverted=defaultdict(list)
    for (doc,pno),page in sorted(d['pages'].items()):
        if doc=='MP022' or (doc,pno) in blocked_pages:
            text_exclusions['heldout_or_copy_page']+=1;continue
        for uid,unit in sorted(I.native_units(page).items()):
            text=unit['text'];flat=I.norm(text)
            if len(flat)<25:continue
            if grams(text)&held_shingles:text_exclusions['target_quote_shingle_unit']+=1;continue
            idx=len(contexts);contexts.append(dict(unit_id=uid,doc_id=doc,page=pno,text=text,bbox=unit.get('bbox')))
            for token in set(re.findall(r'[\w]+',flat)):inverted[token].append(idx)
    selected=defaultdict(set)
    for eid,forms in sorted(source_forms.items()):
        for form in sorted(forms):
            if len(form)<4:continue
            tokens=set(re.findall(r'[\w]+',form))
            if not tokens:continue
            token=min(tokens,key=lambda x:len(inverted.get(x,[])))
            for idx in inverted.get(token,[]):
                if form in I.norm(contexts[idx]['text']):selected[eid].add(idx)
    texts=[]
    for e in all_entities:
        ids=sorted(selected[e['index']],key=lambda i:(len(contexts[i]['text']),contexts[i]['unit_id']))[:3]
        texts.append(dict(entity_index=e['index'],label=e['label_zh'],context_ids=ids,
                          text=e['label_zh']+'\n'+'\n'.join(contexts[i]['text'][:800] for i in ids)))
    known_pairs=[]
    for r in d['normalized']:
        k=[r['head_type'],I.norm(r['head_canonical_zh']),r['relation'],r['tail_type'],I.norm(r['tail_canonical_zh'])]
        known_pairs.append(dict(key=k,record_id=r['triple_id'],doc_id=r['doc_id'],page=r['pdf_page_number']))
    held_docs=[r for r in d['pages'].values() if r['doc_id']=='MP022']
    save(RUN/'data/catalogue.json',dict(entities=all_entities,relations=relations,registry=registry,nbase=len(entities)))
    save(RUN/'data/base_split.jsonl',base);save(RUN/'data/candidate_edges.jsonl',candidate_edges)
    save(RUN/'data/candidate_ledger.jsonl',ledger);save(RUN/'data/fact_groups.jsonl',group_manifest)
    save(RUN/'data/safe_context_units.jsonl',contexts);save(RUN/'data/entity_text.jsonl',texts)
    save(RUN/'audit_only/full_initial_pool_keys.jsonl',known_pairs)
    save(RUN/'audit_only/independent_document.jsonl',held_docs)
    save(RUN/'audit_only/blocked_text_pages.json',sorted(blocked_pages))
    save(RUN/'audit_only/heldout_quote_shingles.json',sorted(held_shingles))
    save(RUN/'audit_only/base_source_records.jsonl',graph['source_records'])
    # No target-equivalent candidate may survive, including reversed/alternative predicates.
    assert all(not why or not (set(why)-{'independent_document','masked_alias_or_reverse_pair','masked_native_unit'}) for _,_,why in candidate_records)
    assert all(pair_record(r) not in blocked_pairs for r,a,why in candidate_records if not why)
    assert all(u['doc_id']!='MP022' and (u['doc_id'],u['page']) not in blocked_pages and not grams(u['text'])&held_shingles for u in contexts)
    active={e['index'] for e in all_entities if any(e['index'] in [h,t] for h,r,t in base_train)}
    cold=defaultdict(Counter)
    for c in base:
        h,r,t=c['triple'];cold[c['fold']]['warm' if h in active and t in active else 'one_cold' if h in active or t in active else 'both_cold']+=1
    summary=dict(base_assertions=len(graph['evidence_assertions']),base_claims=len(base),base_entities=len(entities),all_entity_vocabulary=len(all_entities),
          folds=dict(Counter(c['fold'] for c in base)),groups=len(group_manifest),largest_group=max(map(len,grouped.values())),
          endpoint_status_by_G1_train={k:dict(v) for k,v in cold.items()},
          candidate_occurrences=len(ledger),candidate_exclusions_overlapping=dict(dropped),
          surviving_candidate_occurrences=sum(not r['exclusions'] for r in ledger),unique_candidate_edges=len(candidate_edges),
          extra_candidate_edges=sum(not r['already_base_train'] for r in candidate_edges),
          candidate_strata=dict(Counter(e['bucket'] for e in candidate_edges)),
          G2_extra_candidates=sum(e['conservative'] and not e['already_base_train'] for e in candidate_edges),
          safe_native_units=len(contexts),entities_with_safe_context=sum(bool(t['context_ids']) for t in texts),
          text_exclusions=dict(text_exclusions),blocked_text_pages=len(blocked_pages),
          independent_document='MP022',split_seed=14112026,domain_input_git_object=I.REV,
          evaluation='base-label recovery proxy; not factual accuracy',block_aliases_used_for_split_only=True)
    save(RUN/'data/summary.json',summary)
    save(RUN/'data/freeze.json',dict(inputs=d['inputs'].hashes,source_git_object=I.REV,
         data_files={str(p.relative_to(RUN)):file_sha(p) for p in sorted((RUN/'data').glob('*')) if p.name!='freeze.json'},
         safety=dict(no_other_graph_read=True,no_external_documents=True,no_graph_write=True),
         protocol=dict(fractions=[.70,.15,.15],independent_doc='MP022',grouping='type-agnostic source/Chinese aliases + unordered endpoint pair + exact quote + shared native unit; blockers never used to add facts',
                       ranking='full base entity catalogue, same all arms, filtered known base truths, average tied rank',
                       G4='native training units only; target/copy pages and overlapping 20-char shingles excluded; MP022 inaccessible to training',
                       caveat='Conservative finite alias/copy closure, not proof against every unobserved semantic paraphrase')))
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
