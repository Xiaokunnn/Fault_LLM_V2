"""Research deliverables from the completed, read-only controlled experiment."""
from common import *


def table(headers,rows):
    cell=lambda v:str(v).replace('|','/').replace('\n',' ')
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(cell(v) for v in row)+' |\n' for row in rows)


def main():
    l=read(OUT/'lineage/complete.json');o=read(OUT/'ontology/complete.json');v=read(OUT/'counterfactual/complete.json');s=read(OUT/'source_sample/REFERENCE_FREEZE.json');f=read(OUT/'SOURCE_SAMPLE_FREEZE.json');detail=read(OUT/'details/complete.json');ret=read(OUT/'details/retention_complete.json');units=read(OUT/'SOURCE_UNIT_AUDIT.jsonl');summ={r['view']:r for r in v['view_summary']};dec=list(csv.DictReader((OUT/'counterfactual/concept_layer_decomposition.csv').open()))
    categories=read(OUT/'lineage/category_counts.json');names={'published_representative':'已发布，同五元签名代表','published_aggregated':'已发布，同Claim的额外候选','published_after_reconstruction':'有发布后代，五元签名已变','same_typed_signature_already_published_other_lineage':'同五元签名已由其他链路发布','schema_excluded':'当前类型/Domain/Range不合法','location_or_evidence_contract':'保存的定位/证据合同未过','semantic_negative_or_direction':'保存的语义否定/方向问题','condition_modality_or_stage_unresolved':'条件/否定/阶段线索未结构化','semantic_support_unresolved':'语义支持未决','terminology_not_published':'已自动准入但术语/发布未入图','other_confidence_or_unresolved':'其他置信/未决'}
    lineagetable=table(['互斥主归因','记录','去重五元签名','条件感知签名'],[[names.get(x['category'],x['category']),x['records'],x['distinct_typed_signatures'],x['condition_aware_signatures']] for x in categories])
    relationrows=list(csv.DictReader((OUT/'ontology/relation_inventory.csv').open()))
    relationtable=table(['关系','Domain → Range','原始导出行','规范化记录','正式Claim'],[[x['relation'],x['domain']+' → '+x['range'],x['raw_export_records'],x['normalized_records'],x['published_claims']] for x in relationrows])
    maintable=table(['视图','业务实体','业务Claim','业务分量','单Claim双实体分量','最大业务分量','18项精确检索'],[[name,x['semantic_entities'],x['business_claims'],x['components'],x['strict_single_claim_components'],x['largest_component'],str(x['atomic_questions_answered'])+'/18'+('（按构造）' if name=='GC' else '')] for name,x in summ.items()])
    virtualtable=table(['概念投影','业务Claim','虚拟映射边','异构分量','最大异构分量','其中业务实体/虚拟概念','原组件组织减少'],[[x['view']+' / '+x['subview'],x['business_claims'],x['virtual_links'],x['heterogeneous_components'],x['largest_heterogeneous_nodes'],x['largest_semantic_entities']+'/'+x['largest_virtual_concepts'],x['original_component_merger_reductions']] for x in dec])
    gradetable=table(['类别','单元数','口径'],[['A',s['judgment_counts']['A'],'固定焦点原文有支持，正式图表达'],['B',s['judgment_counts']['B'],'原文焦点有支持，旧候选有而正式图未表达'],['C',s['judgment_counts']['C'],'留存导出主张未匹配该完整焦点；不等于所有API从未生成'],['D',s['judgment_counts']['D'],'对象/条件/否定/参数或概念表示不足；含超出核心诊断的属性'],['E',s['judgment_counts']['E'],'本单元明确依赖其他输入/引用，不能推出全语料缺失'],['U',s['judgment_counts']['U'],'表头、范围外、介绍或不完整片段，不强判漏抽']])
    nav=read(OUT/'navigation/counts.json');navtable=table(['视图','可逆向遍历的诊断两跳','其中同源页'],[[name,x['two_hop_diagnostic_traversals'],x['same_source_page_traversals']] for name,x in nav.items()])
    save('EXTRACTION_ATTRIBUTION.md',f'''# 抽取—筛选—发布的知识损失归因

2026-11-17。范围仅expanded1456、域对象`{I.REV}`、15份构建手册。本轮没有运行旧发布门控或重新抽取。以下是记录处理链路与源文代理归因，**不是8000条候选的事实准确率审计**。

## 统计单位与真实链路

- 原始导出{l['raw_export_rows']}行，{l['raw_unique_ids']}个不同原始ID；3行是重复ID出现，不能当3个新事实。
- 当前规范化候选{l['normalized_records']}条；原始导出与规范化并非按行一一对应。{l['raw_rows_linked']}行原始导出有显式ID后代，{l['raw_rows_unresolved']}行未解析出显式链接；规范化中有{l['audit_records_with_raw_ID']}条链接到该原始导出，其余保留未解析状态。不能由16行未链接断言16项知识丢失，也不能由8007−8003推断只淘汰4条。
- 保存的审核状态为1698条自动证据准入候选、881条隔离、5424条拒绝；状态是程序合同结果，不是专家事实标签，也不构成expanded1456的直接母集。
- 从旧证据审核到当前术语规范化，候选当前ID只有6387个相同；利用原/legacy ID后，8003条均可找回对应审核阶段。这是实际ID漂移，不按数组位置拼接。
- 最终1456条来源Assertion对应1400个Claim、2150个业务实体。38个Claim有多条来源记录，Assertion比Claim多56，属于证据聚合，不是56项事实被淘汰。
- 显式发布来源为1326条`baseline_reused`和130条`new_recovered`。这是expanded文件的构建来源字段，**不是读取另一个图谱作本轮实验，也不是1456是1698直接子集**。
- 1456条规范化候选具有发布后代，其中1449条保留相同的类型—中文头名—关系—类型—中文尾名签名，7条签名变化。130条独立重核记录中的定位、条件或表格绑定变化，不能仅凭签名是否变化判断是否发生过修复。发布后代存在也不证明原候选完整正确。

## 互斥主归因与重叠原因

主表先识别发布和已有同签名，再按Schema、保存的定位合同、语义与条件等顺序归类。它是可复算的优先级分解；不是互斥的真实错误因果。各类头尾类型、关系完整分布在`lineage/category_counts.json`，8003条逐条账本在`CANDIDATE_LINEAGE.csv`。

{lineagetable}

完整规范化池有7583个不同类型化中文五元签名；293个重复签名组包含713条记录，21组跨文档。签名相同仍未证明型号、条件、语言副本的事实等价。条件感知签名另列，不能先去掉条件再称同一事实。

重叠信号见`lineage/overlapping_signals.csv`：保存的`evidence_invalid`、`relation_not_entailed`、`dual_qwen_relation_not_entailed`等属于程序记录。许多语义否定同时定位失败，在主表先落入定位类；主表某一语义否定类为0不意味着没有语义问题，更不能把所有`not_entailed`当源文证实错误。E3、缺少证据级别、单元地址和端点定位问题也不能统称PDF解析失败。

## A1：有效但未发布知识的证据等级

六类诊断/维护关系未发布信号共{l['unpublished_six_relation_records']}条，逐条保留旧状态和理由，见`lineage/unpublished_six_relation_signals.jsonl`。信号分布如下；这些不是新语义标签。

{table(['信号类','记录'],sorted(l['A1_signal_classes'].items()))}

冻结源文单元中，7项B有明确局部支持和旧候选；2项C是在留存导出主张中未表达完整焦点；15项D包括对象/条件/类型表示问题，但有些文字已在候选证据或动作文本中出现。它们都来自本轮助手源文阅读代理，不是专家Gold、全语料流失率或新的自动修复成果。

例如MP007 p18导流器O型圈损坏→更换O型圈（SU019）有原生故障表及旧候选，未入正式图；MP004 p4（SU012）的“泄漏时不会失去全部引水”却生成正向导致失水命题，不能作为有用知识简单回收。MP019 p8（SU036）已经输出了0.05mm文字，但把量化条件当成Standard检查对象；这是表示问题，不等于数字从API输出彻底消失。

## A2：只加入强自动支持候选的反事实

未发布池中276条记录满足保存的类型、定位、entailed、无否定veto及有限条件检查，并通过只读原生地址复查；去重为271个关系族，新增419个实体。已识别的条件/禁止/前后阶段线索若无结构条件则暂不纳入（69条被此项暂缓）。**没有识别到线索不证明条件完整；这些边仍全部是未确认的自动代理**。

GA共1671个业务Claim，但只有5条直接连接两个原有组件，另有经新节点形成的联系，原组件数累计减少6；新实体完全独立的组件有156个。271条中184条仅连新节点、74条为新叶连接、8条接入新枢纽，最大业务分量仍54。三诊断角色在同一实体上结构共现仍4个，固定18项参考焦点仍检索4项。

5条直接桥中还出现推进轴套与泵轴套同中文类名的范围风险、一般压力容器试验、以及“故障—处置措施”的抽象定义。源文复查在`details/direct_bridge_source_reviews.jsonl`；不能叫5条已确认可信新增桥。

**结论：抽取/筛选确有局部损失证据；但在当前较保守自动支持口径下，单纯多放入候选主要增加叶节点和新小组件，不能证明会显著解决碎片化。其他未决候选的可恢复量未测，不把8003−1400当潜在收益。**
''')

    save('ONTOLOGY_ASSESSMENT.md',f'''# 实体与关系建模充分性

本轮未修改Schema，也未将相似实体合并。实体/关系清单和类型分布分别在`ontology/type_inventory.csv`、`ontology/relation_inventory.csv`。

## 13类实体与诊断组织

Equipment、Component表示设备和部件；FaultMode、FailureMechanism、Cause区分失效状态、机制和致因角色；Symptom、SignalFeature表示观察表现/量化信号；OperatingCondition保留运行条件；InspectionMethod/InspectionAction与MaintenanceAction分别表达方法、具体检查和处理动作；Standard、Risk提供规范与风险对象。

类型是知识在关系中的语义角色，不应把物理变频器为了满足causes而直接改成Cause，或把材料名为了满足maintained_by而直接改成MaintenanceAction。Cause与FaultMode有时可共享一个故障概念，但不同角色不等于同一实体实例。

实际有{o['same_label_cross_type_groups']}个跨类型同中文名组（例如不对中），{o['numbered_components']}个带括号零件号的Component。不能据此认定全是错分/错拆；应区分类别、带编号部件与来源限定出现。GB保留原ID，只在概念导航层建立联系。

动作实体{o['action_entities']}个：503个MaintenanceAction、252个InspectionAction。检查/维护动作名称中位长度分别10/11，≥35字的动作仅{o['action_labels_ge35']}个。不能用“文本太长”解释全部碎片化；重点是动作对象、阶段和条件是否可组合查询。条件词形标记{o['condition_label_flags']}个也不是17个已证实条件错误。

## 15种关系、方向与实际使用

{relationtable}

当前抽取合同枚举全部15种关系，未发现“某关系未被Schema允许”的接口缺口；显式提示正文、历史不同生成版本及实际模型遵从度仍需分开。记录的生成模型以qwen3.7-max为主，完整分布在`ontology/complete.json`。不能将本轮数据归因于后来7B/27B或SimKGC模型。当前代码可支持不等于已经重建每次历史提示词，原`prompt_sha256`仍保留。

`diagnosed_by`服务诊断目标→方法/检查，`inspected_by`也允许设备、部件及若干故障目标，两者Domain有意重叠。实际类型合法不等于两者语义总能互换。只找到1个同页同源端点的检查/诊断或维护/缓解关系变体组，不能宣称全库普遍混用；真实问题需按源文判读。

`maintained_by`头应为Equipment/Component，`mitigated_by`头应为Cause/FailureMechanism/FaultMode/Risk。材料、零件、工况与动作对象混淆是记录表示问题，不是新增一个任意关系就能解决。`causes`方向按致因→结果；SU012的否定语境不能只用类型翻转纠正。

contains=17、located_in=5、occurs_at=1，而维护/因果/检查较多，不能推出原文没有部件关联或关系定义错误。SU037“Premature bearing failure”把部件与失效复合在同一FaultMode名称中；源手册还存在零件图、编号和矩阵，未转成独立结构关系。发生关系少至少有“已含在复合名词/表格/引用中”这一替代解释。

## 明确的问题与边界

- SU042检查对象应是泵口，原候选却以OperatingCondition“对中”为头。现有Component inspected_by InspectionAction已经足够，不需要增加关系。
- SU036间隙参数被当成Standard头实体，正确对象/参数绑定不足；数字并非必然没有保存。
- SU029把检查和紧固一起标InspectionAction，源文字已出现，检查角色与纠正角色却未分开。
- SU023故障原因编号需要关联同手册的编号定义；把数字串当Cause会保留文字而丢失可查询原因。
- SU009、SU012、SU045需保留许可例外、否定、操作先后及设备状态；普通正向三元组不足以替代这些命题。
- 材质、设计能力和替代密封（SU038/040/043）属于本体/属性边界，但并非所有说明书属性都必须扩成主图关系。先判断是否服务实际诊断问题，再选择适用范围/属性字段，避免无必要扩展Schema。

当前1400个Claim全部类型合法，但仍只有自动合同意义。原Assertion中130条有结构条件字段、130条有modality；其余没有独立字段不自动等于条件已丢失，因为条件可能还在实体名、动作或证据文字中。条件字段存在同样不证明作用对象绑定正确。

## GB分层表示究竟做了什么

GB保持2150业务实体、1400个业务Claim及1456来源记录不变；增加239个虚拟概念、1004条映射。映射包括既有别名假设、相同词形跨角色、编号部件家族及动作中的明确部件名提及。它们不确认身份相等，也不增加业务事实。

来源限定出现单独保留`entity + Claim + doc/page + pump_type + conditions/modality`。这是来源限定实例出现，不虚称实际船舶物理设备实例。共享文档/Scope节点不参与业务或概念投影连通统计。

{virtualtable}

GB最大异构分量1175个节点包含989业务实体和186虚拟概念；原业务最大分量仍54。去掉部件提及索引后，最大异构分量203（187业务实体+16概念）。组织增强主要不是证实了很多身份等价。无论主GB还是GAB，固定焦点的精确检索并未增加，概念候选检索也没有提高。

**判断：13/15模式覆盖了多数核心因果、检查和处理关系，本轮不足以认定Schema整体过窄。更直接的问题是类别/实例/角色、动作对象、原生分支及适用条件缺少清晰可计算关联。虚拟概念导航可组织片段，但不能代替缺失的合法业务事实，也未证明本轮词形索引足够解决诊断覆盖。**
''')

    book=['# 实体、关系和来源范围案例\n\n下列为本轮助手阅读分析，非专家Gold。显示折行可压缩；精确原文、原生ID、页哈希和全部候选ID在`SOURCE_UNIT_AUDIT.jsonl`。分类针对固定焦点，并非整个页面所有事实的穷尽标注。\n']
    for sid in ['SU003','SU010','SU012','SU019','SU023','SU027','SU029','SU031','SU032','SU033','SU036','SU039','SU040','SU042','SU043','SU045']:
        u=next(x for x in units if x['sample_id']==sid);book.append(f"## {sid}：{u['doc_id']}物理p{u['pdf_page_number']}，{u['primary_source_judgment']}\n\n原文：\n\n> "+'\n> '.join(u['original_source'].splitlines())+f"\n\n原生单元：`{u['native_unit_id']}`；页SHA256 `{u['page_text_sha256']}`。\n\n初始候选ID：{'、'.join(u['all_same_page_candidate_ids'][:8]) or '本页留存候选未发现'}；完整清单见逐单元JSONL。\n\n焦点正式Claim：{'、'.join(u['exact_typed_published_claims']) or '未发现焦点的同类型五元签名'}。同页其他Claim不能替代本焦点。\n\n解释：{u['reason']}\n")
        if u['reference']:book.append(f"源文代理参考：{u['reference']['head_canonical_zh']} → {u['reference']['relation']} → {u['reference']['tail_canonical_zh']}。仅评价/GC使用，不是新修复器或新增正式知识。\n")
    book.append('## GA直接桥的源文复查\n\n结构上连接旧组件并不等于语义上可用于同一泵实例。5条直接桥全保留，不按结果挑选：\n')
    for b in read(OUT/'details/direct_bridge_source_reviews.jsonl'):
        ss=b['sources'][0];book.append(f"- `{b['claim_id']}`：{b['head']['label_zh']} → {b['relation']} → {b['tail']['label_zh']}；{ss['doc_id']}物理p{ss['pdf_page_number']}，原文 `{ss['evidence_text']}`。{b['source_reading_note']}\n")
    book.append('\n同一中文“轴套”若代表部件类别，可组织推进轴套与泵轴套；若解释为同一个物理实例则越界。MP003 p312明确是Propulsion Shafting，不是泵手册。这说明问题在于身份层与适用范围，而非水压试验这个关系本身一定错误。\n')
    save('ENTITY_RELATION_CASEBOOK.md','\n'.join(book))

    unittable=table(['单元','文档/物理页','主类','焦点正式Claim数','说明'],[[u['sample_id'],u['doc_id']+'/'+str(u['pdf_page_number']),u['primary_source_judgment'],len(u['exact_typed_published_claims']),u['reason']] for u in units])
    save('DOCUMENT_KNOWLEDGE_AUDIT.md',f'''# 原始文档诊断知识的固定样本核查

## 先抽样、后判断、再计算视图

15文档各3个单元，共45；实际14个原生表组、31个正文行窗口。三层为原生表、无发布记录页面正文、有条件线索正文，跨不同物理页，散列种子`rp1-root-cause-20261117`。实际无发布记录页面单元{f['unpublished_pages']}项；不是只抽正式KG证据。采样前纯格式检查剔除目录点线、页脚和空表头，初始样本与变更说明保存在`source_sample/pre_format_check/`和`FORMAT_CHECK.md`；没有按语义类别/视图成绩替换。

样本仍含14项U：部分表头、前言、设备范围外或窗口不完整。它们全部保留，说明采样框不等于确切可抽事实集，不事后删除来提高覆盖。该样本不是全语料代表性/独立现场案例，不能外推严格Recall。

源文判断来自Codex助手，非另一个独立模型或专家。18个原子焦点参考与16个复合焦点在计算视图前固定，文件哈希见`source_sample/REFERENCE_FREEZE.json`；规范名与既有候选对齐不构成独立Gold。

{gradetable}

4项A、7项B、2项C和5项D中的纠正后原子表示组成18项原子参考。正式图精确可检索4项，另外14项分别是7项已有候选未发布、2项导出主张未表达、5项需要对象/角色等表示调整。不能把这14项当全语料新增事实估计。

16项复合焦点中，完整必需字面片段在单个导出记录保留字段中匹配{ret['export_records_literal_context_present_units']}项，正式来源字段匹配{ret['published_literal_context_present_units']}项。该严格字面检查不等于语义判分；未匹配可能是断行、近义表述或分散字段，不能断言彻底丢失。SU029的检查/紧固、SU036的0.05mm等本就有文字，问题是角色和参数归属。

## 逐单元结果

{unittable}

## 跨文档共性不等于精确重复

复用原结构审计的12个跨文档同Claim族（全为同声明来源家族）与本轮32个跨类型同名概念组，不能用前者代替所有共通知识。前者只覆盖类型化名称精确一致的记录；后者也不是身份等价。

已有17条跨文档三前提模式线索已复制到`details/cross_document_pattern_leads.jsonl`：15条仅MP004/MP005，1条再涉及MP018，1条MP018/MP019。SA与NSL共享吸入/流量相关模式，泵与电机轴承可共享润滑词汇，但型号、部位和操作条件未因此相同。它们可成为概念/模式研究样本，不是17项确认可迁移事实。

可追溯分类应分为：精确类型化Claim族；可共享词形/概念；有显式关系前提但范围未决的模式；仅表面相似；具体条件不兼容；未知。每类不能由cosine阈值直接提升为事实。

## 哪些才支持补资料

SU033（MP018 p15）明确要求本机Actual Assembly Drawing，而不是Typical Drawing，用于确定轴承类型和位置；且源页区分Model F与Model FS。这是具体配置资料需求。SU041的ESB-515引用在本手册附录，先处理跨引用，不能据此认定需要新手册。SU005是RCM分析输入要求，不证明这些输入在其他15文档均不存在。

与上一轮已定位原句合并，具体资料需求限于：MP005 p13所指NSL型号产品数据/运行曲线；MP017 p18所指匹配型号的Maintenance and Repair Manual；MP018 p15所指本机装配图与轴承配置。没有全语料语义不存在证明，也没有批量下载。

**结论：现有手册确有尚未被正式图正确、完整组织的诊断知识；同时存在真实的型号/配置资料引用需求。当前证据不支持把总体碎片化主要归咎于“15份文档没有共性”，也不能给全语料漏抽率。**
''')

    save('COUNTERFACTUAL_VIEWS.md',f'''# G0 / GA / GB / GAB / GC受控对照

所有视图在本目录，正式expanded1456不变。原始事实的“已知”仅指现有自动构图发布状态，未经过逐条专家确认。

| 视图 | 事实集合与表示 |
| --- | --- |
| G0 / GB0 | 现有2150实体、1400 Claim、1456来源记录 |
| GA | G0加276条强自动支持记录，聚合为271潜在Claim；不重写原值、不重新发布 |
| GB / GB1 | 与G0完全相同的业务事实；添加概念导航及独立的来源限定出现层，不合并实体 |
| GAB | 与GA完全相同的业务事实，叠加同一映射机制 |
| GC | 固定源文样本的18项原子代理参考子图，另存16项复合源文参照；非全语料完整参考图 |

GA按类型、旧语义状态、保存的定位合同、无旧否定veto、声明范围及有限条件检查筛选；原生地址复查只是只读确认，不是重跑发布门控。未决条件和隐含型号仍未全部识别，所以所有GA边都保留自动代理标志。

GB的词形/别名/编号/部件提及虚拟边与业务边分开；不引入“同文档就全连”的来源hub。来源限定出现不冒充真实物理设备实例。条件、阶段、可能性都保留来源；异构路径不自动蕴含业务关系。

## 业务投影：可比较的统计

{maintable}

GA新增419实体、271 Claim，其中184条只连新节点、74条新叶、8条新枢纽、5条直接旧组件桥。旧组件累计减少6，新节点独立组件156；最大分量不变54。总组件数上升是新增许多小片段，不等于旧组件反而断裂。GA/GAB的271条都未确认事实正确性。

在业务投影中GB与G0逐条Claim相同，GAB与GA相同，因此不能将其精确业务规模或节点度的变化伪装成增益。三诊断角色（原因/检查/措施）同节点结构共现G0/GA/GB/GAB=4/4/4/4，且不证明条件可联合。

有效两跳只统计预先固定的合法导航模式，如causes→diagnosed_by、causes→mitigated_by、occurs_at→maintained_by；保存同源页/声明泵型重叠，不推导传递因果或强制处理路径。数量见QUALITY_METRICS和`diagnostic_navigation_paths.jsonl`，条件联合支持仍未确认。

诊断也可先逆向查原因再查该原因的检查/措施；补充遍历视图如下。`causes^-1`只是遍历方向标签，未存成新的关系或推断事实。与正向路径分开，避免把少量正向路径误解为完全无法诊断：

{navtable}

## 概念投影：只能解释组织能力

{virtualtable}

GB原业务分量仍758，概念投影491；267是虚拟组织连接减少量，不是267项新事实或被修复错误。去掉部件提及后只剩77的组织减少量，说明很大部分来自词面索引，而不是已证实身份对齐。该拆解是事后解释性消融，没有改变主方法或参考问题。

## 固定任务的含义

18项问题在每个视图使用完全相同的焦点和答案；精确要求类型化五元签名与相同来源文档。G0/GA/GB/GAB均4/18，较弱概念导航候选也均4/18。它是局部源文代理的可检索性，不是诊断准确率、严格召回率或模型独立测试。没有重新使用224测试答案选参。

GC的18/18按参考子图构造成立，不是模型学会恢复18项。其18个单边分量来自每个可评价焦点只标一项，**不能以此判断原文也碎片化**。GC的16个复合源文参照单独存储，来源可访问性按构造可用，与正式Claim条件字段率不是同一指标。

对于仅本体改变的视图，精确五元关系检索不变部分是设计不变性；不能据此断言任何本体改造无效。需要检验的是概念导航是否找到额外、范围一致的候选，本轮有限映射在这18项上尚未做到。新对象/条件结构化方法仍不能从本轮虚拟层自动获得有效性证据。

## 不可识别的因果贡献

GA依赖旧自动判断，GB依赖词形/别名假设，二者可能交互；样本非独立Gold，原始文档也没有全量事实清单。不能把组件减少比例写成文档、抽取、建模三因素的因果百分比。当前边界是：正式图修改0；GA潜在增加271关系族、6个原组件减少；GB增加0业务事实、267个虚拟组织减少；正确知识收益未由独立事实参考证明。
''')

    save('QUALITY_EVALUATION_FRAMEWORK.md','''# RP1知识图谱质量的分维评价体系

只把相同统计对象的指标作配对比较，不以单一密度衡量质量。QUALITY_METRICS.csv为长表，每行注明视图、投影、分母、单位、证据等级与限制；NA表示当前无法测量，不能用0代替。

| 维度 | 本轮可精确自动计量 | 需要源文语义判断的代理 | 需要独立事实/任务参考才能声称 |
| --- | --- | --- | --- |
| 事实质量 | 类型/方向合同、旧状态、字面地址、显式字段 | 原文支持、真正方向、条件所有权、重复风险 | 真实事实准确率、方向正确率、同设备同阶段冲突率 |
| 知识覆盖 | 固定源文单元与Claim/候选链接、各角色记录量 | 18项AI焦点可检索性、未表达复杂语义 | 全语料Recall、独立故障类别覆盖 |
| 本体质量 | 13/15关系可用性、Domain/Range、名称粒度、角色分布 | 类别/实例是否合理、对象与参数绑定 | 经独立参考验证的建模完整性 |
| 结构质量 | 业务度数、分量、旧组件联系、导航两跳 | 路径的实际诊断意义与适用范围 | 正确可执行诊断链的有效率 |
| 来源追溯 | 来源文档/物理页/单元/哈希、来源族标签数量 | 来源家族独立性、条件与原文共同支持 | 经独立核验的多来源佐证效力 |
| 任务质量 | 同一固定参考集合的精确/概念候选检索计数 | 源文AI支持与复杂问题可回答性 | 现场诊断准确率、真实安全决策表现 |

定义与实际程序对应：

1. Schema合规比=合法Domain/Range的业务Claim数/业务Claim总数。它只测合同合法。
2. 来源覆盖比=至少有一条来源记录的Claim数/Claim总数。源文存在不等于语义正确。
3. 单Claim双实体分量：只有两个业务实体、一对邻接及一个Claim；Assertion多重来源不增加边数。
4. 角色覆盖：按真实方向统计incoming causes、outgoing diagnosed_by/inspected_by、mitigated_by/prevented_by和occurs_at；不人为创造症状→原因的新关系。
5. 固定参考检索比=有相同类型化命题且同文档来源的焦点数/18。它不是独立Recall；概念导航候选数另列，不能代替精确关系或完整条件支持。
6. 声明来源族数=Claim支持记录的不同source_family_id标签数；这是依赖代理，不保证真正独立。语言版本不增加独立性。
7. 旧组件合并减少量：将新增视图的每个连通块映射回原组件集合，累计其中原组件数减1；仅GA是自动业务假设，GB是虚拟组织，二者不得混作正确事实增益。
8. 条件字段数量与文字保留频道分别统计。缺独立字段不能直接判语义丢失，有字段也不能直接判作用对象正确。

本轮G0类型合规1400/1400、来源覆盖1400/1400，沿用既有审计的1456来源原生地址合同；这些都不得改称100%事实准确率。当前每个Claim只有一个声明来源家族，不能声称已证明真实独立多来源佐证。

对事实准确率、完整条件绑定率、真实冲突率、全量Recall和现场诊断准确率，CSV明确保留NA。未来如果获得新的独立参考，应冻结版本、范围和评分规则；无需也不得把现有自动审核提升为专家Gold来填满表格。
''')

    save('ROOT_CAUSE_ANALYSIS.md',f'''# 图谱碎片化成因：证据而非虚构贡献率

结论：**目前证据最直接指向“知识虽在源文中，但对象/角色、分支和适用范围没有充分成为可查询的Claim结构”；抽取/筛选亦有局部流失。缺少特定配置资料是真问题，但没有证据把总体碎片化主要归因于文档没有共性。**不能用这一次代理实验给三因素编造贡献百分比。

## 原始文档因素

15份手册服务不同厂家、泵型、驱动和规范语境，不是同一艘船的同一台设备记录，本来就不应把所有同名部件合并。固定45单元中有14个非目标/不完整或非诊断片段，体现资料用途异质。另有明确的型号曲线、维修手册、实际装配图引用需求。

但SU010/019/031/037等故障表本身有原因、表现和措施；原文并非普遍没有诊断关联。17条跨文档模式前提与32个跨类型同名概念也表明精确重复Claim数不足以衡量共性。没有穷尽事实参考，文档因素的比例未知。

## 抽取—筛选因素

8007行原始导出、8003规范化记录和1400 Claim的单位不同。显式ID和来源链路已复算；重复、聚合、7条签名变化、130条独立重核均保留。源文焦点B7、C2证明局部流失存在，D15还有文字/参数已出现但结构未充分表达的情况。

GA的276记录/271关系族是当前强自动条件下的潜在池，不是271项已证实正确知识。新增271边后最大业务分量54不变，只有5条直接桥，旧组件累计减少6；且直接桥仍有适用范围或抽象性问题。该结果不能推导其他拒绝候选永远不可恢复，也不能证明靠宽松门控就能解决碎片化。

## 实体与关系表示因素

13/15模式在核心因果、检查、维护上可用，当前1400 Claim也全部类型合法。实际问题包括条件作对象、物理材料作动作、量化条件作Standard头、部件/失效复合名词、编号引用和跨范围类名等；多数例子不需要增加关系种类。

GB保持全部业务事实不变，概念导航将异构分量758→491，但业务分量仍758、最大54；18个固定焦点仍只检索4项。去掉部件提及索引后，组织减少量267降到77。**这证明单纯加概念hub可以显著改变图形，却未证明事实/诊断改善。**也不能据GB有限词形映射的负结果否定真正的对象—条件—实例建模。

## 可识别边界

| 论断 | 当前证据 |
| --- | --- |
| 存在源文支持但未发布的知识 | 7个固定焦点的助手源文代理；保留候选ID与原文 |
| 存在导出主张遗漏 | 2个固定焦点；不等于全API输出完全没有 |
| 存在对象/条件/粒度问题 | 15个D，包含部分属性/范围边界；非全库错误率 |
| 强自动池可以增加多少结构 | 271潜在Claim、419实体；不是正确知识增益 |
| 能否连接旧组件 | 自动假设下减少6；5条直接桥仍需范围复核 |
| 概念层能否组织更多片段 | 1004虚拟映射、239概念；267组织减少，0新增业务事实 |
| 是否增加本轮诊断焦点检索 | G0/GA/GB/GAB均4/18；概念候选检索也未增加 |
| 文档、抽取、建模各占百分之几 | 不可识别；代理集合交互且无独立完整事实参考 |

GC18/18是源文代理参考的构造结果，其18个孤立焦点也不是原文知识拓扑的完整描述。不得拿这个GC证明原文稀疏，或拿它冒充新算法100%准确。

**总体判断：先改善源文到Claim的对象/角色/范围表示，比继续调transport_R3更有依据；同时仅补明确缺口的具体型号资料。当前不支持重新全语料抽取、放松门控、强行实体合并或继续扩大模型复杂度。**
''')

    save('RP1_NEXT_STEP.md',f'''# RP1下一步：优先修正知识表示基础，暂缓继续调transport_R3

2026-11-17。一次性归因实验已完成，不再把本阶段扩成重复稀疏性调查。

**决定：下一阶段优先做隔离的、保持源文条件的Claim/实体表示修订验证；不直接修改正式expanded1456，也不先优化transport_R3。**

实际依据：

1. 固定45个源文单元中有7项B、2项C、15项D；18个可表达原子焦点只有4项能从正式图精确检索。数据说明源文与模型可用的结构化命题之间存在局部断层，不能全归咎于文档缺乏共性。
2. 276条强自动支持记录仅增加271个潜在关系族，主要形成新叶与小组件；直接旧组件桥5条、累计旧组件减少6，最大业务分量仍54。单纯回收旧候选不够。
3. 概念层1004条虚拟映射显著组织片段，但业务事实与18项焦点检索未变。后续不应以连通性作为成功判据，也不应仅将相似实体强行合并。
4. 原有transport_R3验证结果为已知历史开发结果，上一轮T3微弱且不稳定、T4实际无阻断；本轮没有新训练或测试。对象、型号/阶段等若尚未进入输入，再调检索融合或门控损失缺乏针对性。

## 四项工作的优先级

| 优先级 | 工作 | 边界和理由 |
| --- | --- | --- |
| 1 | 完善实体/Claim的对象、概念与适用范围表示 | 首先处理物理对象与角色、类别与编号部件、条件/否定/阶段，保留原ID与source，不靠聚合制造事实 |
| 2 | 定向原生表格分支/跨引用映射 | SU019更换O型圈、SU023原因编号、SU036参数对象和SU042泵口检查等可作为固定开发反例；不重抽15手册、不重跑旧发布门控 |
| 3 | 条件满足后再检验transport_R3 | 使用独立、固定的源文任务与可观察范围；先证明有用输入增加，再决定GPU训练是否必要，不使用旧224测试调参 |
| 并行限量 | 补具体技术资料 | 仅查找NSL型号数据/曲线、Gorman-Rupp匹配型号维修手册、Patterson本机装配图。先查已有附件/附录，不批量下载通用手册 |

这里“优先修正知识图谱本身”指**知识表示/输入版本的隔离候选**，不是现在覆盖正式图。当前所有GA/GB/GC都只是本目录诊断视图；RP2/RP3、原图和旧模型保持原样。

## 下一次最小验收边界

如继续实施，只冻结一个保留对象与适用条件的表示版本，复用现有候选与源文，不再堆叠新的门控损失。比较相同事实来源下的原表示与新表示；以源文支持的对象/条件绑定及固定问题可检索性为主，结构只是辅助。现有45单元已作为开发诊断，未来独立验证须另冻结，不能重命名成新测试。

只有新表示在独立参考上增加完整可用诊断知识、且范围错误不增加，才进入KGC模型比较；否则保留负结果。不要以LCC、规则通过率或把参考答案装入GC后的18/18作为算法收益。

## 论文可以与不能写

可以写：记录链路已追踪；局部源文损失与表示问题有实例；自动候选补入与概念导航的作用不同；多维质量评价揭示密度不代表任务质量。不能写：三因素贡献率、专家事实准确率、271项确认新知识、GB证实身份合并、或本轮已证明新的补全算法有效。

复现、逐条原文与全部数值分别见`REPRODUCE.md`、`SOURCE_UNIT_AUDIT.jsonl`、`QUALITY_METRICS.csv`。这份结论本身不授权改变正式图或历史实验。
''')

    save('REPRODUCE.md','''# 一次性归因实验复现

运行环境：服务器CPU、Python 3.11、NumPy、NetworkX。无需GPU、模型推理、外部API或新的embedding。域对象833c8040058055434c7f6a9595ec524c3935755f；使用同一输入工具的允许列表，其他历史图谱不作为本轮事实输入。

```bash
cd /home/hengshan10/08-zxk/Fault_LLM_V2
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/freeze_sample.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/lineage.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/review_source_units.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/views.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/ontology.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/detail.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/add_quality.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/navigation.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/retention.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/write_reports.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/verify.py
```

已有阶段产物时脚本复用，不重写。完全重新计算应在独立checkout、同一输入版本和父实验文本资产下复制本目录code/与local_llm/，不复制本轮完成标记/结果，再按顺序运行；不要删除现有研究结果强制重跑。格式检查前初始采样保留，但最终采样规则在代码中，完全复算直接得到最终样本。

freeze_sample只切分原生单元并固定样本，不重新抽取三元组。review_source_units中的A—U与参考是显式助手阅读注释；统计重现不能证明注释独立正确。所有原审核状态原样保留，GC参考只用于评价，不作为GA/GB或KGC训练输入。

读取领域原始对象和15页缓存的工具为`../kg_enhancement_task_comparison/code/inputs.py`。定位合同复用`../post_extraction_feasibility_20261113/candidate_locator_audit.jsonl`，没有运行旧发布流水线。G0结构基准与原组件ID复用`../kg_structure_cross_document_audit_v1/`，并作等值校验。上一轮17模式与具体文档引用仅作为已有证据复用。

SHA256见source_sample/input_hashes.json、lineage/input_hashes.json、details/parent_input_hashes.json和verification/。完整新成果清单为delivery_manifest.json。模型、响应、数值缓存及日志保留本地；Git发布源代码、文本结果和哈希，不因未上传二进制而删除资产。

可选本机复核工具见local_llm/；默认关闭，当前服务器硬拒绝，只有获得逐输入外传授权并在本机显式启用才可能发送。主流程0次API调用，所有统计在服务器执行。未进行任何新的SimKGC/transport_R3训练，未用旧224测试答案选参，未写expanded1456、RP2/RP3或Neo4j。
''')
    save('README.md','''# RP1稀疏性成因与建模充分性：一次性受控归因

2026-11-17。入口：[下一步决定](RP1_NEXT_STEP.md)、[成因结论](ROOT_CAUSE_ANALYSIS.md)、[五视图对照](COUNTERFACTUAL_VIEWS.md)。

实际完成8007原始导出行/8003规范化记录的链路追踪、45个冻结源文单元、18项原子及16项复合代理参考、G0/GA/GB/GAB/GC对照和多维质量评价。

GA：276自动记录→271潜在关系族，直接旧组件桥5条、累计组件减少6，最大业务分量仍54。GB：0新增业务事实，239虚拟概念/1004映射；异构连接改善，固定精确焦点仍4/18。GC的18/18按参考构造成立，不能作算法收益。

- [候选流失归因](EXTRACTION_ATTRIBUTION.md)，逐条账本CANDIDATE_LINEAGE.csv
- [实体与Schema充分性](ONTOLOGY_ASSESSMENT.md)，[实际案例](ENTITY_RELATION_CASEBOOK.md)
- [源文诊断单元核查](DOCUMENT_KNOWLEDGE_AUDIT.md)，逐条SOURCE_UNIT_AUDIT.jsonl
- [多维质量体系](QUALITY_EVALUATION_FRAMEWORK.md)，数值QUALITY_METRICS.csv
- [复现步骤](REPRODUCE.md)，[可选本机复核](local_llm/README.md)

本轮不重抽、不重训、不重跑旧发布门控、不合并实体、不修改正式图谱或RP2/RP3，不调用外部LLM。助手源文判断与自动合同均非专家Gold，无独立事实准确率/Recall或三因素因果贡献百分比。
''')
    print('Required research reports written',flush=True)


if __name__=='__main__':main()
