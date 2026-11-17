# 一次性归因实验复现

运行环境：服务器CPU、Python 3.11、NumPy、NetworkX。无需GPU、模型推理、外部API或新的embedding。域对象833c8040058055434c7f6a9595ec524c3935755f；使用同一输入工具的允许列表，其他历史图谱不作为本轮事实输入。

```bash
cd /home/hengshan10/08-zxk/Fault_LLM_V2
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/freeze_sample.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/lineage.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/review_source_units.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/views.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/ontology.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/detail.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/add_quality.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/navigation.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/retention.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/write_reports.py
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/code/verify.py
```

已有阶段产物时脚本复用，不重写。完全重新计算应在独立checkout、同一输入版本和父实验文本资产下复制本目录code/与local_llm/，不复制本轮完成标记/结果，再按顺序运行；不要删除现有研究结果强制重跑。格式检查前初始采样保留，但最终采样规则在代码中，完全复算直接得到最终样本。

freeze_sample只切分原生单元并固定样本，不重新抽取三元组。review_source_units中的A—U与参考是显式助手阅读注释；统计重现不能证明注释独立正确。所有原审核状态原样保留，GC参考只用于评价，不作为GA/GB或KGC训练输入。

读取领域原始对象和15页缓存的工具为`../kg_enhancement_task_comparison/code/inputs.py`。定位合同复用`../post_extraction_feasibility_20261113/candidate_locator_audit.jsonl`，没有运行旧发布流水线。G0结构基准与原组件ID复用`../kg_structure_cross_document_audit_v1/`，并作等值校验。上一轮17模式与具体文档引用仅作为已有证据复用。

SHA256见source_sample/input_hashes.json、lineage/input_hashes.json、details/parent_input_hashes.json和verification/。完整新成果清单为delivery_manifest.json。模型、响应、数值缓存及日志保留本地；Git发布源代码、文本结果和哈希，不因未上传二进制而删除资产。

可选本机复核工具见local_llm/；默认关闭，当前服务器硬拒绝，只有获得逐输入外传授权并在本机显式启用才可能发送。主流程0次API调用，所有统计在服务器执行。未进行任何新的SimKGC/transport_R3训练，未用旧224测试答案选参，未写expanded1456、RP2/RP3或Neo4j。
