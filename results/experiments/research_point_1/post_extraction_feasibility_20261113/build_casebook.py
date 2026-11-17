#!/usr/bin/env python3
"""Render a bounded, analyst-selected casebook. No new truth or repair labels."""
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from research_point_1_graph_evidence.stage03_schema_validation.evidence_span_validator import locate_surface


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def witness_text(items):
    parts=[]
    for item in items:
        if 'text' in item:parts.append(item['text'])
        elif 'witnesses' in item:parts.append(witness_text(item['witnesses']))
    return ' | 原生片段分隔 | '.join(parts)


CASES=[
 dict(id='A01',title='跨家族关系级重叠正例：润滑剂过量与轴承过热',
      record_ids=['MPT-0a7c947864ba00fc6bfc','MPT-9f5573d9faacb30a6d3e','MPT-da874a4cb007069f3880'],
      explanation='ABB电机和Flowserve泵手册均有过量润滑与轴承过热的关系线索；中文“过多/过量”造成拆分。可作为关系族对齐候选，但设备范围不同，应保留各自证据。西语候选虽定位合法，原决策仍是拒绝，不能自动改成融合正例。它是1个可回查机制案例，不是3份已确认独立事实。'),
 dict(id='A02',title='跨文档但同族：过高吸上高度与低流量',
      cluster_id='K-afdd61b40218d687',explanation='两份DESMI手册形成同一规范主张族，已在expanded中聚合。SA与NSL适用范围不同，不能删除断言；这不是两个独立来源家族。'),
 dict(id='A03',title='同一文档的多语言重复：泵头O形圈/垫片更换',
      cluster_id='K-0294c095548d977f',explanation='同一MP016手册的英语、荷兰语、意大利语和瑞典语页已聚合为主张族。源语言元数据可能均为en，应以实际引文识别语言；译本不能视为独立家族。现有去重与来源族规则已经覆盖这类重复。'),
 dict(id='A04',title='相似但不能合并：轴承过早失效与轴承过热',
      record_ids=['EXP-7553c787a9008478f53d438b','MPT-4db3cce871d96a3bedaa'],
      explanation='同一“不对中”原因可对应不同后果。名称和关系相似并不意味着两个后果等价，也不是冲突。需检查新增记录的完整table source_witnesses，不能仅用短引文判断全部后果。'),
 dict(id='A05',title='安装与拆卸并存：阶段不同，不是真冲突',
      record_ids=['MPT-b0e376ff1333acff24dd','MPT-e5f5c6c6558df05e6197'],
      explanation='Fit the guard与Dismantle guard来自不同维护阶段及文档。应保留动作差异和阶段，不能因相同部件把动作合并，也不能算相同工况下相互矛盾。'),
 dict(id='A06',title='一个Claim承载七页证据，不代表七条独立事实',
      cluster_id='K-2aa5455f565a534e',explanation='橡胶密封安装前润滑的7条断言被同一Claim聚合，均来自MP022。Claim作为主张族的聚合本身并非错误；若消费程序只取裸边、丢弃装配配置和before时机，就会损失上下文。'),
 dict(id='B01',title='可在候选层关联的步骤：停机—消因—恢复',target_id='T03',
      explanation='两项原子动作和before returning字面信息已存在，是构图阶段局部步骤关联的正向可行性线索。当前没有独立、完整的重启前置边，不能把可能恢复写成已成功恢复，也不能由这1例证明通用事件图融合必要。'),
 dict(id='B02',title='型号条件未绑定：损坏衬套更换',record_ids=['MPT-b60af75fc3a32754dfb0'],
      source_anchor='Ø330/415/418/465/525',
      explanation='既有B24 AI评价为源文S、条件E。源页存在组合型号标题，候选短引文不足以独立给出范围。若构图可读取原生章节元数据，存在局部补绑定可能；仅用候选三元组不能凭空知道型号。此处不是已执行修复。'),
 dict(id='B03',title='否定语义被正向裸边遮蔽',record_ids=['MPT-0927c8970e1124c5c738'],
      explanation='既有B06 AI评价已指出Do not operate without liquid被表示为正向operates_under无液充注。禁止文字仍保留在证据中，属于关系表示/消费风险，而非原文彻底丢失。不能把一个新极性字段缺失与全图否定错误数量画等号。'),
 dict(id='B04',title='纯候选构图无法补齐的数值时序',target_id='T13',source_anchor='90°C',
      explanation='原文有90°C 12–16小时后105°C 6–8小时；已有候选涉及绕组受潮和烘干，但不含完整有序参数。若仅允许候选及其现有引文，无法恢复数值；重读完整页面发现参数是额外源文信息提取，应单列，不能算融合算法免费收益。'),
 dict(id='B05',title='反例：清液限制已经字面保留',target_id='T14',
      explanation='clear liquids applications only已在候选/引文及已发布记录保留。conditions_source为空不等于条件丢失；可查询字段不齐与语义缺失需分开。'),
 dict(id='B06',title='反例：OR已经在完整动作中，主要瓶颈是定位',target_id='T07',
      explanation='增加流量或改用小泵的OR仍在动作尾端。旧原生链拒绝引用不等于模型未生成OR，也不能把它当需要专门替代方案算法的证明。最终页级记录与相关原始候选分列，避免用ID变动断言知识缺失。'),
 dict(id='B07',title='首次启动泄漏前提：上下文仍可回查',record_ids=['MPT-f7412885a38d453e7a6d'],source_anchor='initial leakage',
      explanation='既有B36为源文S、条件E：观察泄漏是否停止的建议属于首次启动尚未跑合的少量初始泄漏。直接推广为任何泄漏都等待不成立。源文邻句仍存在，但尚未证明自动选择正确作用对象。'),
 dict(id='B08',title='表格工况组合不是独立关键词',target_id='T11',source_anchor='Extreme dirt',
      explanation='一行共同规定污物、湿度、负载、速度、温度及每日冲洗。旧候选虽保留多项字面线索，却存在单位字形/类型与引用问题，不能归为纯构图条件错。需要先分清原子关系是否已合法存在。'),
 dict(id='C01',title='潜在同义拆分：耐磨板磨损检查',
      entity_ids=['EXE-d4e670d4261a0e53ddb2032a','EXE-e64c181b374d093ed0a2d5ba','EXE-ff5329218134a3845956ced7'],
      explanation='中文仅有“的/是否”等表述差异，多语言源语均指同一检查，并共享受检部件。是明显的对齐候选；多数这类差异可能用短语规范化或词典解决，不能据此证明实体—关系联合模型必要。'),
 dict(id='C02',title='名称和邻域都相近仍不能合并：最大/最小流量',
      entity_ids=['EXE-54af26eddc9837e4996aaefc','EXE-6402c32607bceaef537aebbe'],
      explanation='名称相似度0.9375且共享2项关系邻居，但maximum与minimum规定不同边界。共同邻域不保证同义；合并后会抹去一项约束。'),
 dict(id='C03',title='高液位与高高液位：级别应保留',
      entity_ids=['EXE-7403e39465af225145bbd937','EXE-c047c210d32188a47f40f1f8'],
      explanation='同一来源页分别命名high level alarm和high-high level alarm，名称相似并共享邻居；它们可能对应不同报警阈级，不能以字面或结构相似直接合并。'),
 dict(id='C04',title='部件与层级差异：泵和电机轴承/泵和电机轴',
      entity_ids=['EXE-1daf2840b5dd5d143ea0f609','EXE-a6b7044ee27a38847769b033'],
      explanation='bearings与shaft不同，中文长公共前缀使相似度高；这不是同一部件。名称相似检索只能提议，不能给出对齐真值。'),
 dict(id='C05',title='检查润滑剂与检查已润滑：对象/前置条件不同',
      entity_ids=['EXE-1a79d5ee4a165607488e30e4','EXE-fa246b57a5ce67c14ff3648c'],
      explanation='一个检查bearing lubricant，另一个要求轴承启动前或紧接启动后已润滑；不能在未检查动作对象和时机时当完全同义。这也说明动作短语不是简单命名实体。'),
]


def main():
    raw=rows(ROOT/'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl')
    raw_index={r['triple_id']:r for r in raw}
    audit=rows(ROOT/'data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl')
    exp=rows(ROOT/'data/kg/marine_pump/versions/expanded_v1_20261012/source_records.jsonl')
    lookup={r['triple_id']:r for r in [*raw,*audit,*exp]}
    expids={r['triple_id'] for r in exp}
    exact={g['cluster_id']:g for g in rows(HERE/'clusters/expanded1456_exact.jsonl')}
    targets={t['target']['target_id']:t for t in rows(HERE/'existing17_full_chain.jsonl')}
    occ={r['entity_id']:r['occurrences'] for r in rows(HERE/'entities/entity_occurrences.jsonl')}
    pages={};final=[]
    text=['# RP1构图数据可行性：可回查案例簿','',
          '日期：2026-11-13。以下19例为本次助手定向阅读的分析性案例，不是新专家Gold或独立评价样本；不把案例比例外推全图。引文和图状态从文件读取。候选源键未映射不等于最终知识不存在。',
          '', '完整逐条载荷和精确页内上下文见`casebook_records.jsonl`；相似性集合见`clusters/`及`entities/`。']
    for c in CASES:
        ids=list(c.get('record_ids',[]))
        if c.get('cluster_id'):ids += [r['triple_id'] for r in exact[c['cluster_id']]['evidence']]
        if c.get('target_id'):ids += targets[c['target_id']]['old_AI_judgment']['related_raw_ids']
        for eid in c.get('entity_ids',[]):ids += [o['record_id'] for o in occ[eid]]
        ids=list(dict.fromkeys(ids)); missing=[i for i in ids if i not in lookup]
        assert not missing,(c['id'],missing)
        records=[lookup[i] for i in ids]
        related_pages={(r['doc_id'],r['pdf_page_number']) for r in records}
        if c.get('target_id'):
            target=targets[c['target_id']]['target']; doc,number=target['page_key'].split(':p');related_pages.add((doc,int(number)))
        views=[]
        for doc,number in sorted(related_pages):
            if doc not in pages:pages[doc]={r['pdf_page_number']:r for r in rows(ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl')}
            page=pages[doc][number];txt=page['page_text'];snippets=[]
            if c.get('source_anchor'):
                at=txt.find(c['source_anchor'])
                if at>=0:snippets.append(dict(start=max(0,at-120),end=min(len(txt),at+400),text=txt[max(0,at-120):at+400]))
            views.append(dict(doc_id=doc,pdf_page_number=number,source_path=page['local_file'],page_text_sha256=page['page_text_sha256'],extra_native_context=snippets,
                              expanded_page_record_ids=[r['triple_id'] for r in exp if r['doc_id']==doc and r['pdf_page_number']==number]))
        rr=[]
        for r in records:
            same=[s for s in exp if s.get('legacy_triple_id')==r['triple_id'] or all(s.get(k)==r.get(k) for k in ['doc_id','pdf_page_number','head_surface','relation','tail_surface','evidence_text'])]
            legacy=r.get('legacy_triple_id',r['triple_id'])
            aa=[a for a in audit if a.get('legacy_triple_id')==legacy or a['triple_id']==r['triple_id']]
            rr.append(dict(candidate=r,original_raw_candidate=raw_index.get(legacy,raw_index.get(r['triple_id'])),audit_trace=[dict(triple_id=a['triple_id'],decision=a['decision'],rejection_reasons=a.get('rejection_reasons'),review_reasons=a.get('review_reasons')) for a in aa],
                expanded_matches=[dict(triple_id=s['triple_id'],claim_id=s['expanded_claim_id'],assertion_id=s['expanded_assertion_id'],conditions_source=s.get('conditions_source'),modality=s.get('modality','legacy_unspecified'),match_basis='explicit_legacy_id' if s.get('legacy_triple_id')==r['triple_id'] else 'exact_source_key') for s in same]))
        final.append(dict(selection=c,records=rr,source_pages=views,existing_target=targets.get(c.get('target_id'))))
        text += ['',f'## {c["id"]} {c["title"]}','',c['explanation'],'']
        if c.get('target_id'):
            t=targets[c['target_id']];text += [f'既有靶点：{c["target_id"]}；范围`{t["existing_full_chain_trace"]["scope"]}`；旧AI状态`{t["old_AI_judgment"]["raw_preservation"]}`。',
                f'原文证据（多单元分隔，非伪造连续偏移）：{witness_text(t["target"]["source_witnesses"])}', '']
        for entry in rr[:8]:
            r=entry['candidate'];status='已发布' if r['triple_id'] in expids else '显式legacy ID或精确源键映射到已发布' if entry['expanded_matches'] else '未发现显式legacy ID/精确源键发布映射；不外推为整页知识不存在'
            text += [f'- `{r["triple_id"]}`，{r["doc_id"]}物理p{r["pdf_page_number"]}，族`{r["source_family_id"]}`；原状态`{r.get("decision","原始缓存未判定")}`；**{status}**。',
                f'  候选：{r["head_canonical_zh"]} [{r["head_type"]}] → {r["relation"]} → {r["tail_canonical_zh"]} [{r["tail_type"]}]。',
                '  证据：'+re.sub(r'\s+',' ',r['evidence_text'])[:900],
                '  审计链：'+json.dumps(entry['audit_trace'],ensure_ascii=False),
                '  图谱：'+json.dumps(entry['expanded_matches'],ensure_ascii=False)]
            original=entry['original_raw_candidate']
            if original is not None and original['triple_id']!=r['triple_id']:
                text += [f'  原始抽取`{original["triple_id"]}`：{original["head_canonical_zh"]} [{original["head_type"]}] → {original["relation"]} → {original["tail_canonical_zh"]} [{original["tail_type"]}]；完整原载荷保留在案例JSONL。']
        for view in views:
            text += ['',f'源页：`{view["source_path"]}`，物理p{view["pdf_page_number"]}；页哈希`{view["page_text_sha256"]}`。']
            for snippet in view['extra_native_context']:
                text += ['页内位置'+str(snippet['start'])+'—'+str(snippet['end'])+'：'+re.sub(r'\s+',' ',snippet['text'])]
        text += ['','判断边界：'+('仅支持局部构图恢复的可能性；未执行修复。' if c['id'].startswith('B') else '关系/实体层级的分析解释；未执行合并或改写。')]
    (HERE/'casebook_records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in final))
    (HERE/'rp1_casebook.md').write_text('\n'.join(text)+'\n')
    print(f'Rendered {len(final)} analyst-selected cases; graph unchanged.')


if __name__=='__main__':main()
