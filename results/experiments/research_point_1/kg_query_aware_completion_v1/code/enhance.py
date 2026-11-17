"""Validation-selected application proposals, with post-score provenance audit."""
from collections import Counter,defaultdict
import re
import numpy as np
import torch
from io_utils import *
from evaluate import get_scores
from build_index import edge_sources


def main():
    if (EXP/'enhancement/complete.json').exists():return
    torch.set_num_threads(2);selection=read(EXP/'analysis/application_selection.json');method=selection['method'];seed=selection['seed']
    cat=read(EXP/'data/catalogue.json');n=cat['nbase'];rels=cat['relations'];R=len(rels)
    keys=[(h,r) for h in range(n) for r in range(R) if cat['entities'][h]['entity_type'] in cat['registry'][rels[r]]['domain']]
    # This function sees only catalogue query keys, not held targets or sources.
    matrix=get_scores(method,seed,keys)
    # Only after scores freeze, read full facts to classify novelty and audit text.
    d=I.load();uf=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for x in pop:
            for s in ['head','tail']:uf.join('L|'+x[s+'_type']+'|'+I.norm(x[s+'_canonical_zh']),'S|'+I.norm(x[s+'_surface']))
    def root(e):return uf.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh']))
    alias=[root(e) for e in cat['entities']]
    def key_record(x):return (uf.find('L|'+x['head_type']+'|'+I.norm(x['head_canonical_zh'])),x['relation'],uf.find('L|'+x['tail_type']+'|'+I.norm(x['tail_canonical_zh'])))
    def equivalents(k):
        yield k
        for a,b in [('contains','located_in'),('indicates','manifests_as')]:
            if k[1]==a:yield (k[2],b,k[0])
            if k[1]==b:yield (k[2],a,k[0])
    base=set();base_records=defaultdict(list)
    for x in d['graph']['source_records']:
        for k in equivalents(key_record(x)):base.add(k);base_records[k].append(I.source_pointer(x))
    initial=defaultdict(list)
    for x in d['normalized']:
        for k in equivalents(key_record(x)):initial[k].append(x)
    raw=[];known=[];rejected=[];seen=set()
    for ix,(h,r) in enumerate(keys):
        count=0;range_=cat['registry'][rels[r]]['range']
        for t in np.argsort(-matrix[ix],kind='stable')[:20]:
            t=int(t);k=(alias[h],rels[r],alias[t]);score=float(matrix[ix,t]);rank_=1+int((matrix[ix]>score+1e-8).sum())+.5*(int(np.isclose(matrix[ix],score,rtol=0,atol=1e-8).sum())-1)
            row=dict(head_id=cat['entities'][h]['entity_id'],head=cat['entities'][h]['label_zh'],head_type=cat['entities'][h]['entity_type'],relation=rels[r],tail_id=cat['entities'][t]['entity_id'],tail=cat['entities'][t]['label_zh'],tail_type=cat['entities'][t]['entity_type'],h=h,r=r,t=t,score=score,raw_rank=rank_)
            if cat['entities'][t]['entity_type'] not in range_:
                if len(rejected)<30:rejected.append(row)
                continue
            if k in base:
                if len(known)<30:known.append(dict(row,category='already_base_or_recognized_inverse',source=base_records[k][:1]))
                continue
            if alias[h]==alias[t] or k in seen:continue
            seen.add(k);raw.append(dict(row,initial_pool=bool(initial[k]),_alias_key=k));count+=1
            if count>=3:break
    raw.sort(key=lambda x:(-x['score'],x['h'],x['r'],x['t']))
    picked=[];perhead=Counter();perrel=Counter()
    for row in raw:
        if perhead[row['head_id']]>=2 or perrel[row['relation']]>=20:continue
        picked.append(row);perhead[row['head_id']]+=1;perrel[row['relation']]+=1
        if len(picked)>=150:break
    registry=read(EXP/'data/training_source_registry.json');edges=read(EXP/'index/edges.jsonl');views=read(EXP/'index/oriented_views.jsonl');z=np.load(EXP/'retrieval/R3_all_global.npz')
    trained_ids={rid for e in edges for rid in e['source_keys']};trainpages={tuple(p) for e in edges for p in e['pages']};traingrams=set()
    for e in edges:
        for x in edge_sources(e,registry):traingrams.update(shingles(x.get('evidence_text','')))
    allunits=[]
    for (doc,page),p in sorted(d['pages'].items()):
        for uid,u in I.native_units(p).items():
            if len(u['text'])>=15:allunits.append(dict(unit_id=uid,doc_id=doc,page=page,text=u['text'],bbox=u.get('bbox'),_flat=I.norm(u['text'])))
    forms=defaultdict(set)
    for pop in [d['raw'],d['normalized'],d['graph']['source_records']]:
        for x in pop:
            for s in ['head','tail']:
                a=uf.find('L|'+x[s+'_type']+'|'+I.norm(x[s+'_canonical_zh']))
                if len(I.norm(x[s+'_surface']))>=4:forms[a].add(I.norm(x[s+'_surface']))
    cache={}
    def matching(a):
        if a not in cache:
            ff=sorted(forms[a],key=lambda f:(-len(f),f))[:12]
            cache[a]={i for i,u in enumerate(allunits) if any(f in u['_flat'] for f in ff)}
        return cache[a]
    cues={'causes':r'caus|result|due to|lead|导致|引起','prevented_by':r'prevent|avoid|防止|避免','maintained_by':r'clean|lubric|replac|repair|maint|清洗|更换','mitigated_by':r'correct|clean|replac|repair|检查|清洗|更换','inspected_by':r'inspect|check|检查','indicates':r'indicat|detect|diagnos|表明|检测','manifests_as':r'indicat|symptom|表现'}
    audit={k:x for x in d['audit'] for k in I.record_ids(x)};out=[]
    for row in picked:
        k=tuple(row.pop('_alias_key'));h,r,t=row['h'],row['r'],row['t'];context=[]
        for view,rs in zip(z['ids'][h,r,:5],z['scores'][h,r,:5]):
            if view<0:continue
            v=views[int(view)];e=edges[v['edge_index']]
            context.append(dict(edge_id=e['edge_id'],triple=e['triple'],oriented_anchor=v['anchor'],oriented_relation=v['relation'],oriented_neighbor=v['neighbor'],retrieval_score=float(rs),is_base=e['is_base'],automatic_status=e['bucket'],source=edge_sources(e,registry)[:1],structural_relation_to_query='same_anchor' if v['anchor']==h else 'retrieved_analogy_not_asserted_fact'))
        existing=[]
        for x in initial[k][:3]:
            a=next((audit[u] for u in I.record_ids(x) if u in audit),x)
            existing.append(dict(source=I.source_pointer(x),automatic_status=a.get('decision'),rejection_reasons=a.get('rejection_reasons',[]),native_address=I.address_check(x,d['pages'][x['doc_id'],x['pdf_page_number']]),record_used_in_context=x['triple_id'] in trained_ids,
                unseen_page=(x['doc_id'],x['pdf_page_number']) not in trainpages,old_semantic_contract=a.get('relation_entailment_validation',{}).get('status'),fact_truth_confirmed=False))
        hits=[]
        for i in sorted(matching(k[0])&matching(k[2]),key=lambda i:((allunits[i]['doc_id'],allunits[i]['page']) in trainpages,len(allunits[i]['text']))):
            u=allunits[i];samequote=bool(shingles(u['text'])&traingrams)
            hits.append(dict(**{a:b for a,b in u.items() if a!='_flat'},page_seen=(u['doc_id'],u['page']) in trainpages,quote_overlap_with_training=samequote,lexical_relation_cue=bool(re.search(cues.get(row['relation'],r'(?!)'),u['_flat'])),semantic_support='cooccurrence_only_requires_semantic_check'))
            if len(hits)>=2:break
        out.append(dict(prediction_id='PRED-'+digest([method,seed,row['head_id'],row['relation'],row['tail_id']])[:20],**row,method=method,seed=seed,model_score_is_not_fact_probability=True,novelty='initial_candidate_already_present' if row['initial_pool'] else 'model_only_beyond_base_and_initial_alias_closure',
            context=context,initial_evidence=existing,posthoc_native_hits=hits,evidence_class='existing_candidate_record_unverified' if existing else 'local_cooccurrence_unverified' if hits else 'inference_only_no_local_match',
            independent_semantic_confirmation=False,published_to_graph=False))
    save(EXP/'ENHANCEMENT_CASES.jsonl',out);save(EXP/'enhancement/known_prediction_controls.jsonl',known);save(EXP/'enhancement/schema_rejected_examples.jsonl',rejected)
    summary=dict(method=method,seed=seed,query_count=len(keys),raw_nonbase_proposals=len(raw),delivered=len(out),novelty=dict(Counter(x['novelty'] for x in out)),evidence_classes=dict(Counter(x['evidence_class'] for x in out)),posthoc_unseen_page_hits=sum(any(not h['page_seen'] and not h['quote_overlap_with_training'] for h in x['posthoc_native_hits']) for x in out),confirmed_new_facts=0,formal_graph_writes=0,
        selection='Top scores, maximum2 per head and20 per relation, cap150, legal endpoint types; output filters never applied to benchmark ranks',independence='Unseen quote/page is not independent source-family validation. Exact initial candidate and cooccurrence are not semantic truth.')
    save(EXP/'enhancement/complete.json',summary);print(summary,flush=True)


if __name__=='__main__':main()
