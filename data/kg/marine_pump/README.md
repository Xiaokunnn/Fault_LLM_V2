# Marine Pump Knowledge Graph Data

该目录是正式主实验的新数据线，与原轴承图谱完全隔离。

计划产物：

```text
schema/
triples/
graph_versions/
silver_evidencebench/
experiment_results/
```

所有三元组必须符合 `schema/provenance_schema_v1.json`，并保留来源 URL、页码/章节、原文证据和抽取置信度。

当前已完成4份代表性文档的页级候选三元组试抽取，并在 `data/interim/candidate_triples/` 保存逐条校验状态；这些记录仍是中间层Silver候选。`triples/`、`graph_versions/` 和 `silver_evidencebench/` 尚未形成正式版本，不应将当前试抽取描述为已完成的新知识图谱。
