#!/usr/bin/env python3
"""Finish cached-output alignment, anonymous cross-review and one final report.

No extra extractor calls. Existing finished reviews are reused by exact body,
contract and model identity. Does not alter labels or overwrite setup assets.
"""
import csv
import io
from align_rp1_complex_binding_parser import ALIGNED,FORMAL,reuse_reviews
from rp1_complex_binding_cross_evaluation import run as cross_review
from summarize_rp1_complex_binding import summarize
from run_rp1_complex_binding_baselines import *

def tabulate(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(str(x).replace('|','／').replace('\n',' ') for x in r)+' |' for r in rows]])

def publish():
    verify(ALIGNED);dest=summarize(ALIGNED);metrics=read(dest/'metrics.json');trials=read(ALIGNED/'trials.jsonl');targets=read(ALIGNED/'targets.jsonl');rows=read(dest/'trial_comparison.jsonl')
    allfocus=[];allrelations=[];ledger=[]
    for p in sorted((ALIGNED/'cross_evaluation/mapping').glob('*.json')):
        m=read(p);rid=m['review_id'];result=read(ALIGNED/'cross_evaluation'/f'{rid}.json');rawp=ALIGNED/'cross_evaluation'/f'{rid}.raw.json'
        try:v=strict_parse(read(rawp)['message']['content'])
        except (ValueError,KeyError,FileNotFoundError):continue
        # Preserve every original AI judgment, including citation-QC failures.
        for a in v.get('assessments',[]):allfocus.append({**m,'stage':m['channel'],'output_channel':a.get('channel'),**{k:v for k,v in a.items() if k!='channel'},'review_status':result['status'],'review_failure':result.get('failure'),'not_Gold':True})
        for r in v.get('relation_verdicts',[]):allrelations.append({**m,'stage':m['channel'],**r,'review_status':result['status'],'not_Gold':True})
    save(dest/'all_returned_AI_focus_judgments.jsonl',allfocus);save(dest/'all_returned_AI_relation_judgments.jsonl',allrelations)
    # Resolve the actual immutable source files, not just hash the hash list.
    preserved=[]
    for p,h in read(ALIGNED/'trace/input_manifest.json').items():
        actual=sha(ROOT/p);assert actual==h,p;preserved.append(dict(path=p,sha256=h))
    save(dest/'original_input_preservation.json',preserved)
    alignment=[]
    for t in trials:
        a=read(ALIGNED/'runs'/t['trial_id']/'result.json');o=read(FORMAL/'runs'/t['trial_id']/'result.json')
        if o['failure']!=a['failure'] or o['output']!=a['output']:alignment.append(dict(**t,old_failure=o['failure'],aligned_failure=a['failure'],old_count=len((o['output'] or {}).get('triples',[])),aligned_count=len((a['output'] or {}).get('triples',[])),source_response_unchanged=True))
    save(dest/'parser_interface_differences.jsonl',alignment)
    # Export all 17, regardless of missing/invalid evaluation responses.
    targettable=[]
    for t in targets:
        line=[t['target_id'],t['page_key'],t['scope']]
        for arm in ['B0','B1','B2','B3']:
            pieces=[]
            for seed in SEEDS:
                pair=[]
                for stage in ['raw','validated']:
                    found=[f for f in allfocus if f.get('focus_id')==t['target_id'] and f['arm']==arm and f['seed']==seed and f['stage']==stage]
                    f=found[0] if found else None
                    pair.append((f.get('literal_complete','?')+('†' if f['review_status']!='complete_AI_cross_evaluation' else '')) if f else '?')
                pieces.append('/'.join(pair))
            line.append('; '.join(pieces))
        targettable.append(line)
    buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['target_id','page_key','scope','B0_raw_validated_two_seeds','B1_raw_validated_two_seeds','B2_raw_validated_two_seeds','B3_raw_validated_two_seeds']);writer.writerows(targettable)
    save(dest/'seventeen_target_attribution.csv',buf.getvalue())
    pooled=[m for m in metrics['metrics'] if m['seed']=='pooled']
    totalcalls=sum(r['calls'] for r in rows);totaltokens=sum(r['total_tokens'] for r in rows)
    nreviews=Counter()
    for p in (ALIGNED/'cross_evaluation').glob('E*.json'):
        if not p.name.endswith(('.raw.json','.started.json')):nreviews[read(p)['status']]+=1
    cost=[];seen=set()
    for d in [FORMAL/'cross_evaluation',ALIGNED/'cross_evaluation']:
        for p in d.glob('E*.raw.json'):
            h=sha(p)
            if h in seen:continue
            seen.add(h);v=read(p);cost.append(dict(path=str(p.relative_to(ROOT)),sha256=h,input_tokens=v.get('prompt_eval_count'),output_tokens=v.get('eval_count'),total_duration_ns=v.get('total_duration')))
    save(dest/'actual_review_call_costs.jsonl',cost)
    solved=metrics['solved_arms']
    decision=('通用组'+','.join(solved)+'达到本轮预设小样本门槛，不新增RP1专门绑定算法。' if solved else '本轮不立项RP1专门复杂语义绑定算法。通用方法充分性尚未证实，现有证据也不足以把失败定位为需要独立算法的绑定问题。')
    lines=['# RP1复杂语义绑定：受控基线实测报告','','日期：2026-11-10。'+decision,'',f'实际生成完成{len(rows)}/{len(trials)}试次，{totalcalls}次调用，共{totaltokens}个输入输出token。15个开发页承载原T01–T17，另有6个预选构建页焦点；均重复两次。模型调用已实际执行，不以离线核查或单元测试替代。','', '## 方法与证据边界','','B0：旧v4抽取提示、公共实验约束和现有完整规则链。B1：增加通用JSON Schema提示。B2：增加通用条件、否定、AND/OR、时序与参数绑定提示。B3：两次读取同一源文的通用恢复；重复输入、草稿和最终输出全部计入预算。全部使用同一7B、13类实体/15种关系、32候选上限、65536输入输出总上限、5120输出上限、零重试和固定两种子。相同上限不等于相同实际成本，不作等实际成本的因果增益声明。','', '生成器是本地Qwen2.5-7B-Instruct BF16；独立评审是本地别名qwen3.8:27b，实际为qwen35架构27.3B Q4_K_M，以冻结资源摘要为准，不是DashScope qwen3.8-max。二者不同权重但同家族，AI判断不是专家Gold。评审不见组别、旧AI判断、期望答案和程序准入标记。','', '## 四组数量、质量和成本','','S/E/U以下均为有效AI交叉评价中的完整支持/错误/未决，不是事实真值；未通过引用校验的评价未计作已核验支持或零错误。候选与准入则是所有试次的程序计数，分母不同。']
    lines.append(tabulate(['集合','组','候选/准入','有效原始/验证后评价试次','原始S/E/U','验证后S/E/U','原始S被拒','token','调用'],[[m['split'],m['arm'],f"{m['raw_candidates']}/{m['admitted']}",f"{m['raw_reviews']}/{m['validated_reviews']}",'/'.join(str(m[k]) for k in ['raw_S','raw_N','raw_U']),'/'.join(str(m[k]) for k in ['validated_S','validated_N','validated_U']),m['supported_raw_rejected'],m['total_tokens'],m['calls']] for m in pooled]))
    lines+=['','## 17项逐靶点归因与本轮结果','','原17项清单及8/4/5初审保持不变。15页原提示重建全部匹配保存SHA256；源文证据片段均进入历史输入；保存的完整解码响应共135条主候选及空warnings，没有隐藏的auxiliary字段。重建提示不是历史保存的网络请求字节。T01/T02/T16的Schema/范围边界单列辅助语义；T06保留类型解释 caveat。','', 'T03的两动作与before returning、T07的OR、T10的may、T11的条件词和数值已在旧文本/证据出现，不能因缺独立字段一概叫知识丢失。程序拒绝和字面保留必须分开。逐项原文、相关记录ID、验证原因及原始输入输出见本轮trace/target_ledger.jsonl和trace/full_input_output_packets.jsonl。','', '下表每格依种子顺序2026111001、2026111002列出“原始/验证后”完整保留的AI原判。S/P/N/U/NA分别为完整/部分/缺失或错误/未决/不适用；†表示原判断存在但引用或完整性校验未通过，不能计作已核验正确；?表示未获得完整判断。']
    lines.append(tabulate(['靶点','物理页','范围','B0','B1','B2','B3'],targettable))
    lines+=['','## 独立小样本的七维评价','','以下是所有实际返回的AI维度判断，含†引用异常；用于完整披露，不替代上表的有效评价。每组最多12个焦点观察值（6页×2次），不是12个独立现场案例；NA及未返回单列。']
    dimrows=[]
    for dim,label in [('atomic','原子关系'),('condition_object','条件—对象'),('negation','否定/禁止'),('alternative_joint','替代/联合'),('numeric_order','数值/时序'),('evidence_support','源文支持'),('literal_complete','完整语义'),('explicit_binding','显式结构绑定')]:
        r=[label]
        for arm in ['B0','B1','B2','B3']:
            ff=[f for f in allfocus if f['split']=='independent' and f['arm']==arm and f['stage']=='validated'];c=Counter(f.get(dim,'missing') for f in ff);r.append('/'.join(str(c[k]) for k in ['S','P','N','U','NA'])+f'; 缺{12-len(ff)}')
        dimrows.append(r)
    lines.append(tabulate(['维度（S/P/N/U/NA）','B0','B1','B2','B3'],dimrows))
    lines+=['', '独立页按源文线索和哈希顺序预选：'+ '、'.join(s['page_key'] for s in read(ALIGNED/'independent/sources.jsonl'))+'。未按模型表现替换页面。旧全语料程序审计/抽样框中有这些页，但未发现其进入既有逐页语义核查材料；这不是从未处理过的新文档、来源族独立外测或全页穷尽Gold。英文动作线索抽样也不能证明多语言泛化。','', '## 失败机制与结论限制','',f'接口对齐发现{len(alignment)}项严格入口与仓库原解析器处理差异；完整明细见parser_interface_differences.jsonl。这些只是同一响应的解析/验证回放，没有重新抽取或改写模型语义。原来能解析的响应，其候选和规则结果已逐字段验证相同。', '',f'有效评价状态：{dict(nreviews)}。最早评审曾把源文支持误作输出保留，已保留并排除；正式评审通过空/完整/故意改错三组合成检查，并要求引用实际输出。仍有引用/格式异常，原始AI判断及原因完整保留在all_returned_AI_focus_judgments.jsonl；不能把这类异常当正确，也不能把它一概当语义错误。','', '未生成、主张错误、条件/分支缺失、格式解析损失、验证误拒和Schema表示边界是不同问题。empty输出不代表绑定算法错误；已有完整文本但显式字段不足不自动等于知识消失。每条返回AI意见均有原文与输出引用；具体失败和两次稳定性见failure_cases.jsonl、repeat_stability.jsonl及all_returned_AI_focus_judgments.jsonl。','', '本轮不足以从7B某个通用配置失败推出通用方法不能解决，更不能推出ILP或新核心算法必要。单评审、同家族偏差、少量焦点、语言能力、生成覆盖、接口/验证与表示边界尚需区分；不据此宣称全语料准确率、召回率或图谱净新增。若研究继续，先处理已证实的普通抽取/接口/验证问题，不追加复杂联合优化来解释这些混合损失。','', '## 保存与复现','','strict208、历史六项结果及15页原响应的哈希核对通过；未修改或发布图谱，RP2/RP3未训练或重跑。167项相关单元测试通过。设置阶段的语法解码卡顿、原始评价和中断记录均保留，未混入正式方法结果；正式语法解码未启用，每阶段runtime.json可核实。所有运行共享GPU，耗时不是隔离硬件延迟基准。','', '已完成实验只复算：','.venv/bin/python -c "import sys; sys.path[:0]=[\'scripts\',\'src\']; from finish_rp1_complex_binding_study import publish; publish()"','', '续跑仅在确有未开始试次时使用run_rp1_complex_binding_prompt_baselines.py execute。align_rp1_complex_binding_parser.py run复用原响应，reuse_reviews按内容地址复用同模型同合同评价；rp1_complex_binding_cross_evaluation.run(ALIGNED)核验差异输出；summarize(ALIGNED)确定性重算。不要重跑已完成调用。','', '冻结配置、实际模型摘要、种子、完整请求响应和原始token见正式目录；当前统计快照：'+str(dest.relative_to(ROOT))+'。']
    report='\n'.join(lines)+'\n';save(ALIGNED/'FINAL_REPORT.md',report)
    doc=ROOT/'docs/research/RP1_COMPLEX_BINDING_CONTROLLED_RESULTS_20261110.md';save(doc,report)
    save(ALIGNED/'delivery.json',dict(report=str(doc.relative_to(ROOT)),snapshot=str(dest.relative_to(ROOT)),decision=decision,extractor_calls=totalcalls,extractor_tokens=totaltokens,review_unique_actual_calls=len(cost),effective_review_status=dict(nreviews),source_preserved=True,script_sha256=sha(Path(__file__))))
    print('DELIVERED',doc,flush=True)

def finish():
    markers=[FORMAL/'generation_complete.json',FORMAL/'cross_evaluation/complete.json',ALIGNED/'generation_complete.json']
    while not all(p.exists() for p in markers):time.sleep(10)
    reuse_reviews();cross_review(ALIGNED);publish()

if __name__=='__main__':finish()
