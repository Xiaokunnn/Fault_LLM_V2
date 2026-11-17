"""Frozen train-source role prototypes, type-legal perturbations and exposure."""
from collections import Counter,defaultdict
import re
from role_io import *
from model import Neighborhood


def qualifier(rec):
    explicit=rec.get('conditions_source') or rec.get('condition') or rec.get('conditions')
    text=I.norm(rec.get('evidence_text',''))
    cues=re.findall(r'\b(?:if|when|unless|otherwise|before|after|never|not)\b',text)
    if cues and not explicit:return None
    return (I.norm(explicit),I.norm(rec.get('modality')),tuple(sorted(set(cues))))


def contract(rec):
    return bool(rec.get('evidence_validation',{}).get('valid') and rec.get('relation_entailment_validation',{}).get('status')=='entailed'
        and rec.get('relation_type_validation',{}).get('valid'))


def compatible(a,b):
    return a['doc_id']==b['doc_id'] and all(a.get(k) and a.get(k)==b.get(k) for k in ['pump_type','service','applicability_scope']) and qualifier(a) is not None and qualifier(a)==qualifier(b)


def main():
    if (OUT/'data/freeze.json').exists():print('REUSE prepared',DATASET);return
    cat=read(RUN/'data/catalogue.json');R=len(cat['relations']);graph=Neighborhood('full',SEEDS[0]);train=read(RUN/'data/train_base.jsonl')
    ids={x['id'] for x in train};split=read(RUN/'data/base_split.jsonl');source=defaultdict(list)
    for rec in read(RUN/'audit_only/base_source_records.jsonl'):
        if rec['expanded_claim_id'] in ids:source[rec['expanded_claim_id']].append(rec)
    d=I.load();norm={r['triple_id']:r for r in d['normalized']};audit={k:r for r in d['audit'] for k in I.record_ids(r)}
    alias=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for rec in pop:
            for side in ['head','tail']:alias.join('L|'+rec[side+'_type']+'|'+I.norm(rec[side+'_canonical_zh']),'S|'+I.norm(rec[side+'_surface']))
    ea=[alias.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities']]
    forbidden={tuple(sorted([ea[x['triple'][0]],ea[x['triple'][2]]])) for x in split if x['fold']!='train'}
    rawrows=read(RUN/'data/context_edges.jsonl');registry={}
    for edge in rawrows:
        rr=source[edge['edge_id']] if edge['is_base'] else [next((audit[k] for k in I.record_ids(norm[rid]) if k in audit),norm[rid]) for rid in edge['occurrences']]
        registry[edge['edge_id']]=[r for r in rr if contract(r)]
    # Mutually exclusive main reasons on the whole context ledger, not just sampled neighbors.
    incident=Counter();eligible=Counter();selected=Counter();failure_flags=defaultdict(Counter)
    for q in train:
        g=graph.ids[q['id']];meta=graph.meta[g]
        for h in [q['triple'][0],q['triple'][2]]:
            for t,r,e in graph.adj[h]:
                if e['is_base']:continue
                incident[e['edge_id']]+=1;flags=[]
                if e['group_id']==g:flags.append('self_group')
                if e['pair'] in meta['pairs']:flags.append('alias_or_same_pair')
                if set(map(tuple,e['pages']))&set(map(tuple,meta['pages'])):flags.append('same_source_page')
                if not flags:eligible[e['edge_id']]+=1
                failure_flags[e['edge_id']].update(flags)
            for _,_,e in graph.entries(h,q['id']):
                if not e['is_base']:selected[e['edge_id']]+=1
    ledger=[]
    for e in rawrows:
        if e['is_base']:continue
        key=e['edge_id']
        reason='schema_illegal' if not e['legal'] else 'used' if selected[key] else 'not_incident_to_supervised_anchors' if not incident[key] else 'all_incident_queries_excluded_by_copy_or_source' if not eligible[key] else 'max16_truncation_only'
        ledger.append(dict(edge_id=key,legal=e['legal'],bucket=e['bucket'],primary_reason=reason,incident=incident[key],eligible_before_cap=eligible[key],selected=selected[key],
            secondary_exclusion_occurrences=dict(failure_flags[key]),semantic_error_inferred=False))
    save(OUT/'data/candidate_exposure_ledger.jsonl',ledger)
    save(OUT/'data/candidate_exposure_summary.json',dict(total=len(ledger),counts=dict(Counter(x['primary_reason'] for x in ledger)),
        legal=sum(e['legal'] for e in ledger),source='Exact old Neighborhood.entries protocol; unsampled is never semantic error',quality_rejection_other_than_schema=0))
    observed={tuple(e['triple']) for e in rawrows};positives=defaultdict(set)
    for q in train:
        h,r,t=q['triple'];positives[h,r].add(t);positives[t,r+R].add(h)
    def legal(h,r,t):
        if r>=R:h,t=t,h;r-=R
        rule=cat['registry'][cat['relations'][r]]
        return cat['entities'][h]['entity_type'] in rule['domain'] and cat['entities'][t]['entity_type'] in rule['range']
    def original(h,r,t):return (h,r,t) if r<R else (t,r-R,h)
    by_tail_type=defaultdict(list)
    for edge in rawrows:
        if not registry[edge['edge_id']]:continue
        h,r,t=edge['triple']
        for anchor,dr,tail in [(h,r,t),(t,r+R,h)]:by_tail_type[cat['entities'][tail]['entity_type']].append((anchor,dr,tail,edge))
    proposals=[];reasons=Counter();seen=set();evidence={};unobservable=[]
    for query in train:
        h,r,t=query['triple']
        for anchor,rel,y in [(h,r,t),(t,r+R,h)]:
            entries=graph.entries(anchor,query['id'])
            for slot,(u,erel,edge) in enumerate(entries):
                if erel!=rel or ea[u]==ea[y] or ea[anchor]==ea[u]:continue
                if not edge['is_base'] and not edge['conservative']:continue
                witnesses=[(a,b) for a in source[query['id']] for b in registry[edge['edge_id']] if contract(a) and compatible(a,b)]
                if not witnesses:reasons['scope_or_contract_not_demonstrated']+=1;continue
                key=(anchor,rel,edge['edge_id'])
                if key in seen:continue
                seen.add(key);qa,cs=witnesses[0]
                # Every source pointer here belongs to a retained training-context edge.
                evidence[edge['edge_id']]=[I.source_pointer(x) for x in registry[edge['edge_id']]]
                pos=dict(h=anchor,r=rel,y=y,training_id=query['id'],edge_id=edge['edge_id'],slot=slot,neighbor=u,edge_relation=erel,
                    support='Same directed-role, automatically evidence-qualified source prototype in same document scope, then utility-screened; not logical entailment',
                    scope_level='document metadata + explicit stored qualifier compatibility; unrecorded local conditions not certified')
                changes=[]
                donors=[]
                for ah,ar,ut,donor in by_tail_type[cat['entities'][u]['entity_type']]:
                    if ut==u or ut in positives[anchor,rel] or ea[ut] in {ea[z] for z in positives[anchor,rel]}:continue
                    if tuple(sorted([ea[anchor],ea[ut]])) in forbidden or ea[anchor]==ea[ut]:continue
                    if original(anchor,rel,ut) in observed:continue
                    if donor['edge_id']==edge['edge_id'] or not any(z['doc_id']==cs['doc_id'] for z in registry[donor['edge_id']]):continue
                    chars=set(cat['entities'][u]['label_zh']);other=set(cat['entities'][ut]['label_zh']);sim=len(chars&other)/max(1,len(chars|other))
                    # Prefer true column/row variation when both have real table roles.
                    sr={z.get('row_group_id') for z in cs.get('evidence_units',[]) if z.get('row_group_id')}
                    dr={z.get('row_group_id') for z in registry[donor['edge_id']][0].get('evidence_units',[]) if z.get('row_group_id')}
                    kind='different_table_row_object' if sr and dr and sr.isdisjoint(dr) else 'source_object_swap'
                    donors.append((kind!='different_table_row_object',-sim,donor['edge_id'],ut,kind,donor))
                for _,_,_,ut,kind,donor in sorted(donors,key=lambda x:x[:4])[:3]:
                    changes.append((ut,erel,kind,donor['edge_id']));evidence[donor['edge_id']]=[I.source_pointer(x) for x in registry[donor['edge_id']]]
                # Relation and direction alternatives must pass the real Domain/Range.
                for rr in range(2*R):
                    if rr==erel or not legal(anchor,rr,u) or original(anchor,rr,u) in observed:continue
                    name=cat['relations'][rr%R];oldname=cat['relations'][erel%R]
                    if {name,oldname} in [set(['contains','located_in']),set(['indicates','manifests_as'])]:continue
                    kind='direction_swap' if rr%R==erel%R else 'type_legal_relation_swap'
                    changes.append((u,rr,kind,None))
                    if len(changes)>=6:break
                for v,rr,kind,donor in changes:
                    record=dict(pos,negative_neighbor=v,negative_relation=rr,negative_kind=kind,donor_edge_id=donor,
                        synthetic_proxy=True,negative_is_proven_false=False,features_identical=True,
                        split='probe' if int(digest(['role-probe',anchor,rel])[:8],16)%5==0 else 'fit')
                    record['pair_id']='RP-'+digest([anchor,rel,edge['edge_id'],v,rr])[:20];proposals.append(record)
                # With unchanged model inputs, pure qualifier swaps are exactly unobservable.
                unobservable.append(dict(h=anchor,r=rel,edge_id=edge['edge_id'],kind='scope_or_condition_only_swap',
                    changed_input_fields=[],identical_gate_input=True,trainable=False,
                    explanation='Current 12 features contain only qualifier cue bits, no owner/model/phase identity; do not attach contradictory binary labels'))
    save(OUT/'data/role_pairs_unfiltered.jsonl',proposals)
    save(OUT/'data/train_evidence_registry.json',evidence)
    save(OUT/'data/unobservable_condition_controls.jsonl',unobservable)
    save(OUT/'data/train_positive_tails.json',[dict(h=h,r=r,tails=sorted(tt)) for (h,r),tt in sorted(positives.items())])
    summary=dict(dataset=DATASET,role_proposals=len(proposals),fit_probe=dict(Counter(p['split'] for p in proposals)),
        kinds=dict(Counter(p['negative_kind'] for p in proposals)),role_anchor_queries=len({(p['h'],p['r']) for p in proposals}),
        evidence_edges=len(evidence),excluded=dict(reasons),unobservable_conditions=len(unobservable),old_model_architecture_unchanged=True,
        factual_labels='Only original automatic evidence contract and synthetic contrast proxies; no expert truth',
        source_object=I.REV,old_data_freeze=file_sha(RUN/'data/collab_freeze.json'))
    save(OUT/'data/freeze.json',dict(summary=summary,files={str(f.relative_to(OUT)):file_sha(f) for f in sorted((OUT/'data').glob('*'))}))
    print(summary,flush=True)


if __name__=='__main__':main()
