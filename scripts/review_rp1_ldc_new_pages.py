#!/usr/bin/env python3
"""Explicit AI source review of all 141 original and five changed payloads.

This is evaluation code only. It is never imported by the extraction or repair
runtime. E includes representation errors; U is not counted as either correct
or an established factual error. Full and partial reference matches are separate.
"""
import json
from pathlib import Path
from rp1_offline_contract_v3 import ROOT, BASE, rows, sha, write, object_sha, bind, flat
from postprocess_rp1_holdout_v1 import load
from run_rp1_ldc_new_pages import verify, OUT, PAGE

TARGET=OUT/'new_page_comparison'
J={}

def add(page,indices,verdict,category,reason,full=(),partial=()):
    for i in indices:
        key=f'{page}:LDC:{i:03d}'
        assert key not in J,key
        J[key]=dict(verdict=verdict,error_category=category,reason_zh=reason,
            reference_matches=[f'{page}:LREF{n:02d}' for n in full],
            partial_reference_matches=[f'{page}:LREF{n:02d}' for n in partial])

p='MP015:p0106'
add(p,[1],'S','none','表12题注明确把法兰允许载荷与EN-ISO 5199关联；这里只表示规范来源，不把允许载荷当故障阈值。')
add(p,[2],'U','structural_scope_ambiguous','本页出现法兰和泵壳材料，但不能单凭载荷表确定该contains边所指的泵壳结构层级；保留未决。')
add(p,[3,4],'E','entity_type','材料倍率是真实参数，但Cast iron/Stainless steel材料值被作为物理Component；应保留为泵壳的材料约束和参数规格。')
p='MP015:p0105'
add(p,[1],'S','none','源文直接说明法兰力/扭矩引起机组变形，因果方向与泵范围一致。',full=[1])
add(p,[2],'S','none','These可由前句唯一回指机组变形，表现为泵轴颈相对电机轴颈位移。',full=[2])
add(p,[3],'S','none','四组轴颈径向位移上限、单位和支架组均完整；属于非核心参数规范。')
add(p,[4],'E','quotation_rewritten','数学式被重写成ASCII公式放入verbatim evidence_text；不是原页或原生单元的原字符引文。公式数值真伪与引用契约错误区分。')
p='MP016:p0012'
add(p,[1],'S','none','原文Some Bronze FIP can be supplied with Clutches attached支持可选离合器与该泵的安装关联；possible及Some范围保留。')
add(p,[2],'S','none','原生表头Datasheet Number与Clutch行支持43010-0664为选件资料规范引用；不是诊断关系。')
add(p,[3],'S','none','法文引言明确列出青铜柔性叶轮泵设计输送介质；双栏串行解析不改变单栏原句的支持。')
add(p,[4],'S','none','隔离并锁定驱动电机及检查/维护之前的前提均在动作和applicability中明确；法文avant不要求改写为英文before。',full=[2])
add(p,[5],'E','generic_action_not_inspection','原文要求检查或维护前隔离电机，没有给出具体检查对象/内容或方法；inspecter ou entretenir不能独立充当检查方法。',partial=[2])
add(p,[6,7],'E','modality_strengthened','法文pourrait是可能后果，输出probable把可能升级为较大概率；并未给出这种概率强度。')
add(p,[8,9,10,11,12],'E','hazard_list_as_causal_claim','安全提醒只是列举危险因素；输出把每个因素连到同义的“与该因素有关的危险”，未给出具体风险事件，不能当作五条核心诊断因果知识。')
add(p,[13,14],'E','type_and_negative_requirement','Component不能作为mitigated_by的起点；禁止拆旁通/修改保护装置是负向安全要求，不是正向缓解动作。')
add(p,[15,16],'S','none','端盖/护罩在本设备上的局部结构身份由禁止缺失运行的原句支持；该结构边不替代完整安全禁令。')
add(p,[17],'U','connection_vs_location','原文是进出管路必须连接设备，未明确其在设备内部；located_in的空间层级不能仅由连接推定。')
add(p,[18],'S','none','退回供应商的对象限制、完全清洁并去污动作完整。危险介质FDS是另一项随附要求，不能将未抽FDS等同此清洁命题为假。',full=[1])
p='MP016:p0021'
add(p,[1,2],'S','none','本页明确柔性叶轮泵的泵头及吸排接口；仅认可局部结构事实，不把转向关系算故障。')
add(p,[3,4],'E','normal_mechanism_and_type','正常动力传递不是故障/失效机制，OperatingCondition不在occurs_at起点域内；属于运行结构说明。')
add(p,[5],'S','none','共同底板/框架变形可能影响联轴器对中；条件对应刚度语境，könnte与possible一致。',full=[2])
add(p,[6],'S','none','可能的联轴器对中失调定位于联轴器得到局部源句支持；这是位置事实，不能替代变形因果参考。')
add(p,[7],'E','entity_type','检查对象“泵与驱动的对中”被标成InspectionAction，inspected_by的起点不允许该类型；不能只凭动作句正确就放行关系。',partial=[3])
add(p,[8],'S','none','泵轴和电机轴按联轴器制造商指示精确对中，动作对象与要求均保留。',full=[1])
add(p,[9,10],'E','relation_direction','规范在specified_by起点、实体在终点，关系方向反了；源文指向制造商限值/扭矩计算资料。')
add(p,[11],'E','undeclared_relation','caused_by不在冻结的15个关系中，modality=negative也不在枚举中；且原文为预防汽蚀，不是反向否定因果。',partial=[5])
add(p,[12],'S','none','为预防汽蚀可能需要比接口更大管径，尤其黏性液体；u.U.与推荐强度保留。仅覆盖固定参考中“大管径”部分。',partial=[5])
add(p,[13],'E','relation_direction','源文堵塞过滤器导致汽蚀，输出变成汽蚀导致堵塞过滤器，且Cause不在causes终点域。',partial=[7])
add(p,[14],'S','none','吸入侧过滤器堵塞可能在本泵引起汽蚀，因此可能发生位置在该泵有支持；不替代完整因果参考。')
add(p,[15],'E','entity_type','过滤器Component不在mitigated_by起点域内；“尽量避免吸入侧过滤器”应按有条件配置要求表示。')
add(p,[16,18],'E','spatial_phrase_as_equipment','jeder/beiden Seite der Pumpe是泵两侧的空间位置，不能标成独立Equipment实体并声称仪表/阀位于该设备内部。')
add(p,[17],'E','inspection_target_and_instrument','压力状态标成OperatingCondition，不在diagnosed_by起点域；仪表名称本身也未保留两侧监测动作与稳定后可移除的上下文。',partial=[6])
add(p,[19],'E','requirement_as_causal_fact','源文要求支撑管路使含液重量不加载接口；不是已发生的“重量增加接口承载风险”事实，输出还丢了管内液体重量。')
add(p,[20],'E','entity_type','Component泵接口不在prevented_by起点域，预防目标应为不希望发生的载荷/事件而非物体本身。')
add(p,[21],'E','requirement_as_causal_fact','源文允许按需安装补偿器防止热膨胀力传递，不直接支持无条件asserted的风险因果边。')
add(p,[22],'E','conditional_strength','原文Sie können ggf.表示必要/适宜时可安装，输出把有条件可选设计措施泛化为无条件recommended缓解措施。')
add(p,[23,24],'E','negative_requirement_as_fact','无真空进气/无压力漏液是管接头的要求，不是已核验的故障不存在事实；asserted negative occurs_at混淆规范与事实。')
add(p,[25],'E','procedure_goal_and_cross_column','隔离电机的可行性要求被写为MaintenanceAction prevented_by MaintenanceAction；引文还混入另一栏的auf。')
add(p,[26],'E','design_requirement_not_action','所有活动部件需保护是设备防护要求，不是具体维护动作；原文的当地规范条件也未保留。')
add(p,[27,28],'S','none','防护装置不锈材料、危险区不打火材料均为原文明确规范；后者危险区条件保留。')
add(p,[29],'E','negative_requirement_encoding','tail是整个不得运行的禁令而非运行条件，外层再negative造成不清楚的二重否定；应保留辅助安全要求。')
add(p,[30],'E','entity_type','阀门Component不是mitigated_by允许的故障/风险起点；避免使用某类阀的介质约束不能据此转成维修边。')
add(p,[31],'E','configuration_not_maintenance','选择大半径弯头与全通阀是管路配置要求，不是这些部件自身的维护方式。')
p='MP018:p0017'
add(p,[1,12,13],'S','none','原文直接支持轴承在泵内的结构位置，Model FS局部范围在两种FS轴承中保留。')
add(p,[2,3,4,5,6,7],'E','relation_direction_and_scope','specified_by写成润滑脂Standard指向轴承Component；还把通用推荐表扩到所有脂润滑轴承而遗漏FS替代限制。')
add(p,[8],'E','relation_direction','冲洗旧脂维护动作写在prevented_by起点、轴承Component在终点，两个方向都不满足该关系的域/值域。',partial=[1])
add(p,[9],'E','material_not_action','Fina Lithium 2R是润滑材料规范，不是MaintenanceAction；原文说明不推荐替代和咨询条件。')
add(p,[10],'E','modality_and_antecedent','源文may被写成asserted；警告的Failure to observe this指违反替代限制，不等于任意经咨询的替代都必然导致失效。',partial=[2])
add(p,[11],'E','causal_chain_and_modality','可能警告的两个后果被改成必然的bearing failure evolves_to pump damage；未保留may，也未证明独立链边。')
add(p,[14],'E','startup_and_relation_direction','初次启动前加油是运行准备，且MaintenanceAction prevented_by Component方向/关系均不合法。')
add(p,[15],'E','relation_direction','检查动作在inspected_by起点，轴承在终点；源文动作虽正确，关系方向不可用。',partial=[3])
add(p,[16],'E','inspection_vs_maintenance_relation','moisture Cause indicates MaintenanceAction不合域值，If present未展开为油中水分与启动前检查情境。',partial=[4,5])
add(p,[17],'E','relation_direction','specified_by从Fina GL-5140 Standard指向轴承Component，方向倒置。')
add(p,[18],'E','modality_strengthened','can cause是可能导致，输出asserted升级为确定因果；冻结C仅识别may，未修复can。',partial=[6])
add(p,[19],'E','causal_chain_and_modality','两个可能后果被串成确定演化链，既缺可能性也缺该独立因果链的证据。')
add(p,[20,21],'S','none','FS油润滑轴承约190°F/88°C正常温度，以及除另有规定的标准FS所配油杯均有直接支持；温度不是故障报警阈值。')
p='MP018:p0015'
add(p,[1],'U','alternative_conditions_ambiguous','原文是不足或污染任一不宜运行，条件数组同时列两项未说明OR/AND；位置/可能性有支持，但完整条件逻辑未决。',partial=[2])
add(p,[2,3,4,5,6],'E','relation_direction','原文为润滑不足/污染导致性能损害、过量导致过热、混用/错误材料导致损伤；输出将现象置于原因之前，反转因果。')
add(p,[7],'S','none','Model F泵的脂润滑轴承属于泵，局部结构关系明确。')
add(p,[8],'E','inspection_vs_maintenance_relation','检查润滑剂应为检查关系，maintained_by的终点不允许InspectionAction；虽有启动前时序仍不合法。',partial=[6])
add(p,[9],'E','maintenance_prerequisite','该含水处理位于Model F启动前检查段，输出只保留Model F/脂润滑，缺启动前阶段；清洁方法的氯化溶剂限制也未保留。',partial=[7,8])
add(p,[10],'S','none','润滑前查实际装配图确定轴承类型和位置，是具体检查动作；参考还包含有经验人员承担润滑这一另行约束，因此只记部分匹配。',partial=[11])
add(p,[11],'S','none','原文明示轴承运行时可接受注脂；是运行特性，不当成具体维护程序。')
add(p,[12],'E','relation_direction','源文润滑脂搅动可能造成轴承过热，输出过热causes搅动；两端类型恰好都合法，不允许只按模式盲翻。',partial=[16])
add(p,[13],'E','entity_type','Standard specified_by Standard不在声明的域中；Table II引用可保留辅助规范，不能自动作为有效当前关系。')
p='MP021:p0004'
add(p,[1],'U','insufficient_record_evidence','Locknut确实在零件表，但引用仅图题且无对应单元，无法从所给证据地址直接回读到该零件；保留引用完整性未决。')
add(p,[2,3,4,14,15],'E','alternative_configuration','同位置的Packing/Mechanical/Cartridge Seal为备选配置，图注明代表性；不能无条件并列声称列出的全部系列/尺寸均包含每一密封选项。')
add(p,[5,6,7,8,9,10,11,12,13,16],'S','none','代表性图的局部零件条目及对应单元真实，尺寸组、半圆环排除H/HL或数量在输出中保留。仅认可该图中的结构记录，不推为每台实物的完整BOM或仍在生产。')
p='MP021:p0011'
add(p,[1],'S','none','安全阀调节螺钉盖属于安全阀，原文部件名称与朝向要求支持该局部结构身份。')
add(p,[2],'E','orientation_vs_location','point towards suction side是朝向，不是located_in；suction side也不是Equipment实体。')
add(p,[3],'E','procedure_trigger_not_cause','转向反转是拆阀调头的动作前提，不是causes MaintenanceAction；即使补回If也未修正关系。',partial=[2])
add(p,[4],'S','none','阀因修理拆下后装回原位置，前提明确；冻结参考还含螺钉盖朝吸入侧，故只是参考的部分覆盖。',partial=[1])
add(p,[5],'E','alternative_triggers_misread','换新弹簧或改变出厂压力设定是两个可独立触发调压的条件，不能读成新弹簧导致压力设定变化。')
add(p,[6],'E','procedure_title_not_action','“遵循下列指示”是程序引言，不能当具体MaintenanceAction，更不是causes的结果类型。')
add(p,[7,8],'U','structural_granularity','盖覆盖螺钉、锁母锁紧螺钉由源文支持，但contains/located_in所断言的内部结构层级并不明确；不凭常识补全。')
add(p,[9],'E','entity_type','locknut Component不在mitigated_by起点域，松锁母是调压程序动作，不是锁母自身故障缓解。',partial=[3])
add(p,[10],'S','none','压力调整时表安装在排出管，结构位置和调整情境明确；未误把此结构关系算压力检查参考。')
add(p,[11],'E','maintenance_prerequisite','旋转螺钉升/降压方向正确，但未保留新弹簧/改变设定情境及拆盖松锁母、装表等调压前提，不能当无条件完整维护动作。',partial=[5])
add(p,[12],'E','relation_direction','ES-37规范与指导尺寸被写成Standard specified_by Standard，域和方向均不符合声明。')
add(p,[13],'E','operation_and_missing_limit','关闭表后排出管是调压运行步骤，不是该管自身维护；还遗漏限时和泵内迅速升温要求。')
add(p,[14],'S','none','表后排出管关闭且泵运行时温度迅速上升，原因情境与源文will强度一致。参考同时含限时要求，完整匹配不计。',partial=[6])
add(p,[15],'E','instrument_as_indicator','Gauge Component不是indicates起点Symptom/SignalFeature，最大压力SignalFeature也不在该关系终点；需把读表动作与测量状态区别。',partial=[7])
add(p,[16,17,18],'S','none','压力设定完成后分别紧锁母、复位垫片和阀盖，Once pressure is set保留；独立部件动作有支持，但任一条不足独占组合参考。',partial=[8])
add(p,[19,20],'E','installation_action_as_condition','靠近液源/尽量低于液源是安装位置建议，tail是安装动作，不能直接充当operates_under的运行条件实体。')
add(p,[21],'U','capability_vs_operating_condition','self priming是泵能力/类型描述，是否能无损表示为operates_under的运行条件不明确；不因语句真实就认定关系表示完整。')
add(p,[22],'E','normal_relation_and_type','更好吸入条件对应更好性能不构成该故障关系的OperatingCondition结果类型；未出现声明的故障/现象对象。')
add(p,[23,24],'E','accessibility_not_inspection','应便于检查或预留拆卸空间是安装可达性要求，不是检查方法/动作。')
add(p,[25],'E','inspection_target_type','port location是端口的位置属性而非Component；虽然安装前检查动作真实，端点类型和型号不同的适用提示未完整表达。',partial=[9])
add(p,[26,28,29,30],'E','normal_mechanism_and_type','正常转向、齿轮啮合与吸排液是运行机制；把OperatingCondition放入causes终点不符合冻结故障关系模式。')
add(p,[27,32],'S','none','泵内齿轮及泵头内偏置惰轮销是源文明确的局部结构事实；不外推所有旋转容积泵。')
add(p,[31],'E','entity_type','rotation OperatingCondition不是operates_under允许的Equipment/Component起点；默认CW还需要观察方向上下文。')
add(p,[33],'E','configuration_not_maintenance','销相对端口的布置是安装结构要求，不是完整维护动作；原文should也被加强成required。')
add(p,[34],'E','commercial_status_as_condition','系列2020年第四季度停产是商业状态，不能标成negative运行条件。')

def anchors(page,a,module):
    # Evidence diagnostics and independent source judgments are distinct. A
    # semantically supported sentence may need multiple real source blocks.
    w=bind(page,a['evidence_text'])
    if w:return [w],'original_page_or_cell_span'
    hits,_=module.locate(page,a['evidence_text'],a['evidence_unit_ids'])
    if len(hits)==1:return hits[0]['witnesses'],'native_reading_path'
    ws=[];quote=''.join(a['evidence_text'].split())
    for b in page['text_blocks']:
        text=''.join(b['text'].split())
        if len(text)>=18 and text in quote:
            ws.append(dict(kind='native_block_subspan',block_id=b['block_id'],start=0,end=len(b['text']),text=b['text'],bbox=b['bbox']))
    for t in page['tables']:
        for row in t['rows']:
            for c in row['cells']:
                if c['cell_id'] in a['evidence_unit_ids'] and c['text'].strip():
                    ws.append(dict(kind='native_cell_subspan',cell_id=c['cell_id'],start=0,end=len(c['text']),text=c['text'],bbox=c['bbox']))
    return ws,'separate_fragments_only_not_full_binding'

def main():
    verify()
    outputs=rows(TARGET/'outputs.jsonl');raw={r['candidate_id']:r for r in outputs if r['stage']=='raw'}
    assert set(raw)==set(J) and len(J)==141
    original={(r['page_key'],object_sha(r['payload'])):cid for cid,r in raw.items()}
    sources={p['page_key']:p for p in rows(PAGE/'source_only.jsonl')}
    by_key={}
    for r in outputs:by_key.setdefault((r['page_key'],object_sha(r['payload'])),[]).append(r)
    module=load('layout_direction_context_v1');judgments=[]
    for packet in rows(TARGET/'review_packets.jsonl'):
        key=(packet['page_key'],packet['payload_sha256']);records=by_key[key]
        ids={r['candidate_id'] for r in records};assert len(ids)==1
        cid=next(iter(ids));j=json.loads(json.dumps(J[cid]));a=packet['payload']
        original_a=raw[cid]['payload']
        if a!=original_a:
            delta={k for k in set(a)|set(original_a) if a.get(k)!=original_a.get(k)}
            if cid=='MP018:p0017:LDC:010':
                assert delta=={'modality'} and a['modality']=='possible'
                j.update(verdict='U',error_category='antecedent_ambiguous',reason_zh='may已恢复为possible；但Failure to observe this回指替代限制及工厂咨询要求，是否支持任意替代都增加失效风险仍未决。不能凭模态修复自动判S。')
            else:
                assert cid in ['MP016:p0012:LDC:005','MP018:p0015:LDC:009','MP021:p0011:LDC:003','MP021:p0011:LDC:023']
                j['reason_zh']+=' 旧B仅截取引文或补局部If；上述语义问题仍在，改动载荷重新核对后仍为E。'
        ws,mode=anchors(sources[packet['page_key']],a,module)
        judgments.append(dict(review_id=packet['review_id'],page_key=packet['page_key'],payload_sha256=packet['payload_sha256'],
            source_page_sha256=sources[packet['page_key']]['page_text_sha256'],source_witnesses=ws,quote_binding_basis=mode,
            **j))
    write(TARGET/'source_quality_judgments.jsonl',judgments)
    paths=[Path(__file__),TARGET/'review_packets.jsonl',TARGET/'outputs.jsonl',TARGET/'source_quality_judgments.jsonl',PAGE/'reference_and_request_freeze.json']
    write(TARGET/'review_freeze.json',dict(sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},reviewer='Codex AI source review',
        raw_assertions=141,unique_payloads=146,changed_payloads_separately_reviewed=5,
        human_review=False,blindness='packet omitted arm flags; reviewer also audits output deltas; not an independent blinded human study',
        S='source-supported proposition with consistent representation',E='representation/support/condition/quotation error; not necessarily fabricated fact',U='unresolved representation or source attachment',
        source_first_reference_count=45,partial_matches_not_promoted=True))
    print(json.dumps(dict(reviewed=len(judgments),complete_original_catalog=len(J)),ensure_ascii=False))

if __name__=='__main__':main()
