# Fault LLM v2

面向船舶机舱泵系的大语言模型知识增强故障辅助诊断研究项目。当前研究结构以两篇已经完成的小论文为事实主线，第三个研究点在此基础上继续推进。

## 三个研究点

1. **研究点一：无需逐条人工审批的证据可追溯知识图谱构建。** 大模型从技术文档提出候选三元组；可执行证据契约自动检查本体类型与方向、连续原文或表格单元格定位、关系支持、来源谱系、语料边界和非推断条件，并将记录分为自动证据合格、隔离和拒绝三类。自动合格表示通过所声明的证据契约，不表示专家确认的事实正确性。
2. **研究点二：预算约束型混合证据选择与核验负载控制。** BGE-M3宽召回后，以诊断角色、故障范围、一跳尾部召回信号、来源去冗余和主动欠填在最多三条证据内完成选择；固定Qwen2.5-7B只做两阶段支持判别，确定性渲染器输出带证据ID的原子建议或拒答。
3. **研究点三：轻量证据控制器与选择性边缘推理。** 把研究点二教师系统的证据排序、支持判别、字段欠填和回退策略蒸馏成可由LLM或编排器调用的小模块LEC；LEC从有界本地证据记忆返回证据ID和三动作路由，规则组件组合卡片，LLM不得新增无证据诊断主张。

统一主线为：

```text
多源技术文档
→ 自动证据契约门控与可追溯知识生产
→ 预算约束的证据选择、支持判别与拒答
→ 可调用轻量证据控制器与选择性边缘推理
```

## 当前事实基线

- 研究点一以 [`papers/ICSMD_2026/RP1_ICSMD2026_English_Final.tex`](papers/ICSMD_2026/RP1_ICSMD2026_English_Final.tex) 为英文主稿。15份构建文档、1934个物理页产生8003条审计记录，其中1698条满足自动证据契约、881条隔离、5424条拒绝。论文的标准中文应用层为1326条证据记录、1281项Claim和2022个中文实体。
- 研究点二以 [`papers/D2AI_ICDM_2026/RP2_D2AI2026_English_Final_v1.tex`](papers/D2AI_ICDM_2026/RP2_D2AI2026_English_Final_v1.tex) 为英文主稿。冻结v6在208条严格中文证据、40条受控查询上完成；相对Dense K3，Full K3的Recall为0.431、NDCG为0.822、Citation F1为0.426，平均端到端时延为531.2 ms。
- 研究点二论文教师只生成“给定故障范围与诊断角色下的原子建议”，尚不是完整诊断卡，也不是从传感器信号识别故障。
- 研究点三主教师固定为研究点二论文真实使用的严格208条底座；620条和1326条层只做主方案冻结后的容量/层迁移压力测试。训练前必须冻结唯一的 `TeacherGraph_RP3_v1` 并精确重放研究点二流程。
- 研究点三已在模型服务器完成严格208教师冻结、40题轨迹与MP008开发集构造、基线LEC训练、FP32 ONNX导出和INT8量化。基线在MP008量化后校准中0/40路由为本地回答，因而未生成部署校准证书；当前进入预先规划的构建集证据移除增强实验，不能将该失败解释成已完成边缘部署。
- 当前没有逐条领域专家审核。自动证据合格、自动语义支持和基准相关性均不能解释为专家事实正确率、故障诊断准确率或工程安全保证。

最新统一规划见 [`docs/research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md`](docs/research/MASTER_THESIS_THREE_RESEARCH_POINTS_PLAN.md)，本轮审查结论见 [`docs/research/MASTER_THESIS_REVIEW_AND_OPTIMIZATION_REPORT.md`](docs/research/MASTER_THESIS_REVIEW_AND_OPTIMIZATION_REPORT.md)。历史规划与阶段报告统一放在 `docs/archive/`，不得作为当前状态入口；精简后的 [`docs/RESEARCH_HANDOFF.md`](docs/RESEARCH_HANDOFF.md) 只保留继续工作所需事实。
研究点三的基线矩阵、最低必做实验和有序TODO见 [`docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md`](docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md)。

## 数据边界

- 构建集：MP001–MP007、MP015–MP022。
- MP008：仅开发使用，不补充构建覆盖。
- MP009–MP013：仅用于冻结后的外部评价，不进入图谱构建、蒸馏训练、课程设计、阈值选择或路由校准。
- MP014：排除，原因是其为海上ESP信号数据集，不属于船舶机舱泵系文档证据语料。
- 原文、物理页、URL、文档哈希、页面哈希及上游已有的定位信息始终保留，不被中文规范名覆盖。当前strict208导出记录没有bbox，只有字符偏移；下游必须显式标注bbox缺失，不能声称已完整保留该字段。

## 目录

```text
configs/       Schema、冻结配置和实验配置
data/          原始文档、页对象、候选记录、图谱与评价集
docs/          当前协议、统一规划和历史归档
papers/        研究点一、二论文主稿及历史版本
results/       正式实验结果与冻结报告
scripts/       可重复运行入口
src/           三个研究点的实现
tests/         单元与集成测试
```

数据资产保留规则见 [`docs/research/INTERMEDIATE_ARTIFACT_RETENTION_POLICY.md`](docs/research/INTERMEDIATE_ARTIFACT_RETENTION_POLICY.md)。原始PDF、真实API响应、候选及失败理由、冻结图谱和正式实验结果不得因“清理中间文件”而删除。
