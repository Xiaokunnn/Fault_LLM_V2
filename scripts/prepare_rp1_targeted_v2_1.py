#!/usr/bin/env python3
"""Reproduce the fixed, provisional AI development annotations; never overwrite differing artifacts."""
import copy,hashlib,json,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
V1=ROOT/'results/experiments/research_point_1/loss_page_audit_v1'
V2=ROOT/'results/experiments/research_point_1/scope_repair_v2'
OUT=ROOT/'results/experiments/research_point_1/adjudication_targeted_v2_1'
def rows(p): return [json.loads(l) for l in p.read_text().splitlines()]
def save(name,x):
 content=(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in x) if name.endswith('.jsonl') else json.dumps(x,ensure_ascii=False,indent=2)+'\n')
 target=OUT/name
 if target.exists():
  assert target.read_text()==content,('Refuse to overwrite differing existing artifact',name)
  return
 with target.open('x',encoding='utf-8') as f:f.write(content)
def pagekey(p):return f"{p['doc_id']}:p{p['pdf_page_number']:04d}"
def span(p,a,b=None):
 text=p['page_text']; pos=[i for i,c in enumerate(text) if not c.isspace()]; flat=''.join(text[i] for i in pos)
 aa=''.join(a.split()); start=flat.find(aa)
 assert start>=0,(pagekey(p),a)
 assert flat.find(aa,start+1)<0,(pagekey(p),'ambiguous',a)
 end=start+len(aa)
 if b:
  bb=''.join(b.split()); stop=flat.find(bb,end);assert stop>=0,(pagekey(p),b);end=stop+len(bb)
 i,j=pos[start],pos[end-1]+1
 return {'kind':'page_span','start':i,'end':j,'text':text[i:j]}
pack={x['audit_id']:x for x in rows(V1/'record_review_packets.jsonl')}
second={x['audit_id']:x for x in rows(V2/'second_opinion/adjudication_packets.jsonl')}
pages={pagekey(x['page']):x['page'] for x in pack.values()}
selected=['MP002:p0089','MP004:p0010','MP007:p0012','MP007:p0015','MP015:p0039','MP018:p0026']
assert len(selected)==len(set(selected))==6
holdout=rows(V2/'holdout_manifest.jsonl');holdout_keys={x.get('page_key',f"{x.get('doc_id')}:p{x.get('pdf_page_number',0):04d}") for x in holdout}
assert not set(selected)&holdout_keys
# All judgments are source-relative AI technical overlays, never expert adjudication.
specs=[
('R021','qualifiers_required','primary','incomplete_method','测电流不能在当前表述中单独替代流量测定；下一句还要求压差读数与泵特性。保留整段联合方法，不把电流单独视为充分方法。','组合方法中电流对应流量还是功率的语法仍可交由专家确认。','Therefore, after start-up, it is necessary','the characteristics of the pump.'),
('R087','granularity_repair','primary','procedure_heading','维修章节明确包含泵/轴封拆解，不能说源文没有维护依据；但标题不足以成为具体原子动作，需拆成有顺序、部件号和章节范围的步骤。','不得把每一步都无条件作用于轴封；图示部件绑定仍需专家确认。','5.3 Dismantling of pump/shaft seals','casing (29)'),
('R010','background_and_type_mismatch','background','non_fault_target','原文确实要求在失效年龄数据不足或使用假设数据时实施寿命探索任务；它是可靠性分析方法，不是泵故障原因及其维修措施。保留背景知识，不发布为主任务 Cause→mitigated_by。','背景知识有用性不等于核心故障知识覆盖。','17 Age Exploration Tasks','updating the analysis.'),
('R038','relation_mismatch','primary','parameter_source_not_inspection','铭牌提供额定电流参数来源；没有实际检测动作，不能发布为 diagnosed_by。作为参数来源辅助事实保留。','可用于判断额定范围的辅助信息，不由此产生故障诊断真值。','3.4 RATED CURRENT','protect the motor.'),
('R047','qualifiers_required','primary','material_and_assembly_scope','原文支持涂 Loctite 572，但限定在叶轮装配、轴承架1、青铜或不锈钢泵，为隔离容差环与液体。原记录省掉限定，需条件化修复。','不迁移到其他材料、其他轴承架或所有泵。','7.6.4 Assembly of the impeller, bearing bracket 1','rearmost part of the tolerance ring'),
('R009','background_and_type_mismatch','background','hardware_not_action','vibration taps 是设计中预留的振动测量接口示例，本段没有把接口名称定义成检查动作；一般旋转设备背景不能直接实例化为泵诊断。','不否认该硬件可支持监测；实际方法需另有源文。','v) Definition of Required Maintenance Tasks.','risk-based inspection.'),
('R004','outside_primary_scope','out_of_scope','engine_system_context','瞬态分析与突发失效事件的关系有明确原文；本段处在发动机/系统监测语境，未说明泵应用。不能据此判为凭空捏造，也不能计入泵主任务覆盖。','可另行保留一般分析知识，泵应用映射未证实。','At times, transient analyses are performed','operation outside of predetermined parameters.'),
('R037','polarity_mismatch','primary','negative_requirement','原文明确为无喷嘴电机无需维护。原 maintained_by 正向维护关系误表极性；保留负向维护要求，不生成维护动作。','nozzle 原文原样保留，不自行修正译名。','Motor bearing','lubricate before starting the motor.'),
('R014','outside_primary_scope','out_of_scope','propulsion_shafting','原文有挠度/间隙检查，但属于推进轴系，并且包含临时支撑、同时检查、停坞/下水条件和容差。排除于泵主任务，不宣称原文虚假。','原文 +0.1 mm 按原样留存，不自行改成 ±0.1 mm。','11.1.2(d) Sag and Gap Verification','corresponding calculated values.'),
('R039','qualifiers_required','primary','heading_and_interrogative','启动前检查标题赋予后续项目检查动作语义。If ... or not 是“是否”的嵌入问句，不是条件前提；规范为“启动前检查进口阀是否全开”。','旧关键词筛查可能误报，尚未据此统计总体误拒率或修改旧规则。','7.2 CHECK BEFORE PUMP STARTUP','The outlet valve shall be opened slowly after the pump is started up.'),
('R063','qualifiers_required','primary','table_header_modality','同一行明确把轴不对中列为保持架破裂的可能原因；需保存 PROBABLE CAUSE 表头与轴承/泵型范围。既不能升级为必然原因，也不能从表头缺失的短引用断定没有因果支持。','需要同时复核表头和行；不能只靠端点共现。',None,None),
('R015','qualifiers_required','primary','alarm_location_and_scope','高位舱底报警检测可能进水有原文支持，且直接关联消防泵/海底门舱保护，应按 v2 的直接关联保护范围保留；不是把所有消防系统知识纳入。必须保留消防泵在机舱外及舱室配置条件。','区分同舱且海底门阀锁开、不同舱两种配置，不泛化为全船通用报警规则。','ix) Starting of a fire pump located outside','centralized control station.'),
('R033','granularity_repair','primary','bundled_inspection_action','启动检查确实要求确认旋转方向及无异常声振；这是检查动作，不足以推断唯一故障原因。原尾实体合并两个目标，拆为泵旋向检查及异常声振检查，保留启动阶段。','不把检查是否有异常声振误说成诊断异常的原因；不是无源文支持。','Before startup','the installation')]
adjud=[]
for rid,decision,scope,problem,reason,pending,a,b in specs:
 p=pack[rid]['page'];r=pack[rid]['record'];s=second[rid]; assert not s['agreement']
 if rid=='R063':
  table=p['tables'][0]; witnesses=[{'kind':'native_table_cells','table_id':table['table_id'],'row_id':table['rows'][3]['row_id'],'cells':copy.deepcopy(table['rows'][0]['cells']+table['rows'][3]['cells'])}]
 else:witnesses=[span(p,a,b)]
 adjud.append({'audit_id':rid,'page_key':pagekey(p),'old_triple_id':r['triple_id'],'old_candidate':{k:r.get(k) for k in ['head','head_type','relation','tail','tail_type','evidence_text','decision']},'first_pass_label':s['first_pass_label'],'second_opinion_label':s['second_opinion_label'],'v2_technical_resolution':decision,'scope':scope,'issue':problem,'reason_zh':reason,'remaining_expert_question_zh':pending,'source_page_sha256':p['page_text_sha256'],'document_sha256':p['document_sha256'],'source_witnesses':witnesses,'reviewer':'Codex assistant','review_status':'provisional_ai_technical_review','expert_adjudication':'pending','automatic_qualification':False})
save('dispute_resolutions.jsonl',adjud)
save('adjudication_sources.jsonl',[{'page_key':k,**pages[k]} for k in sorted({x['page_key'] for x in adjud})])
save('pilot_sources.jsonl',[{'page_key':k,**pages[k]} for k in selected])
save('pilot_page_manifest.jsonl',[{'page_key':k,'source_page_sha256':pages[k]['page_text_sha256'],'document_sha256':pages[k]['document_sha256'],'source':'previously_read_record_audit_development_page','purpose':purpose,'independent_test':False} for k,purpose in zip(selected,['background_scope_negative_control','combined_measurement_and_operating_conditions','heading_inheritance_and_startup_checks','negative_maintenance_and_frost_conditions','material_and_bearing_bracket_conditioned_actions','table_row_binding_and_probable_cause'])])
refs=[];aux=[]
def atom(k,h,r,t,ht,tt,conditions,modality,a,b=None,polarity='positive',note=''):
 p=pages[k];x={'reference_id':f'{k}:V21:{1+sum(y["page_key"]==k for y in refs):03d}','page_key':k,'head':h,'head_type':ht,'relation':r,'tail':t,'tail_type':tt,'conditions_zh':conditions,'modality':modality,'polarity':polarity,'scope':'primary','applicability_scope':p['applicability_scope'],'source_page_sha256':p['page_text_sha256'],'document_sha256':p['document_sha256'],'evidence':[span(p,a,b)],'annotation_note_zh':note,'expert_review':'pending','reference_status':'provisional_ai_development_reference'};refs.append(x);return x

def extra(k,text,why,a,b=None):
 p=pages[k];aux.append({'item_id':f'{k}:AUX:{1+sum(y["page_key"]==k for y in aux):03d}','page_key':k,'statement_zh':text,'exclusion_from_primary_core':why,'evidence':[span(p,a,b)],'source_page_sha256':p['page_text_sha256'],'expert_review':'pending'})
# MP004 p10: full-page source inventory; atomic split retains shared conditions.
k='MP004:p0010';eq='Equipment';co='Component';act='MaintenanceAction';inspect='InspectionAction'
atom(k,'pump casing','maintained_by','Remove the plug, fill with cold liquid and refit the plug',co,act,['SA 型自吸离心泵启动灌液程序；动作顺序保持'],'required','A self-priming centrifugal pump','ready for service.')
extra(k,'灌注液还用于冷却轴封；不得未灌液启动或干运转。','作用/禁止运行要求不强行映射为维护动作','The liquid also serves as coolant','never run dry.')
for event in ['damage to the pump','steam explosion']:
 atom(k,'operation against closed discharge valve beyond the allowed limits','causes',event,'OperatingCondition','Risk',['标准泵；关排出阀运行仅短时，最多5分钟且最高80°C；超出该限制的风险，不将两限制改成必须同时超限'],'risk','For safety reasons the pump','steam explosion.')
atom(k,'unintentional operation','prevented_by','installation of a safety device','Risk',act,['泵无人监控时；源文仅建议；安全装置未指明型号'],'recommended','For safety reasons the pump','safety device is recommended.',note='装置针对前文关排出阀运行风险；unintentional operation 是下一段术语，不以该词改变风险目标。')
# Replace the paraphrased target above with the actual preceding risk, avoiding unsupported cross-paragraph binding.
refs[-1]['head']='damage or steam-explosion risk during unmonitored closed-discharge operation'
extra(k,'泄压阀在预定压力打开；不得拆除或重新调整，排出液可能很热。','设备功能与禁止调节；不转换成正向维护动作','To protect the pump against unintentional operation','removed or re-adjusted !')
atom(k,'shaft','inspected_by','check free rotation without jarring sounds',co,inspect,['启动前'],'required','Before starting the pump check that','the pump casing is filled with liquid.')
atom(k,'pump casing','inspected_by','check filled with liquid',co,inspect,['启动前'],'required','Before starting the pump check that','the pump casing is filled with liquid.')
atom(k,'pump','inspected_by','start briefly to check direction of rotation',eq,inspect,['先短时启动核对；旋向与箭头一致才继续启动'],'required','Start the pump for a moment','the pump may be started.')
atom(k,'considerably smaller delivery head than expected','causes','increased quantity of liquid delivered','OperatingCondition','SignalFeature',['SA 泵及管路；相对预期扬程'],'asserted','A considerably smaller delivery head','cavitation in pump and piping.')
atom(k,'increased quantity of liquid delivered','causes','increased power consumption','OperatingCondition','SignalFeature',['明显低于预期扬程导致的流量上升'],'asserted','A considerably smaller delivery head','cavitation in pump and piping.')
atom(k,'increased quantity of liquid delivered','causes','cavitation in pump and piping','OperatingCondition','FaultMode',['明显低于预期扬程导致的流量上升'],'possible','A considerably smaller delivery head','cavitation in pump and piping.')
atom(k,'cavitation','causes','heavy erosion of the impeller','FailureMechanism','FaultMode',['SA 泵；源文 may；不推广为每次汽蚀必然严重侵蚀'],'possible','In the pump the impeller','in a very short time.')
atom(k,'heavy erosion of the impeller','causes','impeller unfit for use','FaultMode','FaultMode',['源文 may at times；可能在很短时间内发生'],'possible','In the pump the impeller','in a very short time.')
atom(k,'power consumption of the pump','diagnosed_by','measuring current intensity of the connected motor','SignalFeature','InspectionMethod',['启动后检查；源文为示例 e.g.，不表示测量精度保证'],'example','Therefore, after start-up','the characteristics of the pump.')
atom(k,'quantity of water delivered','diagnosed_by','motor-current check together with differential pressure and pump characteristics','SignalFeature','InspectionMethod',['启动后；保留电流检查、压差读数与泵特性联合语境；联合测量句法仍待专家裁定'],'conditional','Therefore, after start-up','the characteristics of the pump.',note='不能以电流单一测量匹配本条。')
extra(k,'未按预期工作时按故障查找表处理；制造商称多数故障源于管路。','本页未给出具体故障表动作；总体经验不转成任意具体因果边','Should the pump not function as intended','stem from the piping system.')
# MP007 p12
k='MP007:p0012'
for component in ['pump bearing','shaft seal']:
 atom(k,'dry running','causes',f'damage to {component}','OperatingCondition','FaultMode',['MVA/MVS 泵；未灌水/排气时不得启动'],'asserted','Caution: Do not start the pump','will be damaged.')
extra(k,'有向下排出管、虹吸或需阻止污水回流任一特征时，在泵附近安装真空阀。','正向安装要求；本页未为每个条件分别陈述明确预防因果，不拆成三个确定预防断言','If your installation is characterized','backflow of unclean water.')
extra(k,'电机可靠接地；拆接线盒或泵前断电；单相和三相采用不同热保护配置。','电气安全及配置辅助要求，本轮核心参考不据此补造故障事件','Electrical connection','before installation.')
checks=[('foot bolts','check tightened',co),('pump','check full of water',eq),('power grid','check correct voltage',eq),('pump','check direction of rotation',eq),('pipes','check tight connections',co),('pipes','check normal water supply',co),('valves on inlet pipes','check completely open',co)]
for h,t,ht in checks: atom(k,h,'inspected_by',t,ht,inspect,['7.2 启动前检查；If ... or not 表示检查是否'],'required','7.2 CHECK BEFORE PUMP STARTUP','All controls required by normal running.')
atom(k,'working pressure','diagnosed_by','check using a pressure meter','SignalFeature','InspectionMethod',['启动前；已经安装压力表时'],'conditional','7.2 CHECK BEFORE PUMP STARTUP','All controls required by normal running.')
atom(k,'outlet valve','maintained_by','open slowly',co,act,['泵已启动后；不得把标题启动前条件覆盖此项目中的明确后置时序'],'required','If valves on inlet pipes','slowly after the pump is started up.')
extra(k,'压力开关控制时检查/调节启停压力并检查满载电流。','英文段落将压力开关与电流检查混用，方法映射有歧义，未计入确定参考','If the pump is controlled by the pressure switch','via the pressure switch.')
extra(k,'排气时避免排出水伤人或损物，热水特别防烫。','人身伤害/物料损害辅助要求；不改成消除泵故障的措施','When discharging air, pay attention that water drained shall not injure people or damage objects, especially avoid scalding','convey hot water.')
# MP007 p15
k='MP007:p0015'
for h in ['pump bearing','shaft seal','motor without a nozzle']:
 a='Before maintenance, confirm' if h!='motor without a nozzle' else 'Motor bearing'
 b='require no maintenance.' if h!='motor without a nozzle' else 'requires no maintenance.'
 extra(k,h+'：源文规定无需维护。','负向维护要求，禁止编码为正向 maintained_by',a,b)
extra(k,'维护前确认泵停机，以避免事故。','维护前置安全条件，在下面维护动作中继承','Before maintenance, confirm','require no maintenance.')
atom(k,'motor with a nozzle','maintained_by','lubricate with lubricant or similar high-temperature lithium base grease',eq,act,['包括11kW以上电机；按原文 nozzle 保留；维护前停机；详见源文 windscreen 说明'],'required','Motor bearing','instructions on the windscreen.')
atom(k,'motor','maintained_by','lubricate before starting',eq,act,['季节性运行且停机超过6个月；本段电机润滑适用范围；不得泛化为所有电机日常维护'],'conditional','Motor bearing','lubricate before starting the motor.')
atom(k,'pump','maintained_by','add a proper quantity of antifreezing agent',eq,act,['安装处可能冻结；数量原文未定量；介质相容性未由本页给出'],'conditional','If the pump is installed at a place','freezing of the liquid conveyed by the pump.')
atom(k,'freezing of the liquid conveyed by the pump','causes','damage to the pump','OperatingCondition','FaultMode',['安装处可能冻结'],'risk','If the pump is installed at a place','freezing of the liquid conveyed by the pump.')
atom(k,'pump','maintained_by','drain the liquid inside it',eq,act,['霜冻期间停用；可经泵头注水口和底部排水口排液；注意冷/热排液安全'],'conditional','If the pump is out of service','during water drainage (cold or hot).')
atom(k,'vent plug and drainage valve','maintained_by','tighten before using the pump again',co,act,['前述霜冻停用排液后恢复使用'],'required','When using the pump once again','vent plug and drainage valve.')
atom(k,'drainage valve','maintained_by','loosen bypass valve then unscrew drain plug',co,act,['需更换排水阀时；步骤顺序固定；前述维护停机条件'],'conditional','When it is necessary to replace','(refer to Fig. 5).')
atom(k,'drainage valve','maintained_by','tighten drain plug then tighten bypass valve',co,act,['安装排水阀时；步骤顺序固定；前述维护停机条件'],'conditional','If you want to install','then tighten the bypass valve.')
extra(k,'机械密封自动调整；动静环接触面由输送液润滑和冷却；滑动轴承由输送液润滑。','源文描述运行机理，不直接等同于操作者正向维护动作','The mechanical seal is adjusted automatically.','lubricated by the liquid conveyed by the pump.')
extra(k,'可使用60Hz电机但流量/扬程/功率改变，需咨询制造商。','运行规格辅助信息；本页顶部为前页延续数表，表头不全不猜测','The pump may run with 60hz motor.','please consult DESMI.')
# MP015 p39: complete steps; phase and bracket never discarded.
k='MP015:p0039'
groups=[
('7.6.4 Assembly of the impeller, bearing bracket 1','7.6.5 Disassembly', ['FreFlow；叶轮装配；轴承架1'],[
('tolerance ring (1880)','place into shaft recess of pump shaft (2200)',[]),
('tolerance ring','isolate from liquid by applying Loctite 572 on impeller stop face, shaft end and rearmost ring part',['仅青铜和不锈钢泵']),
('impeller','push over tolerance ring onto shaft; ensure square with shaft',[]),
('impeller bolt and spring washer (1825)','apply Loctite 243 to thread and mount',['紧固力矩须查第10章；本页不给数值'])]),
('7.6.5 Disassembly of the impeller, other bearing brackets','7.6.6 Assembly',['FreFlow；叶轮拆卸；非轴承架1'],[
('Back Pull Out-unit','remove',['完整程序见7.5.2，本页只是子程序调用']),
('locking ring (1825)','tap lips straight',['仅轴承架4']),
('impeller nut or impeller bolt (1820)','disassemble',[]),
('washer (1830)','remove',['仅轴承架2和3']),
('impeller (0120)','pull off pump shaft using proper puller',[]),
('impeller nut (1860)','remove from pump shaft',['保留原文部件号，与下节1860名称不同处不自行纠正'])]),
('7.6.6 Assembly of the impeller, other bearing brackets','7.6.7 Disassembly',['FreFlow；叶轮装配；非轴承架1'],[
('impeller key (1860)','place into keyway of pump shaft (2200)',[]),
('impeller','slide onto pump shaft',[]),
('washer (1830)','fit',['仅轴承架2和3']),
('locking ring (1825)','fit',['仅轴承架4']),
('pump shaft and impeller nut (1820) or bolt (1820)','degrease threads',[]),
('impeller nut or bolt','apply Loctite 243 to thread and mount',['紧固力矩须查第10章；本页不给数值']),
('locking ring (1825)','tap edges into recesses of shaft and impeller nut or bolt',['仅轴承架4'])]),
('7.6.7 Disassembly of the wear plate','7.6.8 Assembly',['FreFlow；耐磨板拆卸；Back Pull Out-unit 已拆除；部件号见图55'],[
('screws (0115)','loosen',[]),
('wear plate (0125)','remove from casing together with cutting blade (0105) if fitted',['切削刀片仅在泵配有切削机构时'])]),
('7.6.8 Assembly of the wear plate','FRE/EN (2502)',['FreFlow；耐磨板装配'],[
('pump casing edge','clean where wear plate is fitted',[]),
('wear plate','fit aligned in casing with holes correctly positioned and cutting blade if provided',['切削刀片仅在配有切削机构时']),
('wear plate screws (0115)','tighten using Loctite 243 to lock screws',[])])]
for start,end,conds,items in groups:
 for order,(h,t,c) in enumerate(items,1):atom(k,h,'maintained_by',t,co,act,conds+c+[f'源文程序步骤顺序{order}；不得独立视为完整维修程序'],'required',start,end)
# MP018 p26: preserve and enrich all 30 old IDs; native table rows/header, not invented spans.
k='MP018:p0026';p=pages[k];table=p['tables'][0]
old=next(x for x in rows(V1/'page_reference_annotations.jsonl') if x['page_key']==k)['atoms']
for a in old:
 n=int(a['atom_id'].split('A')[-1]); rownum=1 if n<=4 or n>=29 else 2 if n<=8 else 3 if n<=13 else 4 if n<=17 else 5 if n<=21 else 6 if n<=23 else 7
 row=table['rows'][rownum];r=a['relation']; conditions=['本离心泵维护手册轴承；保留泵型/手册适用范围']
 if r=='causes':conditions+=['PROBABLE CAUSE 表头；列项为可能原因，不推唯一诊断、不逆转方向']
 if r=='mitigated_by':conditions+=['发现该轴承缺陷时；按 Failures–Replace if Found 标题；不可套用到适度变色例外']
 if rownum==6:conditions+=['源文明确适度滚珠/滚道变色不构成废弃理由']
 ht,tt=('Cause','FaultMode') if r=='causes' else ('FaultMode','MaintenanceAction') if r=='mitigated_by' else ('FaultMode','Symptom') if r=='manifests_as' else ('FaultMode','FaultMode')
 x={'reference_id':f'{k}:V21:{n:03d}','supersedes_reference_id':a['atom_id'],'page_key':k,'head':a['head'],'head_type':ht,'relation':r,'tail':a['tail'],'tail_type':tt,'conditions_zh':conditions,'modality':'probable' if r=='causes' else 'required' if r=='mitigated_by' else 'descriptive','polarity':'positive','scope':'primary','applicability_scope':p['applicability_scope'],'source_page_sha256':p['page_text_sha256'],'document_sha256':p['document_sha256'],'evidence':[{'kind':'native_table_cells','table_id':table['table_id'],'row_id':row['row_id'],'cells':copy.deepcopy(table['rows'][0]['cells']+row['cells'])},span(p,'BEARING DEFECTS','(Failures – Replace if Found)')],'reference_status':'provisional_ai_development_reference','expert_review':'pending'};refs.append(x)
extra(k,'滚珠和滚道适度变色不是报废轴承的理由。','负向更换要求；不添加“变色→更换”正向措施','(Moderate','for discard).')
# Background control: primary target is empty by v2 scope, not absence of useful knowledge.
k='MP002:p0089'
for a,b,text in [
('14 Trend Analysis','related to performance (temperatures, pressures, power,','趋势分析关注系统/部件劣化，列出停机时间、振动/热成像/摩擦学和性能量等输入。'),
('15 Maintenance Requirements Document Reviews','reduce lifecycle costs.','至少每年复核维护要求文件以识别过时流程、工具与备件。'),
('16 Task Packaging','optimum packaged intervals are maintained.','定期复核维护任务打包间隔，以应对任务增删修改。'),
('17 Age Exploration Tasks','updating the analysis.','数据不足或初始分析采用假设数据时实施寿命探索，反馈更新可靠性分析。')]:extra(k,text,'background：本段无明确泵应用连接，主任务分母为0；不称知识错误',a,b)
# Source review coverage ledger, including deferred source material.
ledger=[]
for k in selected:
 ledger.append({'page_key':k,'source_review':'full previously-read development page reread under v2','new_primary_reference_count':sum(x['page_key']==k for x in refs),'auxiliary_or_unresolved_count':sum(x['page_key']==k for x in aux),'completeness':'provisional_non_exhaustive_pending_independent_source_first_review','blind_to_historical_candidates':False,'blind_to_new_extraction_outputs':True,'new_extraction_outputs_exist':False,'visual_table_validation':'prior_v1_visual_check_reused; native cells checked' if k=='MP018:p0026' else 'no new visual validation claimed','expert_review':'pending'})
save('page_reference_v2_1.jsonl',refs);save('auxiliary_and_unresolved.jsonl',aux);save('page_coverage_ledger.jsonl',ledger)
lineage=[]
for pg in rows(V1/'page_reference_annotations.jsonl'):
 for a in pg['atoms']:
  updates=[x['reference_id'] for x in refs if x.get('supersedes_reference_id')==a['atom_id']]
  lineage.append({'old_reference_id':a['atom_id'],'page_key':pg['page_key'],'new_reference_ids':updates,'status':'v2_qualifiers_and_native_witness_overlay' if updates else 'v2_background_scope_already_declared' if pg['page_key'] in ['MP001:p0014','MP002:p0121'] else 'v2_review_pending_outside_this_pilot','old_reference_unchanged':True})
save('v1_reference_lineage.jsonl',lineage)
# Blank expert queues: never prepopulate final human decisions with AI labels.
save('expert_dispute_queue.jsonl',[{'audit_id':x['audit_id'],'page_key':x['page_key'],'source_page_sha256':x['source_page_sha256'],'reviewer_id':None,'reviewer_role':None,'reviewed_at':None,'decision':None,'reason':None,'status':'pending'} for x in adjud])
save('expert_page_queue.jsonl',[{'page_key':k,'source_page_sha256':pages[k]['page_text_sha256'],'reviewer_id':None,'reviewer_role':None,'reviewed_at':None,'source_first_inventory_path':None,'reference_completeness':None,'status':'pending','instruction':'先只读源文独立列知识，再打开 AI 清单作差异裁定；运行时不要求逐条人工审批。'} for k in selected])
counts={'disputes':len(adjud),'resolution_counts':dict(Counter(x['v2_technical_resolution'] for x in adjud)),'pilot_pages':len(selected),'references':len(refs),'reference_by_page':dict(Counter(x['page_key'] for x in refs)),'auxiliary_or_unresolved':len(aux),'v1_lineage_counts':dict(Counter(x['status'] for x in lineage)),'expert_adjudication':'pending','formal_accuracy_recall':'not_computed','new_api_calls':0,'new_qualified_records':0,'holdout_pages_opened':0}
save('technical_summary.json',counts)
print(json.dumps(counts,ensure_ascii=False,indent=2))
