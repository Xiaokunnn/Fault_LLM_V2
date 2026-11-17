# RP1稀疏性成因与建模充分性：一次性受控归因

2026-11-17。入口：[下一步决定](RP1_NEXT_STEP.md)、[成因结论](ROOT_CAUSE_ANALYSIS.md)、[五视图对照](COUNTERFACTUAL_VIEWS.md)。

实际完成8007原始导出行/8003规范化记录的链路追踪、45个冻结源文单元、18项原子及16项复合代理参考、G0/GA/GB/GAB/GC对照和多维质量评价。

GA：276自动记录→271潜在关系族，直接旧组件桥5条、累计组件减少6，最大业务分量仍54。GB：0新增业务事实，239虚拟概念/1004映射；异构连接改善，固定精确焦点仍4/18。GC的18/18按参考构造成立，不能作算法收益。

- [候选流失归因](EXTRACTION_ATTRIBUTION.md)，逐条账本CANDIDATE_LINEAGE.csv
- [实体与Schema充分性](ONTOLOGY_ASSESSMENT.md)，[实际案例](ENTITY_RELATION_CASEBOOK.md)
- [源文诊断单元核查](DOCUMENT_KNOWLEDGE_AUDIT.md)，逐条SOURCE_UNIT_AUDIT.jsonl
- [多维质量体系](QUALITY_EVALUATION_FRAMEWORK.md)，数值QUALITY_METRICS.csv
- [复现步骤](REPRODUCE.md)，[可选本机复核](local_llm/README.md)

本轮不重抽、不重训、不重跑旧发布门控、不合并实体、不修改正式图谱或RP2/RP3，不调用外部LLM。助手源文判断与自动合同均非专家Gold，无独立事实准确率/Recall或三因素因果贡献百分比。
