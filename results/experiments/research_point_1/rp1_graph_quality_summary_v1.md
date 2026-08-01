# 研究点一图谱方法收口报告 v1

- 版本：`marine_pump_rp1_graph_quality_v1`
- 执行范围：纯本地；未调用模型或网络。
- 标签政策：仅 Silver，绝不称 Gold；未进行领域专家审核。

## 核心结果

| 模块 | 结果 |
|---|---|
| CQ v1 | 34/40，可追溯结构可回答率 85.0%；该指标不是准确率 |
| 来源族封顶佐证 | 1698条Silver、1650个Claim、自然跨至少2族Claim=0、真实多文档同族审计=3/3、同族复制不变性=通过 |
| 标准化约束 | 36项检查，0项发布阻断，`release_blocked=false`；不是SHACL/RDF验证 |

## CQ空缺

- 汽蚀—检查 (`CQ-F01-INS`)：no_legal_semantic_path
- 空气侵入或失去自吸—症状 (`CQ-F02-SYM`)：no_legal_semantic_path
- 空气侵入或失去自吸—检查 (`CQ-F02-INS`)：no_legal_semantic_path
- 流道、叶轮、过滤器或管路堵塞—症状 (`CQ-F03-SYM`)：no_legal_semantic_path
- 电机缺相、过载或电气驱动异常—症状 (`CQ-F08-SYM`)：no_legal_semantic_path
- 电机缺相、过载或电气驱动异常—检查 (`CQ-F08-INS`)：no_legal_semantic_path

## 结论边界

- 冻结的CQ v1中有6个任务在KG_v1_validated中不存在可追溯合法答案路径。
- 没有精确Claim ID获得两个来源族的自然佐证；当前来源族实验只验证了同族复制不变性。
- 约束报告含非阻断失败或警告，需结合Markdown明细解释。
- 基线、消融和自然跨来源族区分实验尚未完成。

当前流水线已具备开始对照与消融实验的条件；这不表示方法证据完整或研究点一已经完成。
- 方法证据完整：否
- 研究点一完成：否
CQ空缺和精确Claim跨来源族对齐缺口必须作为结果报告，不得通过自动降门槛或改写Silver标签隐藏。
