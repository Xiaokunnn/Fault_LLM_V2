#!/usr/bin/env python3
"""Read-only failure attribution after the controlled study, no new AI calls.

Keep AI source-support grades separate from executable ontology legality.
Neither AI S nor a legal type pair by itself proves a complete correct claim.
"""
from collections import Counter,defaultdict
from align_rp1_complex_binding_parser import ALIGNED,FORMAL
from rp1_complex_binding_common import *
from run_rp1_complex_binding_baselines import verify
from research_point_1_graph_evidence.stage03_schema_validation.relation_type_validator import load_provenance_schema,validate_relation_type

def run():
    verify(ALIGNED)
    delivery=read(ALIGNED/'delivery.json');snapshot=ROOT/delivery['snapshot']
    grades={(r['trial_id'],r['index']):r for r in read(snapshot/'relation_verdicts.jsonl') if r['channel']=='raw'}
    schema=load_provenance_schema(ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json')
    records=[];counts=Counter();supported=Counter();groups=defaultdict(Counter);flags=Counter();normalization=Counter();input_hashes={}
    for p in sorted((ALIGNED/'runs').glob('*/result.json')):
        input_hashes[str(p.relative_to(ROOT))]=sha(p);r=read(p);t=r['trial'];vm={v['index']:v for v in r['validation']}
        for i,a in enumerate((r['output'] or {}).get('triples',[]),1):
            v=vm[i];z=v.get('legacy_result',{});ff=z.get('screen_flags',[])
            # Fixed mutually exclusive stage priority; secondary flags retained.
            category='normalization_rejected' if 'normalization_error' in v else 'admitted' if z.get('included') else 'schema_type_direction' if 'schema_type_direction' in ff else 'unbound_quote' if 'unbound_quote' in ff else 'conditional_context' if 'conditional_context_not_explicit' in ff else 'other_barrier'
            ty=validate_relation_type(relation=a.get('relation',''),head_type=a.get('head_type',''),tail_type=a.get('tail_type',''),schema=schema)
            ai=grades.get((t['trial_id'],i));s=ai is not None and ai['verdict']=='S'
            row=dict(**t,index=i,primary_loss=category,raw_schema_legal=ty.valid,raw_schema_reasons=list(ty.reasons),AI_source_verdict=ai['verdict'] if ai else None,AI_reason=ai.get('reason') if ai else None,AI_not_Gold=True,raw=a,normalization_error=v.get('normalization_error'),final_payload=z.get('payload'),screen_flags=ff,barriers=z.get('barriers',[]),normalizer_actions=z.get('normalizer_actions',[]),included=bool(z.get('included')))
            records.append(row);counts[category]+=1;groups[(t['split'],t['arm'])][category]+=1;flags.update(ff)
            if row['normalization_error']:normalization[row['normalization_error']]+=1
            if s:
                supported[category]+=1;supported['raw_schema_legal' if ty.valid else 'raw_schema_illegal']+=1
                supported[('legal' if ty.valid else 'illegal')+('_admitted' if row['included'] else '_rejected')]+=1
    targets=[r for r in records if r['AI_source_verdict']=='S' and r['raw_schema_legal'] and not r['included']]
    dest=ALIGNED/'failure_attribution';save(dest/'input_manifest.json',input_hashes)
    save(dest/'candidate_stage_ledger.jsonl',records);save(dest/'AI_S_schema_legal_rejected_targets.jsonl',targets)
    save(dest/'summary.json',dict(total_candidates=len(records),mutually_exclusive_primary=dict(counts),overlapping_flags=dict(flags),normalization_errors=dict(normalization),AI_S_partition=dict(supported),groups={split+'_'+arm:dict(v) for (split,arm),v in groups.items()},rejected_legal_AI_S_count=len(targets),source_labels_unchanged=True,new_model_calls=0,script_sha256=sha(Path(__file__))))
    label={'normalization_rejected':'字段/词表规范化拒绝','schema_type_direction':'后续类型/方向不合法','unbound_quote':'证据无法按原生约束绑定','conditional_context':'必要条件未显式绑定','admitted':'局部规则准入','other_barrier':'其他屏障'}
    lines=['# 受控基线失败归因复核','','结论：本轮不支持为RP1另立复杂语义绑定算法。首先暴露的是7B输出词表/类型遵从、生成覆盖及现有接口/规则的混合问题。这里不把AI源文判S当作满足Schema的正确图谱关系，也不把所有拒绝都算误拒。','', '## 761条候选的互斥阶段统计','','统计单位为试次中的候选出现次数，包含两次重复，不是去重后的图谱净新增量。各行按“规范化拒绝→准入→类型/方向→定位→条件→其他”优先级互斥；详细重叠标记另保留。','', '| 阶段 | 数量 | 占761条 |','| --- | --- | --- |']
    for k,n in counts.items():lines.append(f'| {label[k]} | {n} | {n/len(records):.2%} |')
    nS=sum(1 for r in records if r['AI_source_verdict']=='S');rej=sum(1 for r in records if r['AI_source_verdict']=='S' and not r['included'])
    lines+=['','## 为什么不能称为大量正确知识被误拒','',f'有效原始AI评价中共{nS}条判S，其中{supported["raw_schema_illegal"]}条原始关系名或Domain/Range不合法，只有{supported["raw_schema_legal"]}条类型对合法。AI判的是源文语义支持，不能单独证明符合图谱接口。原始S被拒共{rej}条，其中{supported["illegal_rejected"]}条原始Schema非法；余下{len(targets)}条是“AI判S且类型对合法但被拒”的待诊断候选。它们仍可能违反原文端点、证据位置、条件、中文规范名等契约，不能直接叫{len(targets)}条已证实误拒。', '', '| AI判S的原始候选 | 准入 | 拒绝 |','| --- | --- | --- |',f'| 原始Domain/Range合法 | {supported["legal_admitted"]} | {supported["legal_rejected"]} |',f'| 原始关系名/类型对非法 | {supported["illegal_admitted"]} | {supported["illegal_rejected"]} |', '', 'AI原判、候选内容和所有拒绝原因逐条保存在candidate_stage_ledger.jsonl。没有重写AI标签，没有调用模型修复，没有把结构非法直接改判成源文不支持。','', '## 14条待诊断记录（不是已恢复正确知识）','','| 试次/序号 | 主要阶段 | 拒绝依据 |','| --- | --- | --- |']
    for r in targets:lines.append('| '+r['trial_id']+':'+str(r['index'])+' | '+label[r['primary_loss']]+' | '+str(r['normalization_error'] or r['screen_flags'] or r['barriers']).replace('|','／')+' |')
    lines+=['','## 对四组基线的解释','','B1为通用Schema提示，不是一个成功运行的硬语法解码对照；设置阶段所试语法库卡顿被保留并排除。因此不能据本轮失败宣布通用结构化解码无效。B2/B3同样没有证明专门绑定算法必要；更多输出或更高源文判S次数不等于更多合格关系。','', '本轮程序准入边界是已声明的局部链：normalize_relation_direction → automatic_contract_v4_1 → clause_binding_v1 → layout_direction_context_v1 → batch_evidence_repair_v1，并使用native_evidence_binding_v2及冻结筛查器。它没有执行图谱发布、术语治理、来源族聚合，准入数不是strict208或论文最终发布层的质量指标。','', '335个S与原始候选/验证后候选不是同一分母，也不是专家正确率。本轮少量独立页、两次重复和有引用异常的AI评价不足以证明普遍效果；但足以否定“把所有拒绝理解为复杂绑定问题，再直接立项新算法”这一推理。','', '建议：先以通用方式保证合法词表、类型对、原文端点和正常序列化输出，再判断剩余的复杂绑定错误是否稳定存在。不要优先加联合优化、领域核验器或新的流程层。若换用通用硬约束解码或更强生成模型，应另行预注册，不能把本轮提示版冒充该对照的失败证据。','', '复算：PYTHONPATH=src:scripts .venv/bin/python scripts/audit_rp1_complex_binding_failures.py。只读已有响应及评价，无新模型调用。']
    report='\n'.join(lines)+'\n';save(dest/'REVIEW.md',report)
    # One reviewer-facing document: statistics remain untouched, clarification
    # is explicitly a deterministic post-analysis supplement.
    original=(ALIGNED/'FINAL_REPORT.md').read_text()
    combined=original+'\n\n---\n\n'+report
    save(ROOT/'docs/research/RP1_COMPLEX_BINDING_CONTROLLED_REVIEW_20261110.md',combined)
    print('Reviewed:',dest,'AI S raw-schema-legal rejected',len(targets))

if __name__=='__main__':run()
