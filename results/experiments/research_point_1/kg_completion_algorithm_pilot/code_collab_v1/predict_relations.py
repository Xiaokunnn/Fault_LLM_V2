"""Full proposed-model proposals with contributor and held-source packets."""
from collections import Counter,defaultdict
import numpy as np
import torch
from collab_io import *
from fit_collab import load


def main():
    assert DATASET=='cold'
    assert (STUDY/'cold/evaluation/complete.json').exists() and (STUDY/'structured/evaluation/complete.json').exists()
    seed=SEEDS[0];folder=RUN/'models'/f'collab_full_s{seed}'
    model,data,graph=load(seed,'full',folder/'best.pt');model.eval();cat=read(RUN/'data/catalogue.json');n=cat['nbase'];R=graph.R
    # The proposed model/first seed is predeclared; never choose by best test score.
    d=I.load();aliases=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for rec in pop:
            for side in ['head','tail']:aliases.join('L|'+rec[side+'_type']+'|'+I.norm(rec[side+'_canonical_zh']),'S|'+I.norm(rec[side+'_surface']))
    ea=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities']]
    entindex={e['entity_id']:e['index'] for e in cat['entities'][:n]}
    known={(ea[entindex[c['head_entity_id']]],c['relation'],ea[entindex[c['tail_entity_id']]]) for c in d['graph']['claims']}
    initial={(aliases.find('L|'+r['head_type']+'|'+I.norm(r['head_canonical_zh'])),r['relation'],aliases.find('L|'+r['tail_type']+'|'+I.norm(r['tail_canonical_zh']))) for pop in [d['raw'],d['audit'],d['normalized']] for r in pop}
    keys=[(h,r) for h,e in enumerate(cat['entities'][:n]) for r,rel in enumerate(cat['relations']) if e['entity_type'] in cat['registry'][rel]['domain']]
    proposals=[]
    with torch.no_grad():
        for off in range(0,len(keys),128):
            batch=keys[off:off+128];h=[x[0] for x in batch];r=torch.tensor([x[1] for x in batch],device='cuda');pack=graph.pack(h)
            original=data['queries'][torch.tensor(h,device='cuda'),r];enhanced,details=model(original,r,data['entities'],pack,True)
            score=(enhanced@data['entities'][:n].T).cpu().numpy();baseline=(original@data['entities'][:n].T).cpu().numpy()
            for j,(head,rel) in enumerate(batch):
                allowed=[e['index'] for e in cat['entities'][:n] if e['entity_type'] in cat['registry'][cat['relations'][rel]]['range'] and e['index']!=head]
                tops=sorted(allowed,key=lambda t:(-score[j,t],t))[:3]
                contexts=[dict(edge_id=e['edge_id'],neighbor=t,edge_relation=erel,pages=e['pages'],gate=float(details['gates'][j,k]),weight=float(details['weights'][j,k]),base=e['is_base']) for k,(t,erel,e) in enumerate(graph.entries(head))]
                for rank,t in enumerate(tops,1):
                    fact=(ea[head],cat['relations'][rel],ea[t]);inv={'contains':'located_in','located_in':'contains','manifests_as':'indicates','indicates':'manifests_as'}.get(cat['relations'][rel]);reverse=(ea[t],inv,ea[head]) if inv else None
                    novelty='base_known' if fact in known or reverse in known else 'initial_pool_known' if fact in initial or reverse in initial else 'beyond_both'
                    proposals.append(dict(prediction_id='P-'+digest([head,rel,t])[:20],h=head,r=rel,t=t,head=cat['entities'][head]['label_zh'],relation=cat['relations'][rel],tail=cat['entities'][t]['label_zh'],
                        score=float(score[j,t]),rank=rank,baseline_score=float(baseline[j,t]),score_change=float(score[j,t]-baseline[j,t]),novelty=novelty,
                        contexts=contexts,null=float(details['null'][j]),residual_norm=float(details['residual_norm'][j]),
                        inference_layer=True,calibrated_fact_probability=False))
    proposals.sort(key=lambda p:(-p['score'],p['prediction_id']));save(STUDY/'discovery/predictions.jsonl',proposals)
    forms=defaultdict(set);bylabel={(e['entity_type'],I.norm(e['label_zh'])):e['index'] for e in cat['entities'][:n]}
    for pop in [d['normalized'],d['graph']['source_records']]:
        for rec in pop:
            for side in ['head','tail']:
                key=(rec[side+'_type'],I.norm(rec[side+'_canonical_zh']))
                if key in bylabel:forms[bylabel[key]].add(I.norm(rec[side+'_surface']))
    pages=[p for p in d['pages'].values() if p['doc_id']=='MP022'];matches=defaultdict(dict)
    for entity,ff in forms.items():
        for page in pages:
            units=[dict(u,unit_id=uid) for uid,u in I.native_units(page).items() if any(len(f)>=3 and f in I.norm(u['text']) for f in ff)]
            if units:matches[entity][page['pdf_page_number']]=units
    selected=[]
    for pred in sorted(proposals,key=lambda p:(p['novelty']!='beyond_both',-abs(p['score_change']),-p['score'],p['prediction_id'])):
        common=sorted(set(matches[pred['h']])&set(matches[pred['t']]))
        if common and len(selected)<12:
            page=common[0];source=next(x for x in pages if x['pdf_page_number']==page)
            selected.append(dict(review_id=f'N{len(selected)+1:02d}',prediction=pred,source_document='MP022',physical_page=page,
                units=list({u['unit_id']:u for u in matches[pred['h']][page]+matches[pred['t']][page]}.values()),
                full_page=source['page_text'],applicability_scope=source.get('applicability_scope'),
                document_held_out=True,independence_caveat='Entity names are shared closed catalogue; literal overlaps still require checking; no human/independent-model Gold'))
    save(STUDY/'discovery/source_packets.jsonl',selected)
    save(STUDY/'discovery/summary.json',dict(predictions=len(proposals),novelty=dict(Counter(p['novelty'] for p in proposals)),
        changed_score_over_1e_6=sum(abs(p['score_change'])>1e-6 for p in proposals),packets=len(selected),model=folder.name,selection='proposed full first fixed seed, not test-selected',
        checkpoint_sha256=file_sha(folder/'best.pt'),graph_published=False))
    print('Predicted',len(proposals),'packets',len(selected),flush=True)


if __name__=='__main__':main()
