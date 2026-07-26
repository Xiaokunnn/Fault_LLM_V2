# 构建集全量抽取门槛冻结记录 v1

冻结日期：2026-07-26

## 1. 冻结结论

最终语义修复产生1810条治理记录，其中534条为Silver、188条为自动待判/隔离、1088条为拒绝。全部过程未进行人工专家审核，所有结果只能称为Silver，不能称为Gold。

故障类别映射v1.4将新增的管路/阀件预防检查规则限制在三元组头尾字段，避免同一表格其他单元格中的管路词触发无关动作映射。该复算移除7条误映射，未改变证据、关系裁决或Silver标签。收紧后10类仍全部通过冻结的证据覆盖门槛，决策为：

`start_full_extraction`

## 2. 收紧后的逐类覆盖

| 故障类别 | 症状 | 原因/机理 | 检查/维护 | 文档数 | 来源家族数 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| 汽蚀 | 12 | 12 | 6 | 7 | 6 | 通过 |
| 空气侵入/失去自吸 | 11 | 26 | 7 | 4 | 3 | 通过 |
| 水力堵塞 | 6 | 17 | 5 | 6 | 5 | 通过 |
| 叶轮或耐磨件损坏 | 7 | 9 | 10 | 5 | 5 | 通过 |
| 机械轴封故障 | 5 | 14 | 15 | 9 | 7 | 通过 |
| 轴承或润滑故障 | 33 | 41 | 14 | 9 | 6 | 通过 |
| 泵—电机不对中 | 8 | 10 | 5 | 4 | 4 | 通过 |
| 电机电气驱动故障 | 10 | 14 | 7 | 3 | 3 | 通过 |
| 管路或阀件完整性故障 | 11 | 30 | 8 | 6 | 5 | 通过 |
| 干运转或维护引入故障 | 5 | 5 | 2 | 3 | 2 | 通过 |

冻结门槛为：症状不少于5条，原因/机理不少于3条，检查/维护不少于2条，至少来自2份独立文档和2个独立来源家族。机械轴封症状以及干运转的症状、检维和来源家族恰好达到门槛，批量抽取后仍应作为重点质量监测类别，但不得再用开发集或保留测试集补门槛。

## 3. 适用边界

本冻结结论仅说明15份`build_train`文档具备支撑10类故障的原文证据基础，可以开始构建集全量抽取。它不表示：

- 中文知识图谱已经构建；
- Silver EvidenceBench已经形成；
- 待判或拒绝记录已经由人工专家复核；
- 研究点一的低时延检索方法已经验证；
- 系统具有真实船舶运行安全保证。

当前中文发布覆盖为0/10。全量抽取后必须继续执行中文规范名、术语ID、受保护词、类型和翻译状态校验；英文或其他语言的原文、页码、bbox、URL和文档哈希必须原样保留。

## 4. 冻结产物

- 记录：`data/interim/candidate_triples/final_semantic_gap_v1_gate_frozen/candidate_triples.gate_frozen.jsonl`
- 证据覆盖：`data/interim/candidate_triples/final_semantic_gap_v1_gate_frozen/coverage_evidence_only.json`
- 中文发布覆盖：`data/interim/candidate_triples/final_semantic_gap_v1_gate_frozen/coverage_chinese_release.json`
- 冻结摘要：`data/interim/candidate_triples/final_semantic_gap_v1_gate_frozen/gate_freeze_summary.json`

本地复算入口为`scripts/freeze_full_extraction_gate.py`，不调用外部模型。
