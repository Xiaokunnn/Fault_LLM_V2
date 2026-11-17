"""Additional source limits and validation-copy risk, not new method labels."""
from common_local import *
from transport_cpu import CPUIndex


def main():
    if (OUT/'support_limits/complete.json').exists():print('REUSE support limits');return
    d,cat,entities,ei,claims,src,uf=load_domain();index=CPUIndex()
    contexts={}
    for edge in index.edges:
        contexts[edge['edge_id']]=src.get(edge['edge_id'],[]) if edge['is_base'] else sources(edge,index.registry)
    # Evaluation-only risk screen: the answer is used here solely to diagnose
    # contamination, never for ranking or building candidate contexts.
    by_answer=defaultdict(list)
    for v in index.views:by_answer[v['relation'],v['neighbor']].append(v)
    targets=read(STUDY/'data/validation_targets.jsonl');selected=np.load(OUT/'mechanism/T0_k16_selection.npz');keys=[tuple(k) for k in read(OUT/'mechanism/query_keys.json')];ki={k:j for j,k in enumerate(keys)}
    risks=[]
    for q in targets:
        hh,r,tt=q['triple'];refs=src[q['id']];families={s.get('source_family_id') for s in refs if s.get('source_family_id')};quotes={I.norm(s.get('evidence_text')) for s in refs if len(I.norm(s.get('evidence_text')))>=12}
        for task,h,rel,t in [('tail',hh,r,tt),('head',tt,r+15,hh)]:
            for v in by_answer[rel,t]:
                cos=float(index.vec['entities'][h]@index.vec['entities'][v['anchor']]);edge=index.edges[v['edge_index']];ss=contexts[edge['edge_id']];same_family=bool(families&{s.get('source_family_id') for s in ss});exact=bool(quotes&{I.norm(s.get('evidence_text')) for s in ss})
                if cos<.9 or not (same_family or exact):continue
                risks.append(dict(validation_claim_id=q['id'],task=task,head_index=h,relation_index=rel,answer_index=t,training_edge_id=edge['edge_id'],oriented_view=v['view_id'],anchor_cosine=cos,same_source_family=same_family,exact_long_quote_overlap=exact,selected_T0_k16=v['view_id'] in selected['ids'][ki[h,rel]],target_sources=[I.source_pointer(x) for x in refs],training_sources=[I.source_pointer(x) for x in ss],assessment='proxy near-duplicate/copy risk, not proven semantic equivalence or revised Gold',used_only_after_predictions=True))
    save(OUT/'support_limits/validation_copy_risks.jsonl',risks)
    flagged={(x['validation_claim_id'],x['task']) for x in risks};selected_risk={(x['validation_claim_id'],x['task']) for x in risks if x['selected_T0_k16']};metrics=[]
    for method in ['text_only','T0','T1','T2','T3','T4','T5']:
        for seed in SEEDS:
            rr=read(OUT/('diagnostics' if method=='text_only' else 'mechanism')/(f'text_only_s{seed}_ranks.jsonl' if method=='text_only' else f'{method}_k16_s{seed}_ranks.jsonl'))
            for subset in ['copy_risk_flagged','no_flag_found']:
                take=[x for x in rr if (((x['id'],x['task']) in flagged)==(subset=='copy_risk_flagged'))]
                if take:metrics.append(dict(method=method,seed=seed,subset=subset,n=len(take),MRR=float(np.mean([1/x['rank'] for x in take])),Hits1=float(np.mean([x['rank']<=1 for x in take])),Hits10=float(np.mean([x['rank']<=10 for x in take]))))
    csvsave('support_limits/copy_risk_seed_metrics.csv',metrics)
    # Full-graph pattern rejection ledger: retain scope-unknown cross-manual
    # opportunities rather than equating different pump_type tags with falsity.
    outgoing=defaultdict(list);groups=defaultdict(list)
    for cid,c in claims.items():
        h,t=ei[c['head_entity_id']],ei[c['tail_entity_id']];outgoing[h].append((c['relation'],t,cid));groups['out',c['relation'],t].append((h,cid));groups['in',c['relation'],h].append((t,cid))
    attempts=[]
    for shared,anchors in sorted(groups.items()):
        for (h,ch),(a,ca) in itertools.permutations(anchors,2):
            if h==a or entities[h]['entity_type']!=entities[a]['entity_type']:continue
            similarity=float(index.vec['entities'][h]@index.vec['entities'][a])
            if similarity<.85 or conflict(entities[h]['label_zh'],entities[a]['label_zh']):continue
            for r,t,cr in outgoing[a]:
                if t in [h,a,shared[2]] or cr==ca:continue
                rule=cat['registry'][r]
                if entities[h]['entity_type'] not in rule['domain'] or entities[t]['entity_type'] not in rule['range']:continue
                if any(c['head_entity_id']==entities[h]['entity_id'] and c['tail_entity_id']==entities[t]['entity_id'] and c['relation']==r for c in claims.values()):continue
                sets=[{I.norm(s.get('pump_type')) for s in src[c] if s.get('pump_type')} for c in [ch,ca,cr]]
                if set.intersection(*sets):continue
                attempts.append(dict(attempt_id='SCOPE-'+digest([h,r,t,ch,ca,cr])[:18],head=entities[h],relation=r,tail=entities[t],source_anchor=entities[a],shared_role=shared[0],shared_relation=shared[1],shared_neighbor=entities[shared[2]],premises=[dict(claim_id=c,sources=[I.source_pointer(s) for s in src[c]]) for c in [ch,ca,cr]],declared_pump_type_sets=[sorted(x) for x in sets],documents=sorted({s['doc_id'] for c in [ch,ca,cr] for s in src[c]}),reason='No common declared pump_type; actual compatibility unresolved, not a factual conflict',admitted_as_B=False,not_counted_as_new_correct_fact=True))
    save(OUT/'support_limits/scope_unresolved_pattern_attempts.jsonl',attempts)
    # Assistant source-reading notes are kept separate from deterministic labels.
    annotations=[]
    for x in read(OUT/'potential/pattern_supported_relations.jsonl'):
        head=x['head']['label_zh'];tail=x['tail']['label_zh'];docs=sorted({doc for p in x['pattern_support'] for doc in p['documents']})
        if docs==['MP015']:
            caveat='机械密封旋转部件有编号/无编号的端点可能是粒度差异；p42=M7N、p43=MD1，X与X1及组装条件不可混用。共享拆卸动作不能证明所有组装措施通用。'
            required=['mechanical_seal_variant','assembly_or_disassembly_stage','shaft_and_adjustment_table','retained_part_number']
            pages=[42,43]
        elif docs==['MP016']:
            caveat='异常噪音/异常噪声及多个倾听动词来自同一柔性叶轮泵手册的多语言重复。先核实别名与证据去重；不可把五条组合计为五个新诊断事实。'
            required=['same_flexible_impeller_equipment','alias_deduplication','same_source_family_not_independent_corroboration'];pages=[5,15,16,22,28,47]
        else:
            caveat='p93液体渗透仅限表面开口缺陷且不适用高孔隙材料；p94-95磁粉检测有材料和表面/近表面限制。共享磨损原因不能证明检测方法可无条件互换。'
            required=['surface_breaking_vs_near_surface_defect','material_applicability','test_preparation_and_offline_state'];pages=[93,94,95]
        annotations.append(dict(relation_id=x['relation_id'],assessment='conditional analogy with unresolved restrictions, not factual confirmation',source_reading_note=caveat,required_but_unverified_fields=required,source_pages=[dict(doc_id=docs[0],pdf_page_number=page,page_text_sha256=d['pages'][docs[0],page]['page_text_sha256']) for page in pages],evaluator='Codex assistant source-reading analysis; no external API, no expert Gold',changes_existing_labels=False,confirmed_new_fact=False))
    save(OUT/'support_limits/pattern_source_notes.jsonl',annotations)
    save(OUT/'support_limits/complete.json',dict(validation_only=True,copy_risk_pairs=len(risks),copy_risk_query_directions=len(flagged),selected_copy_risk_query_directions=len(selected_risk),exact_quote_overlap_directions=len({(x['validation_claim_id'],x['task']) for x in risks if x['exact_long_quote_overlap']}),no_flag_does_not_prove_leakage_free=True,scope_unresolved_pattern_attempts=len(attempts),cross_document_scope_unresolved_attempts=sum(len(x['documents'])>1 for x in attempts),pattern_source_notes=len(annotations),source_AI_not_Gold=True))
    print(read(OUT/'support_limits/complete.json'),flush=True)


if __name__=='__main__':main()
