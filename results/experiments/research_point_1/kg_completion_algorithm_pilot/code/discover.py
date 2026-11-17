"""Closed-entity latent relation proposals, novelty accounting, held-document packets.

No proposal is published or assigned factual confidence by this script.
"""
from collections import Counter,defaultdict
import time
import re
import numpy as np
import torch
from common import RUN,SEEDS,read,save,digest,file_sha
from prepare import I,UF
from train_simkgc import setup,query_text


PROTOCOL=dict(selection='Highest three-seed mean VALIDATION link MRR among SimKGC G1/G2/G3/G4/continue/anchor/anchor_uniform; fixed first seed for generation, no test choice',
    universe='All base entities as heads; all domain-compatible 15 relations; rank all range-compatible base tails',
    top_k=3,positive_acceptance_threshold=None,publication=False,
    review='Up to 24 source-only packets: max four retrieval hits per novelty class, plus four highest-scoring beyond-both with no same-page endpoint evidence; no semantic labels used for selection',
    independence='MP022 entire document withheld from base/candidate/text training; entity catalogue remains transductive; evaluator is AI, not expert Gold')


def main():
    assert (RUN/'evaluation/complete.json').exists(),'Do not access independent evidence while model decisions remain open'
    save(RUN/'configs/discovery_protocol.json',PROTOCOL)
    cat=read(RUN/'data/catalogue.json');options=[]
    for view,proto in [('G1','none'),('G2','none'),('G3','none'),('G4','none'),('G3','continue'),('G3','anchor'),('G3','anchor_uniform')]:
        folders=[RUN/'models'/(f'simkgc_{view}_s{s}'+('' if proto=='none' else '_'+proto)) for s in SEEDS]
        mean=float(np.mean([read(f/'complete.json')['validation_link_MRR'] for f in folders]))
        options.append((mean,view,proto,folders[0]))
    mean,view,proto,folder=max(options,key=lambda x:x[0])
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2)
    model,tokenizer,descriptions,_=setup(view,cat);model=model.to(device)
    model.load_state_dict(torch.load(folder/'best.pt',map_location=device,weights_only=True));model.eval()
    def encode(texts,encoder):
        out=[]
        with torch.no_grad():
            for off in range(0,len(texts),128):
                b=tokenizer(texts[off:off+128],padding='max_length',truncation=True,max_length=96,return_tensors='pt')
                ids=b['input_ids'].to(device);mask=b['attention_mask'].to(device);typ=b.get('token_type_ids',torch.zeros_like(b['input_ids'])).to(device)
                out.append(model._encode(encoder,ids,mask,typ))
        return torch.cat(out)
    start=time.perf_counter();n=cat['nbase'];entities=cat['entities'][:n]
    keys=[(h,r) for h,e in enumerate(entities) for r,name in enumerate(cat['relations']) if e['entity_type'] in cat['registry'][name]['domain']]
    tail_vectors=encode(descriptions[:n],model.tail_bert)
    qvectors=encode([query_text(h,r,descriptions,cat) for h,r in keys],model.hr_bert)
    # Audit-only labels are used ONLY now for novelty/source classification, not prediction.
    d=I.load();aliases=UF()
    for population in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for rec in population:
            for side in ['head','tail']:aliases.join('L|'+rec[side+'_type']+'|'+I.norm(rec[side+'_canonical_zh']),'S|'+I.norm(rec[side+'_surface']))
    alias=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in entities]
    index={e['entity_id']:i for i,e in enumerate(entities)}
    base_facts={(alias[index[c['head_entity_id']]],c['relation'],alias[index[c['tail_entity_id']]]) for c in d['graph']['claims']}
    initial_facts={(aliases.find('L|'+r['head_type']+'|'+I.norm(r['head_canonical_zh'])),r['relation'],aliases.find('L|'+r['tail_type']+'|'+I.norm(r['tail_canonical_zh']))) for population in [d['raw'],d['audit'],d['normalized']] for r in population}
    base_pairs={tuple(sorted([h,t])) for h,r,t in base_facts};initial_pairs={tuple(sorted([h,t])) for h,r,t in initial_facts}
    proposals=[]
    model_descriptions=read(RUN/'data/training_entity_text.jsonl')
    for off in range(0,len(keys),256):
        scores=(qvectors[off:off+256]@tail_vectors.T).detach().cpu().numpy()
        for j,(h,r) in enumerate(keys[off:off+256]):
            allowed=[i for i,e in enumerate(entities) if e['entity_type'] in cat['registry'][cat['relations'][r]]['range'] and i!=h]
            ordered=sorted(allowed,key=lambda t:(-float(scores[j,t]),t))[:3]
            for pos,t in enumerate(ordered,1):
                fact=(alias[h],cat['relations'][r],alias[t]);pair=tuple(sorted([alias[h],alias[t]]))
                inv={'contains':'located_in','located_in':'contains','manifests_as':'indicates','indicates':'manifests_as'}.get(cat['relations'][r])
                reverse=(alias[t],inv,alias[h]) if inv else None
                inverse_seen=reverse in base_facts or reverse in initial_facts
                kind='base_already_known' if fact in base_facts or reverse in base_facts else 'initial_pool_already_observed' if fact in initial_facts or reverse in initial_facts else 'new_predicate_on_seen_pair' if pair in base_pairs|initial_pairs else 'beyond_both_pools'
                proposals.append(dict(prediction_id='P-'+digest([h,r,t])[:20],h=h,r=r,t=t,head=entities[h]['label_zh'],head_type=entities[h]['entity_type'],
                    relation=cat['relations'][r],tail=entities[t]['label_zh'],tail_type=entities[t]['entity_type'],score=float(scores[j,t]),query_rank=pos,
                    novelty_class=kind,layer='model_inference_only',source_evidence_class='not_yet_verified',score_is_factual_probability=False))
                proposals[-1]['observed_inverse_form']=inverse_seen
                proposals[-1]['inverse_caveat']='Conservatively excluded from new-discovery count; not asserting inverse predicates are universally logically equivalent' if inverse_seen else None
                proposals[-1]['inference_basis']=dict(kind='learned normalized query/tail encoder cosine; not a logical or physical proof',
                     model=folder.name,query_relation_label=cat['registry'][cat['relations'][r]]['label_zh'],
                     head_native_context_ids=model_descriptions[h]['context_ids'] if view=='G4' else [],
                     tail_native_context_ids=model_descriptions[t]['context_ids'] if view=='G4' else [],
                     known_entity_labels_used=True,source_support_requires_separate_verification=True)
    proposals.sort(key=lambda r:(-r['score'],r['prediction_id']))
    save(RUN/'discovery/predictions.jsonl',proposals)
    save(RUN/'discovery/model_selection.json',dict(view=view,prototype=proto,folder=folder.name,seed=SEEDS[0],mean_validation_link_MRR=mean,
        all_options=[dict(mean_validation=x[0],view=x[1],prototype=x[2]) for x in options],checkpoint_sha256=file_sha(folder/'best.pt')))
    # Independent source retrieval. It is never fed back to the prediction model.
    forms=defaultdict(set)
    by_label={(e['entity_type'],I.norm(e['label_zh'])):j for j,e in enumerate(entities)}
    for population in [d['graph']['source_records'],d['normalized']]:
        for rec in population:
            for side in ['head','tail']:
                k=(rec[side+'_type'],I.norm(rec[side+'_canonical_zh']))
                if k in by_label:forms[by_label[k]].add(I.norm(rec[side+'_surface']))
    pages=[p for p in d['pages'].values() if p['doc_id']=='MP022']
    matches=defaultdict(list)
    for e,fs in forms.items():
        for page in pages:
            for uid,unit in I.native_units(page).items():
                flat=I.norm(unit['text'])
                if any(len(f)>=3 and f in flat for f in fs):
                    matches[e].append(dict(unit,doc_id='MP022',page=page['pdf_page_number'],unit_id=uid))
    enriched=[]
    for p in proposals:
        heads=matches.get(p['h'],[]);tails=matches.get(p['t'],[])
        common_pages=sorted({u['page'] for u in heads}&{u['page'] for u in tails})
        if common_pages:
            page=common_pages[0]
            units={u['unit_id']:u for u in heads+tails if u['page']==page}
            enriched.append(dict(prediction=p,page=page,units=list(units.values()),same_native_unit=bool({u['unit_id'] for u in heads}&{u['unit_id'] for u in tails})))
    selected=[];seen=set();counts=Counter()
    for row in sorted(enriched,key=lambda r:(not r['same_native_unit'],-r['prediction']['score'],r['prediction']['prediction_id'])):
        kind=row['prediction']['novelty_class']
        if counts[kind]>=4:continue
        pair=(row['prediction']['h'],row['prediction']['r'],row['prediction']['t'])
        if pair in seen:continue
        selected.append(row);seen.add(pair);counts[kind]+=1
    # High-scoring unverified predictions, without pretending evidence exists.
    used={r['prediction']['prediction_id'] for r in selected}
    for p in proposals:
        if p['novelty_class'] not in ['beyond_both_pools','new_predicate_on_seen_pair'] or p['prediction_id'] in used:continue
        if len([r for r in selected if not r.get('units')])>=4:break
        selected.append(dict(prediction=p,page=None,units=[],same_native_unit=False));used.add(p['prediction_id'])
    # Additional low-score-agnostic source controls to reach a bounded set, never labels.
    for row in enriched:
        if len(selected)>=24:break
        if row['prediction']['prediction_id'] in used:continue
        selected.append(row);used.add(row['prediction']['prediction_id'])
    positive_seen={i for row in read(RUN/'data/train_base.jsonl') for i in [row['triple'][0],row['triple'][2]]}
    positive_seen.update(i for row in read(RUN/'data/training_candidate_edges.jsonl') if row['legal'] and row['weight']>0 for i in [row['triple'][0],row['triple'][2]])
    from refine_safety import shingles
    training_shingles=set()
    for unit in read(RUN/'data/training_safe_context_units.jsonl'):training_shingles.update(shingles(unit['text']))
    packets=[];mapping=[]
    for i,row in enumerate(selected,1):
        p=row['prediction'];packet=dict(review_id=f'R{i:02d}',head=p['head'],head_type=p['head_type'],relation=p['relation'],tail=p['tail'],tail_type=p['tail_type'],
             document='MP022',source_page=row['page'],source_units=row['units'],
             source_context=' '.join(next(x['page_text'] for x in pages if x['pdf_page_number']==row['page']).split()) if row['page'] is not None else None,
             review_contract='AI source support and full scope/phase/role; no cooccurrence=>entailment; use U if no source. Do not modify predicted relation.')
        if row['page'] is not None:
            source_page=next(x for x in pages if x['pdf_page_number']==row['page'])
            packet['source_metadata']={k:source_page.get(k) for k in ['title','pump_type','service','applicability_scope','source_family_id','document_sha256','page_text_sha256']}
            packet['source_tables']=source_page.get('tables',[])
        overlaps=[dict(unit_id=u['unit_id'],shared_20grams=len(shingles(u['text'])&training_shingles)) for u in row['units'] if shingles(u['text'])&training_shingles]
        independence=dict(document_withheld=True,both_endpoints_observed_in_positive_training=p['h'] in positive_seen and p['t'] in positive_seen,
             possible_training_text_duplicates=overlaps,
             strict_independent_evidence_eligible=bool(row['units']) and not overlaps and p['h'] in positive_seen and p['t'] in positive_seen,
             caveat='Conservative text overlap against all allowed safe units, including units not selected by a particular model; known entity labels are transductive side information')
        packets.append(packet);mapping.append(dict(review_id=packet['review_id'],prediction=p,retrieval_same_unit=row['same_native_unit'],independence=independence))
    save(RUN/'discovery/review_packets.jsonl',packets);save(RUN/'discovery/review_private_mapping.jsonl',mapping)
    save(RUN/'discovery/summary.json',dict(queries=len(keys),predictions=len(proposals),novelty_counts=dict(Counter(r['novelty_class'] for r in proposals)),
        independent_source_retrieval_hits=len(enriched),review_packets=len(packets),seconds=time.perf_counter()-start,
        independent_document='MP022',all_predictions_in_inference_layer=True,no_graph_publication=True,
        score_threshold=None,warning='Top3 typed proposals are NOT accepted facts or an accuracy estimate'))
    print('Discovery complete',len(proposals),'packets',len(packets),flush=True)


if __name__=='__main__':main()
