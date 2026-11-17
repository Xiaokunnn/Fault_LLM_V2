"""Schema-correct diagnostic slots, source leads and document requisitions.

This is not a completeness annotation or an extraction/validation rerun.  Old
automatic decisions are read as features, never converted into factual Gold.
"""
from common_local import *

ROLES={
 'cause':dict(orientation='incoming',relations=['causes']),
 'inspection':dict(orientation='outgoing',relations=['diagnosed_by','inspected_by']),
 'remedy':dict(orientation='outgoing',relations=['mitigated_by','prevented_by']),
 'component':dict(orientation='outgoing',relations=['occurs_at']),
}
DESCRIPTIONS={
 '1_existing_automatic_support':'已有候选及旧自动证据/语义契约可用，主图未表达；不是新发现或事实确认',
 '2_conditional_pattern':'有三前提局部关系类比；局部条件与对象适用性尚未证实',
 '3_existing_partial_or_unverified':'已有主题原文或候选线索，但缺失关系的完整支持尚未建立',
 '5_scope_not_established':'仅找到其他声明设备类别的同名候选；可迁移性未知，不当作确定冲突',
 'U_not_located_by_bounded_search':'有限别名/原文检索未定位；不能据此认定15份文档未覆盖',
}

def main():
    if (OUT/'gaps/complete.json').exists():print('REUSE gaps');return
    d,cat,entities,ei,claims,src,uf=load_domain()
    def root(typ,label):return uf.find('L|'+typ+'|'+I.norm(label))
    roots=[root(e['entity_type'],e['label_zh']) for e in entities]
    old={k:x for x in d['audit'] for k in I.record_ids(x)}
    def audit(x):return next((old[k] for k in I.record_ids(x) if k in old),x)
    candidate=defaultdict(list);subjects=defaultdict(list);base=defaultdict(list);ownsrc=defaultdict(list)
    for x in d['normalized']:
        for side in ['head','tail']:
            key=root(x[side+'_type'],x[side+'_canonical_zh'])
            subjects[key].append((side,x))
            candidate[key,'outgoing' if side=='head' else 'incoming',x['relation']].append(x)
    for cid,c in claims.items():
        h,t=ei[c['head_entity_id']],ei[c['tail_entity_id']]
        base[h,'outgoing',c['relation']].append(cid);base[t,'incoming',c['relation']].append(cid)
        for a in [h,t]:ownsrc[a].extend(src[cid])
    predicted=read(OUT/'POTENTIAL_RELATIONS.jsonl');inferred=defaultdict(list)
    for x in predicted:
        if x['primary_category']!='B':continue
        h,r,t=x['triple_indices'];inferred[h,'outgoing',x['relation']].append(x['relation_id']);inferred[t,'incoming',x['relation']].append(x['relation_id'])
    pages={k:I.norm(p['page_text']) for k,p in d['pages'].items()};ledgers=[];gaps=[];search_ledger=[]
    for h,e in enumerate(entities):
        if e['entity_type'] not in ['FaultMode','Symptom']:continue
        sr=ownsrc[h];scope={x['pump_type'] for x in sr if x.get('pump_type')};docs=sorted({x['doc_id'] for x in sr});root_h=roots[h]
        related=subjects[root_h]
        variants={x[side+'_surface'] for side,x in related if x[side+'_surface']}
        for x in sr:
            for side in ['head','tail']:
                if x.get('expanded_'+side+'_entity_id')==e['entity_id'] and x.get(side+'_surface'):variants.add(x[side+'_surface'])
        # Exact source-language phrase search, retaining only bounded informative
        # terms. This is a retrieval lead, never an entailment judgment.
        terms=sorted({I.norm(v) for v in variants if 4<=len(I.norm(v))<=160})
        hits=[]
        for (doc,page),text in pages.items():
            matches=[v for v in terms if v in text]
            if matches:hits.append(dict(doc_id=doc,pdf_page_number=page,matched_terms=matches[:3],page_text_sha256=d['pages'][doc,page]['page_text_sha256']))
        search_ledger.append(dict(entity_id=e['entity_id'],entity_type=e['entity_type'],label_zh=e['label_zh'],method='exact finite source-surface substrings; no semantic judgment',searched_pages=len(pages),terms=terms,hit_pages=hits))
        for role,rd in ROLES.items():
            rels=[]
            for r in rd['relations']:
                rule=cat['registry'][r];key='domain' if rd['orientation']=='outgoing' else 'range'
                if e['entity_type'] in rule[key]:rels.append(r)
            if not rels:continue
            existing=sorted({cid for r in rels for cid in base[h,rd['orientation'],r]})
            if existing:continue
            cc={x['triple_id']:x for r in rels for x in candidate[root_h,rd['orientation'],r]}
            compatible=[];other_scope=[];qualified=[]
            for x in cc.values():
                a=audit(x);ok=x.get('pump_type') in scope
                (compatible if ok else other_scope).append(x)
                if ok and a.get('relation_type_valid') and a.get('evidence_validation',{}).get('valid') and a.get('relation_entailment_validation',{}).get('status')=='entailed':qualified.append(x)
            patterns=sorted({v for r in rels for v in inferred[h,rd['orientation'],r]})
            if qualified:category='1_existing_automatic_support'
            elif patterns:category='2_conditional_pattern'
            elif compatible:category='3_existing_partial_or_unverified'
            elif other_scope:category='5_scope_not_established'
            elif hits:category='3_existing_partial_or_unverified'
            else:category='U_not_located_by_bounded_search'
            gid='KGAP-'+digest([e['entity_id'],role])[:18]
            row=dict(gap_id=gid,entity_id=e['entity_id'],topic=e['label_zh'],entity_type=e['entity_type'],declared_pump_types='|'.join(sorted(scope)),existing_topic_documents='|'.join(docs),missing_diagnostic_slot=role,orientation=rd['orientation'],allowed_relations='|'.join(rels),gap_class=category,class_description=DESCRIPTIONS[category],same_scope_initial_records=len(compatible),other_scope_initial_records=len(other_scope),old_contract_qualified_same_scope=len(qualified),conditional_pattern_count=len(patterns),source_surface_hit_pages=len(hits),source_surface_hit_documents='|'.join(sorted({x['doc_id'] for x in hits})),document_absence_confirmed=False,needs_new_document='not_proven; check source leads or targeted companion manual first',scope_conflict='other declared class only; compatibility unresolved' if other_scope and not compatible else 'not established',ledger_file='gaps/gap_sources.jsonl')
            gaps.append(row)
            recordrows=[]
            for x in list(qualified)+[x for x in cc.values() if x not in qualified]:
                a=audit(x)
                recordrows.append(dict(record_id=x['triple_id'],source=I.source_pointer(x),same_declared_scope=x.get('pump_type') in scope,automatic_status=a.get('decision'),old_type_valid=a.get('relation_type_valid'),old_evidence_valid=a.get('evidence_validation',{}).get('valid'),old_entailment_status=a.get('relation_entailment_validation',{}).get('status'),rejection_reasons=a.get('rejection_reasons',[])))
            ledgers.append(dict(**row,source_anchor_assertions=[I.source_pointer(x) for x in sr],related_existing_claims=sorted({cid for rr in cat['relations'] for orient in ['incoming','outgoing'] for cid in base[h,orient,rr]}),initial_candidate_leads=recordrows,pattern_relation_ids=patterns,topic_page_hits=hits,semantic_gap_verified=False))
    csvsave('KNOWLEDGE_GAPS.csv',gaps);save(OUT/'gaps/gap_sources.jsonl',ledgers);save(OUT/'gaps/source_searches.jsonl',search_ledger)
    # Real, explicit references to additional information, not low page/edge
    # counts, justify these document requests. Save exact spans and hashes.
    requests=[
        dict(priority='P1',request_id='DOCREQ-NSL-LIMITS',doc='MP005',page=13,needle='Observe the information on minimum flow rates',topic_terms=['流量','汽蚀','过热','机械密封','轴承'],kind='DESMI NSL具体型号/叶轮配置的产品数据表、性能曲线与允许运行包络',scope='NSL monobloc/spacer centrifugal pump; fluid, impeller diameter and speed must match',need='把最小/最大流量、温压运行限值与汽蚀/过热风险绑定；当前源文明确把数值引用到产品资料',status='explicit_reference_to_product_literature; whole-corpus numerical absence not established'),
        dict(priority='P1',request_id='DOCREQ-GR-REPAIR',doc='MP017',page=18,needle='Maintenance And Repair Manual',topic_terms=['噪','振动','堵','流量','泄漏'],kind='与OM-04760对应具体泵型号的Gorman-Rupp Maintenance and Repair Manual及故障排查表',scope='Gorman-Rupp self-priming centrifugal pump; recorded model/serial number needed',need='将异常噪声/过振动与原因及排查、维修步骤关联；已有运行手册明确指向配套维修手册',status='explicit_companion_manual_reference; generic equivalent fault tables already exist elsewhere'),
        dict(priority='P2',request_id='DOCREQ-NDT-APPLICATION',doc='MP001',page=93,needle='Liquid Dye Penetrant',topic_terms=['裂纹','裂','不连续','缺陷'],kind='对应泵轴/泵壳材料的无损检测工艺和验收规范（含表面/近表面边界）',scope='actual pump component material and test condition, not all rotating machinery',need='对液体渗透与磁粉检测迁移补齐材料、缺陷深度与可检性约束；已有ABS材料不应再泛化复制',status='conditional need: current guide already contains limitations; first bind existing p93-94 source'),
    ]
    saved=[]
    for q in requests:
        p=d['pages'][q['doc'],q['page']];text=p['page_text'];idx=text.lower().find(q['needle'].lower());assert idx>=0,(q['request_id'],q['needle'])
        a=max(0,idx-180);b=min(len(text),idx+650)
        related=[x['gap_id'] for x in gaps if q['doc'] in x['existing_topic_documents'].split('|') and any(t in x['topic'] for t in q['topic_terms'])]
        saved.append(dict(**q,physical_page=q['page'],page_text_sha256=p['page_text_sha256'],document_sha256=p['document_sha256'],exact_context=text[a:b],context_start=a,context_end=b,related_gap_ids=related,not_a_proven_global_document_absence=True,no_download_performed=True))
    save(OUT/'gaps/document_requests.jsonl',saved)
    summary=dict(entities_scanned=len(search_ledger),diagnostic_slot_opportunities=len(gaps),unit='entity × schema-applicable missing diagnostic role; not distinct missing true facts',gap_classes=dict(Counter(x['gap_class'] for x in gaps)),missing_roles=dict(Counter(x['missing_diagnostic_slot'] for x in gaps)),confirmed_document_absences=0,qualified_old_candidate_slots=sum(x['old_contract_qualified_same_scope']>0 for x in gaps),pattern_slots=sum(x['conditional_pattern_count']>0 for x in gaps),not_a_recall_denominator=True,source_AI_Gold=False,document_requests=len(saved),domain_revision=I.REV)
    save(OUT/'gaps/complete.json',summary);save(OUT/'gaps/input_hashes.json',d['inputs'].hashes);print(summary,flush=True)


if __name__=='__main__':main()
