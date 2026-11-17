# CPU复现与资产定位

本研究可仅依赖已保存向量、Python/NumPy/PyTorch在CPU完成。不要启动GPU或重新编码。当前输出已存在时脚本校验/复用，拒绝覆盖不同内容；历史图谱、实验和缓存只读。

```bash
cd /home/hengshan10/08-zxk/Fault_LLM_V2
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/transport_cpu.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/potential.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/gaps.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/diagnostics.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/support_limits.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/reports.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/verify.py
```

完整重新计算可在独立checkout还原同一锁定Git对象与父实验资产，复制本目录的`code/`、`local_llm/`和`RUN_PROTOCOL.md`，保持同一父级路径但不复制本轮结果，再按以上顺序运行；不要删除本研究输出以强制重跑。时间数字会随环境变化，排名和统计应保持一致/数值容差内一致。

输入读取器：`../kg_enhancement_task_comparison/code/inputs.py`，仅允许expanded1456及15份构建文档，Git对象833c8040058055434c7f6a9595ec524c3935755f。

父模型/索引：`../kg_query_aware_completion_v1/features/G2_s{16112026,16112027,16112028}.pt`，`index/vectors.pt`、`index/edges.jsonl`、`index/oriented_views.jsonl`、`retrieval/R3_all_global.npz`、`R1_all_global.npz`。领域原始导出8007行与规范化审计8003条分开计，不把其中所有记录当合法融合样本。

遮蔽评价只用父目录`data/validation_targets.jsonl`和`validation_truth.json`中的实际187验证关系。没有调用测试目标评测函数。原完整图分量来自`../kg_structure_cross_document_audit_v1/node_degrees.csv`，没有再次计算全图稀疏性。

输入SHA256在`potential/input_hashes.json`、`gaps/input_hashes.json`和`verification/input_hashes.json`。父实验868个和结构审计61个封存文件的SHA256再次核验；本轮自己的文件清单在`delivery_manifest.json`。源文位置按物理PDF页，不能与印刷页混用；连续offset与表格单元不同，不伪造bbox。

输出顺序：先读取FINAL_DECISION，再看TRANSPORT_COMPARISON/CASEBOOK；逐记录潜在关系见POTENTIAL_RELATIONS，初始来源与条件另有context_provenance/pattern_source_notes；缺口CSV一行是一个待检查的诊断角色，详细来源见gaps/gap_sources.jsonl。

全部默认流程都不需要API Key或网络。可选本机LLM工具单独列在`local_llm/README.md`，本次未启用，当前模型服务器主机硬拒绝。没有新的GPU计算需求或必须提交的服务器任务；本机资源不足时也不得自动把API程序送到服务器。
