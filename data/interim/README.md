# Intermediate Data

该目录只保存可重新生成的中间产物：

- `parsed_pages/`：页级文本、章节和版面元数据。
- `candidate_triples/`：抽取后的候选三元组及逐条类型、关系方向、连续原文跨度、来源、置信度和语义抽样审计状态。
- `candidate_triples/*/rejected_proposals.jsonl`：未达到候选阈值的模型原始提议及重叠的拒绝原因，用于失败分析，不进入候选三元组统计。

中间数据即使标记为高置信Silver候选，也不能作为已冻结的正式图谱或 EvidenceBench 结果引用。
