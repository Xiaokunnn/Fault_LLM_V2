"""Actual bounded relation hypotheses; distinguish analogy from confirmation."""
from common_local import *
from transport_cpu import CPUIndex,score_transport


def main():
    if (OUT/'potential/complete.json').exists():print('REUSE potential relations');return
    d,cat,entities,ei,claims,src,uf=load_domain();R=len(cat['relations']);ri={r:j for j,r in enumerate(cat['relations'])}
    def root(typ,label):return uf.find('L|'+typ+'|'+I.norm(label))
    roots=[root(e['entity_type'],e['label_zh']) for e in entities]
    def rec_key(x):return (root(x['head_type'],x['head_canonical_zh']),x['relation'],root(x['tail_type'],x['tail_canonical_zh']))
    def equivalents(k):
        yield k
        for a,b in [('contains','located_in'),('indicates','manifests_as')]:
            if k[1]==a:yield (k[2],b,k[0])
            if k[1]==b:yield (k[2],a,k[0])
    base={};initial=defaultdict(list)
    for cid,c in claims.items():
        h,t=ei[c['head_entity_id']],ei[c['tail_entity_id']]
        for k in equivalents((roots[h],c['relation'],roots[t])):base.setdefault(k,[]).append(cid)
    for x in d['normalized']:
        for k in equivalents(rec_key(x)):initial[k].append(x)
    sourceaudit={k:x for x in d['audit'] for k in I.record_ids(x)}
    out=defaultdict(list);role_groups=defaultdict(list)
    for cid,c in claims.items():
        h,t=ei[c['head_entity_id']],ei[c['tail_entity_id']];out[h].append((ri[c['relation']],t,cid))
        role_groups['out',c['relation'],t].append((h,cid));role_groups['in',c['relation'],h].append((t,cid))
    semantic=torch.load(STUDY/'index/vectors.pt',map_location='cpu',weights_only=True)['entities'][:2150].numpy();patterns=defaultdict(list);exclusion=Counter()
    for shared,anchors in sorted(role_groups.items()):
        for (h,ch),(a,ca) in itertools.permutations(anchors,2):
            if h==a or entities[h]['entity_type']!=entities[a]['entity_type']:continue
            sim=float(semantic[h]@semantic[a])
            if sim<.85:continue
            if conflict(entities[h]['label_zh'],entities[a]['label_zh']):exclusion['explicit_identity_or_stage']+=1;continue
            for r,t,cr in out[a]:
                if t in [h,a,shared[2]] or cr==ca:continue
                rule=cat['registry'][cat['relations'][r]]
                if entities[h]['entity_type'] not in rule['domain'] or entities[t]['entity_type'] not in rule['range']:continue
                k=(roots[h],cat['relations'][r],roots[t])
                if k in base:exclusion['already_base_or_equivalent']+=1;continue
                sets=[{I.norm(x.get('pump_type')) for x in src[c] if x.get('pump_type')} for c in [ch,ca,cr]];common=set.intersection(*sets)
                if not common:exclusion['no_common_declared_equipment_scope']+=1;continue
                premises=[dict(claim_id=c,head_entity_id=claims[c]['head_entity_id'],relation=claims[c]['relation'],tail_entity_id=claims[c]['tail_entity_id'],sources=[I.source_pointer(x) for x in src[c]]) for c in [ch,ca,cr]]
                docs={x['doc_id'] for c in [ch,ca,cr] for x in src[c]}
                patterns[h,r,t].append(dict(rule='shared_role_neighbor_analogy',shared_role=shared[0],shared_relation=shared[1],shared_neighbor=entities[shared[2]],source_anchor=entities[a],target_anchor=entities[h],head_similarity=sim,premises=premises,documents=sorted(docs),cross_document=len(docs)>1,common_declared_pump_type=sorted(common),local_conditions_fully_verified=False,logical_entailment=False,assumption='Same-role shared neighbor + similar typed anchors may support transferring another relation within retained scope; only an analogy hypothesis, not a universal Horn rule'))
    proposed={}
    old=read(STUDY/'ENHANCEMENT_CASES.jsonl')
    notes={x['prediction_id']:x for x in read(STUDY/'enhancement/ai_case_notes.jsonl')}
    for x in old:
        proposed[x['h'],x['r'],x['t']]=dict(origins=['saved_transport_R3'],previous_prediction=x,previous_analysis=notes.get(x['prediction_id']))
    # Bounded deterministic selection is fixed by IDs, before model scores.
    for triple in sorted(patterns,key=lambda t:digest(['bounded-pattern',t]))[:300]:
        p=proposed.setdefault(triple,dict(origins=[]));p['origins'].append('shared_role_pattern_generation')
    triples=sorted(proposed);keys=sorted({(h,r) for h,r,t in triples});ix={k:j for j,k in enumerate(keys)};index=CPUIndex();ids=np.stack([index.cached['R3']['ids'][h,r,:16] for h,r in keys]);ss=np.stack([index.cached['R3']['scores'][h,r,:16] for h,r in keys]);data=torch.load(STUDY/'features'/'G2_s16112026.pt',map_location='cpu',weights_only=True);scores=score_transport(data,keys,ids,ss,index)
    components={}
    import csv
    for x in csv.DictReader((AUDIT/'node_degrees.csv').open()):
        if x['view']=='G_full':components[x['entity_id']]=int(x['component_id'])
    outcomes=[];excluded=[];pattern_all=[]
    for (h,r,t),meta in proposed.items():
        key=(roots[h],cat['relations'][r],roots[t]);existing=key in base;first=meta.get('previous_prediction');ps=patterns.get((h,r,t),[]);value=float(scores[ix[h,r],t]);rank=1+int((scores[ix[h,r]]>value+1e-8).sum())+.5*(int(np.isclose(scores[ix[h,r]],value,rtol=0,atol=1e-8).sum())-1)
        if existing:
            excluded.append(dict(triple=[h,r,t],reason='already_base_or_known_alias_inverse',claim_ids=base[key]));continue
        issue=meta.get('previous_analysis');hard=issue and issue['assessment'] in ['unsupported_causal_or_alias_restatement','unsupported_direction_and_temporal_relation']
        if hard:category='D';grade='prior_AI_source_reading_role_direction_issue';explanation=issue['reason']
        elif initial[key]:category='A';grade='already_initial_candidate_not_published';explanation='Initial record already expresses this relation under finite aliases; not a new algorithm discovery.'
        elif ps:category='B';grade='conditional_three_premise_relation_analogy';explanation='Three explicit known relation premises + typed similar anchors + retained common scope; not logical entailment or confirmed fact.'
        else:category='C';grade='insufficient_current_direct_or_pattern_support';explanation='No admitted three-premise analogy; absence of an exact quote is not a rejection or proof of document absence.'
        actual=[]
        for vi,sv in zip(ids[ix[h,r]],ss[ix[h,r]]):
            if vi<0:continue
            v=index.views[int(vi)];e=index.edges[v['edge_index']]
            same_component = (v['anchor'] < 2150 and
                components.get(entities[v['anchor']]['entity_id']) ==
                components[entities[h]['entity_id']])
            actual.append(dict(edge_id=e['edge_id'],oriented_anchor=v['anchor'],oriented_relation=v['relation'],oriented_neighbor=v['neighbor'],retrieval_score=float(sv),source_pages=e['pages'],automatic_status=e['bucket'],is_base=e['is_base'],source=sources(e,index.registry)[:1],same_full_component_as_target_anchor=same_component,cross_component_or_outside_base=not same_component))
        matched=[]
        for x in initial[key][:4]:
            a=next((sourceaudit[u] for u in I.record_ids(x) if u in sourceaudit),x)
            matched.append(dict(record_id=x['triple_id'],source=I.source_pointer(x),automatic_status=a.get('decision'),existing_semantic_contract=a.get('relation_entailment_validation',{}).get('status'),existing_location_contract=a.get('evidence_validation',{}).get('valid'),rejection_reasons=a.get('rejection_reasons',[])))
        outcome=dict(relation_id='GAPREL-'+digest([h,r,t])[:20],head=entities[h],relation=cat['relations'][r],tail=entities[t],triple_indices=[h,r,t],already_base=False,already_initial_candidate=bool(initial[key]),primary_category=category,support_grade=grade,support_explanation=explanation,origins=meta['origins'],transport_R3_score=value,raw_rank=rank,score_is_not_fact_probability=True,transport_seed=16112026,transport_actual_contexts=actual,pattern_support=ps,initial_records=matched,prior_native_evidence_hits=first.get('posthoc_native_hits',[]) if first else [],prior_AI_analysis=issue,scope_condition_status='retained common declared equipment type; local conditions unresolved' if ps else 'not established for this transfer',cross_document_pattern=any(p['cross_document'] for p in ps),pattern_premises_not_necessarily_in_frozen_transport_context=True,published=False,confirmed_new_fact=False)
        outcomes.append(outcome)
        if ps:pattern_all.append(outcome)
    save(OUT/'POTENTIAL_RELATIONS.jsonl',outcomes);save(OUT/'potential/pattern_supported_relations.jsonl',pattern_all);save(OUT/'potential/excluded_existing_controls.jsonl',excluded)
    save(OUT/'potential/complete.json',dict(saved_transport_inputs=len(old),pattern_generated_unique=len(patterns),bounded_new_pattern_proposals=min(300,len(patterns)),delivered=len(outcomes),categories=dict(Counter(x['primary_category'] for x in outcomes)),B_cross_document=sum(x['primary_category']=='B' and x['cross_document_pattern'] for x in outcomes),generation_exclusions=exclusion,excluded_existing=len(excluded),confirmed_new_facts=0,device='cpu',LLM_requests=0,pattern_is_not_deductive_proof=True))
    save(OUT/'potential/input_hashes.json',dict(domain_object=I.REV,domain_inputs=d['inputs'].hashes,parents={str(p.relative_to(ROOT)):sha(p) for p in [STUDY/'ENHANCEMENT_CASES.jsonl',STUDY/'enhancement/ai_case_notes.jsonl',STUDY/'data/catalogue.json',AUDIT/'node_degrees.csv']}))
    print(read(OUT/'potential/complete.json'),flush=True)


if __name__=='__main__':main()
