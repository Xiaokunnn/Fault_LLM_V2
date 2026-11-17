# 只读复现与文件索引

在仓库根目录执行：

```bash
RP1_STRUCTURE_AUDIT=results/experiments/research_point_1/kg_structure_cross_document_audit_v1
.venv/bin/python "$RP1_STRUCTURE_AUDIT/code/audit_structure.py"
.venv/bin/python "$RP1_STRUCTURE_AUDIT/code/audit_cross_document.py"
.venv/bin/python "$RP1_STRUCTURE_AUDIT/code/audit_model_implications.py"
.venv/bin/python "$RP1_STRUCTURE_AUDIT/code/verify_audit.py"
.venv/bin/python "$RP1_STRUCTURE_AUDIT/code/write_report.py"
```

所有阶段已有完成标记会复用；输出不一致时拒绝覆盖。没有模型训练、重新抽取、预测重评分或外部API。预训练语义相似度复用前轮`index/vectors.pt`的2150个基础实体缓存，CPU运行；不是新编码器，也不是新语义真值。

唯一域对象833c8040058055434c7f6a9595ec524c3935755f，由既有expanded-only只读输入器载入。源和当前实验输入哈希见source_manifest.json，前轮868个封存文件逐一复核；不读取其他历史图谱。

主文件：

- `REPORT.md`：五个问题的结论、三图统计、冷端点分解和算法影响。
- `graph_statistics.csv`：G_full/G_train/G_masked使用相同2150实体ID目录，记录Claim/Assertion及邻接对差异。
- `node_degrees.csv`、`components.jsonl`、`full_degree_by_entity_type.csv`：逐节点、逐分量、分类型。
- `relation_structure.csv`、`document_structure.csv`：全部15种Schema关系（出现14种，缺失关系保留0）和15文档在三个视图的分布。
- `paths/`、`directed_path_patterns.csv`、`path_source_distribution.csv`：实际节点简单路径、方向/关系标签及来源分布；没有添加传递边。
- `cold_endpoint_ledger.jsonl`、`cold_fact_ledger.jsonl`、`cold_by_removal_stage.csv`、`cold_causes_complete_categories.csv`：448端点出现/224关系的完整追踪，首要原因互斥，包含零计数类别。
- `mask_removals.jsonl`：测试组/无序别名对删除依据。G_masked只删测试组；G_train再删验证，不把文本源页屏蔽误当所有业务边删除。
- `actual_model_inputs.json`：989基础训练事实与G2的168辅助候选/3671不确定检索上下文分别列出，未将候选升级成正式知识。
- `document_pair_overlap.csv`、`cross_document_shared_claims.jsonl`、`cross_document_bridge_entities.jsonl`：105文档对、12共享Claim和共享实体的逐条依据。
- `initial_candidate_cross_document_clusters.jsonl`：21个规范化表达跨文档簇，保留各状态、证据和条件签名；并非21条确认共同事实。
- `semantic_entity_pair_candidates.jsonl`、`semantic_claim_pair_candidates.jsonl`、`alias_hypothesis_clusters.jsonl`：相似/别名假设，不能直接当正确融合标签。
- `typed_alias_sensitivity.csv`：同类型、同旧别名根的假设商图，三个视图使用同一映射；不是真正实体合并结果。
- `manual_concept_mentions.csv`：主题提及探针，不是共同事实/召回率。
- `saved_model_results_by_full_graph_shape.csv`、`r3_context_component_ledger.jsonl`：仅连接已保存的排名和检索，不改分数/测试。
- `CASEBOOK.md`、`casebook.jsonl`、`directed_three_hop_cases.jsonl`：实际Claim、实体ID、文档/物理页、引文、条件和判断边界。
- `verification.json`：原资产保全、独立路径公式、度数恒等式及147/72/5重建。

所有计数的定义见definitions.json。图连通只说明结构，不保证Assertion条件能同时成立；同一来源家族/同文档副本不等于独立来源。字面提及、相似度、自动状态和已有基础标签均不是专家Gold。

主视图没有改变实体身份。别名敏感性只是只读假设，且可能混合型号/概念层级；不能据其数字直接修图。原训练划分及所有模型也未因诊断改变。
