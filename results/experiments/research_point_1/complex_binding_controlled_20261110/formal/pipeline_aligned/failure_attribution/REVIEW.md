# 受控基线失败归因复核

结论：本轮不支持为RP1另立复杂语义绑定算法。首先暴露的是7B输出词表/类型遵从、生成覆盖及现有接口/规则的混合问题。这里不把AI源文判S当作满足Schema的正确图谱关系，也不把所有拒绝都算误拒。

## 761条候选的互斥阶段统计

统计单位为试次中的候选出现次数，包含两次重复，不是去重后的图谱净新增量。各行按“规范化拒绝→准入→类型/方向→定位→条件→其他”优先级互斥；详细重叠标记另保留。

| 阶段 | 数量 | 占761条 |
| --- | --- | --- |
| 局部规则准入 | 77 | 10.12% |
| 后续类型/方向不合法 | 427 | 56.11% |
| 必要条件未显式绑定 | 13 | 1.71% |
| 字段/词表规范化拒绝 | 187 | 24.57% |
| 证据无法按原生约束绑定 | 57 | 7.49% |

## 为什么不能称为大量正确知识被误拒

有效原始AI评价中共335条判S，其中306条原始关系名或Domain/Range不合法，只有29条类型对合法。AI判的是源文语义支持，不能单独证明符合图谱接口。原始S被拒共319条，其中305条原始Schema非法；余下14条是“AI判S且类型对合法但被拒”的待诊断候选。它们仍可能违反原文端点、证据位置、条件、中文规范名等契约，不能直接叫14条已证实误拒。

| AI判S的原始候选 | 准入 | 拒绝 |
| --- | --- | --- |
| 原始Domain/Range合法 | 15 | 14 |
| 原始关系名/类型对非法 | 1 | 305 |

AI原判、候选内容和所有拒绝原因逐条保存在candidate_stage_ledger.jsonl。没有重写AI标签，没有调用模型修复，没有把结构非法直接改判成源文不支持。

## 14条待诊断记录（不是已恢复正确知识）

| 试次/序号 | 主要阶段 | 拒绝依据 |
| --- | --- | --- |
| B0_MP016_p0029_2026111002:2 | 证据无法按原生约束绑定 | ['unbound_quote'] |
| B0_MP019_p0097_2026111001:5 | 证据无法按原生约束绑定 | ['unbound_quote'] |
| B1_MP005_p0053_2026111001:4 | 必要条件未显式绑定 | ['conditional_context_not_explicit'] |
| B1_MP005_p0053_2026111002:1 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal |
| B1_MP005_p0053_2026111002:2 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal |
| B1_MP005_p0053_2026111002:4 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal |
| B1_MP005_p0053_2026111002:5 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal |
| B1_MP005_p0053_2026111002:6 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal |
| B1_MP005_p0053_2026111002:7 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal |
| B1_MP017_p0015_2026111002:1 | 字段/词表规范化拒绝 | ValueError: Unknown evidence role: causal_or_mechanism |
| B2_MP005_p0053_2026111001:1 | 必要条件未显式绑定 | ['conditional_context_not_explicit'] |
| B2_MP005_p0053_2026111002:1 | 必要条件未显式绑定 | ['conditional_context_not_explicit'] |
| B3_MP005_p0053_2026111001:1 | 必要条件未显式绑定 | ['conditional_context_not_explicit'] |
| B3_MP005_p0053_2026111002:1 | 必要条件未显式绑定 | ['conditional_context_not_explicit'] |

## 对四组基线的解释

B1为通用Schema提示，不是一个成功运行的硬语法解码对照；设置阶段所试语法库卡顿被保留并排除。因此不能据本轮失败宣布通用结构化解码无效。B2/B3同样没有证明专门绑定算法必要；更多输出或更高源文判S次数不等于更多合格关系。

本轮程序准入边界是已声明的局部链：normalize_relation_direction → automatic_contract_v4_1 → clause_binding_v1 → layout_direction_context_v1 → batch_evidence_repair_v1，并使用native_evidence_binding_v2及冻结筛查器。它没有执行图谱发布、术语治理、来源族聚合，准入数不是strict208或论文最终发布层的质量指标。

335个S与原始候选/验证后候选不是同一分母，也不是专家正确率。本轮少量独立页、两次重复和有引用异常的AI评价不足以证明普遍效果；但足以否定“把所有拒绝理解为复杂绑定问题，再直接立项新算法”这一推理。

建议：先以通用方式保证合法词表、类型对、原文端点和正常序列化输出，再判断剩余的复杂绑定错误是否稳定存在。不要优先加联合优化、领域核验器或新的流程层。若换用通用硬约束解码或更强生成模型，应另行预注册，不能把本轮提示版冒充该对照的失败证据。

复算：PYTHONPATH=src:scripts .venv/bin/python scripts/audit_rp1_complex_binding_failures.py。只读已有响应及评价，无新模型调用。
