#!/usr/bin/env python3
"""Explicit AI editorial development ledger; NOT an autonomous repair algorithm.

Candidate-ID dispatch is intentional and disclosed. The reference file is never
used to generate a repaired assertion. No expert identities or labels are filled.
"""
import copy
import re
from rp1_offline_contract_v3 import *

PAGES={p['page_key']:p for p in rows(SOURCE/'pilot_sources.jsonl')}
PACKETS=rows(REVIEW/'arm_masked_review_packets.jsonl')
ARM={p['review_id']:p['arm'] for p in rows(REVIEW/'private_arm_mapping.jsonl')}
CAND={a['candidate_review_id']:(p,a) for p in PACKETS for a in p['assertions']}
LEDGER={}

def ids(v,nums):
    return [f'VR{v:02d}:A{n:03d}' for n in nums]
def snippets(page,*quotes):
    out=[]
    for q in quotes:
        w=bind(page,q)
        if w is None: raise ValueError(('unbound new source witness',page['page_key'],q))
        if w not in out: out.append(w)
    return out

def edit(cid,status,reason,patch=None,quotes=(),kernel=True,outcome='complete'):
    assert cid not in LEDGER,cid
    p,a=CAND[cid];page=PAGES[p['page_key']]
    raw={k:copy.deepcopy(v) for k,v in a.items() if k not in {'mechanical','candidate_review_id'}}
    after=copy.deepcopy(raw)
    if patch: after.update(copy.deepcopy(patch))
    if status=='unresolved': outcome='unresolved'
    original=bind(page,a['evidence_text'])
    ws=snippets(page,*quotes)
    if original and original not in ws: ws.insert(0,original)
    if not ws and status!='unresolved': raise ValueError(('no witness',cid))
    if patch and not original and ws: after['evidence_text']=ws[0]['text']
    # Every proposal includes the original page binding, without inventing boxes.
    if outcome!='unresolved':
        assert after.get('record_kind') or type_valid(after),(cid,'invalid repaired schema',after)
    LEDGER[cid]={
      'candidate_review_id':cid,'page_key':p['page_key'],'prompt_arm':ARM[p['review_id']],
      'reviewer':'same_assistant_AI_technical_development_review_not_blinded',
      'expert_review':'pending','original_sha256':object_sha(raw),'original':raw,
      'original_contract_status':status,'source_supported_knowledge_kernel':kernel,
      'reason_zh':reason,'source_page_sha256':p['source_page_sha256'],
      'source_witnesses':ws,'repair_kind':'AI_editorial_patch' if after!=raw else 'unchanged',
      'changes':{k:{'before':raw.get(k),'after':after.get(k)} for k in sorted(set(raw)|set(after)) if raw.get(k)!=after.get(k)},
      'proposal':after if outcome!='unresolved' else None,
      'proposal_status':outcome,'independent_postrepair_support_check':'pending',
    }

def group(v,nums,status,reason,patch=None,quotes=(),**kwargs):
    for cid in ids(v,nums): edit(cid,status,reason,patch=patch,quotes=quotes,**kwargs)
def aux_patch(a,kind,statement=None,**extra):
    return {'record_kind':kind,'statement_source':statement or a['evidence_text'], **extra}
def to_aux(v,nums,status,reason,kind='source_requirement',**extra):
    for cid in ids(v,nums):
        a=CAND[cid][1]
        edit(cid,status,reason,aux_patch(a,kind,**extra))
def patch_ins(v,n,h,ht,tail=None,rel='inspected_by',conditions=None,quotes=(),status='representation_error'):
    cid=ids(v,[n])[0];a=CAND[cid][1]
    patch={'head_surface':h,'head_type':ht,'relation':rel,'tail_surface':tail or a['tail_surface'],'tail_type':'InspectionAction'}
    if conditions is not None:patch['conditions']=conditions
    edit(cid,status,'根据源文检查宾语绑定受检对象；仪器、动作与设备不互换，保留启动时序。',patch,quotes)

def prepare_background():
    for n in range(1,9):
        cid=ids(2,[n])[0];a=CAND[cid][1]
        q=a['evidence_text'];page=PAGES['MP002:p0089']
        if n==6:q='Documents containing maintenance requirements for systems, equipment items or components are to be reviewed at least annually'
        if n==7:q='Task packaging reviews should be conducted periodically to evaluate the packaged maintenance intervals'
        edit(cid,'semantic_error' if n==8 else 'representation_error',
             '保留通用可靠性背景；趋势输入不是被趋势法诊断的故障；任务启动条件不能写成预防该任务。年/周期要求保留在独立证据中。',
             aux_patch(a,'background_statement',q,scope='background'),quotes=(q,))

def prepare_p15():
    group(1,[1,2,8,9,10,11,15,16,17],'complete','结构/运行适用关系可由本页原文支持；与核心诊断量分开。')
    group(10,[1,6,8,11,12,13,15,22,23],'complete','本页结构/运行关系；不计为核心诊断增量。')
    for v,ns in [(1,[3,4,5]),(10,[4,5,7])]:
        for cid in ids(v,ns):
            a=CAND[cid][1]
            patch=aux_patch(a,'maintenance_requirement',requirement='not_required',action='maintenance',modality='not_required')
            edit(cid,'representation_error','原响应已保留 negative，并非极性翻转；无需维护不是维护动作，也不等于禁止维护。',patch)
    shut='Before maintenance, confirm that the pump is shut off so as to avoid accident.'
    motor='The motor with a nozzle (including motor above 11kW) shall be lubricated with lubricant or similar high-temperature lithium base grease.'
    for v,ns in [(1,[6,7]),(10,[9,10])]:
        for cid in ids(v,ns):
            a=CAND[cid][1]
            patch={'conditions':a['conditions']+['Before maintenance: confirm that the pump is shut off','motor with a nozzle; including motor above 11kW'],
                   'applicability':a['applicability']+'; Motor bearing maintenance; motor with a nozzle'}
            edit(cid,'incomplete','补充维护前停机及 Motor bearing 段的带 nozzle 电机范围；including >11kW 不是仅限 >11kW。',patch,(shut,motor,'Motor bearing'))
    group(1,[12],'complete','冻液导致泵损坏，安装处可能冻结的条件已保存。')
    group(10,[3,17,19],'complete','检查停机或霜冻风险有明确源文/前提；这些是额外受支持条目，不从参考缺席推为错误。')
    to_aux(10,[2],'representation_error','60Hz 下性能改变属于运行规格，不能仅用 Symptom 标签变成故障。','operating_mechanism')
    to_aux(10,[14,16],'representation_error','输送液自动润滑/冷却是机理，不是操作者维护步骤。','operating_mechanism')
    for v,n in [(1,13),(10,18)]:
        cid=ids(v,[n])[0];a=CAND[cid][1]
        edit(cid,'incomplete','添加防冻剂为保养要求，补维护停机，保留可能冻结及未定量 proper quantity。',
             {'head_surface':'pump','head_type':'Equipment','relation':'maintained_by','conditions':a['conditions']+['Before maintenance: confirm that the pump is shut off']},(shut,))
    drain='If the pump is out of service during a frost period, you should drain the liquid inside it so as to avoid any damage to the pump.'
    path='The liquid inside the pump may be drained via the water injection hole at the pump head and the drainage hole at bottom.'
    safety='Pay attention to safety of persons and objects during water drainage (cold or hot).'
    for v,n in [(1,14),(10,20),(10,21)]:
        edit(ids(v,[n])[0],'semantic_error' if n==21 else 'representation_error',
             '排液是泵保养动作，不是检查液体；补霜冻停用、停机和排液通道，不将危险工况作为被缓解的设备。',
             {'head_surface':'pump','head_type':'Equipment','relation':'maintained_by','tail_surface':'drain the liquid via the water injection hole at the pump head and the drainage hole at bottom','tail_type':'MaintenanceAction','conditions':['pump out of service during a frost period','Before maintenance: confirm that the pump is shut off','Pay attention to safety of persons and objects during water drainage (cold or hot)'],'modality':'recommended'},(shut,drain,path,safety))
    cid=ids(10,[24])[0];a=CAND[cid][1]
    edit(cid,'semantic_error','再次使用是操作目的，不是要预防的事件；保留为排液后恢复运行程序。',
         aux_patch(a,'operating_procedure',conditions=['recommissioning after the preceding frost-period drainage procedure']),
         (drain,'When using the pump once again, firstly tighten the vent plug and drainage valve.'))
    for n,cond in [(25,'when replacing the drainage valve'),(26,'when installing the drainage valve')]:
        cid=ids(10,[n])[0];a=CAND[cid][1]
        edit(cid,'semantic_error','更换/安装的目的不得当作被预防事件；改为排水阀检修程序，then 顺序及停机前提保留。',
             {'head_surface':'drainage valve','head_type':'Component','relation':'maintained_by','conditions':[cond,'Before maintenance: confirm that the pump is shut off'],'procedure_sequence_preserved':True},(shut,))

def prepare_p12():
    for v in (5,11):
        cid=ids(v,[1])[0];a=CAND[cid][1]
        edit(cid,'semantic_error','near 不等于 located_in；one of 表示任一条件，不能暗作三个同时满足。',
             aux_patch(a,'installation_requirement',condition_operator='OR',location_relation='near'))
        group(v,[2,3,4,5],'complete','干运转损伤/发生位置及部件归属有源文；复合损伤条目在覆盖中最多分配一项参考。')
    group(5,[7],'complete','单相电机有内部热保护器，原条件已存。')
    group(11,[6,8,9,10,11,12],'complete','类型、检查对象及 before startup 条件已在 applicability 中，不因 conditions 空而误判遗漏。')
    to_aux(5,[6],'semantic_error','禁止未灌水排气启动，不可逆写动作 prevented_by 干运转。','operating_prohibition',requirement='prohibited_before_filling_and_venting')
    to_aux(5,[8,9],'representation_error','电气安装配置与接地要求单列，不强写为检修保养。','electrical_requirement')
    to_aux(11,[7],'representation_error','provided with 三相保护器不证明一定装在电机内部；保留安装前配置要求。','electrical_requirement')
    for n,h,ht,tail in [(10,'foot bolts','Component','check foot bolts are tightened'),(11,'pump','Equipment','check full of water'),(12,'pump','Equipment','check direction of rotation'),(13,'valves on inlet pipes','Component','check completely opened')]:
        patch_ins(5,n,h,ht,tail,conditions=['before pump startup'],quotes=('7.2 CHECK BEFORE PUMP STARTUP',))
    for v,n in [(5,14),(11,13)]:
        patch_ins(v,n,'working pressure','SignalFeature','check working pressure using an installed pressure meter','diagnosed_by',['before pump startup','if a pressure meter is installed'],('7.2 CHECK BEFORE PUMP STARTUP',),status='semantic_error')
    to_aux(5,[15],'representation_error','启动后慢开出口阀是运行操作，保留 after 覆盖章节 before 的局部时序。','operating_procedure')
    to_aux(5,[16,17],'semantic_error','烫伤/物料受损与热水工况方向倒置，保留排气安全警示，不补造设备故障边。','safety_requirement')
    group(11,[14],'unresolved','源文通过 pressure switch 检查电流的方法有歧义；不凭工程常识代改。')

def prepare_p4():
    group(8,[1,2,9,13,17,18,20,21,22,23],'complete','结构、真实检查或带可能性的发生/后果关系由源文支持；演化关系不自动当 causes 参考匹配。')
    group(6,[1,2,8,10,17,20,21,23,24],'complete','对象、方向和原显式条件有支持；风险关系允许条件式风险模态，不等价确定损坏。')
    for v in (6,8):
        to_aux(v,[3],'representation_error','液体用作冷却介质，不是 liquid causes coolant 的因果关系。','operating_mechanism')
    to_aux(6,[4],'semantic_error','作为冷却介质不证明轴封结构包含 coolant；保留功能原文。','operating_mechanism')
    group(8,[4],'unresolved','不得未灌液启动的警告未直接指明 damage to shaft seal，具体损伤目标是推断；保留未决。')
    group(6,[5,6],'unresolved','本页明确禁止未灌液/干转，具体 shaft seal/pump 损伤端点未直接给出，不以常识补真值。')
    to_aux(8,[5],'representation_error','negative occurs_at 不能表示不得干转；这是禁止运行要求。','operating_prohibition',requirement='prohibited')
    warning='For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps). Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.'
    for v,ns in [(8,[6,7]),(6,[7])]:
        for cid in ids(v,ns):
            edit(cid,'incomplete','最大允许值不是危险发生条件；补 otherwise 的超限逻辑，5分钟或80°C任一越界，不改成AND。',
                 {'conditions':['closed discharge valve operation','duration exceeds 5 minutes OR liquid temperature exceeds 80°C (standard pumps)'],'modality':'risk'},(warning,))
    for v,n in [(8,8),(6,9)]:
        edit(ids(v,[n])[0],'representation_error','安全装置安装用于降低前述损坏/蒸汽爆炸风险；保留无人监控与 recommended，不声称确定消除风险。',
             {'head_surface':'damage or steam-explosion risk during closed-discharge operation','head_type':'Risk','relation':'prevented_by','conditions':['pump is not monitored','closed discharge valve operation'],'modality':'recommended'},
             (warning,'If the pump is not monitored, the installation of a safety device is recommended.'))
    for v,n in [(8,10),(6,11)]:
        to_aux(v,[n],'representation_error','泄压阀装置及预设压力保护功能不是维护动作，保留功能与阈值未给定。','protective_function')
    to_aux(8,[11],'representation_error','仅有维护章节交叉引用，尚无具体维护动作。','cross_reference')
    to_aux(6,[12],'representation_error','仅有维护章节交叉引用，尚无具体维护动作。','cross_reference')
    to_aux(6,[13],'semantic_error','禁止拆除/重调应为 prohibited 要求，不是缓解动作本身。','maintenance_requirement',requirement='prohibited')
    patch_ins(8,12,'shaft','Component',status='semantic_error')
    patch_ins(6,14,'shaft','Component')
    patch_ins(6,15,'pump casing','Component',quotes=('Before starting the pump check that','- the pump casing is filled with liquid.'))
    rotation='Start the pump for a moment to check the direction of rotation. If the direction is correct (i.e. in the direction of the arrow), the pump may be started.'
    for v,n in [(8,14),(6,16)]:
        patch_ins(v,n,'pump','Equipment','start briefly to check direction of rotation',conditions=['brief check before continued startup','continue only when direction agrees with arrow'],quotes=(rotation,))
    chain='A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.'
    for v,ns in [(8,[15,16]),(6,[18,19])]:
        for cid in ids(v,ns):
            edit(cid,'representation_error','原文为低扬程→流量增加→功耗/可能汽蚀；保存相邻因果边，不将传递路径冒作直接边。',
                 {'head_surface':'increased quantity of liquid delivered','head_type':'Cause','conditions':['considerably smaller delivery head than expected']},(chain,))
    erosion='In the pump the impeller may show signs of heavy erosion caused by cavitation (corrosion) which may at times render an impeller unfit for use in a very short time.'
    for v,n in [(8,19),(6,22)]:
        edit(ids(v,[n])[0],'incomplete' if v==8 else 'representation_error','源文明说 erosion caused by cavitation；保留 impeller 和 may，不当必然，也不把表现关系当因果边。',
             {'relation':'causes','tail_surface':'heavy erosion of the impeller','tail_type':'FaultMode','modality':'possible','conditions':['in the pump impeller']},(erosion,))
    edit(ids(6,[25])[0],'representation_error','侵蚀发生于弯管和阀门有支持；发生位置关系的主体需为故障/机理而非 Symptom。',{'head_type':'FaultMode'})
    for v,n in [(8,24),(8,26),(6,27)]:
        group(v,[n],'unresolved','流量、功率、电流、压差和泵曲线的联合测定句法尚未裁定；不把缺失测量链强行补全。')
    for v,n in [(8,25),(6,26)]:
        patch_ins(v,n,'power consumption of the pump','SignalFeature','measuring current intensity of the connected motor','diagnosed_by',['after start-up; example method, not accuracy guarantee'],
                  ('Therefore, after start-up, it is necessary to check either the quantity of liquid delivered or the power consumption of the pump e.g. by measuring the current intensity of the connected motor.',))
    to_aux(8,[27],'representation_error','仅指向未在本页给出的 fault-finding list；保持交叉引用，不充作具体诊断方法。','cross_reference')
    to_aux(6,[28],'representation_error','仅指向未在本页给出的 fault-finding list；保持交叉引用，不充作具体诊断方法。','cross_reference')

def program_segments(page):
    text=page['page_text']
    hs=list(re.finditer(r'7\.6\.[4-8] [^\n]+',text));result=[]
    footer=text.find('FRE/EN (2502)')
    for i,h in enumerate(hs):
        end=hs[i+1].start() if i+1<len(hs) else footer if footer>=0 else len(text)
        chunk=text[h.end():end]
        ms=list(re.finditer(r'(?m)^\s*([1-7])\s+(?=(?:Place|For|Push|Put|Remove|Bearing|Disassemble|Pull|Slide|Degrease|Tap|Loosen|Clean|Fit|Tighten)\b)',chunk))
        for j,m in enumerate(ms):
            begin=h.end()+m.end();finish=h.end()+(ms[j+1].start() if j+1<len(ms) else len(chunk))
            body=text[begin:finish].strip()
            result.append({'section':flat(h.group()),'step':int(m.group(1)),'start':begin,'end':finish,'body':body})
    return result

def prepare_freflow():
    page=PAGES['MP015:p0039'];segments=program_segments(page)
    assert len(segments)==22,len(segments)
    for v in (4,12):
        packet=next(p for p in PACKETS if p['review_id']==f'VR{v:02d}')
        for a in packet['assertions']:
            cid=a['candidate_review_id'];n=int(cid[-3:])
            if (v==4 and n in [11,12]) or (v==12 and n==6):
                edit(cid,'unresolved','1860 在相邻程序同时称 nut/key，保留原文不自行改件号/对象；等待部件图或专家裁定。');continue
            if v==4 and n in [5,18]:
                section='7.6.4' if n==5 else '7.6.6'
                head='impeller bolt and spring washer (1825)' if n==5 else 'impeller nut or impeller bolt (1820)'
                edit(cid,'representation_error','chapter 10 是紧固力矩的外部规范引用，Standard 不能作为该关系主体；未编造力矩数值。',
                     {'head_surface':head,'head_type':'Component','conditions':[section+' assembly; torque value must be read from chapter 10']});continue
            if v==4 and n==20:
                edit(cid,'complete','Back Pull Out 拆除后耐磨板可拆的高层前提有原文；不当成已包含所有螺钉/刀片步骤。');continue
            w=bind(page,a['evidence_text']);assert w and w['kind']=='page_span',cid
            hits=[s for s in segments if s['start']<=w['start']<s['end']]
            assert len(hits)==1,(cid,hits)
            s=hits[0];cs=[s['section'],f"source procedure step {s['step']}; previous applicable steps/order retained; this is not a complete procedure"]
            if s['section'].startswith('7.6.7'):
                cs.append('after disassembly of the Back Pull Out unit; item numbers refer to figure 55')
            patch={'relation':'maintained_by','tail_type':'MaintenanceAction','tail_surface':flat(s['body']),
                   'conditions':a['conditions']+cs,'applicability':page['applicability_scope']+'; FreFlow; '+s['section'],
                   'procedure_step':{'section':s['section'].split()[0],'ordinal':s['step'],'complete_procedure':False}}
            qs=[s['section'],s['body']]
            if s['section'].startswith('7.6.7'):qs.append('After disassembly of the Back Pull Out unit the wear plate can be removed. The item numbers refer to figure 55.')
            edit(cid,'representation_error' if v==4 and n==2 else 'incomplete',
                 '从实际章节和编号步骤补全拆装范围、步骤次序、材料/轴承架及步骤内条件；动作从该候选自己的源文段取，不从参考复制。原 location 只保留了局部位置，现另存操作边。',patch,qs)

def prepare_bearings():
    page=PAGES['MP018:p0026']
    exception='(Moderate discoloration of balls and races not a reason for discard).'
    for v in (3,7):
        packet=next(p for p in PACKETS if p['review_id']==f'VR{v:02d}')
        for a in packet['assertions']:
            n=int(a['candidate_review_id'][-3:]);patch={'scope':'primary','applicability':page['title']+'; '+page['pump_type']+'; '+page['service']+'; '+page['applicability_scope']}
            reason='依据泵专用手册→轴承维护表的局部范围链统一继承泵型；不称船舶现场特异性，不把范围重分算新抽取。'
            qs=['BEARING DEFECTS']
            status='complete'
            if a['relation']=='causes':qs.append('PROBABLE CAUSE')
            if a['relation']=='manifests_as' and a['modality']=='probable':
                status='representation_error';patch['modality']='descriptive';reason+=' PROBABLE CAUSE 仅辖原因列，表现列的描述模态单独保留。';qs.append('APPEARANCE')
            if n in [23,24]:
                patch['related_negative_requirement']={'subject':'moderate discoloration of balls and races','requirement':'not_sufficient_reason_for_discard'}
                qs.append(exception)
                reason+=' 变色的负向废弃依据以独立要求附存，不冒作原因成立的前提。'
            if v==7 and n==30:
                status='incomplete';patch['conditions']=['bearing defect found','moderate discoloration of balls and races alone is not a reason for discard'];qs.append(exception)
                reason+=' 全局更换标题保留例外；不从此条扩生成六条已匹配的具体更换边。'
            edit(a['candidate_review_id'],status,reason,patch,qs)

def reference_overlay():
    op={'MP004:p0010:V21:001','MP007:p0012:V21:011','MP007:p0015:V21:006'}
    undecided={'MP004:p0010:V21:014','MP015:p0039:V21:010','MP015:p0039:V21:011'}
    out=[]
    for ref in rows(SOURCE/'page_reference_v2_1.jsonl'):
        kind='operating_sidecar' if ref['reference_id'] in op else 'unresolved' if ref['reference_id'] in undecided else 'core'
        r={'reference_id':ref['reference_id'],'page_key':ref['page_key'],'v21_reference_unchanged':ref,'v3_evaluation_channel':kind,'expert_review':'pending','coverage_capacity':'one candidate per one full reference',
           'v3_note_zh':'按源文对象、方向、条件与模态匹配；原参考总账保留。'}
        if kind=='operating_sidecar':r['v3_note_zh']='启动/恢复运行操作单列，不能自动当检修保养；不以移出核心掩盖遗漏。'
        if kind=='unresolved':r['v3_note_zh']='源句测定关系或1860部件命名未决，不能作为确定覆盖分母。'
        if ref['page_key']=='MP018:p0026':
            r['v3_note_zh']+=' 泵型范围采用手册局部继承；适度变色例外约束报废要求，不是润滑导致变色的因果前提。'
        if ref['page_key']=='MP004:p0010' and ref['reference_id'][-3:] in ['002','003']:
            r['v3_note_zh']+=' risk 模态 causes 与同对象 increases_risk_of 允许等价；不允许必然损坏。'
        out.append(r)
    assert sum(x['v3_evaluation_channel']=='core' for x in out)==79
    return out

# Matching seeds are technical annotations, never read by the source repair functions.
def match_candidates():
    M={}
    def add(page,vs,left,right):
        assert len(left)==len(right)
        for i,(l,r) in enumerate(zip(left,right),1):
            rid=f'{page}:V21:{i:03d}'
            for arm,v,ns in [('E0',vs[0],l),('E1',vs[1],r)]:
                if ns is None:ns=[]
                if isinstance(ns,int):ns=[ns]
                M[(rid,arm)]={'reference_id':rid,'prompt_arm':arm,'candidate_review_ids':ids(v,ns),'auxiliary_locations':[],
                              'relation_equivalence':'same_direct_relation_required','annotation_kind':'AI_technical_matching_not_independent_expert'}
    add('MP004:p0010',(8,6),[None,6,7,8,12,13,14,None,15,16,19,21,25,[24,26]],
        [None,7,8,9,14,15,16,17,18,19,22,24,26,27])
    add('MP007:p0012',(5,11),[2,2,10,11,None,12,None,None,13,14,15],
        [2,2,8,9,None,10,11,11,12,13,None])
    add('MP007:p0015',(1,10),[6,7,13,12,14,None,None,None],
        [9,10,18,17,[20,21],24,25,26])
    add('MP015:p0039',(12,4),[1,3,2,4,None,None,None,None,5,None,6,None,None,None,7,8,None,None,9,11,None,12],
        [1,2,3,4,6,7,8,9,10,11,12,13,14,15,16,17,19,21,22,23,24,25])
    bt=[3,4,2,30,7,8,6,30,11,12,13,10,30,16,17,15,30,20,21,19,30,24,23,27,28,29,26,30,4,2]
    add('MP018:p0026',(7,3),bt,[None if n==30 else n for n in bt])
    def loc(page,n,arm,review,field,index):M[(f'{page}:V21:{n:03d}',arm)]['auxiliary_locations'].append(f'{review}:{field}:{index:03d}')
    for arm,v in [('E0',8),('E1',6)]:loc('MP004:p0010',1,arm,f'VR{v:02d}','unresolved',1)
    loc('MP007:p0012',11,'E1','VR11','auxiliary',5)
    loc('MP007:p0015',6,'E0','VR01','auxiliary',2)
    for n in [7,8]:loc('MP007:p0015',n,'E0','VR01','auxiliary',3)
    for n in [4,8,13,17,21,28]:
        loc('MP018:p0026',n,'E1','VR03','auxiliary',1)
        M[(f'MP018:p0026:V21:{n:03d}','E0')]['relation_equivalence']='generic_replacement_only_partial'
    for arm in ('E0','E1'):
        for n in [29,30]:M[(f'MP018:p0026:V21:{n:03d}',arm)]['relation_equivalence']='embedded_text_only_partial'
        for n in [2,3]:M[(f'MP004:p0010:V21:{n:03d}',arm)]['relation_equivalence']='risk_causes_equivalent_increases_risk_of'
        M[('MP007:p0015:V21:004',arm)]['relation_equivalence']='risk_causes_equivalent_increases_risk_of'
    assert len(M)==170
    return sorted(M.values(),key=lambda x:(x['reference_id'],x['prompt_arm']))

def main():
    prepare_background();prepare_p15();prepare_p12();prepare_p4();prepare_freflow();prepare_bearings()
    assert set(LEDGER)==set(CAND),(set(CAND)-set(LEDGER),set(LEDGER)-set(CAND))
    write(OUT/'candidate_adjudications.jsonl',[LEDGER[k] for k in sorted(LEDGER)])
    write(OUT/'reference_overlay.jsonl',reference_overlay())
    write(OUT/'reference_match_annotations.jsonl',match_candidates())
    aux=[]
    for p in PACKETS:
        for kind in ['auxiliary','unresolved']:
            for i,item in enumerate(p[kind],1):
                aux.append({'location':f"{p['review_id']}:{kind}:{i:03d}",'page_key':p['page_key'],'prompt_arm':ARM[p['review_id']], 'original':item,'preserved_only_not_added_to_233_candidate_pool':True})
    write(OUT/'original_response_sidecars.jsonl',aux)
    # No aggregate effect metrics are computed until this annotation/code freeze exists.
    paths=[OUT/'candidate_adjudications.jsonl',OUT/'reference_overlay.jsonl',OUT/'reference_match_annotations.jsonl',OUT/'original_response_sidecars.jsonl',
           ROOT/'docs/research/RP1_OFFLINE_CONTRACT_V3_PROTOCOL_20261002.md',Path(__file__),ROOT/'scripts/rp1_offline_contract_v3.py',
           SOURCE/'pilot_sources.jsonl',SOURCE/'page_reference_v2_1.jsonl',REVIEW/'arm_masked_review_packets.jsonl',REVIEW/'mechanical_checks_corrected.jsonl']
    write(OUT/'adjudication_freeze.json',{'stage':'AI annotations frozen before aggregate offline arm execution; development data already inspected',
         'sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},'extra_API_calls':0,'expert_review':'pending','holdout_contents_read':False})
    print('233 explicit source adjudications; 85 reference overlay entries; 170 technical matching entries; expert queues untouched')

if __name__=='__main__':main()
