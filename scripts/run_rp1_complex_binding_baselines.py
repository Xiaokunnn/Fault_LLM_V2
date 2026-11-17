#!/usr/bin/env python3
"""Controlled generic baselines, isolated artifacts, immutable historical inputs."""
import argparse
from collections import Counter,defaultdict
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from rp1_complex_binding_common import *
from run_rp1_six_checks import Archive,source_anchor,screen_from_archive
from run_targeted_triple_extraction import _load_candidate_pool_pages
from research_point_1_graph_evidence.stage02_triple_extraction.chinese_extraction_contract import system_prompt_for_version,build_user_prompt,normalize_model_candidate
from research_point_1_graph_evidence.stage03_schema_validation.native_local_reconstruction_v1 import legacy_rules

LEGACY=system_prompt_for_version('marine_pump_full_corpus_prompt_v4')
SEEDS=[2026111001,2026111002]
JUDGE_URL='http://127.0.0.1:11434'

# This defines evaluation scope, never candidate-generation rules or prompts.
# Target IDs come verbatim from the sealed six-check audit, not other 17-lists.
SCOPE={
 'T01':('auxiliary_only','预测准确性与环境一致的条件；Schema没有InspectionMethod的准确度/适用性关系，排除故障关系召回分母。','环境在整个测试期一致；准确预测为条件性陈述。'),
 'T02':('auxiliary_only','共用传感器法规许可/例外没有直接对应关系；不得借specified_by伪造许可关系。','许可排除停机功能及所列必需泵自动启动/切换，保持例外作用域。'),
 'T03':('core','现有故障→措施可表达两个动作；跨记录时序另作保留诊断。','异常/损坏语境；立即停泵；消除原因在重新投运之前；不得添加强制重启。'),
 'T04':('core','泵→operates_under→闭出口状态，许可限制可在端点/条件/证据保存。','标准泵；闭出口；最长5分钟 AND 最高80°C；不构成现场操作许可。'),
 'T05':('core','部件维护/保温禁令可作负向动作，不得改成正向覆盖。','电机支架孔/网罩开口；保温场景；不得覆盖。'),
 'T06':('core_with_type_caveat','沿用现有Component inspected_by InspectionMethod候选作为可检验假设；跳机阈值不是普适故障因果。','电机非驱动端；建议跳机而非报警；严格>15 mm/s；DESMI局部范围。'),
 'T07':('core','故障/原因到MaintenanceAction可保留复合替代措施。','对应低流量/堵塞表格分支；增加流量 OR 使用较小泵，不能变成AND。'),
 'T08':('core','部件检查及必要维修在Schema内。','密封面磨损、弹性体状态检查；必要时替换 OR 记录待计划维护；指代对象一致。'),
 'T09':('core','过热/部件到冷却维护动作可表达。','开泵/检修之前；IF 已过热 THEN 完全冷却，不能无条件化。'),
 'T10':('core','OperatingCondition causes FaultMode已有关系可表达。','偏离选型工况；may；汽蚀或轴承/密封/填料/轴寿命缩短；非必然后果。'),
 'T11':('core','轴承维护政策及作用条件可表达；原OperatingCondition mitigated_by类型本身不合法。','同一行：极脏、干、轻至中负载、低至中速、0–200°F→每日冲排污物；不能跨行。'),
 'T12':('core','电机/轴承补充润滑政策可在维护动作文字中表达。','使用其他润滑脂时，周期可能缩短；非确定强制缩短。'),
 'T13':('core','潮湿绕组→烘干措施可表达，参数为动作限定。','参考电阻未达到；先90°C×12–16h，后105°C×6–8h；温度/时长必须成对且有序。'),
 'T14':('core','Component operates_under OperatingCondition已有表示。','整流器仅清液适用；only不可删除。'),
 'T15':('core','风险防护/维修措施可表达；单纯传感器监测不等于压力保护。','四种压力保护替代：泵上阀/管路阀/扭矩限制/爆破盘；可能反转时双侧保护。'),
 'T16':('auxiliary_only','禁止泄压阀用于某功能属于用途/运行限制；当前没有用途/许可关系，不强塞成维护或因果。','不可用于流量控制，也不可用于出口压力调节；在辅助要求中完整保留。'),
 'T17':('core','Component inspected_by InspectionAction已有关系。','运行前；叶轮旋向检查。')}

def ollama(endpoint,payload,timeout=600):
    req=urllib.request.Request(JUDGE_URL+endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

def trace(out):
    targets=read(SIX/'frequency/representation_targets.jsonl');old=read(SIX/'frequency/representation_judgments.json');jm={r['target_id']:r for r in old['judgments']}
    assert [r['target_id'] for r in targets]==[f'T{i:02d}' for i in range(1,18)]
    pages={r['page_key']:r['target'] for r in read(SIX/'frequency/source_sample.jsonl')}
    plan=ROOT/'data/interim/candidate_pages/full_extraction_v1/candidate_pages.jsonl'
    loaded=_load_candidate_pool_pages(ROOT/'data/interim/parsed_pages/corpus_v2',plan);historical={f"{r['doc_id']}:p{r['pdf_page_number']:04d}":r for r in loaded}
    candidates=read(SIX/'frequency/representation_candidates.jsonl');replays=read(SIX/'frequency/native_baseline_replays.jsonl');rep={r['triple_id']:r for r in replays}
    ledger=[];packets=[];input_hashes={str(p.relative_to(ROOT)):sha(p) for p in [SIX/'frequency/representation_targets.jsonl',SIX/'frequency/representation_judgments.json',SIX/'frequency/representation_candidates.jsonl',SIX/'frequency/native_baseline_replays.jsonl',SIX/'completion_summary.json',SIX/'completion_seal.json',plan]}
    for t in targets:
        tid=t['target_id'];key=t['page_key'];p=pages[key]
        path=ROOT/'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/raw_responses'/f'{key.replace(":","_")}.json'
        cache=read(path);input_hashes[str(path.relative_to(ROOT))]=sha(path)
        user=build_user_prompt(historical[key]);h=hashlib.sha256((LEGACY+'\n'+user).encode()).hexdigest();assert h==cache['prompt_sha256'],key
        # Saved response_json is decoded full model content, not a raw HTTP
        # envelope. Actual request bytes weren't saved; this reconstruction is
        # proved by its saved cryptographic prompt digest, not called original.
        parts=sorted(path.parent.glob(path.stem+'_part*.json')) if cache['finish_reason']=='merged_chunks' else []
        meta=[]
        for pp in parts:
            pr=read(pp);input_hashes[str(pp.relative_to(ROOT))]=sha(pp)
            assert pr['prompt_sha256']==h and pr['finish_reason']=='stop'
            meta.append({k:pr[k] for k in ['request_id','finish_reason','prompt_sha256','usage','attempt']})
        if not parts:meta=[{k:cache[k] for k in ['request_id','finish_reason','prompt_sha256','usage','attempt']}]
        page_records=[r['record'] for r in candidates if r['layer']=='raw_cached' and r['page_key']==key]
        assert len(cache['response_json']['triples'])==len(page_records)
        related=[r for r in page_records if r['triple_id'] in jm[tid]['related_raw_ids']]
        def leaves(w):
            if 'witnesses' in w:
                for ww in w['witnesses']:yield ww
            else:yield w
        pieces=[w['text'] for a in t['source_witnesses'] for w in leaves(a)]
        source_strings=[p['page_text'],*[c['text'] for tb in p['tables'] for row in tb['rows'] for c in row['cells']]]
        in_input=[any(norm(x) in norm(s) for s in source_strings) for x in pieces]
        response_strings=list(strings(cache['response_json']))
        anchor_hits=[any(norm(x) in norm(s) for s in response_strings) for x in t['anchors']]
        # Literal checks only; no fuzzy keyword overlap is treated as semantic
        # loss or recovery. All full responses are in the evidence packet.
        mapped=[]
        for r in related:
            rr=rep[r['triple_id']]
            mapped.append(dict(triple_id=r['triple_id'],raw_head=r['head_surface'],relation=r['relation'],raw_tail=r['tail_surface'],raw_evidence=r['evidence_text'],admitted=rr['included'],flags=rr['screen_flags'],barriers=rr['barriers'],audit=[{'layer':x['layer'],'decision':x['record'].get('decision'),'head':x['record'].get('head_surface'),'tail':x['record'].get('tail_surface'),'reasons':x['record'].get('rejection_reasons',[])} for x in candidates if x['layer']!='raw_cached' and x['record'].get('triple_id')==r['triple_id']]))
        scope,why,must=SCOPE[tid]
        notes={
            'T03':'两动作、immediately及before returning均已出现。跨边动作链是否足够可由源文读者判断，不能仅因没有sequence字段称信息全丢。',
            'T07':'OR已在动作文字中；未准入是证据/规则问题，不是OR未生成。',
            'T10':'工况在head，may在evidence；无独立modality字段只表示不可直接按字段查询。',
            'T11':'全部工况及每日冲排已在原evidence，0F/200F仍保留F量纲；度符号缺失不直接等于单位语义丢失。需分开记录literal保留、未绑定字段、类型/定位拒绝。',
            'T13':'潮湿诊断及烘干动作已生成；有序温度—时长片段未在保存响应中出现。',
            'T08':'相关检查和其他更换动作存在，但计划维护的替代分支未见；不能把其他条目的更换强配为此分支。'}
        row=dict(target_id=tid,page_key=key,semantic_tags=t['tags'],scope=scope,scope_reason=why,required_semantics=must,source_witnesses=t['source_witnesses'],old_AI_judgment=jm[tid],historical_prompt_sha256=h,prompt_reconstruction_matches_saved_hash=True,source_pieces_in_actual_input=in_input,response_finish_parts=meta,complete_response_fields=list(cache['response_json']),auxiliary_field_keys=[k for k in cache['response_json'] if k not in ['triples','warnings']],warnings=cache['response_json'].get('warnings'),raw_proposals=len(cache['response_json']['triples']),retained_page_candidates=len(page_records),normalization_count_loss=0,literal_anchor_hits=anchor_hits,related_candidates=mapped,diagnostic=notes.get(tid,'字面片段检查不等于语义裁定；原AI初审保持原样，完整请求/响应与所有页面候选供复查。'),AI_analysis_not_Gold=True)
        ledger.append(row)
        packets.append(dict(target_id=tid,source=p,historical_verified_reconstruction={'system':LEGACY,'user':user,'sha256':h,'not_original_saved_request_bytes':True},complete_saved_response=cache,all_page_candidates=page_records,related_pipeline_records=[rep[r['triple_id']] for r in related]))
    save(out/'trace/target_ledger.jsonl',ledger);save(out/'trace/full_input_output_packets.jsonl',packets)
    save(out/'trace/input_manifest.json',input_hashes)
    save(out/'targets.jsonl',[dict(**t,scope=SCOPE[t['target_id']][0],scope_reason=SCOPE[t['target_id']][1],required_semantics=SCOPE[t['target_id']][2]) for t in targets])
    lines=['# T01–T17全链路归因（开发性AI分析，非Gold）','','原17项及其编号不变。提示为经过原缓存SHA256验证的重建，不冒充历史保存的请求字节。完整解码响应及主候选逐页计数一致；没有auxiliary字段、warnings为空，不靠搜索主候选推断全响应。5页merged_chunks均逐part确认stop。','', '| 靶点 | 文档物理页 | 范围 | 原AI初审 | 相关缓存 | 完整响应锚点 | 原生回放准入 | 必保留内容/归因 |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in ledger:
        lines.append('| '+' | '.join(str(x).replace('|','／').replace('\n',' ') for x in [r['target_id'],r['page_key'],r['scope'],r['old_AI_judgment']['raw_preservation'],','.join(x['triple_id'] for x in r['related_candidates']) or '无原相关ID',r['literal_anchor_hits'],[x['admitted'] for x in r['related_candidates']],r['required_semantics']+' '+r['diagnostic']])+' |')
    lines+=['','范围外/无现有关系可表达的T01/T02/T16不进入核心关系保留分母，另评价辅助要求保留；T06标为类型解释需核验。字段缺失、类型拒绝、发布阻断及文字仍在分别保留，不能合并成LLM未生成。','', '逐项原文、输入、原始解码输出、全部候选和验证记录见full_input_output_packets.jsonl；这些材料不进入新生成提示或盲审的期望答案。']
    save(out/'trace/TARGET_ATTRIBUTION.md','\n'.join(lines)+'\n')
    return pages,targets

def independent_selection(out):
    excluded=set();exposure={}
    for p in BASE.rglob('*'):
        if not p.is_file() or p.is_relative_to(out) or p.suffix not in ['.json','.jsonl']:continue
        if p.name not in ['source_sample.jsonl','sources.jsonl','pages_source_only.jsonl','pilot_sources.jsonl','adjudication_sources.jsonl','source_only.jsonl','selection.json','representation_targets.jsonl']:continue
        content=p.read_text();exposure[str(p.relative_to(ROOT))]=sha(p)
        excluded.update(re.findall(r'MP\d{3}:p\d{4}',content))
        for r in strings(read(p)):
            if re.fullmatch(r'MP\d{3}:p\d{4}',r):excluded.add(r)
        # Native source objects can lack page_key.
        def walk(x):
            if isinstance(x,dict):
                if 'doc_id' in x and isinstance(x.get('pdf_page_number'),int):excluded.add(f"{x['doc_id']}:p{x['pdf_page_number']:04d}")
                for v in x.values():walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        walk(read(p))
    cues={'condition':r'\bif\b|\bwhen\b|\bunless\b','negation':r'\bnever\b|\bmust not\b|\bdo not\b','alternative':r'\balternatively\b|\beither\b|\bor\b','sequence':r'\bbefore\b|\bafter\b|\bthen\b|\bfollowed by\b','numeric':r'\d+\s*(?:°\s*[CF]|hours?|minutes?|mm/s|bar|rpm)\b','control':r'.'}
    candidates=[];parsed_hashes={}
    for doc in sorted(BUILD):
        p=ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl';parsed_hashes[str(p.relative_to(ROOT))]=sha(p)
        for pg in read(p):
            key=f"{doc}:p{pg['pdf_page_number']:04d}"
            text=' '.join(pg['page_text'].split())
            if key in excluded or not 500<=len(text)<=8500 or not re.search(r'\bpump|\bbearing|\bmotor',text,re.I):continue
            if pg['document_split']!='build_train':raise ValueError('split')
            candidates.append((digest(['RP1-complex-independent-20261110',key]),key,pg,text))
    selected=[];used=set()
    # Source-only relevance requirement, fixed before looking at ANY new
    # model output: the focus itself must describe an actionable operation.
    action=r'\b(?:inspect(?:ed|ing)?|check(?:ed|ing)?|replac(?:e|ed|ing)|lubricat(?:e|ed|ing)|stop(?:ped|ping)?|start(?:ed|ing)?|remov(?:e|ed|ing)|install(?:ed|ing)?|clean(?:ed|ing)?|tighten(?:ed|ing)?|dry|heat(?:ed|ing)?|cool(?:ed|ing)?|operat(?:e|ed|ing)|maintain(?:ed|ing)?|service)\b'
    from research_point_1_graph_evidence.stage03_schema_validation.layout_direction_context_v1 import native_views
    for kind,pat in cues.items():
        for _,key,p,text in sorted(candidates):
            if p['doc_id'] in used or any(s['page_key']==key for s in selected):continue
            if not re.search(pat,text,re.I):continue
            if kind=='control' and any(re.search(p,text,re.I) for k,p in cues.items() if k!='control'):continue
            # A source paragraph, not an answer: exact native view excerpt and
            # full page context are fixed before ANY model generation.
            views,_=native_views(p);options=[]
            for view in views:
                txt=view['text']
                for m in re.finditer(r'[^.!?]{70,450}[.!?]',txt):
                    q=m.group()
                    if not re.search(r'\b(?:pumps?|bearings?|motors?|seals?|impellers?|valves?|shafts?|couplings?|bolts?|lubricant|grease)\b',q,re.I):continue
                    if kind=='alternative' and len(re.findall(action,q,re.I))<2:continue
                    if re.search(pat,q,re.I) and re.search(action,q,re.I):options.append(q.strip())
            if not options:continue
            quote=sorted(options,key=lambda x:digest([kind,x]))[0]
            try:w=source_anchor(p,quote)
            except ValueError:continue
            selected.append(dict(sample_id=f'I{len(selected)+1:02d}',page_key=key,stratum=kind,target=p,focus_quote=quote,source_witness=w));used.add(p['doc_id']);break
    if len(selected)!=6:raise ValueError('Insufficient predefined untouched strata; do not substitute: '+str([s['stratum'] for s in selected]))
    save(out/'independent/sources.jsonl',selected)
    save(out/'independent/selection.json',dict(seed='RP1-complex-independent-20261110',sample_size=6,allocation=list(cues),source_action_pattern=action,semantic_cue_patterns=cues,excluded_pages=sorted(excluded),exposure_sources_sha256=exposure,parsed_sources_sha256=parsed_hashes,selection_before_outputs=True,reference_status='source-first independent AI evaluation pending; not Gold',limits='English-action-cue small sample; page-disjoint against enumerated exposure manifests within build docs, not exhaustive proof of no historical exposure and not source-family-disjoint field validation; prior automatic full-corpus extraction does not imply manual/error-analysis exposure'))
    return selected

def prepare(out):
    out.mkdir(parents=True,exist_ok=True)
    pages,targets=trace(out);independent=independent_selection(out)
    sources=[dict(split='development',page_key=k,target=pages[k]) for k in sorted({t['page_key'] for t in targets})]+[dict(split='independent',page_key=s['page_key'],target=s['target']) for s in independent]
    save(out/'sources.jsonl',sources)
    packages={p.name:importlib.metadata.version(p.name) for p in []}
    resources=ollama('/api/show',{'model':JUDGE});tags=json.load(urllib.request.urlopen(JUDGE_URL+'/api/tags'))
    judge_meta=next(x for x in tags['models'] if x['name']==JUDGE)
    save(out/'resources.json',dict(generator=dict(path=str(MODEL.relative_to(ROOT)),config=read(MODEL/'config.json'),weight_sha256={p.name:sha(p) for p in sorted(MODEL.glob('*.safetensors'))},tokenizer_sha256=sha(MODEL/'tokenizer.json')),judge=dict(alias=JUDGE,digest=judge_meta['digest'],details=resources['details'],model_info={k:v for k,v in resources.get('model_info',{}).items() if not isinstance(v,(list,dict))},local_url=JUDGE_URL,not_DashScope_qwen_max=True),libraries={x:importlib.metadata.version(x) for x in ['torch','transformers','lm-format-enforcer','jsonschema']}))
    methods={a:system(a,LEGACY) for a in ['B0','B1','B2','B3']};save(out/'methods.json',methods);save(out/'output_schema.json',response_schema())
    save(out/'protocol.json',dict(date='2026-11-10',generator='Qwen2.5-7B-Instruct local BF16 RTX5880',judge_alias=JUDGE,judge_independence='different model weights/architecture/version; same broad family, not independent expert truth',arms={'B0':'frozen v4 semantic prompt + same common envelope + existing validation','B1':'B0 + generic common JSON Schema constrained decoding','B2':'B1 + generic conditions/AND-OR/negation/order/value binding instruction','B3':'B2 draft + source reread/recovery; all calls and repeated prompts charged'},ontology='unchanged13types15relations; binding annotations are not published graph edges',seeds=SEEDS,temperature=.2,total_input_output_token_cap=65536,total_output_cap=5120,draft_output_cap=1536,final_recovery_output_cap=3584,context_cap=32768,call_cap=2,retries=0,candidate_cap=32,matched_budget_meaning='same strict total-token/output/call ceilings, not equal realized usage; one-pass arms may spend their output ceiling at once, B3 splits it and pays repeated source input; report actual costs and do not claim iso-realized-cost causal gains',source_context='same entire native page for all arms; no target answers, no extra pages for B3',evaluation_dims=DIMENSIONS,tests_not_human_Gold=True,decision_rules={'generic_solved':'one generic arm reaches >=0.8 complete_literal and >=0.9 atomic on applicable independent focuses in BOTH repeats; source-unsupported triple count no higher than B0; per-dimension failures disclosed','remaining_gap':'same source-grounded binding failure across repeats in >=2 independent documents after ruling out input/schema/parse/validation losses; indicates mechanism to investigate, NOT automatic novel-algorithm GO','default':'insufficient sample, U/disagreement or capacity limitations => necessity unproven; no new mechanism'},no_graph_publication=True))
    trial=[]
    for s in sources:
        source=source_view(s['target']);save(out/'inputs'/f'{s["page_key"]}.json',source)
        for arm in methods:
            for seed in SEEDS:trial.append(dict(trial_id=arm+'_'+s['page_key'].replace(':','_')+'_'+str(seed),arm=arm,page_key=s['page_key'],split=s['split'],seed=seed,input_sha256=digest(source)))
    trial=sorted(trial,key=lambda x:digest(['fixed-run-order',x['trial_id']]))
    save(out/'trials.jsonl',trial)
    paths=[Path(__file__),ROOT/'scripts/rp1_complex_binding_common.py',ROOT/'scripts/run_rp1_six_checks.py',ROOT/'scripts/run_targeted_triple_extraction.py',ROOT/'tests/unit/test_rp1_complex_binding_controlled.py',*sorted((ROOT/'src/research_point_1_graph_evidence').rglob('*.py'))]
    paths += [p for p in out.rglob('*') if p.is_file() and p.name!='freeze.json']
    save(out/'freeze.json',dict(git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},original_target_source='six_checks_final_v1_20261110/frequency/representation_targets.jsonl',target_ids=[t['target_id'] for t in targets],old_result_sha256={str(p.relative_to(ROOT)):sha(p) for p in SIX.rglob('*') if p.is_file()},teacher_sha256={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'data/kg/marine_pump/triples/KG_v1_validated').rglob('*') if p.is_file()}))
    print(canonical(dict(status='frozen_not_generated',targets=len(targets),development_pages=len(sources)-len(independent),independent_pages=len(independent),trials=len(trial))))

def verify(out):
    f=read(out/'freeze.json')
    for group in ['sha256','old_result_sha256','teacher_sha256']:
        for p,h in f[group].items():
            if sha(ROOT/p)!=h:raise ValueError('Changed frozen input '+p)

def preflight(out):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(MODEL,local_files_only=True,dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa').eval()
    text='Synthetic source: If the bearing is damp, inspect it before restart. Never lubricate while rotating. Return JSON {"order":"...","negation":"..."}.'
    inp=tok.apply_chat_template([dict(role='user',content=text)],add_generation_prompt=True,tokenize=True,return_tensors='pt').to('cuda')
    small={'type':'object','properties':{'order':{'type':'string'},'negation':{'type':'string'}},'required':['order','negation']}
    fn=build_transformers_prefix_allowed_tokens_fn(tok,JsonSchemaParser(small))
    with torch.inference_mode():ids=model.generate(inp,attention_mask=torch.ones_like(inp),max_new_tokens=96,prefix_allowed_tokens_fn=fn,do_sample=False,pad_token_id=tok.eos_token_id)
    result=tok.decode(ids[0,inp.shape[1]:],skip_special_tokens=True);strict_parse(result)
    save(out/'preflight.json',dict(model_path=str(MODEL),dtype='bfloat16',gpu=torch.cuda.get_device_name(0),synthetic_only=True,response=result,grammar_works=True))
    print('preflight passed')

def execute(out):
    verify(out)
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
    from jsonschema import Draft202012Validator
    cfg=read(out/'protocol.json');tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(MODEL,local_files_only=True,dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa').eval();methods=read(out/'methods.json');schema=read(out/'output_schema.json')
    pages={s['page_key']:s['target'] for s in read(out/'sources.jsonl')};screen=screen_from_archive(Archive());runtime=[]
    for trial in read(out/'trials.jsonl'):
        d=out/'runs'/trial['trial_id'];done=d/'result.json'
        if done.exists():continue
        if (d/'started.json').exists():raise ValueError('Uncertain interrupted trial; preserve and review before retry '+str(d))
        save(d/'started.json',dict(trial=trial,config_sha256=sha(out/'protocol.json')))
        source=read(out/'inputs'/f'{trial["page_key"]}.json');user=canonical(source)
        stages=2 if trial['arm']=='B3' else 1;used=0;output_used=0;draft=None;last='';meta=[];failed=None
        for stage in range(stages):
            messages=[dict(role='system',content=methods[trial['arm']]),dict(role='user',content=user)]
            if stage:
                messages[1]['content']+='\nDRAFT_UNTRUSTED\n'+draft+'\nReread the SAME original source. Recover omissions and correct unsupported claims. Return one complete replacement JSON, not a patch. Do not add information from outside this source.'
            ids=tok.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_tensors='pt').to('cuda');n=ids.shape[1]
            ceiling=cfg['draft_output_cap'] if stages==2 and stage==0 else cfg['final_recovery_output_cap'] if stages==2 else cfg['total_output_cap']
            limit=budget(used,n,min(ceiling,cfg['total_output_cap']-output_used),cfg['total_input_output_token_cap'],cfg['context_cap'])
            if limit<64:failed='insufficient_budget_or_context_no_source_clipping';break
            save(d/f'stage{stage+1}.request.json',dict(messages=messages,input_tokens=n,max_new_tokens=limit,seed=trial['seed']+stage*10000,constrained=trial['arm']!='B0',full_source_sha256=digest(source)))
            torch.manual_seed(trial['seed']+stage*10000);torch.cuda.manual_seed_all(trial['seed']+stage*10000);t=time.monotonic()
            fn=build_transformers_prefix_allowed_tokens_fn(tok,JsonSchemaParser(schema)) if trial['arm']!='B0' else None
            with torch.inference_mode():output=model.generate(ids,attention_mask=torch.ones_like(ids),max_new_tokens=limit,do_sample=True,temperature=cfg['temperature'],top_p=1.,prefix_allowed_tokens_fn=fn,pad_token_id=tok.eos_token_id,use_cache=True)
            generated=output[0,n:];m=len(generated);last=tok.decode(generated,skip_special_tokens=True);used+=n+m;output_used+=m
            eos=model.generation_config.eos_token_id;eos=eos if isinstance(eos,list) else [eos]
            finish='stop' if int(generated[-1]) in eos else 'length'
            info=dict(input_tokens=n,output_tokens=m,total_tokens=n+m,elapsed_seconds=time.monotonic()-t,finish_reason=finish)
            save(d/f'stage{stage+1}.response.json',dict(content=last,token_ids=generated.tolist(),**info));meta.append(info);draft=last
        errors=[];parsed=None;validation=[]
        try:
            if failed:raise ValueError(failed)
            if not meta or meta[-1]['finish_reason']!='stop':raise ValueError('final_output_truncated')
            parsed=strict_parse(last);errors=[e.message for e in Draft202012Validator(schema).iter_errors(parsed)]
            if len(parsed.get('triples',[]))>cfg['candidate_cap']:raise ValueError('candidate_cap_exceeded_no_drop')
            for i,r in enumerate(parsed.get('triples',[]),1):
                try:
                    normalized=normalize_model_candidate(r,page=pages[trial['page_key']]);adapter={**normalized,**{k:r[k] for k in ['conditions','polarity','modality'] if k in r}}
                    for k,v in dict(conditions=[],polarity='unspecified',modality='unspecified',scope='primary',applicability=pages[trial['page_key']]['applicability_scope']).items():adapter.setdefault(k,v)
                    result=legacy_rules(adapter,pages[trial['page_key']],screen.REGISTRY,screen.filter_flags)
                    validation.append(dict(index=i,normalized=normalized,legacy_result=result,raw_metadata_preserved_in_response=True))
                except Exception as e:validation.append(dict(index=i,normalization_error=type(e).__name__+': '+str(e),included=False))
        except Exception as e:failed=str(e)
        result=dict(trial=trial,used_total_tokens=used,used_output_tokens=output_used,calls=len(meta),stages=meta,failure=failed,schema_errors=errors,output=parsed,validation=validation,graph_modified=False)
        if used>cfg['total_input_output_token_cap'] or output_used>cfg['total_output_cap']:raise ValueError('budget exceeded')
        save(done,result);print(trial['trial_id'],used,'tokens',failed or 'saved',flush=True)
    verify(out);save(out/'generation_complete.json',dict(trials=len(read(out/'trials.jsonl')),all_completed=True,new_generator_calls=sum(read(p)['calls'] for p in (out/'runs').glob('*/result.json')),external_API_calls=0))

def evaluation(out):
    verify(out)
    if not (out/'generation_complete.json').exists():raise ValueError('generation incomplete')
    before=json.load(urllib.request.urlopen(JUDGE_URL+'/api/tags'));actual=next(x for x in before['models'] if x['name']==JUDGE)
    if actual['digest']!=read(out/'resources.json')['judge']['digest']:raise ValueError('judge identity changed')
    sources={s['page_key']:s for s in read(out/'sources.jsonl')};targets=read(out/'targets.jsonl');ind={s['page_key']:s for s in read(out/'independent/sources.jsonl')}
    private=[];requests={}
    for trial in read(out/'trials.jsonl'):
        r=read(out/'runs'/trial['trial_id']/'result.json');key=trial['page_key']
        focus=[dict(focus_id=t['target_id'],source_quotes=t['anchors']) for t in targets if t['page_key']==key] if trial['split']=='development' else [dict(focus_id=ind[key]['sample_id'],source_quotes=[ind[key]['focus_quote']])]
        # No meaning_zh, requirements, old judgments or arm identifiers reach
        # the independent reviewer. Source quotations are questions, not answers.
        for channel,value in [('raw',r['output'] if r['output'] is not None else {'triples':[],'unresolved':['No complete model JSON was returned.']}),('validated',validated_view(r))]:
            body=dict(source=source_view(sources[key]['target']),focus=focus,anonymous_output=value)
            rid='E'+digest(body)[:24];requests[rid]=dict(review_id=rid,body=body)
            private.append(dict(trial_id=trial['trial_id'],channel=channel,review_id=rid,split=trial['split']))
    save(out/'evaluation/private_mapping.jsonl',private)
    ordered=sorted(requests.values(),key=lambda x:digest(['blinded-order-20261110',x['review_id']]))
    save(out/'evaluation/blind_inputs.jsonl',ordered)
    for i,item in enumerate(ordered,1):
        rid=item['review_id'];p=out/'evaluation'/f'{rid}.json'
        if p.exists():continue
        start=out/'evaluation'/f'{rid}.started.json'
        if start.exists():raise ValueError('Uncertain evaluator attempt, no automatic retry '+rid)
        payload=dict(model=JUDGE,stream=False,think=False,format='json',messages=[dict(role='system',content=JUDGE_SYSTEM),dict(role='user',content=canonical(item['body']))],options=dict(temperature=0,seed=20261110,num_predict=4096,num_ctx=32768))
        save(start,dict(request_sha256=digest(payload),judge_digest=actual['digest']))
        try:
            raw=ollama('/api/chat',payload,timeout=1200);save(out/'evaluation'/f'{rid}.raw.json',raw)
            if not raw.get('done') or raw.get('done_reason')!='stop':raise ValueError('judge_truncated')
            value=strict_parse(raw['message']['content']);expected={x['focus_id'] for x in item['body']['focus']}
            if {x['focus_id'] for x in value['assessments']}!=expected:raise ValueError('incomplete_focus_assessment')
            n=len(item['body']['anonymous_output'].get('triples',[]));verdicts=value['relation_verdicts']
            if len(verdicts)!=n or {x['index'] for x in verdicts}!=set(range(1,n+1)):raise ValueError('incomplete_relation_audit')
            for a in value['assessments']:
                if any(a.get(d) not in ['S','P','N','U','NA'] for d in DIMENSIONS+['explicit_binding']):raise ValueError('bad_grade')
            save(p,dict(status='complete_AI_cross_evaluation',assessment=value,usage={k:raw.get(k) for k in ['prompt_eval_count','eval_count','total_duration']},judge_alias=JUDGE,judge_digest=actual['digest'],human_Gold=False))
        except Exception as e:
            save(p,dict(status='unassessed_failure',failure=type(e).__name__+': '+str(e),human_Gold=False))
        print('review',i,'/',len(ordered),rid,flush=True)
    save(out/'evaluation_complete.json',dict(reviews=len(ordered),independent_model=True,human_Gold=False));report(out)

def report(out):
    verify(out);mapping=read(out/'evaluation/private_mapping.jsonl') if (out/'evaluation/private_mapping.jsonl').exists() else [];by={(r['trial_id'],r['channel']):r['review_id'] for r in mapping};rows=[]
    for t in read(out/'trials.jsonl'):
        p=out/'runs'/t['trial_id']/'result.json'
        if not p.exists():continue
        r=read(p);rid=by.get((t['trial_id'],'raw'));e=read(out/'evaluation'/f'{rid}.json') if rid and (out/'evaluation'/f'{rid}.json').exists() else None
        row=dict(**t,tokens=r['used_total_tokens'],calls=r['calls'],failure=r['failure'],schema_errors=r['schema_errors'],candidates=len((r['output'] or {}).get('triples',[])),legacy_admitted=sum(bool(x.get('legacy_result',{}).get('included')) for x in r['validation']),review_status=e['status'] if e else 'pending')
        if e and e['status']=='complete_AI_cross_evaluation':
            admitted={v['index'] for v in r['validation'] if v.get('legacy_result',{}).get('included')}
            row.update(assessments=e['assessment']['assessments'],errors=sum(x['verdict']=='N' for x in e['assessment']['relation_verdicts']),uncertain_relations=sum(x['verdict']=='U' for x in e['assessment']['relation_verdicts']),raw_supported=sum(x['verdict']=='S' for x in e['assessment']['relation_verdicts']),supported_raw_rejected=sum(x['verdict']=='S' and x['index'] not in admitted for x in e['assessment']['relation_verdicts']))
        rid=by.get((t['trial_id'],'validated'));post=read(out/'evaluation'/f'{rid}.json') if rid and (out/'evaluation'/f'{rid}.json').exists() else None
        row['validated_review_status']=post['status'] if post else 'pending'
        if post and post['status']=='complete_AI_cross_evaluation':
            row.update(validated_assessments=post['assessment']['assessments'],validated_errors=sum(x['verdict']=='N' for x in post['assessment']['relation_verdicts']),validated_supported=sum(x['verdict']=='S' for x in post['assessment']['relation_verdicts']))
        rows.append(row)
    save(out/'comparison.jsonl',rows)
    summary={};targets={t['target_id']:t for t in read(out/'targets.jsonl')}
    for split in ['development','independent']:
        summary[split]={}
        for arm in ['B0','B1','B2','B3']:
            rs=[r for r in rows if r['split']==split and r['arm']==arm];dims={d:Counter() for d in DIMENSIONS+['explicit_binding']}
            main=Counter();aux=Counter()
            for r in rs:
                for a in r.get('assessments',[]):
                    for d in dims:dims[d][a[d]]+=1
                    (aux if a['focus_id'] in targets and targets[a['focus_id']]['scope']=='auxiliary_only' else main)[a['literal_complete']]+=1
            summary[split][arm]=dict(trials=len(rs),format_failures=sum(bool(r['failure']) for r in rs),evaluated_trials=sum(r['review_status']=='complete_AI_cross_evaluation' for r in rs),raw_candidates=sum(r['candidates'] for r in rs),legacy_admitted=sum(r['legacy_admitted'] for r in rs),tokens=sum(r['tokens'] for r in rs),calls=sum(r['calls'] for r in rs),source_errors=sum(r.get('errors',0) for r in rs),dimensions={d:dict(c) for d,c in dims.items()},core_literal=dict(main),auxiliary_literal=dict(aux))
    complete=(out/'evaluation_complete.json').exists() and len(rows)==len(read(out/'trials.jsonl')) and all(r['review_status']=='complete_AI_cross_evaluation' and r['validated_review_status']=='complete_AI_cross_evaluation' for r in rows)
    verdict='necessity_unproven_incomplete_evaluation'
    if complete:
        solved=[]
        for arm in ['B1','B2','B3']:
            good=True
            for seed in SEEDS:
                rs=[r for r in rows if r['split']=='independent' and r['arm']==arm and r['seed']==seed];aa=[a for r in rs for a in r.get('validated_assessments',[])];lc=sum(a['literal_complete']=='S' for a in aa)/max(1,sum(a['literal_complete']!='NA' for a in aa));at=sum(a['atomic']=='S' for a in aa)/max(1,sum(a['atomic']!='NA' for a in aa));err=sum(r.get('validated_errors',0) for r in rs);base=sum(r.get('validated_errors',0) for r in rows if r['split']=='independent' and r['arm']=='B0' and r['seed']==seed)
                good=good and lc>=.8 and at>=.9 and err<=base
            if good:solved.append(arm)
        verdict='generic_baselines_solve_do_not_add_special_algorithm' if solved else 'generic_baselines_not_demonstrated_sufficient_but_novel_algorithm_not_yet_justified'
    failures=[];stability=[]
    for r in rows:
        for channel in ['raw','validated']:
            for a in r.get('assessments' if channel=='raw' else 'validated_assessments',[]):
                if any(a[d] in ['P','N','U'] for d in DIMENSIONS):failures.append(dict(trial_id=r['trial_id'],channel=channel,split=r['split'],arm=r['arm'],**a))
    for split in ['development','independent']:
        for arm in ['B0','B1','B2','B3']:
            group=defaultdict(list)
            for r in rows:
                if r['split']==split and r['arm']==arm:
                    for a in r.get('validated_assessments',[]):group[a['focus_id']].append(dict(seed=r['seed'],**a))
            for focus,aa in group.items():stability.append(dict(split=split,arm=arm,focus_id=focus,repeats=len(aa),stable_literal=len({a['literal_complete'] for a in aa})==1,all_repeats_complete=len(aa)==len(SEEDS) and all(a['literal_complete']=='S' for a in aa),grades=[a['literal_complete'] for a in aa]))
    save(out/'failure_cases.jsonl',failures);save(out/'repeat_stability.jsonl',stability)
    save(out/'summary.json',dict(results=summary,evaluation_complete=complete,decision=verdict,decision_channel='actual validated payloads; NA excluded from applicable atomic/literal denominators, U and failed outputs never treated as S',graph_updated=False,old_AI_labels_not_Gold=True,limits='Six new source focuses, two repetitions, one independent reviewer model; not field/general population accuracy. Same resource ceilings are not identical realized costs.'))
    lines=['# RP1复杂语义绑定：四组受控基线','','T01–T17来自六项受控核查原清单；T01/T02/T16单列辅助语义。全部历史结果只读。','', '| 集合 | 组 | 完成试次 | 失败 | 已交叉评价 | 主候选 | 旧规则准入 | 核心完整S/P/N/U | 错误关系 | 总token | 调用 |','| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for split,arms in summary.items():
        for a,r in arms.items():lines.append('| '+' | '.join(map(str,[split,a,r['trials'],r['format_failures'],r['evaluated_trials'],r['raw_candidates'],r['legacy_admitted'],r['core_literal'],r['source_errors'],r['tokens'],r['calls']]))+' |')
    lines+=['','结论：`'+verdict+'`。','', '逐靶点结果及7维评价见comparison.jsonl；原提示、原始token、每阶段完整输入输出、校验、匿名评审及失败均保留。独立评价为另一实际权重模型的AI交叉评价，不是专家Gold。输出数量、JSON合法与字段齐全均不等于正确；文字完整与显式结构绑定分开报告。','', '复现：`prepare`只生成冻结包；`execute`实际7B生成；`evaluate`使用另一27B匿名评审；`report`仅复算报告。已完成阶段不覆盖重跑；任何不确定中断先审计日志，禁止自动有偿/资源重试。','', '没有证明通用方法足够，不自动推出新算法必要。7B容量、多语言能力、框架/输入/表示损失和单评审偏差必须先排除；不能据本次小样本宣称全语料召回或实际故障诊断精度。']
    save(out/'REPORT.md','\n'.join(lines)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','preflight','execute','evaluate','report','all']);ap.add_argument('--out',type=Path,default=OUT);args=ap.parse_args()
    stages=['prepare','preflight','execute','evaluate'] if args.stage=='all' else [args.stage]
    for stage in stages:globals()[stage](args.out.resolve())
