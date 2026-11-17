"""Freeze 45 source units BEFORE reading or grading semantic outcomes."""
from common import *


def main():
    if (OUT/'SOURCE_SAMPLE_FREEZE.json').exists():print('REUSE frozen source sample');return
    d,E,C,S=dataset();published={(s['doc_id'],s['pdf_page_number']) for s in d['graph']['source_records']};manifest={x['doc_id']:x for x in d['manifest']}
    units=[]
    for (doc,page),p in sorted(d['pages'].items()):
        blocks=sorted(p.get('text_blocks',[]),key=lambda b:b.get('reading_order',0))
        for j,b in enumerate(blocks):
            chosen=blocks[max(0,j-1):j+6];text='\n'.join(z['text'] for z in chosen)
            if len(text)<80 or len(text)>2400 or not DIAGNOSTIC.search(text):continue
            if re.search(r'\.{3,}',text):continue  # contents/index leader lines
            body='\n'.join(z['text'] for z in chosen if not re.search(r'ABS (?:GUIDE|GUIDANCE|RULES)|https?://|www\.|©|^\s*[\d•. /–—-]+\s*$',z['text'],re.I))
            if len(body)<100 or not DIAGNOSTIC.search(body):continue
            # Avoid an arbitrary off-topic paragraph in the 991-page vessel
            # rulebook. This is a lexical sampling boundary, not a truth label.
            if doc=='MP003' and not TOPIC.search(text):continue
            units.append(dict(unit_id=doc+f':p{page:04d}:blockwindow:{j:04d}',doc_id=doc,pdf_page_number=page,native_kind='block_window',native_ids=[z['block_id'] for z in chosen],unit_text=text,native_fragments=chosen,column_names=[],column_roles=[],page_has_published_record=(doc,page) in published,condition_cue=bool(CONDITION.search(text)),source_family_id=p['source_family_id'],pump_type=p['pump_type'],applicability_scope=p['applicability_scope'],page_text_sha256=p['page_text_sha256'],document_sha256=p['document_sha256']))
        for t in p.get('tables',[]):
            groups=defaultdict(list)
            for row in t['rows']:
                for cell in row['cells']:groups[cell.get('row_group_id',row['row_id'])].append(cell)
            for gid,cells in sorted(groups.items()):
                text='\n--- CELL ---\n'.join(c['text'] for c in cells)
                if not 40<=len(text)<=3200 or not (DIAGNOSTIC.search(text) or TOPIC.search(text)):continue
                meaningful=re.findall(r'[A-Za-zÀ-ž]{3,}|[\u4e00-\u9fff]+',' '.join(c['text'] for c in cells))
                if len(meaningful)<5:continue  # repeated empty/header cells
                units.append(dict(unit_id=gid+':native_group',doc_id=doc,pdf_page_number=page,native_kind='table_row_group',native_ids=[c['cell_id'] for c in cells],unit_text=text,native_fragments=cells,column_names=t.get('column_names',[]),column_roles=t.get('column_roles',[]),page_has_published_record=(doc,page) in published,condition_cue=bool(CONDITION.search(text)),source_family_id=p['source_family_id'],pump_type=p['pump_type'],applicability_scope=p['applicability_scope'],page_text_sha256=p['page_text_sha256'],document_sha256=p['document_sha256']))
    selected=[];used_pages=set();frame=Counter();rank=lambda doc,st,u:digest(['rp1-root-cause-20261117',doc,st,u['unit_id'],u['unit_text']])
    for doc in sorted(I.BUILD):
        own=[u for u in units if u['doc_id']==doc]
        for stratum in ['table_diagnostic','unpublished_page_prose','conditional_prose']:
            eligible=[u for u in own if (doc,u['pdf_page_number']) not in used_pages]
            if stratum=='table_diagnostic':pool=[u for u in eligible if u['native_kind']=='table_row_group']
            elif stratum=='unpublished_page_prose':pool=[u for u in eligible if u['native_kind']=='block_window' and not u['page_has_published_record']]
            else:pool=[u for u in eligible if u['native_kind']=='block_window' and u['condition_cue']]
            fallback=False
            if not pool:pool=eligible;fallback=True
            assert pool,doc
            u=min(pool,key=lambda u:rank(doc,stratum,u));used_pages.add((doc,u['pdf_page_number']));selected.append(dict(u,sample_id=f'SU{len(selected)+1:03d}',requested_stratum=stratum,fallback=fallback,selection_hash=rank(doc,stratum,u)))
            frame[doc,stratum]=len(pool)
    save('source_sample/selected_units.jsonl',selected)
    save('SOURCE_SAMPLE_FREEZE.json',dict(date='2026-11-17',domain_object=I.REV,seed='rp1-root-cause-20261117',sampling_rule='3 units per document: native table group, unpublished-page prose, conditional prose; distinct physical pages; hash-minimum before judgments; fallback explicitly retained',semantic_judgments_used=False,existing_candidates_used_to_select=False,published_page_indicator_only=True,source_unit_count=len(selected),documents=sorted(I.BUILD),actual_native_kinds=dict(Counter(u['native_kind'] for u in selected)),requested_strata=dict(Counter(u['requested_stratum'] for u in selected)),unpublished_pages=sum(not u['page_has_published_record'] for u in selected),fallback_count=sum(u['fallback'] for u in selected),eligible_units=len(units),sampling_frames=[dict(doc_id=k[0],stratum=k[1],eligible=n) for k,n in sorted(frame.items())],sample_sha256=sha(OUT/'source_sample/selected_units.jsonl'),code_sha256=sha(Path(__file__)),representative_population_not_statistically_established=True))
    save('RUN_PROTOCOL.md','''# 一次性知识图谱成因归因实验：执行前约束

2026-11-17。仅使用锁定对象833c8040058055434c7f6a9595ec524c3935755f的expanded1456、8007原始导出行、8003规范化候选及15份构建手册。CPU统计与反事实视图，不重抽、不重训、不重跑旧发布门控；外部API调用0。

候选链路按显式原ID、legacy ID、真实来源及规范化签名连接；来源相同或名称相似不自动证明同一事实，重建/新增独立验证的图谱记录另列。8007减1400不解释为知识损失。

GA只暂纳未发布且类型合法、保存语义判断entailed、旧定位契约通过、原生地址可复查的候选；有条件/否定/时序线索但缺结构条件时暂不纳入。字段存在也不保证条件正确，所有GA边保持自动代理身份与源文，不进入正式图谱。

GB不合并实体、不增加业务Claim，只建立可追溯的词形/既有别名/编号粒度概念联系；同义身份、共享类别、来源限定出现与业务事实分层。不能把概念边加入Claim数量或把异构图连通改善解释为正确关系增加。GAB组合两种诊断变更，GC仅是固定源文样本的代理参考子集。

先固定45个诊断单元（15文档×3层），跨页面并包含未发布页面；再进行助手源文阅读归因与参考问题冻结，最后计算各视图。AI阅读不是人工Gold，不根据后续视图指标调整样本或问题。未决保留U；E仅限本单元明确不完整/引用其他资料，不由全语料短语搜索无命中推断缺文档。

只报告可计算量与证据等级，不能给文档/抽取/建模三因素虚构可加的贡献百分比。不使用旧224测试答案选参或改补全模型。完成后将新增代码与文本结果提交到origin/main。
''')
    save('source_sample/input_hashes.json',d['inputs'].hashes)
    print(read(OUT/'SOURCE_SAMPLE_FREEZE.json'),flush=True)


if __name__=='__main__':main()
