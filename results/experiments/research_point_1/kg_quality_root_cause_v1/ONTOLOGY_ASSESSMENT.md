# 实体与关系建模充分性

本轮未修改Schema，也未将相似实体合并。实体/关系清单和类型分布分别在`ontology/type_inventory.csv`、`ontology/relation_inventory.csv`。

## 13类实体与诊断组织

Equipment、Component表示设备和部件；FaultMode、FailureMechanism、Cause区分失效状态、机制和致因角色；Symptom、SignalFeature表示观察表现/量化信号；OperatingCondition保留运行条件；InspectionMethod/InspectionAction与MaintenanceAction分别表达方法、具体检查和处理动作；Standard、Risk提供规范与风险对象。

类型是知识在关系中的语义角色，不应把物理变频器为了满足causes而直接改成Cause，或把材料名为了满足maintained_by而直接改成MaintenanceAction。Cause与FaultMode有时可共享一个故障概念，但不同角色不等于同一实体实例。

实际有32个跨类型同中文名组（例如不对中），29个带括号零件号的Component。不能据此认定全是错分/错拆；应区分类别、带编号部件与来源限定出现。GB保留原ID，只在概念导航层建立联系。

动作实体755个：503个MaintenanceAction、252个InspectionAction。检查/维护动作名称中位长度分别10/11，≥35字的动作仅5个。不能用“文本太长”解释全部碎片化；重点是动作对象、阶段和条件是否可组合查询。条件词形标记17个也不是17个已证实条件错误。

## 15种关系、方向与实际使用

| 关系 | Domain → Range | 原始导出行 | 规范化记录 | 正式Claim |
| --- | --- | --- | --- | --- |
| causes | Cause/FailureMechanism/OperatingCondition/FaultMode → FailureMechanism/FaultMode/Symptom/SignalFeature/Risk | 961 | 971 | 294 |
| contains | Equipment/Component → Component | 653 | 371 | 17 |
| diagnosed_by | Cause/FailureMechanism/FaultMode/Symptom/SignalFeature/Risk → InspectionMethod/InspectionAction | 321 | 751 | 125 |
| evolves_to | FaultMode/FailureMechanism → FaultMode/FailureMechanism/Risk | 1 | 1 | 1 |
| increases_risk_of | Cause/FailureMechanism/FaultMode/OperatingCondition → Risk | 42 | 42 | 0 |
| indicates | Symptom/SignalFeature → Cause/FailureMechanism/FaultMode/Risk | 333 | 349 | 25 |
| inspected_by | Equipment/Component/Cause/FailureMechanism/FaultMode → InspectionMethod/InspectionAction | 2005 | 1575 | 283 |
| located_in | Component → Equipment/Component | 85 | 85 | 5 |
| maintained_by | Equipment/Component → MaintenanceAction | 1351 | 1390 | 344 |
| manifests_as | FaultMode/FailureMechanism → Symptom/SignalFeature | 177 | 163 | 20 |
| mitigated_by | Cause/FailureMechanism/FaultMode/Risk → MaintenanceAction | 824 | 784 | 96 |
| occurs_at | FaultMode/FailureMechanism → Equipment/Component | 15 | 282 | 1 |
| operates_under | Equipment/Component → OperatingCondition | 241 | 241 | 29 |
| prevented_by | Cause/FailureMechanism/FaultMode/OperatingCondition/Risk → MaintenanceAction | 608 | 608 | 110 |
| specified_by | Equipment/Component/FaultMode/FailureMechanism/Symptom/SignalFeature/Cause/OperatingCondition/InspectionMethod/InspectionAction/MaintenanceAction/Risk → Standard | 390 | 390 | 50 |


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

| 概念投影 | 业务Claim | 虚拟映射边 | 异构分量 | 最大异构分量 | 其中业务实体/虚拟概念 | 原组件组织减少 |
| --- | --- | --- | --- | --- | --- | --- |
| GB / all_frozen_mappings | 1400 | 1004 | 491 | 1175 | 989/186 | 267 |
| GB / without_component_mention_index | 1400 | 149 | 681 | 203 | 187/16 | 77 |
| GAB / all_frozen_mappings | 1671 | 1249 | 583 | 1408 | 1187/221 | 278 |
| GAB / without_component_mention_index | 1671 | 185 | 810 | 209 | 193/16 | 83 |


GB最大异构分量1175个节点包含989业务实体和186虚拟概念；原业务最大分量仍54。去掉部件提及索引后，最大异构分量203（187业务实体+16概念）。组织增强主要不是证实了很多身份等价。无论主GB还是GAB，固定焦点的精确检索并未增加，概念候选检索也没有提高。

**判断：13/15模式覆盖了多数核心因果、检查和处理关系，本轮不足以认定Schema整体过窄。更直接的问题是类别/实例/角色、动作对象、原生分支及适用条件缺少清晰可计算关联。虚拟概念导航可组织片段，但不能代替缺失的合法业务事实，也未证明本轮词形索引足够解决诊断覆盖。**
