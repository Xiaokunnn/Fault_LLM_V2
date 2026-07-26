# 现有文档故障覆盖能力判定

- 大候选池：326页
- 严格覆盖通过：1/10类
- 候选层仍缺角色或来源：3/10类
- 总体决策：`do_not_start_full_extraction`

| 故障类别 | 严格判定 | 症状候选页 | 原因候选页 | 检查候选页 | 维护候选页 | 来源族 | 下一步 |
|---|---|---:|---:|---:|---:|---:|---|
| 汽蚀 | not_proven_sufficient | 15 | 11 | 14 | 15 | 4 | inspect_extraction_or_validation_gap_before_new_sources |
| 空气侵入或失去自吸 | current_documents_insufficient_at_candidate_evidence_level | 4 | 4 | 3 | 4 | 2 | add_independent_documents_for_missing_roles_or_sources |
| 流道、叶轮、过滤器或管路堵塞 | current_documents_sufficient | 18 | 19 | 14 | 20 | 4 | eligible_for_full_extraction |
| 叶轮或耐磨部件磨损损坏 | not_proven_sufficient | 6 | 28 | 8 | 21 | 3 | inspect_extraction_or_validation_gap_before_new_sources |
| 机械密封失效与泄漏 | not_proven_sufficient | 21 | 21 | 21 | 22 | 3 | inspect_extraction_or_validation_gap_before_new_sources |
| 轴承磨损、润滑不良或过热 | not_proven_sufficient | 17 | 14 | 19 | 20 | 3 | inspect_extraction_or_validation_gap_before_new_sources |
| 泵电机联轴器或轴系不对中 | not_proven_sufficient | 5 | 5 | 5 | 4 | 2 | inspect_extraction_or_validation_gap_before_new_sources |
| 电机缺相、过载或电气驱动异常 | current_documents_insufficient_at_candidate_evidence_level | 4 | 3 | 4 | 3 | 2 | add_independent_documents_for_missing_roles_or_sources |
| 管路或阀件泄漏、卡滞和完整性失效 | current_documents_insufficient_at_candidate_evidence_level | 2 | 1 | 2 | 2 | 2 | add_independent_documents_for_missing_roles_or_sources |
| 干运转、错误操作或维护引入故障 | not_proven_sufficient | 11 | 12 | 11 | 11 | 4 | inspect_extraction_or_validation_gap_before_new_sources |
