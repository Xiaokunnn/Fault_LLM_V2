# RP1完整方法体系与代码对应

## 1. 研究问题、输入和输出

方法解决的不是“从任意传感器序列直接诊断故障”，而是从泵系技术文档构建可检索、可回溯、有明确质量状态的知识资源。输入为固定构建语料及领域Schema；输出为规范实体、Claim、证据断言、原生来源和全量处理账本。最终研究主图为expanded1456，旧审计池和standard1326承担过程审计与治理对照作用。

工程需求对应四个研究问题：异构格式如何映射到一致的故障知识模式；生成内容如何绑定到可验证的物理页或表格单元；何种执行条件决定保留、隔离或拒绝；如何在中文发布与多文档聚合时保留源语和证据差异。它们构成知识建模与治理问题，不预设存在一个新的联合关系优化算法。

构建文档为MP001—MP007、MP015—MP022，共15份、1934物理页；1889页完成全量抽取。MP008仅供开发；MP009—MP013是外部评价资产，不能补主图覆盖；MP014不属于文档证据语料。物理页与页脚印刷页是不同字段，不能互换。

## 2. 领域模式：实体、关系与诊断组织

Schema由`data/kg/marine_pump/schema/provenance_schema_v3.json`定义13类实体、15类关系。设备/部件提供系统定位，工况/原因/机理描述故障形成，现象和信号提供观测入口，检查和维护动作提供单角色建议，标准和风险约束建议解释。关系均有规范方向和Domain/Range。

这不是强制唯一诊断链。一个现象可以指向多个可能故障，一个故障可以具有多项检查/措施。`causes`不支持把故障表“故障—原因”列按左右顺序直接连成故障导致原因；`diagnosed_by`和`inspected_by`区分诊断目标和设备检查；`mitigated_by`用于纠正目标，`prevented_by`要求明确预防对象，`maintained_by`连接物理对象与维护动作。实际启动/运行操作不能仅为满足Schema而改标成维护动作。

四类诊断证据角色可形成路径模板：故障到现象、原因/机理到故障、故障到检查、故障到维护。`contains`、`located_in`、`occurs_at`支持设备位置约束；`operates_under`、`specified_by`与`increases_risk_of`补充工况、标准和风险。可达路径是证据组织方式，不是已经实现的完整诊断策略。

形式上，类型函数为τ，关系约束为D(r)、R(r)，结构合规条件为：

\[
I_{type}(h,r,t)=\mathbf1[r\in\mathcal R]\mathbf1[\tau(h)\in D(r)]\mathbf1[\tau(t)\in R(r)].
\]

这只是Schema合规，不证明实体语义类型正确。A24将对中状态标为Component、复杂语义实验中大量非法类型对，说明必须区分“字段填写了合法类型名”和“类型语义正确”。

## 3. 解析、生成与输出契约

`stage01_document_ingest/models.py`保存TextBlock、TableCell、TableRow、ParsedTable和ParsedPage；`pdf_parser.py`与`pipeline.py`保存阅读顺序、列角色、行/行组、单元格bbox、文档和页哈希。多栏/合并单元格的结构识别可能出错，字段存在不等于版面恢复完全正确。

`chinese_extraction_contract.build_user_prompt`组合DOCUMENT_METADATA、PARSED_TABLES和页面原文；`system_prompt_for_version`提供冻结契约；`normalize_model_candidate`检查字段、类型词表、关系词表、中文名、证据模式与证据角色。原全语料生成和20页真实API对照使用DashScope别名qwen3.7-max，不是本地Qwen2.5-7B。API没有提供可确认的固定后端快照，不补写精确不可知版本。

每条提议区分源语`head_surface/tail_surface`与`head_canonical_zh/tail_canonical_zh`。证据必须为原文或真实单元引用，中文名不得充当英文原文证据。主候选须满足图谱契约，失败提议和原因保留。旧全量响应不是一个已经实现了通用辅助知识分流的系统：辅助/未决字段主要见后续独立实验，不能倒写成原生成链路具备的全部能力。

有限方向规范化属于已有约束下的确定性重写：`normalize_relation_direction`只处理声明过的类型模式，并保留动作记录。`record_level_repair`是带expected字段的个例修复，不能作为泛化算法。后续`batch_evidence_repair_v1`等是独立恢复实验模块，不应把其全部规则追溯算作早期全量构图时已执行的机制。

## 4. Claim—EvidenceAssertion—Source表示

用c=(h,r,t)表示规范主张族，用a=(c,e,p,g,κ)表示某一来源发生的证据断言。e为源文和实际位置，p为文档、物理页、URL、来源族和哈希，g为验证状态、支持模式与原因，κ为实际存在的条件/模态信息；κ未结构化时保留未知，不虚构空条件。

同一个c可连接多个a，不能在语义去重时覆盖来源。旧图通过`claims.jsonl`、`evidence_assertions.jsonl`和`claim_evidence_links.jsonl`连接；expanded图的`evidence_assertions.jsonl`同时含Claim关联与来源信息。数据结构不是同一套字段逐字复制，接口必须适配。

E1表示可定位连续正文跨度；E2表示真实表格单元及同行/已验证行组；E3是需重建或跨句的证据，只保留审计，不能按E1/E2自动发布。严格208紧凑记忆的145条E1有连续偏移、63条E2连续偏移为空；底层来源记录中的已有表格bbox应保留，但不得称紧凑记忆完整保存bbox，也不得补造连续偏移。

文档哈希确认版本身份，页面哈希确认解析文本身份，原生单元和位置支持回查。它们不证明语义正确。expanded的新位置读取`expansion_source_witnesses`；旧字段保留历史，不用历史`final_confidence`覆盖新契约解释。

## 5. 多阶段质量治理的真实数学化

设α为截断到[0,1]的模型自报分数，wE(E1/E2/E3)=1/0.95/0.75，wR(支持/未定/不支持)=1/0.75/0。`confidence_policy.decide_confidence`实际先计算：

\[
q^{policy}=\operatorname{round}_3\{\operatorname{round}_3[\alpha w_E(l)]w_R(\eta)\}.
\]

来源等级权重记录在旁，但不乘入这一语义支持评分。未知来源级别可触发拒绝；高权威来源不能抵消证据不支持。该分数是工程启发式，不是校准概率。

硬失败包括Schema/类型、定位失败、关系明确不支持及未知来源级别。E3、语义未定、推断边、外部测试记录等产生自动发布屏障。在无硬失败和发布屏障且q≥0.8时准入；候选阈值0.6和未定情况决定隔离，低分或硬失败则拒绝。详细分支以函数为准，不用一个分数抵消任何硬失败。溯源字段和语料白名单还由构建脚本、Schema与验收模块共同落实。

可概括历史准入必要条件为：

\[
H(a)=I_{str}I_{dir}I_{loc}I_{sup}I_{prov}I_{build}I_{noninf}I_{q\ge0.8}.
\]

此式是实际判定链的逻辑归纳，不是训练损失或原创推理优化器。`pipeline.validate_candidate`执行本地类型、E1/E2定位、关系线索与中文规范化；`run_automatic_silver_adjudication.py`处理规则未定记录的同模型双提示判断。两者不是一个会自动调用模型的函数。1698条中784条显式短语、98条表格角色、816条同模型双提示一致性，支持强度必须明示，816不能称为独立验证。

程序通过不能保证条件、否定和适用范围均正确。全量复核、故障注入和语义抽查回答的是不同问题；隔离和拒绝账本用于找损失，不用于证明所有被拒项都是错误。

## 6. 中文治理、发布和有限扩展

`chinese_canonicalizer`与术语治理脚本把源文表述、中文规范名、术语ID、翻译状态分开。词典匹配及既有双提示术语优先；后续局部治理检查同类型名称一致、候选完整性和型号/单位/API/ISO/NPSH等保护字符串。standard0.90、conservative重复0.90/单例0.95、strict历史冻结状态是已实现的发布策略，不是专家翻译等级。

证据准入固定1698条时，术语扩展把中文记录从208提升至1326；这检验术语发布损失，不是提升关系事实正确率。新主图谱另从同一构建语料的既有候选恢复130条，接受条件为唯一原生位置、明确角色/有限句法、类型与标准术语合法，且不覆盖既有明确模型否决。它与原同模型双提示契约不同，不能统一成“1456全部通过原1698条门控”。

扩展集合式仅可写为Gexp=Gstd∪R，R由扩图脚本的源文角色契约产生。它保证旧记录保留及规模增加，不保证事实或条件完整性单调提高。新增记录80样本对照中存在真实角色和条件缺陷，必须进入论证而非删去。

## 7. 来源家族治理

来源族由出版社/厂商/文档来源注册，是内容依赖的工程代理。同厂商不同手册可属于同族，文档数不直接等于独立来源数。按实际`source_family_support.py`，用于聚合的q为`round6(αwEwR)`，与上面的三位中间舍入实现应区别。

\[
s_f(c)=\max_{a\in A_f(c)}q_a,\quad
S_{fam}^{(B)}(c)=\frac1B\sum_{j=1}^{\min(B,|F_c|)}s_{(j)}(c),\ B=2.
\]

缺失族位置补零，所以单来源族主张在B=2时指数至多0.5。它是来源预算下的排序/审计指标，不是“正确概率不足50%”。同族新证据若有更高q，族最大值允许提高；复制不变性专指同q的重复注入或未超过原最大值的重复支持，不表示任意新增同族文档都绝对不改变分数。

完全同族复制不改变族集合与族内最大值，因此不改变此指数。该性质由max及去重实现直接导出；1/2/4/8倍实验验证实现符合预期。当前1650项精确历史Claim没有自然跨至少2族的同一主张，不能把复制稳定性当自然跨来源区分效度的证据，也不能声称来源族在统计上独立。

历史指数分析还按历史准入决策、E1/E2和原支持模式过滤1698条，不能直接用于新增130条的历史根字段。未来expanded接口需区分验证契约与未知分数。

## 8. 方法流程伪代码（对应现有实现）

```text
输入：冻结构建文档、Schema、术语配置、来源注册及已有响应缓存
解析每个物理页，保留原文、原生表格/块、位置与哈希
对抽取提议按字段契约规范化；失败提议及原因入账
按已声明模式规范方向；保存原载荷及重写记录
检查Domain/Range；定位E1或对齐E2；E3进入隔离边界
按显式线索/表格角色判断支持；未定项读取既有双提示核验结果
应用硬失败、发布屏障和启发式阈值，记录全部决定
分别生成主张对象与每条来源断言，保留一对多关联
以中文术语条件发布standard对照；保持源语与出处不变
从已有候选按独立角色恢复契约获得R，输出Gexp=Gstd∪R
读取既有冻结样本、全量合规复核、消融和CQ结果作多口径评价
输出：主图谱、对照图、原始/拒绝/隔离账本及版本清单
```

此处“读取既有”描述本次成果整理，不是重新调用模型。论文方法叙述原始构建过程时可去掉缓存重用表述，但不得将本次核数称为新抽取。

## 9. 关键实现索引

| 机制 | 相对仓库路径 / 函数 | 性质 |
| --- | --- | --- |
| 页面与原生单元 | `stage01_document_ingest/models.py`、`pdf_parser.py` | 确定性解析及领域数据结构 |
| 生成契约 | `stage02_triple_extraction/chinese_extraction_contract.py` | 本体适配Prompt与字段约束 |
| 结构/方向 | `stage03_schema_validation/relation_type_validator.py` | 有限规则，不是学习式重构算法 |
| E1/E2 | `evidence_span_validator.py`、`table_alignment_validator.py` | 源文/表格证据检查 |
| 支持及分级 | `relation_entailment_validator.py`、`confidence_policy.py`、`pipeline.py` | 本地检查与工程状态机 |
| 模型未定项处理 | `scripts/run_automatic_silver_adjudication.py` | 原同模型双提示，不是独立专家 |
| 身份与审计图 | `deduplicator.py`、`scripts/build_versioned_knowledge_graph.py` | 稳定ID及证据保留 |
| 术语发布 | `scripts/run_local_full_terminology_experiment.py`、`run_silver_terminology_governance.py` | 本地一致性与保守发布 |
| 扩图 | `scripts/build_rp1_graph_expansion_v1.py`、`batch_evidence_repair_v1.py` | 独立源文角色恢复与导出 |
| 来源族 | `stage04_graph_build/source_family_support.py` | max/top-B聚合及复制测试 |
| 后续局部实验 | `clause_binding_v1.py`、`layout_direction_context_v1.py`、`native_evidence_binding_v2.py` | 不追溯改写论文冻结结果 |

未写`scripts/`的stage路径均位于`src/research_point_1_graph_evidence/`。下附实体和关系全集由真实Schema导出；英文类型码是稳定接口，不以中文描述替换机器码。

## 附表A：13类实体

| 类型 | 中文 | Schema原定义 |
| --- | --- | --- |
| Equipment | 设备 | A pump, pump set, drive, or explicitly named pump-system equipment. |
| Component | 部件 | A physical component of a pump or its connected suction, discharge, sealing, lubrication, drive, valve, or pipe system. |
| FaultMode | 故障模式 | An observable or diagnosable failure state. |
| FailureMechanism | 失效机理 | A physical process through which degradation or failure develops. |
| Symptom | 症状 | An observable qualitative manifestation. |
| SignalFeature | 信号特征 | A measured or computed diagnostic feature. |
| Cause | 原因 | A stated initiating cause that is not merely a component name. |
| OperatingCondition | 运行工况 | A load, pressure, temperature, flow, speed, medium, or environmental condition. |
| InspectionMethod | 检查方法 | A named diagnostic or inspection method. |
| InspectionAction | 检查动作 | A concrete inspection or verification action. |
| MaintenanceAction | 维护动作 | A concrete repair, adjustment, cleaning, replacement, or preventive-maintenance action. |
| Standard | 标准 | A standard, rule, guide, specification, or acceptance criterion. |
| Risk | 风险 | A stated adverse consequence or risk state. |

## 附表B：15类关系及真实Domain/Range

| 机器码 | 中文 | Domain | Range |
| --- | --- | --- | --- |
| contains | 包含 | Equipment, Component | Component |
| located_in | 位于 | Component | Equipment, Component |
| occurs_at | 发生于 | FaultMode, FailureMechanism | Equipment, Component |
| causes | 导致 | Cause, FailureMechanism, OperatingCondition, FaultMode | FailureMechanism, FaultMode, Symptom, SignalFeature, Risk |
| indicates | 指示 | Symptom, SignalFeature | Cause, FailureMechanism, FaultMode, Risk |
| manifests_as | 表现为 | FaultMode, FailureMechanism | Symptom, SignalFeature |
| evolves_to | 演化为 | FaultMode, FailureMechanism | FaultMode, FailureMechanism, Risk |
| diagnosed_by | 诊断方法为 | Cause, FailureMechanism, FaultMode, Symptom, SignalFeature, Risk | InspectionMethod, InspectionAction |
| inspected_by | 检查方法为 | Equipment, Component, Cause, FailureMechanism, FaultMode | InspectionMethod, InspectionAction |
| mitigated_by | 缓解措施为 | Cause, FailureMechanism, FaultMode, Risk | MaintenanceAction |
| prevented_by | 预防措施为 | Cause, FailureMechanism, FaultMode, OperatingCondition, Risk | MaintenanceAction |
| maintained_by | 维护方式为 | Equipment, Component | MaintenanceAction |
| operates_under | 运行于 | Equipment, Component | OperatingCondition |
| increases_risk_of | 增加风险 | Cause, FailureMechanism, FaultMode, OperatingCondition | Risk |
| specified_by | 由规范规定 | Equipment, Component, FaultMode, FailureMechanism, Symptom, SignalFeature, Cause, OperatingCondition, InspectionMethod, InspectionAction, MaintenanceAction, Risk | Standard |
