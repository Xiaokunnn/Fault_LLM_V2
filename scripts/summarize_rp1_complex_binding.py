#!/usr/bin/env python3
"""Summarize only the corrected output-retention cross-evaluation.

No labels, generations, graph or source are modified. A snapshot is written
to a new directory keyed by the exact completed-input manifest.
"""
import csv
import io
from run_rp1_complex_binding_baselines import *

def summarize(out=OUT):
    verify(out);trials=read(out/'trials.jsonl');d=out/'cross_evaluation'
    sources={s['page_key']:s['target'] for s in read(out/'sources.jsonl')}
    targets={s['target_id']:s for s in read(out/'targets.jsonl')};rows=[];focusrows=[];verdictrows=[];manifest={}
    for t in trials:
        p=out/'runs'/t['trial_id']/'result.json'
        if not p.exists():continue
        manifest[str(p.relative_to(ROOT))]=sha(p);r=read(p)
        admitted={v['index'] for v in r['validation'] if v.get('legacy_result',{}).get('included')}
        row=dict(**t,generation_failure=r['failure'],schema_errors=r['schema_errors'],raw_candidates=len((r['output'] or {}).get('triples',[])),admitted=len(admitted),input_tokens=r['used_total_tokens']-r['used_output_tokens'],output_tokens=r['used_output_tokens'],total_tokens=r['used_total_tokens'],calls=r['calls'],elapsed_seconds=sum(s['elapsed_seconds'] for s in r['stages']))
        for channel in ['raw','validated']:
            mapping=d/'mapping'/f'{t["trial_id"]}_{channel}.json'
            if not mapping.exists():row[channel+'_review_status']='pending';continue
            rid=read(mapping)['review_id'];p=d/f'{rid}.json'
            if not p.exists():row[channel+'_review_status']='pending';continue
            manifest[str(p.relative_to(ROOT))]=sha(p);e=read(p);row[channel+'_review_status']=e['status']
            if e['status']!='complete_AI_cross_evaluation':continue
            for a in e['assessment']['assessments']:
                f={**t,'stage':channel,'scope':targets.get(a['focus_id'],{}).get('scope','independent_source_focus'),'review_id':rid,**a}
                # Keep the model's labels; independently flag citation issues.
                try:source_anchor(sources[t['page_key']],a['evidence_quote']);f['source_citation_locatable']=True
                except (ValueError,KeyError):f['source_citation_locatable']=False
                focusrows.append(f)
            vs=e['assessment']['relation_verdicts']
            row[channel+'_S']=sum(v['verdict']=='S' for v in vs)
            row[channel+'_N']=sum(v['verdict']=='N' for v in vs)
            row[channel+'_U']=sum(v['verdict']=='U' for v in vs)
            if channel=='raw':row['supported_raw_rejected']=sum(v['verdict']=='S' and v['index'] not in admitted for v in vs)
            for v in vs:verdictrows.append(dict(**t,channel=channel,review_id=rid,**v))
        rows.append(row)
    summary=[]
    for split in ['development','independent']:
        for arm in ['B0','B1','B2','B3']:
            rs=[r for r in rows if r['split']==split and r['arm']==arm]
            for seed in [*SEEDS,'pooled']:
                rr=rs if seed=='pooled' else [r for r in rs if r['seed']==seed]
                counts={k:sum(r.get(k,0) for r in rr) for k in ['raw_candidates','admitted','input_tokens','output_tokens','total_tokens','calls','raw_S','raw_N','raw_U','validated_S','validated_N','validated_U','supported_raw_rejected']}
                counts.update(split=split,arm=arm,seed=seed,trials=len(rr),expected_trials=sum(t['split']==split and t['arm']==arm and (seed=='pooled' or t['seed']==seed) for t in trials),generation_failures=sum(bool(r['generation_failure']) for r in rr),raw_reviews=sum(r['raw_review_status']=='complete_AI_cross_evaluation' for r in rr),validated_reviews=sum(r['validated_review_status']=='complete_AI_cross_evaluation' for r in rr))
                for channel in ['raw','validated']:
                    fs=[f for f in focusrows if f['split']==split and f['arm']==arm and f['stage']==channel and (seed=='pooled' or f['seed']==seed)]
                    counts[channel+'_dimensions']={dim:dict(Counter(f[dim] for f in fs)) for dim in DIMENSIONS+['explicit_binding']}
                    for category,ff in [('core',[f for f in fs if f['scope']!='auxiliary_only']),('auxiliary',[f for f in fs if f['scope']=='auxiliary_only'])]:
                        counts[channel+'_'+category+'_literal']=dict(Counter(f['literal_complete'] for f in ff))
                        counts[channel+'_'+category+'_main_complete']=sum(f['literal_complete']=='S' and f['channel']=='main' for f in ff)
                    counts[channel+'_unlocatable_source_citations']=sum(not f['source_citation_locatable'] for f in fs)
                summary.append(counts)
    complete=len(rows)==len(trials) and (d/'complete.json').exists() and all(r['raw_review_status']=='complete_AI_cross_evaluation' and r['validated_review_status']=='complete_AI_cross_evaluation' for r in rows)
    # No missing reviews silently become correct/error-free trials.
    solved=[]
    if complete:
        for arm in ['B1','B2','B3']:
            ok=True
            for seed in SEEDS:
                fs=[f for f in focusrows if f['split']=='independent' and f['arm']==arm and f['seed']==seed and f['stage']=='validated']
                lc=sum(f['literal_complete']=='S' for f in fs)/max(1,sum(f['literal_complete']!='NA' for f in fs));at=sum(f['atomic']=='S' for f in fs)/max(1,sum(f['atomic']!='NA' for f in fs))
                err=sum(r.get('validated_N',0) for r in rows if r['split']=='independent' and r['arm']==arm and r['seed']==seed)
                baseline=sum(r.get('validated_N',0) for r in rows if r['split']=='independent' and r['arm']=='B0' and r['seed']==seed)
                ok=ok and lc>=.8 and at>=.9 and err<=baseline
            if ok:solved.append(arm)
    decision='通用方法已达到本轮小样本门槛，不新增专门算法' if solved else '尚不能证明通用方法足够；也不足以立项新算法，须先排除容量、输出接口与验证损失' if complete else '实验或有效交叉评价尚未全部完成，暂不作算法立项结论'
    sid=digest(manifest)[:16];dest=out/'summaries'/sid
    save(dest/'input_manifest.json',manifest);save(dest/'trial_comparison.jsonl',rows);save(dest/'focus_assessments.jsonl',focusrows);save(dest/'relation_verdicts.jsonl',verdictrows);save(dest/'metrics.json',dict(complete=complete,completed_trials=len(rows),expected_trials=len(trials),solved_arms=solved,decision=decision,metrics=summary,script_sha256=sha(Path(__file__))))
    failure=[f for f in focusrows if any(f[k] in ['P','N','U'] for k in DIMENSIONS)]
    save(dest/'failure_cases.jsonl',failure)
    repeat=[]
    groups=defaultdict(list)
    for f in focusrows:groups[(f['split'],f['arm'],f['stage'],f['focus_id'])].append(f)
    for key,ff in groups.items():repeat.append(dict(split=key[0],arm=key[1],channel=key[2],focus_id=key[3],repeats=len(ff),grades=[f['literal_complete'] for f in ff],all_repeats_complete=len(ff)==len(SEEDS) and all(f['literal_complete']=='S' for f in ff),stable=len({f['literal_complete'] for f in ff})==1))
    save(dest/'repeat_stability.jsonl',repeat)
    lines=['# RP1复杂语义绑定受控基线','','结论：'+decision+'。','',f'生成已完成{len(rows)}/{len(trials)}试次。评价为另一实际权重模型的AI交叉核验，不是专家Gold。下面错误数量只统计已有效评价的输出，未评价不等于零错误。','', '| 集合 | 组 | 已生成 | 有效原始/验证后评价 | 候选/准入 | 原始S/E/U | 验证后S/E/U | 原始S被拒 | 总token | 调用 |','| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in summary:
        if r['seed']!='pooled':continue
        cells=[r['split'],r['arm'],f"{r['trials']}/{r['expected_trials']}",f"{r['raw_reviews']}/{r['validated_reviews']}",f"{r['raw_candidates']}/{r['admitted']}",'/'.join(str(r[k]) for k in ['raw_S','raw_N','raw_U']),'/'.join(str(r[k]) for k in ['validated_S','validated_N','validated_U']),r['supported_raw_rejected'],r['total_tokens'],r['calls']]
        lines.append('| '+' | '.join(map(str,cells))+' |')
    lines+=['','T01–T17逐条历史归因见../../trace/TARGET_ATTRIBUTION.md；本轮逐靶点和七维评价见focus_assessments.jsonl，具体失败理由、输出引用及源文引用均保留。两次重复逐项一致性见repeat_stability.jsonl。','', '独立样本为6个按源文线索预选的构建页、各1个焦点；不是全页穷尽参考、正式召回率或来源族独立外测。语义线索分层不等于已证实每段都属于可表达关系；NA必须单列。T01/T02/T16另列辅助要求。','', 'B0是同一7B上的前瞻性旧提示与规则对照，另有通用公共输出约束，不冒充历史Qwen-max原结果。B1加通用结构约束，B2加复杂语义提示，B3分配两次阅读；相同源文与资源上限不等于相同实际token消耗。B3重复输入已计费。','', '模型：本地Qwen2.5-7B-Instruct BF16；评审为本地qwen3.8:27b别名，实际qwen35架构27.3B Q4_K_M，以resources.json摘要为准，不是DashScope qwen3.8-max。同家族相关偏差不能排除。','', '设置预检的两条空输出和中断试次保留在complex_binding_controlled_v1_20261110，不计正式方法结果。最初评审把源文支持误作输出保留，原记录留在evaluation/且全部排除；cross_evaluation/通过空/正确/改错三组合成控制并要求输出引用。任何评价失败都保留为未评，不自动重试或回填标签。','', '运行时生成与评审共享GPU，耗时不是隔离的模型延迟基准；报告token及调用的实际成本。全部工作不发布图谱、不改strict208/RP2/RP3。','', '复现：.venv/bin/python scripts/run_rp1_complex_binding_baselines.py prepare；execute读取冻结配置，只续未开始的试次；.venv/bin/python scripts/rp1_complex_binding_cross_evaluation.py执行有效匿名评价；.venv/bin/python scripts/summarize_rp1_complex_binding.py确定性复算。保留已有结果，不重新运行已完成试次；遇不确定中断先审计，不自动重试。']
    save(dest/'REPORT.md','\n'.join(lines)+'\n');print(dest)
    return dest

if __name__=='__main__':summarize()
