"""Explicit assistant source-reading annotations, NOT expert or independent Gold.

These fixed diagnostic references are evaluation-only. They never generate GA
edges, concept mappings or training examples for a completion model.
"""
from common import *

# One focal complete proposition/constraint per unit, source reading order.
# Catalog/code snippets and incomplete multi-column clauses remain U.
NOTES={
'SU001':('U','gas turbine失效率模式示例，不是可确认迁移到泵的诊断关系；不把一般可靠性图例当漏抽。'),
'SU002':('U','这是加速度计/振动测量相关标准清单，未给当前泵故障、原因或操作关系。'),
'SU003':('D','铁谱用于确定颗粒来源；颗粒计数超限是使用条件。原候选把条件当成诊断对象，目标角色和条件绑定均有问题。'),
'SU004':('U','PM/CM是维护任务分类缩写对照，不是一个故障诊断事实。'),
'SU005':('E','RCM分析明确需要系统图、设备图、维护要求和操作经验；本单元是资料输入要求，不给出具体故障链。不能因此断言全手册缺乏诊断知识。'),
'SU006':('U','前言与维护计划历史说明，没有完整可评价的泵诊断关系。'),
'SU007':('U','有明确的推进发电机低轴承油压报警/停机要求，但目标是推进发电机，泵系适用性尚未建立，不能为增加泵图覆盖而搬入。'),
'SU008':('U','舵机液压系统单失效设计要求，句子跨窗口未完且当前泵系适用性未建立。'),
'SU009':('D','泵电机专用谐波滤波器可能豁免本节要求；正向specified_by会丢掉may/exception，不应写成强制适用。'),
'SU010':('A','首项背压过低导致泵功耗过大有明确故障表支持，正式图已表达；其余分支和措施并不因此都完整。'),
'SU011':('U','泵报废回收和Green Passport引用不属于本单元的故障诊断关系，不作为诊断文档缺失。'),
'SU012':('D','SA吸入支管设计使止回阀泄漏时不丧失全部引水；原候选正向causes丢失否定，物理设计也不能伪装成维护动作。'),
'SU013':('D','不得无液充注运行是禁止条件；相邻的干运转损伤因果不能自动替代这条运行要求，禁止、对象和阶段需保留。'),
'SU014':('U','原生行窗口交错了两栏轴承说明，句子不完整，不能凭该窗口裁定RS密封方向、润滑量和型号绑定。保留完整页可继续读。'),
'SU015':('A','错误储存条件可能损坏泵组，当前Claim表达该因果；启用前储存阶段和正确湿度的适用性仍需保留在来源。'),
'SU016':('U','当前表组只有内/外驱动及H尺寸分组，缺少对应测量或措施列内容，不能仅凭片段造诊断边。'),
'SU017':('D','变频器向电网产生干扰有原文线索，但物理变频器与运行条件/原因角色不能混同；安装检查与多栏语境也不可任意串联。'),
'SU018':('A','检查螺栓孔对中有正式检查关系；后续热变化后复查是另一条件化操作，不能因为本项匹配就宣称整个窗口完整。'),
'SU019':('B','导流器O型圈损坏对应更换O型圈，有同表原文和旧候选，但未进入正式图。此为AI源文支持代理，不是专家事实。'),
'SU020':('U','手册范围和安全介绍，没有当前窗口内的具体诊断关系。'),
'SU021':('D','启动后缓慢开启出口阀是有时序的运行步骤；不能把阀门检查候选当作已表达这条操作，也不能无条件改写为维修措施。'),
'SU022':('U','润滑/应用表的列标题，缺少本组实际数值或措施；不由标题推断缺失故障事实。'),
'SU023':('D','故障表用原因编号跨页引用；把整串编号当Cause实体并未表达真实原因，需解析手册内引用，不能直接计作新因果事实。'),
'SU024':('B','永久安装时用垫片调平底座有明确步骤及候选，当前图没有该完整操作；必须保留初装/永久布置条件。'),
'SU025':('U','型号、密封、叶轮等纯表头，不是某个型号的实际关系行；保留为采样框假阳性。'),
'SU026':('U','法文两栏交错，固体能力说明和汽蚀句未形成当前窗口内完整诊断操作；不强行裁定。'),
'SU027':('C','沿泵体轴线拉出叶轮是完整操作；既有同页候选有检查/修换叶轮等相关动作，但未表达这个完整方向性动作。只指留存导出主张，不宣称所有API原文从未包含。'),
'SU028':('B','泵配合面和连接处不应有可见泄漏，可形成对应例行检查；旧候选存在而本图未表达，具体工况仍保留。'),
'SU029':('D','检查并紧固松动紧固件同时包含检查和纠正，单标InspectionAction会混合角色；文字出现不等于两个角色均结构化。'),
'SU030':('B','运输/搬运后、运行前检查并重新对中有源文和旧候选；主图未表达此完整候选，不能脱离安装阶段推广。'),
'SU031':('B','腐蚀表现为滚动体/滚道生锈有源文和候选；同表多个腐蚀原因已入图不等于该表现关系也已发布。'),
'SU032':('C','非Patterson来源替代件可能造成泵损坏是明确警告；当前页候选只保留备件储备，留存导出中未见该完整关系。may不能改成必然。'),
'SU033':('E','本单元明确要求借助本机装配图确定轴承类型和位置；泛化润滑程序不能给出该机具体轴承配置。'),
'SU034':('B','德文故障表明确“可能缺相→检查各导线连接”，旧候选存在而当前同名结构未发布；同手册多语言副本不算独立事实。'),
'SU035':('B','海水浸泡的绕组通常需要重绕，有完整原句和候选；normally保留为模态，不宣称无条件必然更换。'),
'SU036':('D','联轴器半体安装间隙b及a1−a2均须小于0.05mm；原候选把量化条件当Standard检查对象，丢掉对象—参数绑定。'),
'SU037':('A','平衡管堵塞/受压导致轴承过早失效有明确表格关系，正式图已表达；多个原因各自措施仍不能任意配对。'),
'SU038':('D','可更换轴套/后拉式结构属于设计能力和结构属性，不能仅见replaceable就当作已经要求执行的维护动作。'),
'SU039':('D','轴承正常温度和过高阈值是不同数值判断，160°F和200°F间不能自行填结论；测温方法已入图不等于阈值被结构化保存。'),
'SU040':('D','O-Pro密封使用食用级复合铝基脂，材料名不能直接伪装为MaintenanceAction；用脂动作与产品/适用密封需分开。'),
'SU041':('E','润滑脂兼容性引用附录ESB-515；是局部跨引用，先查本手册已有附录，不据此要求新增另一份文档。'),
'SU042':('D','首个检查对象是泵口，不是“对中”工况；原候选对象类型/角色错配。现有inspected_by本可表达，无需新增关系。'),
'SU043':('D','过流钢材、密封材料和替代密封需要对象—属性—替代范围关联；平铺三元组或任意Standard映射不能保证完整表达。'),
'SU044':('U','警告符号与CAUTION/NOTE定义，不是实际故障诊断关系，不将格式说明当漏抽。'),
'SU045':('D','检查转向前拆除空气螺钉及叶轮、特定拆装状态禁止启动，包含前提/时序/禁止；当前Equipment prevented_by等伪三元组不能替代。'),
}

EXISTING={
 'SU010':'MPT-3f8658341bc5f183f17b','SU015':'MPT-03c089817b609bccd90f','SU018':'MPT-4a68915cb2829eb208df',
 'SU019':'MPT-d2fedc3790998e35cbdc','SU024':'MPT-374b373c2d0bc6d5870a','SU028':'MPT-bdcf5312de9ff54d6a9e',
 'SU030':'MPT-3f2a9b245167c6ac25fc','SU031':'MPT-896186ead325f34691c6','SU034':'MPT-d5a13c36b51a937bcdf2',
 'SU035':'MPT-a90a3b7cfa8b4ca48215','SU037':'MPT-43cda5b1182a4f6871c3',
}
NEW={
 'SU003':('颗粒来源','Cause','diagnosed_by','铁谱分析','InspectionMethod','source of the particles','Ferrography'),
 'SU027':('叶轮','Component','maintained_by','沿泵体轴线拉出叶轮','MaintenanceAction','Impeller','pulled along the axis of the pump body'),
 'SU029':('紧固件松动','FaultMode','mitigated_by','紧固松动的安装硬件','MaintenanceAction','loose attaching','tighten'),
 'SU032':('使用非Patterson公司供应部件','OperatingCondition','causes','泵损坏','FaultMode','substitute with parts','damage to the pump'),
 'SU036':('联轴器半体','Component','inspected_by','检查联轴器半体安装精度','InspectionAction','coupling half','Mounting accuracy'),
 'SU040':('O-Pro™密封','Component','maintained_by','使用食用级复合铝基润滑脂','MaintenanceAction','O-Pro™ Seal','Edible Grease'),
 'SU042':('泵口','Component','inspected_by','检查泵口是否方正且位置正确','InspectionAction','pump ports','Check pump ports'),
}
COMPLEX={
 'SU003':dict(kind='condition_and_target_role',required=['particle count exceeds a predetermined maximum','source of the particles']),
 'SU009':dict(kind='permitted_exception',required=['pump motors may be excluded','requirements of this section']),
 'SU012':dict(kind='negative_causal_scope',required=['clack flap leakage','will not','priming']),
 'SU013':dict(kind='prohibition',required=['Do not operate','without liquid fill']),
 'SU021':dict(kind='temporal_operation',required=['outlet valve','slowly','after the pump is started']),
 'SU023':dict(kind='numbered_cross_reference',required=['Mechanical seal','15, 18, 21, 28, 30, 31, 32, 33']),
 'SU024':dict(kind='installation_condition',required=['permanent arrangement','shims']),
 'SU029':dict(kind='inspection_and_corrective_action',required=['Check for and tighten','loose attaching']),
 'SU032':dict(kind='possibility_and_manufacturer_scope',required=['Patterson Pump Company','damage to the pump may']),
 'SU035':dict(kind='normally_modality',required=['Windings drenched in seawater','normally need to be','rewound']),
 'SU036':dict(kind='parameter_object_binding',required=['coupling half','0.05 mm','a1 to a2']),
 'SU038':dict(kind='design_capability_not_action',required=['REPLACEABLE SHAFT SLEEVE']),
 'SU039':dict(kind='numeric_judgment',required=['160°F (71°C)','200°F (93°C)','thermometer']),
 'SU040':dict(kind='material_and_action',required=['O-Pro™ Seal','Edible Grease','aluminum complex']),
 'SU043':dict(kind='material_and_alternative_scope',required=['AISI 316L','EPDM','Alternative seals']),
 'SU045':dict(kind='before_and_prohibition',required=['before checking the direction of rotation','pump casing is removed']),
}


def main():
    if (OUT/'source_sample/REFERENCE_FREEZE.json').exists():print('REUSE fixed source judgments/reference questions');return
    d,E,C,S=dataset();units=read(OUT/'source_sample/reviewer_packets.jsonl');N={x['triple_id']:x for x in d['normalized']};base=defaultdict(list)
    for s in d['graph']['source_records']:base[key(s)].append(s['expanded_claim_id'])
    references=[];audits=[]
    for u in units:
        sid=u['sample_id'];grade,note=NOTES[sid];ref=None
        if sid in EXISTING:
            n=N[EXISTING[sid]];ref={k:n[k] for k in ['head_type','head_canonical_zh','head_surface','relation','tail_type','tail_canonical_zh','tail_surface']}
            ref['aligned_existing_label_record']=n['triple_id']
        elif sid in NEW:
            h,ht,r,t,tt,hs,ts=NEW[sid];ref=dict(head_type=ht,head_canonical_zh=h,head_surface=hs,relation=r,tail_type=tt,tail_canonical_zh=t,tail_surface=ts)
        matches=[];pub=[]
        if ref:
            assert legal(ref,d['schema']['relation_registry']),sid
            matches=[n['triple_id'] for n in N.values() if key(n)==key(ref)];pub=sorted(set(base[key(ref)]))
            ref.update(reference_id='REF-'+sid,sample_id=sid,doc_id=u['doc_id'],pdf_page_number=u['pdf_page_number'],pump_type=u['pump_type'],applicability_scope=u['applicability_scope'],source_family_id=u['source_family_id'],page_text_sha256=u['page_text_sha256'],native_ids=u['native_ids'],source_unit_text=u['unit_text'],required_condition=COMPLEX.get(sid),modality='possible' if sid in ['SU032','SU035'] else 'source_scoped',evaluation_only=True,expert_Gold=False,evaluator='Codex assistant source reading with existing label alignment; no external API',source_support_is_AI_proxy=True)
            references.append(ref)
        audit=dict(sample_id=sid,doc_id=u['doc_id'],pdf_page_number=u['pdf_page_number'],native_unit_id=u['unit_id'],native_ids=u['native_ids'],page_text_sha256=u['page_text_sha256'],original_source=u['unit_text'],pump_type=u['pump_type'],source_family_id=u['source_family_id'],page_had_published_record=u['page_has_published_record'],primary_source_judgment=grade,reason=note,reference_id=ref['reference_id'] if ref else None,reference=ref,exact_typed_candidate_matches=matches,exact_typed_published_claims=pub,all_same_page_candidate_ids=[n['record_id'] for n in u['same_page_candidates']],all_same_page_claim_ids=[s['claim_id'] for s in u['same_page_published']],complex_semantics=COMPLEX.get(sid),semantic_reading_is_not_expert_Gold=True,not_independent_or_blinded_AI=True,export_match_is_finite_not_proof_API_never_generated=True)
        audits.append(audit)
    save('SOURCE_UNIT_AUDIT.jsonl',audits);save('source_sample/reference_relations.jsonl',references)
    questions=[]
    for ref in references:questions.append(dict(question_id='Q-'+ref['sample_id'],sample_id=ref['sample_id'],kind='atomic_relation_retrieval',reference_id=ref['reference_id'],question=f"在{ref['doc_id']}所述设备/条件范围内，{ref['head_canonical_zh']}的{ref['relation']}对象是什么？",expected_tail=ref['tail_canonical_zh'],reference=ref,condition_sensitive=bool(ref['required_condition']),answer_is_source_AI_proxy=True))
    for u in audits:
        if u['complex_semantics']:questions.append(dict(question_id='QC-'+u['sample_id'],sample_id=u['sample_id'],kind='complex_source_binding',question='是否可检索到源文中完整保留这些条件/否定/参数的关联表示？',reference=u['complex_semantics'],page_text_sha256=u['page_text_sha256'],not_a_binary_fact_accuracy_question=True))
    save('source_sample/fixed_questions.jsonl',questions)
    save('source_sample/REFERENCE_FREEZE.json',dict(date='2026-11-17',source_units=len(units),judgment_counts=dict(Counter(u['primary_source_judgment'] for u in audits)),atomic_references=len(references),atomic_questions=sum(q['kind']=='atomic_relation_retrieval' for q in questions),complex_questions=sum(q['kind']=='complex_source_binding' for q in questions),question_sha256=sha(OUT/'source_sample/fixed_questions.jsonl'),source_audit_sha256=sha(OUT/'SOURCE_UNIT_AUDIT.jsonl'),sample_freeze_sha256=sha(OUT/'SOURCE_SAMPLE_FREEZE.json'),semantic_evaluator='Codex assistant source-reading; not another independent model or expert',old_candidate_labels_changed=False,view_metrics_computed_before_reference=False,not_formal_recall_or_accuracy=True))
    print(read(OUT/'source_sample/REFERENCE_FREEZE.json'),flush=True)


if __name__=='__main__':main()
