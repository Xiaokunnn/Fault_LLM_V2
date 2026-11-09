#!/usr/bin/env python3
"""Source-first AI reference inventory, written before the eight model calls.

References are propositions, not a human gold standard. Auxiliary inventories
and exclusions are explicit; one output can match at most one core reference.
"""
import datetime
import json
from pathlib import Path
from rp1_offline_contract_v3 import ROOT, BASE, rows, sha, write, span
from run_rp1_targeted_v2_1 import payload_bytes, digest

OUT = BASE/'layout_direction_context_v1'
PAGE = OUT/'new_pages'
# statement, relation, exact source fragments (all must bind to native blocks).
# Conjoined actions have separate references only when they have independent
# physical targets; conditions and sequence are part of each reference.
CATALOG = {
'MP015:p0106': [],
'MP015:p0105': [
('FreFlow：作用于法兰的力和扭矩引起泵机组变形。','causes',['The forces and torques acting on the flanges cause deformations in the pump unit. These']),
('泵机组变形表现为泵轴颈相对电机轴颈位移。','manifests_as',['are manifested in a displacement of the shaft journal of the pump in relation to the shaft','journal of the motor.']),
],
'MP016:p0012': [
('青铜柔性叶轮泵：因任何原因退回供应商前必须完整清洁并去污；清洁与去污按一个组合目标计。','maintained_by',['Toute pompe retournée au fournisseur pour quelque raison','que ce soit doit être entièrement nettoyée et décontaminée et']),
('检查或维护该泵之前，总是隔离并锁定驱动电机。','maintained_by',['Isolez et verrouillez toujours le moteur d’entraînement de la','pompe avant d’inspecter ou d’entretenir la pompe.']),
],
'MP016:p0021': [
('柔性叶轮泵的泵轴与电机轴应严格按联轴器制造商指示对中。','maintained_by',['Pumpen- und Motorwellen müssen exakt nach den Anweisungen','des Kupplungsherstellers ausgerichtet werden.']),
('泵共同底板或框架变形可能影响联轴器对中，非确定必然。','causes',['Ausrüstung ohne Vibrationen zu tragen. Eine Verformung könnte','die Ausrichtung der Kupplung beeinträchtigen.']),
('安装完成后、泵启动前，始终检查泵与驱动的对中。','inspected_by',['immer die Ausrichtung von Pumpe und Antrieb nach der Installa-','tion und vor dem Starten der Pumpe.']),
('安装时管路布置或尺寸因素改变，应复查泵选型是否仍正确。','inspected_by',['Sollten beim Einbau der Pumpe irgendwelche Faktoren davon','abweichen, müssen Sie überprüfen, ob die Pumpenauswahl noch','die richtige ist:']),
('短管路和大管径用于预防汽蚀，尤其输送黏性液体；可能需比泵接口更大的管径。','prevented_by',['Sorgen Sie für kurze Rohrlängen und große Rohrdurchmesser;','die Pumpenanschlüsse – insbesondere zum Fördern viskoser','Flüssigkeiten, um Kavitation zu vermeiden.']),
('泵两侧压力通过两侧真空/压力表监测；工况稳定且不再变化后可拆表，不表示必须拆除。','diagnosed_by',['Druckmessgerät an, um die Druckverhältnisse zu überwachen.','Sobald der Prozess läuft (und sich nicht mehr ändert), können','diese wieder abgebaut werden.']),
('泵吸入侧堵塞的过滤器导致汽蚀。','causes',['Pumpe. Ein verstopfter Filter führt zur Kavitation.']),
],
'MP018:p0017': [
('泵脂润滑轴承：若此前使用另一类型润滑脂，补充润滑前必须冲洗出轴承室全部旧脂。','maintained_by',['All old grease must be flushed out from the bearing chambers before lubricating, if another type of grease','has been used.']),
('Model FS：违背Fina Lithium 2R替代限制可能引起轴承过早失效；与推力轴承油混合的适用情境必须保留。','causes',['other greases for Fina Lithium 2R grease is not recommended due to some mixing of grease with the oil in','WARNING!! Failure to observe this may cause premature bearing failure and']),
('Model FS油润滑球面滚子推力轴承：投入运行前检查油中水分。','inspected_by',['drained out. Oil must be added prior to initial startup. Before placing pump into operation, check oil for','presence of moisture. If present, clean the bearing and replace oil.']),
('Model FS油润滑推力轴承：运行前检查发现油中有水分时清洁轴承。','maintained_by',['presence of moisture. If present, clean the bearing and replace oil.']),
('Model FS油润滑推力轴承：运行前检查发现油中有水分时更换油；油应Fina GL-5140，替代需向工厂咨询。','maintained_by',['presence of moisture. If present, clean the bearing and replace oil.','Oil for spherical roller thrust bearing on the pump should be Fina GL-5140. If substitution for this oil']),
('Model FS油润滑推力轴承使用不合适油可能造成轴承过早失效。','causes',['WARNING ! ! Use of improper oil can cause premature bearing failure and']),
('标准Model FS（除另有规定）：Trico Optomatic Oiler可显示油损失，不把自动补油当人工维护。','diagnosed_by',['make-up oil if the oil level is the thrust bearing should drop, and also give an indication of any loss of oil.']),
],
'MP018:p0015': [
('在轴承箱润滑不足或润滑剂含污物/水分时运行泵，会损害泵性能。','causes',['operate pump if sufficient lubricant is not present in bearing housing or if lubricant','is contaminated with dirt or moisture. Operation of the unit under these conditions','will lead to impaired pump performance and possible bearing failure.']),
('在轴承箱润滑不足或润滑剂含污物/水分时运行泵，可能造成轴承失效。','causes',['is contaminated with dirt or moisture. Operation of the unit under these conditions','will lead to impaired pump performance and possible bearing failure.']),
('泵在润滑剂过多时运行会使轴承过热。','causes',['operate pump with excessive amount of lubricant. Such action will cause bearings','to overheat.']),
('混用不同润滑脂或油会损害泵轴承。','causes',['to overheat. Mixing of different greases or oils and use of the wrong grease or oil','will damage the bearings.']),
('使用错误润滑脂或油会损害泵轴承。','causes',['to overheat. Mixing of different greases or oils and use of the wrong grease or oil','will damage the bearings.']),
('Model F脂润滑轴承：启动前检查润滑剂。','inspected_by',['lubricant should be checked before starting. If moisture is present, bearings should be cleaned and']),
('Model F：启动前发现润滑剂含水时应清洁轴承，清洁不推荐使用氯化溶剂。','maintained_by',['lubricant should be checked before starting. If moisture is present, bearings should be cleaned and','of any kind is not recommended in bearing cleaning.']),
('Model F：启动前发现润滑剂含水时，在轴承清洁后加脂。','maintained_by',['lubricant should be checked before starting. If moisture is present, bearings should be cleaned and','grease applied.']),
('Model F润滑频次按运行和安装地区大气条件确定，不从本页推断具体周期。','maintained_by',['Operating conditions and atmospheric conditions existing in the area of installation must be','considered when determining how often lubrication is necessary.']),
('Model F：有利工况且不需频繁润滑时，脂入口配堵头，仅润滑时换成注脂接头。','maintained_by',['operating under favorable conditions that do not warrant frequent lubrication, the grease inlets should be','equipped with plugs that are replaced with grease fittings only during lubrication.']),
('Model F润滑前根据实际装配图确认轴承类型和位置，仅由有经验维护人员润滑。','inspected_by',['Allow only experienced maintenance personnel to lubricate this unit. Before attempting to lubricate','this unit, refer to your specific assembly drawing to determine the specific type and location of bearings']),
('Model F润滑程序步骤1：有经验人员先清洁注脂及排放堵头周围设备外表。','maintained_by',['1. Clean the exterior of the unit around the grease and drain plugs.']),
('Model F润滑程序步骤2：完成周围清洁后移除排放堵头。','maintained_by',['2. Remove the drain plugs and if grease holes are plugged, remove the plugs and install grease']),
('Model F润滑程序步骤2：如脂孔封堵，移除堵头并装注脂接头；保持步骤前置清洁。','maintained_by',['2. Remove the drain plugs and if grease holes are plugged, remove the plugs and install grease','fittings in their place.']),
('Model F润滑程序步骤3：完成步骤1/2后缓慢注入表II推荐脂，不得过量。','maintained_by',['3. Slowly introduce recommended grease, per Table II into the bearings. DO NOT over','lubricate. Churning of the grease may result in harmful overheating of bearings.']),
('Model F润滑中，润滑脂搅动可能导致有害轴承过热。','causes',['lubricate. Churning of the grease may result in harmful overheating of bearings.']),
('Model F步骤4：先运行约15分钟排出轴承室多余压力，再擦净泄压孔和脂接头周围润滑脂并装回泄压塞；同一部位收尾按组合动作计。','maintained_by',['4. Before replacing the relief plug, operate the unit for approximately 15 minutes to expel any','excess pressure from the bearing chambers. Wipe off all grease from around relief hole and','grease fittings. Replace relief plug.']),
('Model F步骤5：正常工况且不需频繁润滑时，润滑结束把脂接头换回堵头以防过量润滑。','maintained_by',['5. If the unit is being operated under normal conditions, and does not require frequent','lubrication, replace grease fittings with plugs as a precaution against personnel over']),
],
'MP021:p0004': [],
'MP021:p0011': [
('卸下修理的安全阀应装回相同位置，调节螺钉盖始终朝吸入侧。','maintained_by',['is removed for repairs be sure to replace in same position.','Relief valve adjusting screw cap must always point towards']),
('如果泵旋转方向反转，拆下安全阀并调头重装。','maintained_by',['suction side of pump. If pump rotation is reversed, remove','relief valve and turn end for end.']),
('安装新弹簧或改变安全阀出厂压力设定时，步骤1小心取下螺钉阀盖并松锁紧螺母。','maintained_by',['If a new spring is installed or if pressure setting of pressure','1. Carefully remove valve cap which covers adjusting screw.','Loosen locknut which locks adjusting screw so pressure']),
('上述压力调整程序步骤2，在排出管安装压力表用于实际调整；作为压力测量方法，仪器本身不等于检查动作。','diagnosed_by',['2. Install a pressure gauge in discharge line for actual','adjusting operation.']),
('安全阀压力调整步骤3：顺时针向内转调节螺钉升压，逆时针向外转降压；保持新弹簧/改变出厂设定的上下文与步骤1/2。','maintained_by',['Turn adjusting screw CW (in) to increase pressure','and CCW (out) to decrease pressure.']),
('压力调整时，在表后关闭排出管且泵仍运行会令泵内温度迅速升高；必须限时。','causes',['4. Close the discharge line at a point beyond the pressure','operated at this condition. The temperature inside the','pump will rise rapidly. Gauge will show maximum pressure']),
('压力调整步骤4：表后关闭排出管且泵运行时，压力表显示该阀允许的最大压力；限时以防升温。','diagnosed_by',['pump will rise rapidly. Gauge will show maximum pressure','that valve will allow while pump is in operation.']),
('上述安全阀调压步骤5：压力设定完成后，紧固锁紧螺母并装回盖垫片和阀盖。','maintained_by',['5. Once pressure is set, tighten locknut and replace cap','gasket and valve cap.']),
('附录一般安装指导：安装前按泵型号检查接口位置，各型号结构并非全部适用。','inspected_by',['3. Port Arrangement - since the pumps have different port','arrangements depending on the model, port location','should be checked before starting the installation.']),
],
}

NOTES = {
'MP015:p0106':'19型号的允许法兰载荷、底板灌浆状态、材料倍率属于工程参数，不能自动变成故障阈值；核心0不表示此页无价值。',
'MP015:p0105':'4组允许轴颈位移、载荷计算及灌浆差异为参数/规范；解析公式保留未决，不凭常识补数学结构。',
'MP016:p0012':'实际英语/法语混合。保修为非研究知识；正常容积变化吸排液为运行机制；负向保护要求、危险告知和危险流体FDS为辅助要求。',
'MP016:p0021':'实际德语。电气隔离可行性、护罩、支架、阀门/管路选择和人员资质为设计/安全要求；正常旋转端口关系为运行机制。',
'MP018:p0017':'推荐润滑脂表为材料规格；不能把Model FS例外扩到全表。初次加油/自动补油为运行准备/机制。后续泵损害作为警告后果保留，不新造轴承失效必然导致泵损害的独立边。Trico指示按油损失的检查方式建参考，需动作语义。',
'MP018:p0015':'Model F局部范围不得扩到FS。经验人员、实际装配图及程序次序是适用约束；单纯运行15分钟不是独立维护创新。负向限制以辅助要求保存。',
'MP021:p0004':'两张代表性爆炸图的零件关系为结构知识，型号/尺寸/密封备选及已停产限制应保留；核心0。',
'MP021:p0011':'左右栏分别为安全阀修理/调压和一般安装附录；不能互串。调压操作不等于独立维修，参考保留整个步骤前提。正常齿轮吸排机制、布局建议、备件采购和ES-37引用为辅助。',
}

def main():
    if (OUT/'api_run_001').exists():
        raise ValueError('Source-first preparation must precede API execution')
    pages={p['page_key']:p for p in rows(PAGE/'source_only.jsonl')}
    freeze=json.loads((OUT/'method_freeze.json').read_text())
    for name,h in freeze['sha256'].items():
        assert sha(ROOT/name)==h,name
    references=[];inventory=[]
    for key,items in CATALOG.items():
        p=pages[key]
        for i,(statement,relation,fragments) in enumerate(items,1):
            witnesses=[]
            for fragment in fragments:
                hits=[]
                for block in p['text_blocks']:
                    hit=span(block['text'],fragment)
                    if hit: hits.append(dict(**{k:v for k,v in hit.items() if k!='kind'},kind='native_block_subspan',block_id=block['block_id'],bbox=block['bbox']))
                if len(hits)!=1: raise ValueError((key,fragment,len(hits)))
                witnesses+=hits
            references.append(dict(reference_id=f'{key}:LREF{i:02d}',page_key=key,statement_zh=statement,relation=relation,
                evaluation_channel='core',source_witnesses=witnesses,source_page_sha256=p['page_text_sha256']))
        inventory.append(dict(page_key=key,core_references=len(items),notes_zh=NOTES[key],
            declared_language=p['source_language'],observed_languages=['en','fr'] if key=='MP016:p0012' else ['de'] if key=='MP016:p0021' else ['en']))
    write(PAGE/'references.jsonl',references);write(PAGE/'reference_inventory.jsonl',inventory)
    write(PAGE/'reference_policy.json',dict(reviewer='Codex AI source-first review',human_review=False,
        granularity='one conditioned proposition; independently targeted actions separate; same-target clean/decontaminate and closing steps grouped',
        scope='core diagnostic schema only; auxiliary topics inventoried, not included in recall denominator',
        completeness='AI reference estimate, not expert-confirmed exhaustive knowledge',
        match='one-to-one full matches require correct direction, source scope, modality and conditions; partial matches separate',
        uncertainty='ambiguity in a candidate never filled by engineering background; U remains non-supported'))
    template=json.loads((BASE/'independent_review_v1/extraction_template.json').read_text())
    requests=[]
    for i,p in enumerate(pages.values(),1):
        content=json.dumps({k:p.get(k) for k in ['doc_id','pdf_page_number','title','pump_type','service','applicability_scope','document_sha256','page_text_sha256','page_text','tables']},ensure_ascii=False)
        payload={k:v for k,v in template.items() if k!='system_prompt'}
        payload['messages']=[dict(role='system',content=template['system_prompt']),dict(role='user',content=content)]
        requests.append(dict(request_id=f'LDC{i:02d}',page_key=p['page_key'],arm='E1',payload=payload,
            payload_sha256=digest(payload_bytes(payload)),shared_input_sha256=digest(content.encode()),source_page_sha256=p['page_text_sha256']))
    write(PAGE/'requests.jsonl',requests)
    deps=[Path(__file__),OUT/'method_freeze.json']+[PAGE/f for f in ['source_only.jsonl','inventory.jsonl','selection.json','references.jsonl','reference_inventory.jsonl','reference_policy.json','requests.jsonl']]
    write(PAGE/'reference_and_request_freeze.json',dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        sha256={str(p.relative_to(ROOT)):sha(p) for p in deps},reference_count=len(references),requests=8,
        outputs_not_yet_generated=True,no_postselection_page_replacement=True))
    print(json.dumps(dict(references=len(references),requests=len(requests),inventory=inventory),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
