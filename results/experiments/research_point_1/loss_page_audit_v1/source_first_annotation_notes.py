"""Literal source-first judgments by the Codex assistant, prior to candidate opening.
This is an auditable annotation construction record, not an automatic truth labeler.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
pages = {r['page_key']: r for r in map(json.loads, (HERE/'pages_source_only.jsonl').open())}
notes = {}

def page(key, note, uncertain=None, visual=False):
    notes[key] = dict(page_key=key, reviewer='Codex assistant', human_expert_reviewed=False,
                      review_note=note, unresolved_items=uncertain or [], visual_checked=visual,
                      reference_scope='11 core diagnostic relations; source-relative, not exhaustive expert truth', atoms=[])
    return key

def atom(key, head, rel, tail, anchor, condition='Within the document applicability scope; source-stated possible causes are not universal guarantees.'):
    rows=notes[key]['atoms']
    rows.append(dict(atom_id=f'{key}:A{len(rows)+1:03d}', head=head, relation=rel, tail=tail,
                     source_anchor=anchor, conditions=condition,
                     source_page_sha256=pages[key]['page_text_sha256'],
                     reviewer_confidence='provisional_ai_source_review'))

k=page('MP001:p0081','PDF视觉确认旋转表格；解析文本字符倒序。油液颗粒监测限润滑/液压旋转机械。计数仪性能局限不是泵故障因果。',visual=True)
for h in ['wear','fatigue','corrosion','contaminants']:
    atom(k,h,'causes','Particles in lubricating and hydraulic oil systems','Particles in lubricating and hydraulic oil systems caused by wear, fatigue, corrosion, and contaminants')
atom(k,'Particles in lubricating and hydraulic oil systems','diagnosed_by','Light Extinction Particle Counter','Condition Monitored / Oil Analysis Technique', 'Table binds monitored condition to technique; does not identify particle chemistry or uniquely diagnose a fault.')
k=page('MP001:p0014','只抽取磨合期/寿命末期失效定义中的明确归因；网络术语、规则索引和章节导航排除。')
for h in ['manufacturing defects','installation errors','maintenance errors','startup errors']:
    atom(k,h,'causes','Wear-in Failure','Wear-in failure is dominated by “weak” members related to problems such as manufacturing defects and installation/maintenance/startup errors.','General machinery; contributory relation, not deterministic single cause.')
atom(k,'end-of-useful life issues','causes','Wear-out Failure','Wear-out failure is dominated by end-of-useful life issues for equipment.')
page('MP002:p0098','此页故障模式属于点火发动机、蒸汽机、舵机、推进器等；没有明确泵/泵维护映射，不能迁移所有设备模式。')
k=page('MP002:p0121','可靠性维护原理适用于备份/保护系统；保留隐蔽失效检查，不能把统计曲线当实体因果链。')
atom(k,'hidden failures','diagnosed_by','failure-finding tasks','allow the operator to discover the equipment has failed and needs repair','Safety/backup equipment; subject to all six applicability/effectiveness conditions stated on this page.')
atom(k,'multiple failures risk','prevented_by','failure-finding tasks at an appropriate interval','The tasks must be carried out at an interval so that probability of multiple failures allows an acceptable risk level to be achieved.','Reduction to acceptable risk, not zero-risk guarantee; protective system tested in entirety.')
page('MP003:p0472','锅炉/压力容器设计附录材料应力表，超出本文件声明的泵管系及报警保护章节；不将材料性能泛化到泵。')
page('MP003:p0637','蒸汽装置管系章节，单页未指明此处试验对象与泵的关系。', ['Hydrostatic/working-condition tests: preceding subsection scope required; do not assume pump applicability.'])
page('MP004:p0015','符合性声明与标准列表，属于specified_by等非本轮11类目标关系；不从标准名称推导维修措施。')
page('MP004:p0023','页脚和联系信息；无可读诊断知识。图示是否存在亦由渲染文件保留供复核。')
page('MP005:p0025','法兰载荷、工作压力和规格数值，属于运行条件/设计参数；无明确故障诊断关系。')
k=page('MP005:p0013','NSL安全要求；保留最小/最大流量边界及吸入侧节流的限定，不把所有不当操作统称同一原因。')
for h in ['overheating','bearing damage']:
    atom(k,h,'prevented_by','Observe minimum flow rates specified in product literature','Observe the information on minimum flow rates specified in the product literature (to prevent overheating, bearing damage, etc.).')
for h in ['overheating','mechanical seal damage','cavitation damage','bearing damage']:
    atom(k,h,'prevented_by','Observe maximum flow rates specified in product literature','Observe the information on maximum flow rates specified in the product literature (to prevent overheating, mechanical seal damage, cavitation damage, bearing damage, etc.).')
atom(k,'cavitation damage','prevented_by','Do not throttle the flow rate on the suction side','Do not throttle the flow rate on the suction side of the pump (to prevent cavitation damage).')
atom(k,'opening discharge-side shut-off elements further than permitted','increases_risk_of','cavitation damage','Never open the discharge-side shut-off elements further than permitted. ... Risk of cavitation damage','Risk statement; excessive opening exceeds maximum flow; not an unconditional failure.')
k=page('MP006:p0011','变频器干扰及测量可直接判读；轴承/共模滤波器推荐表缺少逐项故障目标绑定，暂不自动反推因果。', ['Insulated-bearing/filter recommendation by IE class and power: target bearing-current mechanism needs context, not inferred as certain prevention.'])
atom(k,'frequency converters','causes','interference for motors and pump installations','Apart from generating interference for motors and pump installations, frequency converters are also known to generate interference towards the electricity grid')
atom(k,'frequency converters','causes','interference towards the electricity grid','frequency converters are also known to generate interference towards the electricity grid')
atom(k,'interference towards the electricity grid','diagnosed_by','DESMI Automation measurement','DESMI Automation can measure and provide solutions for such situations.','Supplier service claim; measurement method unspecified; not a unique diagnostic guarantee.')
page('MP006:p0002','目录与欢迎文字，没有诊断原子关系。')
page('MP007:p0020','外形尺寸表和连接图；不在本轮诊断关系范围。')
page('MP007:p0010','运行参数与图表页；页首只有跨页句尾cavitation，不能单独形成因果关系。',['Cavitation sentence starts on previous page; excluded from determinate single-page reference.'])
page('MP015:p0059','尺寸、底板和电机规格表；无诊断关系。')
k=page('MP015:p0025','保留泵组发动机的检查、安全动作；电气法规与一般装配不扩写故障关系。')
atom(k,'incidental contact with combustion exhaust','prevented_by','screen off exhaust of combustion gases','The exhaust of combustion gases must be screened off to prevent incidental contact.','Combustion-engine-driven pump set only.')
atom(k,'combustion engine','inspected_by','check the oil level before starting','Before starting the engine check the oil level.','Combustion-engine-driven pump set only.')
atom(k,'combustion engine and pump rotation','inspected_by','verify the sense of rotation is the same','Verify whether the sense of rotation of the combustion engine is the same as that of the pump.','Check arrows on engine and pump casing.')
page('MP016:p0010','柔性叶轮泵型号、端口和密封配置表，结构/规格项，不形成诊断关系。')
k=page('MP016:p0027','意大利语双栏PDF已视觉核对。以下为暂定源文判读，保留原语片段和泵型范围；应由双语人员复核。',visual=True)
atom(k,'pressione differenziale superiore a quella indicata nella scheda dati','causes','danneggiare la girante','non utilizzare la pompa a una pressione differenziale superiore a quella indicata nella scheda dati, nemmeno per qualche secondo, per non danneggiare la girante.')
atom(k,'Una pressione di alimentazione insufficiente','causes','cavitazione della pompa','Una pressione di alimentazione insufficiente causerà la cavitazione della pompa')
for tail in ['riduzione delle prestazioni','aumento del rumore','riduzione della vita utile della pompa']:
    atom(k,'cavitazione della pompa','causes',tail,'con una conseguente riduzione delle prestazioni, aumento del rumore e riduzione della vita utile della pompa.')
atom(k,'tubazioni di alimentazione','inspected_by','Verificare che siano corte, abbiano un alesaggio elevato e non collassino a causa del vuoto','Verificare che le tubazioni di alimentazione siano corte, abbiano un alesaggio elevato e non collassino a causa del vuoto.')
atom(k,'pompa','maintained_by','spurgarla con acqua o un agente neutralizzante dopo ogni utilizzo','Per estendere la vita utile della pompa, spurgarla con acqua o un agente neutralizzante dopo ogni utilizzo.')
atom(k,'pompare a lungo prodotti con punto di infiammabilità inferiore a 37°C','increases_risk_of','esplosioni o infortuni mortali','Non utilizzare a lungo nessuna pompa Jabsco per pompare petrolio, derivati del petrolio o qualsiasi prodotto con un punto di infiammabilità inferiore a 37°C per evitare esplosioni o infortuni mortali.')
atom(k,'Distorsione','causes','alterazione dell’allineamento del giunto','La distorsione potrebbe influenzare l’allineamento del giunto.','Could affect alignment; mounting/baseplate context, not unconditional.')
atom(k,'pompa con l’azionamento','inspected_by','Controllare l’allineamento dopo l’installazione e prima di avviare','Controllare sempre l’allineamento della pompa con l’azionamento dopo l’installazione e prima di avviare la pompa.')
atom(k,'contatto di dita, indumenti e utensili con le parti in movimento','prevented_by','ripari per accoppiamenti, cinghie e pulegge','Gli accoppiamenti, le cinghie e le pulegge devono essere sigillate per evitare il contatto di dita, indumenti e utensili con le parti in movimento.')
atom(k,'mancato rispetto delle istruzioni','increases_risk_of','lesioni personali o morte','Il mancato rispetto di queste istruzioni può causare lesioni personali o morte.','Generic warning limited to instructions on flexible-impeller pump installation.')
k=page('MP017:p0013','双栏对中章节与排气阀安装图；保持运输/搬运条件和操作前检查时点。')
atom(k,'transit and handling','causes','Misalignment','Misalignment will occur in transit and handling.')
atom(k,'pump and its power source','inspected_by','check alignment after pump and piping installation before operation','It is imperative that alignment be checked after the pump and piping are installed, and before operation.')
atom(k,'pump and driver','maintained_by','realign before operation','Pumps must be checked and realigned before operation.')
atom(k,'pump','inspected_by','Check Rotation before final alignment','Check Rotation, Section C, before final alignment of the pump.')
page('MP017:p0021','保修信息及联系方式，无诊断关系。')
k=page('MP018:p0026','轴承故障表逐行视觉核对。probable cause保留可能性；中度变色明确不构成丢弃理由，不生成一概更换规则。',visual=True)
bearing_rows=[
 ('Flaking and cracking','small cracks on inner and outer races which flake',['Normal fatigue failure','Bearing loads in excess of bearing capacity caused by misalignment']),
 ('Indentations','Indentations or cavities in the inner and outer races',['Dirt in the bearings','Excessive impact loading of the bearing, such as improper mounting or removal']),
 ('Broken Separator (cage)','Cracked separator or separator in pieces',['Poor lubrication','Misalignment of the shaft','Excessive shaft deflection']),
 ('Wear','Bore and OD of outer ring of bearing galled or braided',['Fit on the shaft or in housing too loose','Bearing locked by dirt and turning of shaft or in housing']),
 ('Fractured Ring','Hairline cracks or complete fracture',['Forcing a cocked bearing on or off a shaft','Too heavy a press fit']),
 ('Discoloration','Balls and races darker than normal appearance of bearing metal',['Inadequate lubrication']),
 ('Corrosion','Balls and raceways rusted',['Water entering the housing','Condensation inside the housing','Lubricant breaks down into acid (Wrong lubricant)']),
]
for fault,appearance,causes in bearing_rows:
    for c in causes: atom(k,c,'causes',fault,f'BEARING DEFECTS table; row {fault}; PROBABLE CAUSE: {c}','Probable cause, bearing scope; not deterministic diagnosis.')
    atom(k,fault,'manifests_as',appearance,f'BEARING DEFECTS table; row {fault}; APPEARANCE: {appearance}')
    if fault!='Discoloration': atom(k,fault,'mitigated_by','Replace bearing if found',f'BEARING DEFECTS (Failures – Replace if Found); row {fault}')
atom(k,'misalignment','causes','Bearing loads in excess of bearing capacity','Bearing loads in excess of bearing capacity caused by misalignment.')
atom(k,'Flaking and cracking','evolves_to','cracks and flaking over entire race surface','The cracks and flaking ultimately spread over the entire race surface.')
k=page('MP018:p0013','启动前检查和灌泵动作；分开正压、带底阀吸上、无底阀吸上三种工况。')
for h,t,q in [
 ('drive','check rotation matches pump before coupling','check the drive rotation to see that it matches the pump rotation'),
 ('shaft','check alignment before each startup','Prior to each startup, check the shaft alignment'),
 ('bearing and stuffing box','check for proper lubrication','Check the bearing and stuffing box for proper lubrication'),
 ('V-ring seals','check seating against bearing covers','Check to see that V-ring seals (if supplied) are properly seated against bearing covers'),
 ('shaft','check free rotation by hand','Check that the shaft turns freely by hand'),
 ('shaft guard','check in place','Check that the shaft guard is in place')]: atom(k,h,'inspected_by',t,q)
atom(k,'oil lubricated bearings','maintained_by','add oil at initial startup','oil must be added at initial startup','Oil-lubricated bearings shipped without oil.')
atom(k,'operation without proper lubrication','causes','damage to the pump','Operation of the pump without proper lubrication will cause damage to the pump and possible personal injury.')
atom(k,'operation without proper lubrication','increases_risk_of','personal injury','Operation of the pump without proper lubrication will cause damage to the pump and possible personal injury.')
atom(k,'three-phase motor','maintained_by','interchange any two of three power leads to reverse rotation if necessary','For a three-phase motor, rotation may be reversed, if necessary, by interchanging any two of the three power leads.','Does not apply to single-phase motors.')
atom(k,'entrained air in pump under positive pressure','mitigated_by','open casing vent until air escapes, then close; rotate shaft if possible','If the pump operates under positive pressure, open the vent valve on top of the pump casing.','Positive pressure only.')
atom(k,'pump on suction lift with foot valve','maintained_by','fill pump and suction line externally and vent trapped air','If the pump operates on a suction lift and a foot valve is included in the system, fill the pump and suction line with liquid from an outside source.','Suction lift with foot valve only.')
atom(k,'air in pump and suction line on suction lift without foot valve','mitigated_by','evacuate using vacuum pump or ejector at priming connection','If the pump operates on a suction lift and no foot valve is provided; use a vacuum pump or ejector','Suction lift without foot valve only.')
for t in ['Overheating','loss of prime']:
    atom(k,'operating against closed valve for more than a few minutes','causes',t,'Overheating and/or loss of prime will result if the pump is operated against a closed valve for more than a few minutes.')
k=page('MP019:p0120','芬兰语页和表格已视觉查看；功率/机座条件、IEC缩写及电气术语需要独立双语专业复核。整页不计作零目标页。', ['Bearing current prevention under ACS800/ACS550 by rating/frame; coating impregnation; potential-difference inspection; EMC grounding. Page reference remains unresolved, not a negative page.'],visual=True)
k=page('MP019:p0009','电机接线与辅助测温；保留传感器阈值及三相接线条件。')
atom(k,'motor and terminal boxes','inspected_by','ensure water cannot enter','make sure that water cannot enter the motor or the terminal boxes.')
atom(k,'terminal box seals','maintained_by','place correctly in provided slots','The seals of terminal boxes must be placed correctly in the slots provided, to ensure the correct IP class.')
for t in ['errors in readings','damage to the system']:
    atom(k,'measuring voltage or current above specified sensor limit','causes',t,'Using a higher measuring voltage or current may cause errors in readings or damage the system.','Thermistor maximum measuring voltage 2.5 V; Pt100 maximum measuring current 5 mA; may cause, not certain.')
atom(k,'motor','maintained_by','interchange any two supply connections to alter rotation','To alter the direction of rotation, interchange any two connections on the supply cables.','Within stated line-phase motor connection context.')
atom(k,'unidirectional motor fan','inspected_by','ensure rotation follows marked arrow','If the motor has a unidirectional fan, ensure that it rotates in the same direction as the arrow marked on the motor.')
k=page('MP020:p0026','Cornell诊断表逐行视觉核对。原因—症状与原因—处理分别记录；同页重复同一关系合并，单纯查阅另一章节不补造具体动作。',visual=True)
table=[
('Failure to pump',[
 ('Pump not properly primed','Prime pump correctly'),('Pump running too slow or system too high','Consult Cornell factory'),('Not enough head to open check valve','Consult Cornell factory'),('Air leak in suction piping','Check and rework suction line'),('Plugged suction pipe or impeller vanes','Unplug suction'),('Suction pipe high point above impeller eye','Rework suction piping'),('Suction lift too high','Consult Cornell factory')]),
('Reduced performance',[
 ('Air pockets or small air leaks in suction line','Locate and correct'),('Obstruction in suction line or impeller','Remove obstruction'),('Insufficient submergence of suction pipe','Consult Cornell factory'),('Excessively worn impeller or wear ring','Replace impeller and/or wear ring'),('Suction lift too high','Consult Cornell factory'),('Wrong direction of rotation','See start-up instructions'),('Missing wear ring(s)','Install wear ring(s)')]),
('Driver overloaded',[
 ('Speed higher than planned','Reduce speed'),('Pump runs out on curve/ system incorrect','Change system head'),('Liquid specific gravity too high','Consult Cornell factory'),('Liquid handled of greater viscosity than water','Consult Cornell factory'),('Too large an impeller diameter','Trim impeller'),('Low voltage','Consult power company'),('Piping stress at flanges/ pump in bind','Support piping properly'),('Packing too tight','Loosen packing gland nuts')]),
('Excessive noise',[
 ('Misalignment','Align all rotating parts'),('Cavitation (excessive suction lift)','Consult Cornell factory'),('Cavitation (improper suction design)','Correct suction piping'),('Material lodged in impeller','Dislodge'),('Worn bearings','Replace bearings'),('Impeller screw loose or broken','Replace'),('Wrong direction of rotation','See start-up instructions')]),
('Excessive vibration',[
 ('Misalignment','Align correctly'),('Unbalanced components','Re-balance components'),('Bent shaft','Replace shaft'),('Structural (rigidity/ soft foot)','Correct bolting/ shim properly')]),
('Premature bearing failure',[
 ('Balance line plugged or pinched','Unplug or replace'),('Worn wear rings','Replace'),('Misalignment','Align all rotating parts'),('Suction or discharge pipe not properly supported','Correct supports'),('Bent shaft','Replace shaft'),('Water or contaminants entering bearings','Protect pump from environment'),('Lubrication to bearings not adequate','See lubrication instr. (O&M manual)'),('Wrong type of lubrication','See lubrication instr. (O&M manual)'),('Excessive belt loads','Consult Cornell factory')]),
('Electric motor failure',[
 ('High or low voltage','Check voltage with voltage meter'),('High electric surge','Monitor voltage and consult power co.'),('Poor electric connection','Turn power off, clean and check connections'),('Overloads','Check amperage; do not exceed nameplate full load amperage'),('Bearing failure','Change bearings in motor'),('Cooling vent plugged (rodent, leaves, dirt, etc.)','Install proper screens'),('Water in motor','Protect pump from environment')]),
('Rapid wear on coupling cushion',[
 ('Misalignment','Align'),('Bent shaft','Replace shaft'),('Wrong elastomer','Change elastomer/ Consult Cornell factory')])]
seen=set()
for symptom, entries in table:
    for cause,correction in entries:
        atom(k,cause,'causes',symptom,f'Table row {symptom} | {cause} | {correction}','Listed possible troubleshooting cause in Cornell pump scope, not unique diagnosis.')
        if correction.startswith('See '):
            notes[k]['unresolved_items'].append(f'{cause}: {correction}; action resides on another page.')
            continue
        normalized_action='Align all rotating parts' if correction in ['Align','Align correctly','Align all rotating parts'] else correction
        if (cause,normalized_action) in seen: continue
        seen.add((cause,normalized_action))
        relation='diagnosed_by' if correction=='Check voltage with voltage meter' else 'mitigated_by'
        atom(k,cause,relation,normalized_action,f'Table row {symptom} | {cause} | {correction}','Corrective-action column; referrals mean seek supplier advice, not a guaranteed physical repair. Object of Replace/Dislodge inherited from cause cell.')
page('MP020:p0017','章节扉页START-UP，无知识目标。')
k=page('MP021:p0007','Viking拆卸/填料维护页，已视觉核对双栏。动作保留型号和拆卸上下文，不输出独立安全操作建议。',visual=True)
atom(k,'failure to follow listed pre-opening precautions','increases_risk_of','serious injury or death','Failure to follow above listed precautionary measures may result in serious injury or death.','Venting, drive lockout and handling-fluid precautions jointly apply.')
atom(k,'idler falling from pin during head removal','prevented_by','tilt top of head back when removing','Do not allow idler to fall from idler pin. To prevent this, tilt top of head back when removing.')
for head,tail,anchor in [
 ('head and casing','mark before disassembly for proper reassembly','Mark head and casing before disassembly to ensure proper reassembly'),
 ('jacket head plate gasket','remove old gasket and use new gasket when assembling','The gasket between head and jacket head plate must be totally removed. Use new gasket when assembling pump'),
 ('packing','remove gland nuts, slide gland out and remove packing and retainer washer','remove packing and packing retainer washer'),
 ('packing rings','stagger joints and seat each ring','Install packing, staggering the joints from one side of shaft to other'),
 ('packing rings','lubricate with oil, grease or graphite to aid assembly','Lubricate packing rings with oil, grease, or graphite to aid assembly'),
 ('packing gland','install square and tighten evenly without over-tightening','Make sure gland is installed square and nuts are tightened evenly'),
 ('bearings','wash in clean solvent','Wash bearings in clean solvent'),
 ('bearings','blow out with compressed air without spinning','Blow out bearings with compressed air. Do not allow bearings to spin'),
 ('bearings','lubricate with light oil after cleaning','Make sure bearings are clean, then lubricate with light oil')]: atom(k,head,'maintained_by',tail,anchor)
for head in ['lipseals','bearings','bushings','idler pin']:
    atom(k,head,'inspected_by','check for wear and damage', 'Check lipseals, bearings, bushings, and idler pin and replace if necessary.')
    atom(k,head,'maintained_by','replace if necessary after inspection','Check lipseals, bearings, bushings, and idler pin and replace if necessary.','Conditional on inspection; not mandatory replacement of every component.')
atom(k,'all other pump parts','inspected_by','check nicks, burrs and excessive wear','Check all other parts for nicks, burrs, excessive wear and replace if necessary.')
atom(k,'all other pump parts','maintained_by','replace if necessary after checking nicks/burrs/excessive wear','Check all other parts for nicks, burrs, excessive wear and replace if necessary.')
atom(k,'spinning bearings during compressed-air cleaning','causes','damage to bearing components','Spinning bearings will damage bearing components.','Cleaning context; not ordinary running rotation.')
atom(k,'bearing roughness','diagnosed_by','turn outer race slowly by hand','Roughness can be determined by turning outer race by hand.')
atom(k,'casing','inspected_by','check wear or damage while mounted on bracket','Casing can be checked for wear or damage while mounted on bracket.')
atom(k,'bracket bushing','inspected_by','inspect for wear','Inspect bracket bushing for wear and remove if damaged or worn.')
atom(k,'bracket bushing','maintained_by','remove if damaged or worn','Inspect bracket bushing for wear and remove if damaged or worn.')
notes[k]['unresolved_items'].append('Disassembly substeps (remove rotor/shaft, bearing housing etc.) are procedural context; whether each should be a standalone maintained_by atom requires annotation-guideline adjudication. Not counted as established complete maintenance recall.')
k=page('MP021:p0002','安全页已视觉核对；不得把Viking回转容积泵开阀要求迁移为离心泵通用启动要求。',visual=True)
for h in ['improper installation','improper operation','improper maintenance']:
    atom(k,h,'increases_risk_of','serious injury or death','IMPROPER INSTALLATION, OPERATION OR MAINTENANCE OF PUMP MAY CAUSE SERIOUS INJURY OR DEATH')
    atom(k,h,'causes','damage to pump or other equipment','AND/OR RESULT IN DAMAGE TO PUMP AND/OR OTHER EQUIPMENT.','May cause; not inevitable.')
for h in ['certain operating conditions','temperature control devices (jackets, heat-tracing)','improper installation','improper operation','improper maintenance']:
    atom(k,h,'causes','high temperatures on pump or drive','Certain operating conditions, temperature control devices (jackets, heat-tracing, etc.), improper installation, improper operation, and improper maintenance can all cause high temperatures on the pump and/or drive.','Can cause; preserve device and operation context.')
for t in ['relief valve mounted directly on pump','in-line pressure relief valve','torque limiting device','rupture disk']:
    atom(k,'pressure hazard','prevented_by',t,'THE PUMP must be provided with pressure protection. This may be provided through a relief valve mounted directly on the pump, an in-line pressure relief valve, a torque limiting device, or a rupture disk.','Pressure protection, both sides if reversible; not flow regulation.')
atom(k,'pump suction and discharge connections','inspected_by','install pressure gauges/sensors to monitor pressures','INSTALL pressure gauges/sensors next to the pump suction and discharge connections to monitor pressures.')
atom(k,'pump','inspected_by','check leakage and monitor operation','inspection during operation to check for leakage and monitor pump operation.')
for target,action in [('pump','check clean and free from debris'),('suction and discharge valves','check fully opened'),('piping','check fully supported and aligned'),('pump rotation','check correct for intended flow'),('drive guards','check in place')]:
    atom(k,target,'inspected_by',action,'BEFORE operating the pump, be sure','Viking rotary positive-displacement pump pre-start checks; preserve full listed conditions.')
notes[k]['unresolved_items'].append('Safety imperative-to-risk mapping for each DANGER box is not inferred separately without an explicit risk proposition; general pre-opening checklist retained as context.')
k=page('MP022:p0023','LKH Prime卫生泵清洗页；清洗方法保留原设备范围，配方浓度/温度不是通用泵建议。')
atom(k,'pump','maintained_by','clean in place (CIP)','The pump is designed for cleaning in place (CIP).','LKH Prime sanitary pump; no claim applicable to all marine pumps.')
atom(k,'pump','maintained_by','rinse well with clean water after cleaning agent','rinse well with clean water after using a cleaning agent.','LKH Prime cleaning sequence; parser duplicates bold characters, original PDF supplies reading.')
atom(k,'caustic exposure risk','prevented_by','use rubber gloves and protective goggles','Caustic danger / Always use rubber gloves / Always use protective goggles','Lye/acid handling in specified cleaning context; not a complete safety procedure.')
notes[k]['unresolved_items'].append('Food-process-specific milk/viscous-liquid sterilisation and reagent recipes excluded from transferable pump diagnostic reference.')
k=page('MP022:p0029','轴封拆卸页，保留机械密封类别与必要条件；按本页明确部件维护动作记录。')
for h,t,q in [
 ('double mechanical shaft seal tubes (42)','unscrew tubes using a spanner','Unscrew tubes (42) using a spanner'),
 ('impeller (27)','remove; if necessary loosen by gentle tapping on vanes','Remove impeller (27). If necessary, loosen the impeller by tapping gently on the impeller vanes'),
 ('O-ring (38)','remove from impeller','Remove the O-ring (38) from the impeller'),
 ('O-ring (26)','remove from back plate (25)','Remove the O-ring (26) from the back plate (25)'),
 ('back plate (25)','unscrew nuts and remove washers and back plate','Unscrew nuts (20) and remove the washers (21) and the back plate (25)'),
 ('stationary seal ring (11)','remove with supplied tool, noting left-hand thread','Remove the stationary seal ring (11)'),
 ('O-ring (12)','remove from back plate (25)','Remove the O-ring (12) from the back plate (25)')]: atom(k,h,'maintained_by',t,q,'LKH Prime shaft-seal disassembly sequence; not standalone operating advice.')

assert set(notes)==set(pages)
with (HERE/'page_reference_annotations.jsonl').open('x',encoding='utf-8') as f:
    for key in pages:
        f.write(json.dumps(notes[key],ensure_ascii=False)+'\n')
print('Source-first pages',len(notes),'atoms',sum(len(p['atoms']) for p in notes.values()))
