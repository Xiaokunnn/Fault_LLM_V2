"""Add provenance/schema and explicitly unavailable truth-quality dimensions."""
from common import *


def main():
    if (OUT/'quality_dimensions/complete.json').exists():print('REUSE quality dimensions');return
    d,E,C,S=dataset();E=dict(E)
    for b in read(OUT/'counterfactual/GA_structure_ledger.jsonl'):
        E[b['head']['entity_id']]=b['head'];E[b['tail']['entity_id']]=b['tail']
    refs={r['sample_id']:r for r in read(OUT/'source_sample/reference_relations.jsonl')}
    gc=read(OUT/'counterfactual/GC_business_claims.jsonl')
    for c in gc:
        r=refs[c['claim_id'].replace('SRCREF-','')]
        for side in ['head','tail']:E.setdefault(c[side+'_entity_id'],dict(entity_id=c[side+'_entity_id'],entity_type=r[side+'_type'],label_zh=r[side+'_canonical_zh']))
    initial=(OUT/'QUALITY_METRICS.csv').read_text();save('counterfactual/primary_quality_metrics.csv',initial);rows=list(csv.DictReader(io.StringIO(initial)));extra=[]
    for view in ['G0','GA','GB','GAB','GC']:
        vc=read(OUT/'counterfactual'/f'{view}_business_claims.jsonl');ve={e:E[e] for c in vc for e in [c['head_entity_id'],c['tail_entity_id']]};save('counterfactual/'+view+'_entities.jsonl',list(ve.values()))
        if view in ['G0','GB']:vs=S
        elif view in ['GA','GAB']:
            vs=defaultdict(list)
            for x in read(OUT/'counterfactual/GA_business_sources.jsonl'):vs[x['claim_id']].append(x['source'])
        else:
            vs=defaultdict(list)
            for x in read(OUT/'counterfactual/GC_business_sources.jsonl'):vs[x['claim_id']].append(x['source'])
        sources=[s for c in vc for s in vs[c['claim_id']]];families=Counter(len({s.get('source_family_id') for s in vs[c['claim_id']] if s.get('source_family_id')}) for c in vc)
        measured={
            'claims_with_source_records':sum(bool(vs[c['claim_id']]) for c in vc),
            'business_schema_legal_claims':sum(ve[c['head_entity_id']]['entity_type'] in d['schema']['relation_registry'][c['relation']]['domain'] and ve[c['tail_entity_id']]['entity_type'] in d['schema']['relation_registry'][c['relation']]['range'] for c in vc),
            'claims_with_one_declared_source_family':families[1],
            'claims_with_multiple_declared_source_families':sum(n for k,n in families.items() if k>=2),
            'source_records_with_structured_condition_field':sum(bool(s.get('conditions_source')) for s in sources),
            'source_records_with_modality_field':sum(bool(s.get('modality')) for s in sources),
            'claims_with_multiple_declared_pump_types':sum(len({s.get('pump_type') for s in vs[c['claim_id']] if s.get('pump_type')})>1 for c in vc),
        }
        for name,value in measured.items():extra.append(dict(view=view,projection='provenance_schema_and_scope_fields',metric=name,value=value,denominator=len(vc) if name.startswith('claims') or name.startswith('business') else len(sources),unit='claim' if name.startswith('claims') or name.startswith('business') else 'source_record',evidence_level='exact_field_or_schema_count',interpretation_limit='Field presence, type contract and family label are not factual correctness, complete conditions or independent corroboration'))
        for name in ['factual_accuracy','direction_correctness_accuracy','complete_condition_binding_accuracy','true_fact_recall','true_same_equipment_conflict_rate','field_diagnosis_accuracy']:
            extra.append(dict(view=view,projection='requires_independent_semantic_reference',metric=name,value='NA',denominator='',unit='unavailable',evidence_level='not_identifiable_from_current_assets',interpretation_limit='No independent expert/field reference; do not replace this with automatic gate rate, graph density or source-AI proxy'))
    allrows=rows+extra;s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(allrows)
    # This is the final aggregation of this NEW experiment's staged metrics,
    # never a change to raw inputs, existing studies or their labels.
    (OUT/'QUALITY_METRICS.csv').write_text(s.getvalue())
    save('quality_dimensions/additional_measures.json',extra);save('quality_dimensions/complete.json',dict(primary_metrics=len(rows),additional_metrics=len(extra),total_metrics=len(allrows),unknown_semantic_metrics_marked_NA=True,condition_fields_not_semantic_accuracy=True))
    print(read(OUT/'quality_dimensions/complete.json'),flush=True)


if __name__=='__main__':main()
