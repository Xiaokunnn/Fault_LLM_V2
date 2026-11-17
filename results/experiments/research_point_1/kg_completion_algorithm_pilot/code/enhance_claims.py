"""Post-freeze, audit-only existing-Claim overlays; never writes a graph."""
from collections import Counter,defaultdict
import numpy as np
import torch
from common import RUN,read,save
from train_simkgc import setup,callback


def main():
    assert (RUN/'evaluation/complete.json').exists()
    selection=read(RUN/'discovery/model_selection.json');cat=read(RUN/'data/catalogue.json')
    rows=read(RUN/'data/base_split.jsonl')
    source=defaultdict(list)
    for r in read(RUN/'audit_only/base_source_records.jsonl'):source[r['expanded_claim_id']].append(r)
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2)
    model,tok,descriptions,_=setup(selection['view'],cat);model=model.to(device)
    model.load_state_dict(torch.load(RUN/'models'/selection['folder']/'best.pt',map_location=device,weights_only=True));model.eval()
    predict=callback(model,tok,descriptions,cat,[dict(triple=r['triple']) for r in rows],device)
    overlays=[]
    for q in rows:
        h,r,t=q['triple'];scores=np.asarray(predict(h,r,t,'relation'));order=np.argsort(-scores,kind='stable');src=source[q['claim_id']]
        evidence=[]
        for x in src:
            evidence.append(dict(assertion_id=x['expanded_assertion_id'],doc_id=x['doc_id'],physical_page=x['pdf_page_number'],
                source_family=x.get('source_family_id'),evidence_level=x.get('evidence_level'),
                evidence_text=x.get('evidence_text'),unit_ids=x.get('evidence_unit_ids',[]),evidence_start=x.get('evidence_start'),evidence_end=x.get('evidence_end'),
                applicability_scope=x.get('applicability_scope'),pump_type=x.get('pump_type'),service=x.get('service'),
                recorded_conditions={k:v for k,v in x.items() if any(w in k.lower() for w in ['condition','polarity','temporal','modality'])},
                document_sha256=x.get('document_sha256'),page_text_sha256=x.get('page_text_sha256'),
                original_quality_fields={k:x.get(k) for k in ['validation_status','final_confidence','review_reasons','rejection_reasons']}))
        overlays.append(dict(claim_id=q['claim_id'],head_entity_id=cat['entities'][h]['entity_id'],tail_entity_id=cat['entities'][t]['entity_id'],
            relation=cat['relations'][r],fold=q['fold'],model=selection['folder'],checkpoint_sha256=selection['checkpoint_sha256'],
            declared_relation_score=float(scores[r]),declared_relation_rank=int(np.where(order==r)[0][0])+1,
            top_alternative_relations=[dict(relation=cat['relations'][int(j)],cosine=float(scores[j])) for j in order[:3]],
            source_families=sorted({x['source_family'] for x in evidence if x['source_family']}),evidence=evidence,
            uncertainty_flags=['model_scores_are_not_calibrated_fact_probability','conditions_copied_not_inferred_or_completed',
                'training_claim_interpolation' if q['fold']=='train' else 'postfreeze_audit_not_new_model_selection'],
            updates_original_graph=False,proposal_layer='existing_claim_audit_overlay'))
    save(RUN/'enhancement/claim_overlays.jsonl',overlays)
    save(RUN/'enhancement/summary.json',dict(claims=len(overlays),assertion_links=sum(len(x['evidence']) for x in overlays),
        original_evidence_coverage=sum(bool(x['evidence']) for x in overlays),model=selection,
        declared_relation_top1=sum(x['declared_relation_rank']==1 for x in overlays),
        folds=dict(Counter(x['fold'] for x in overlays)),condition_binding_learned=False,
        interpretation='E3 audit overlay: provenance/scope organization and model consistency only. No revalidation, truth probability, new condition inference or graph promotion.'))
    print('Saved',len(overlays),'existing-Claim overlays')


if __name__=='__main__':main()
