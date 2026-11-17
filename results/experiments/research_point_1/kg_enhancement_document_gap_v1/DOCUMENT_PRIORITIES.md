# 有具体证据的文档补充需求

2026-11-16。没有下载、上传或重新抽取文档。优先级来自明确引用和关系缺口，不来自文档短或图边少。

## P1：DOCREQ-NSL-LIMITS

需要：DESMI NSL具体型号/叶轮配置的产品数据表、性能曲线与允许运行包络。

范围：NSL monobloc/spacer centrifugal pump; fluid, impeller diameter and speed must match。

依据：MP005物理p13，page SHA256 `93eeb30c8e0845d6d11983113f8be903092ad34c8995c067fb150c93108bae1f`。原文片段：

> • Never operate the pump without the fluid to be handled. • Observe the information on minimum flow rates specified in the product literature (to prevent overheating, bearing damage, etc.). • Observe the information on maximum flow rates specified in the product literature (to prevent overheating, mechanical seal damage, cavitation damage, bearing damage, etc.). • Do not throttle the flow rate on the suction side of the pump (to prevent cavitation damage).

补什么：把最小/最大流量、温压运行限值与汽蚀/过热风险绑定；当前源文明确把数值引用到产品资料。

关联缺口ID：KGAP-1e57abcbfa74adcc92、KGAP-bf80316cf120621aa6、KGAP-a0dea80795a4407f57、KGAP-3dda66e80e52175646、KGAP-ba4415062ece9795be、KGAP-48293b00fe9b3a76e6、KGAP-9e9d2ea9262feaef94、KGAP-be6154635ad51c699a、KGAP-4610f499349b637e51、KGAP-2fde2a642d373a11ea、KGAP-130a46ec7b4500c145、KGAP-7e4284f2e8ce2833ea。完整ID清单见`gaps/document_requests.jsonl`。

先排重：检索15份已有手册的具体型号/配置和数值表，确认是否已有可用段落。仅引用到配套资料不证明整个语料都没有相同知识。不要购买/下载另一份通用维护概述来替代型号资料。

## P1：DOCREQ-GR-REPAIR

需要：与OM-04760对应具体泵型号的Gorman-Rupp Maintenance and Repair Manual及故障排查表。

范围：Gorman-Rupp self-priming centrifugal pump; recorded model/serial number needed。

依据：MP017物理p18，page SHA256 `7d054582c8f605cb21a78d58ba8989d98a3610a1dc36a11e7913ce0835a85f88`。原文片段：

> excessive, stop the pump and refer to Trouble- shooting in the Maintenance And Repair Manual for possible causes. Strainer Check If a suction strainer has been shipped with the pump or installed by the user, check the strainer regularly, and clean it as necessary. The strainer To avoid serious damage to the pump, shouldalsobecheckedifpumpflow ratebeginsto

补什么：将异常噪声/过振动与原因及排查、维修步骤关联；已有运行手册明确指向配套维修手册。

关联缺口ID：KGAP-99f2329f83a88dad9d、KGAP-5c5d63adccadfb55fc、KGAP-222cb0db6538bebd1d、KGAP-5750a106e58bbcb78d。完整ID清单见`gaps/document_requests.jsonl`。

先排重：检索15份已有手册的具体型号/配置和数值表，确认是否已有可用段落。仅引用到配套资料不证明整个语料都没有相同知识。不要购买/下载另一份通用维护概述来替代型号资料。

## P2：DOCREQ-NDT-APPLICATION

需要：对应泵轴/泵壳材料的无损检测工艺和验收规范（含表面/近表面边界）。

范围：actual pump component material and test condition, not all rotating machinery。

依据：MP001物理p93，page SHA256 `f6d7a195f9eb602408749ae54662669b7bac8daef8642ac3fb8c3a42be51f28e`。原文片段：

> 2.2 Liquid Dye Penetrants The use of liquid dye penetrants can help detect surface discontinuities or cracks due to problems such as fatigue, wear, surface shrinkage, and grinding. The technique involves applying liquid dye penetrant to a test surface and then allowing sufficient time for the dye to penetrate the surface. Next, excess penetrant is removed from the surface, and the surface is retreated with a developer that draws the penetrant to the surface revealing the location of imperfections. Liquid penetrants are categorized accordin

补什么：对液体渗透与磁粉检测迁移补齐材料、缺陷深度与可检性约束；已有ABS材料不应再泛化复制。

关联缺口ID：KGAP-428d9d98d8889d0127、KGAP-7f850ceda42d8be548、KGAP-9097eab3b7ce9bcbde、KGAP-4d007795d6873922e6、KGAP-840e841f51d46bb7c0、KGAP-f6cd69b57fe08d123b、KGAP-6f68f085fa1c44781a、KGAP-9b4251a7763b9210db、KGAP-0cc7832616e133a8a4、KGAP-4d45b17c10b4253f3c、KGAP-7b3f862e0fc745a319、KGAP-77fc851e992435044b。完整ID清单见`gaps/document_requests.jsonl`。

先排重：检索15份已有手册的具体型号/配置和数值表，确认是否已有可用段落。仅引用到配套资料不证明整个语料都没有相同知识。不要购买/下载另一份通用维护概述来替代型号资料。

## 不应据此补文档的情况

MP022 p22已有过载、汽蚀、轴封泄漏的原因/处理表；图内断连不说明该手册缺少故障排查知识。MP019各语言版是同一来源家族的副本，不属于新增独立来源。MP006安装指南没有完整诊断表，也不能据此断言其他14份文档没有该知识。MP001 p93–95已经有检测限制；应先关联现有材料，只有特定泵部件的验收标准仍不足时才考虑P2。

## 缺口统计的正确解释

`KNOWLEDGE_GAPS.csv`检查365个FaultMode/Symptom节点，形成886个“实体×Schema允许但当前缺少的诊断角色”机会：原因226、检查281、措施136、部件243。它不是886个真实缺失事实，也不是召回率分母；如“故障模式”之类抽象概念本身未必需要每个槽位。

互斥归因：16项有同声明范围的旧自动证据/语义契约记录；819项只有部分/未核实来源线索；26项只匹配其他声明设备类别，可迁移性未知；25项有限原文别名检索未定位。它们均有原图来源记录；25项甚至可能是PDF断行/粘连导致的精确短语漏检，尤其不能认定原文不存在。11项B只是向已有角色增加新组合，本次没有填补一个全空诊断槽位，pattern_slots=0。

**全语料已证实不覆盖的事实数量未测，不能填0代表已经证明全覆盖。**统计文件中的confirmed_document_absences=0表示本轮没有证实任何全语料缺失；不等于证明没有缺口。当前有两项明确的配套资料查找需求，另有一项条件化标准需求。先查配套资料是否已有，再决定是否补充。
