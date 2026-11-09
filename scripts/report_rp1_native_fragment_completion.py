#!/usr/bin/env python3
"""Describe frozen development artifacts without inventing pending AI metrics."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from run_rp1_native_fragment_completion import DEFAULT,rows,sha,save,semantic_key


def report(out):
    generation=json.loads((out/'generation_complete.json').read_text())
    outputs=rows(out/'outputs.jsonl');sources=rows(out/'sources.jsonl')
    pools=[r for p in (out/'common_candidates').glob('*.jsonl') for r in rows(p)]
    new=[r for r in pools if r['origin']!='cached']
    catalogs=[json.loads(p.read_text()) for p in (out/'catalogs').glob('*.json')]
    lines=['# 原生完整片段补全与局部重构：开发实验','', '日期：2026-10-30。29页及10页均是已分析开发材料，不是新的独立验证。原图、原始响应、原标签及RP2/RP3未改变。','',
        '## 实现与严格对照','',
        '`native_fragment_completion_v1.py`只读取原生单元、真实行列和句子，生成带精确位置的完整片段。显示层去断行/识别重复印字，保留原文和真实bbox，不合成连续页面offset。维护矩阵无法拆列的合并单元继续未决；未知表型保留片段，不强设结构关系。正文提议来自通用语法和复合名词边界，没有记录ID答案规则。','',
        '`native_local_reconstruction_v1.py`复用normalize→context→clause→layout→batch规则，并在同一候选池上提供局部原生证据选择；没有学习分数、ILP或新教师训练。B2新增的是有限结构证据及多片段位置救回规则，不应包装成已验证的重排序算法。','',
        '| 组 | 输入/流程 |','| --- | --- |','| B0 | 484条原始输出，统一的完整声明规则链 |','| B1 | 原始输出+补全片段构造的结构关系假设，使用同一旧规则链 |','| B2 | 与B1完全相同的序列化候选文件，加局部原生证据选择 |','',
        '**基线口径**：这里的B0合并调用现有多个模块，不等于历史29页的三组后处理，也不等于历史10页编译器。不得拿历史16/66等数字直接作本轮B0。所有原始重复候选保留在分母；去重另报。','',
        '## 已确定的结构与程序指标','',
        f'- 39页、484条原始输出；B1/B2各{generation["common_candidates"]}条共同候选，其中新增结构关系假设{len(new)}条。',
        f'- 补全片段{sum(len(c["fragments"]) for c in catalogs)}个，证据单元{sum(len(c["units"]) for c in catalogs)}个；片段数不等于正确实体数或新增知识量。',
        f'- 初步程序选择B0/B1/B2：{generation["included"]["B0"]}/{generation["included"]["B1"]}/{generation["included"]["B2"]}条，**不是完整正确关系数**。',
        '- B1/B2每页候选ID集合及候选文件SHA256一致，由独立验证脚本检查。',
        f'- 原生位置回读：生成阶段{generation["native_roundtrips"]}次；含条件/表头/关系证明的独立核查见verification文件。',
        '- 新结构关系来源：'+json.dumps(dict(Counter(r['proof']['kind'] for r in new)),ensure_ascii=False)+'。','',
        '## 盲态源文核验与评价边界','',
        '采用本地已有Qwen2.5-7B-Instruct CPU FP32，不调用外部API。核验输入不含组名、是否放行、旧S/E/U、修复原因或参考答案；同一语义载荷只核验一次并映射回各组。全部变换后的候选（含拒绝者）重新核验，不继承旧S。','',
        f'三个任务分开：{generation["unique_relation_audit_inputs"]}个去重关系载荷；34条D类记录的旧池/补全池共68项端点充分性诊断；关系核验完成后，依据各组放行且核验为S的集合评价191项既有参考覆盖。参考不会进入片段或候选生成。','',
        '使用限定S/N/U的下一词元比较，保存分数、输入长度、未限定输出词元和上下文超限状态；不把这些条件分数叫校准概率。源文不裁剪，超限保留U。该AI诊断不等于专家真值。生成关系目前为源语实验假设，中文规范化仍未完成，不能直接发布为中文应用图。','',
        '端点诊断比较的是能否从池中取得完整端点，不是证明关系本身正确；新池包含页面原生片段，而历史10页菜单按单元组织，因此不宣称单一粒度控制下的正式端点召回率。','']
    if (out/'metrics.json').exists():
        metrics=json.loads((out/'metrics.json').read_text())
        lines+=['## 盲核验结果','', '| 开发批次 | 组 | 全部候选 | 放行 | 完整源文支持S | 问题N | 未决U | S比例 | S被拒 | 精确去重S | 完整参考覆盖 |','| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for batch,arms in metrics['arms'].items():
            for arm,r in arms.items():
                values=[batch,arm,r['all_candidates'],r['accepted'],r['source_supported'],r['source_error'],r['undetermined'],f'{100*r["supported_fraction"]:.2f}%',r['source_supported_rejected'],r['supported_distinct'],f'{r["complete_reference_coverage"]}/{r["reference_denominator"]}']
                lines.append('| '+' | '.join(map(str,values))+' |')
        lines+=['','端点池盲诊断：`'+json.dumps(metrics['endpoint_pool_AI_audit'],ensure_ascii=False)+'`。','',
            '开发门槛：`'+json.dumps(metrics['gates'],ensure_ascii=False)+'`。','',
            '**决策**：'+('至少一组达到预设开发门槛，下一步仅可另行冻结未参与开发的构建页；当前尚未证明独立泛化。' if metrics['independent_page_validation_authorized_by_development_gate'] else '开发门槛未通过，不选择或评估30–50个新验证页，不扩大图谱，也不继续叠规则追逐本批分数。')]
        labels={p.stem:json.loads(p.read_text())['label'] for p in (out/'blind_reviews').glob('*.json')}
        mapping={r['output_id']:r['review_id'] for r in rows(out/'private_review_mapping.jsonl')}
        details=[]
        for batch in ['29页','10页']:
            base={semantic_key(r['payload']) for r in outputs if r['dataset']==batch and r['arm']=='B0' and r['included'] and labels[mapping[r['output_id']]]=='S'}
            for arm in ['B1','B2']:
                selected=[r for r in outputs if r['dataset']==batch and r['arm']==arm and r['included']]
                newkeys={semantic_key(r['payload']) for r in selected if labels[mapping[r['output_id']]]=='S'}-base
                details.append(dict(dataset=batch,arm=arm,new_supported_exact_keys_relative_B0=len(newkeys),new_supported_keys=sorted(newkeys),limit='精确源语/条件键的增加，可能包含同义/条件表示差异，不是旧图合并后的语义净增'))
        save(out/'paired_supported_changes.json',details)
        lines+=['','相对B0的新增完整支持精确键及限制见`paired_supported_changes.json`；不声称这些均为旧图净新增。']
        target=out/'RESULTS.md'
    else:
        lines+=['## 当前状态','', '**语义结果待定。** 本地盲审仍在运行，尚不能报告新增完整正确关系、错误放行是否增加、误拒或完整参考覆盖。不得用程序放行增加代替算法成功。新页验证保持关闭。']
        target=out/'STATUS.md'
    lines+=['','## 复现入口','', '```bash','.venv/bin/python scripts/run_rp1_native_fragment_completion.py prepare','.venv/bin/python -u scripts/run_rp1_native_fragment_completion.py review','.venv/bin/python scripts/verify_rp1_native_fragment_completion.py','.venv/bin/python scripts/report_rp1_native_fragment_completion.py','```','', '已存在的prepare/review完成产物禁止重跑；中断的review会校验冻结输入并逐项复用已完成核验文件。API加速必须单独记录评价模型与原始响应，不混用本地和远端判断挑有利标签。']
    text='\n'.join(lines)+'\n'
    if target.exists() and target.read_text()!=text:raise ValueError('Refuse overwrite report; preserve research record')
    if not target.exists():target.write_text(text)
    print(target)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=DEFAULT);args=ap.parse_args();report(args.out)
