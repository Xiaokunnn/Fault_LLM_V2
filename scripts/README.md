# Scripts

## 研究点一：24页定向抽取

解析冻结的24页计划，并在终端逐文档打印进度：

```powershell
python -u scripts/run_targeted_page_ingest.py
```

两页真实API联调（安全提示输入密钥，不写入文件）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_targeted_extraction_secure.ps1
```

两页检查通过后执行完整24页抽取：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_targeted_extraction_secure.ps1 -Full
```

严格校验并输出中文图谱就绪数与类别覆盖：

```powershell
python -u scripts/run_targeted_strict_validation.py
```

## 研究点一：11份文档全库候选发现与抽取

单命令执行全库解析、SQLite索引、候选页筛选、Qwen抽取、严格校验和覆盖统计：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_corpus_pipeline_secure.ps1
```

只运行本地解析、索引和候选池构建，用于先查看候选页数量与模型耗时预估：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_corpus_pipeline_secure.ps1 -LocalOnly
```

所有阶段均支持本地进度输出；PDF解析和模型响应可断点续跑。

保存面向用户的流水线命令入口。研究点一的核心逻辑应实现于 `src/research_point_1_graph_evidence/`，脚本只负责参数解析和模块调用；后续研究点使用独立命令前缀，避免入口混淆。

- `run_bailian_triple_pilot.mjs --dry-run`：解析4份代表性PDF并冻结候选页，不调用模型。
- `run_bailian_triple_pilot.mjs`：从当前进程的 `DASHSCOPE_API_KEY` 读取密钥，调用 `qwen3.7-max` 抽取页级候选三元组；密钥不得写入仓库文件。
- `run_document_ingest.py`：运行坐标保持的正文/表格双通道PDF解析。
- `run_strict_pilot_revalidation.py`：不调用外部模型，按严格v2规则回放旧试抽取候选。
- `build_fault_coverage_matrix.py`：合并严格证据覆盖与构建集词法候选页，生成类别缺口矩阵。

其中 `run_bailian_triple_pilot.mjs` 只用于复现历史四页试抽取。24页定向抽取和后续全量构图均已完成；当前研究点一状态以主论文和8003条审计记录为准。

## 研究点一：B0–Ours、消融与敏感性实验

在冻结的8003条审计候选上执行纯本地累计治理对照、关键模块消融、文档/故障类聚类bootstrap、参数敏感性和数据可视化：

```powershell
python scripts/run_rp1_b0_ours_experiments.py
```

该命令不调用模型或网络。实验配置冻结在 `configs/rp1_b0_ours_experiment_v1.json`，默认输出到 `results/experiments/research_point_1/b0_ours_ablation_v1/`。这里的B0–Ours是同一候选集合上的治理门控对照，不是不同提示词的模型端重新抽取对照。

## 研究点三：教师冻结、轻量控制器与边缘导出

研究点三的入口均为失败关闭：只有严格208条教师图、BGE索引、RP2重放、冻结哈希和模型依赖全部一致时，才允许写教师清单。

```powershell
python scripts/freeze_rp3_teacher_graph.py --validate-only
python scripts/export_rp3_teacher_traces.py --validate-only
python scripts/export_rp3_teacher_traces.py
python scripts/freeze_rp3_teacher_graph.py
```

`export_rp3_teacher_traces.py` 在教师系统和top-32候选轨迹两个门禁通过后，一次生成最终40条TeacherTrace和严格208本地证据记忆。它采用 `fixed_memory_query_generalization` 切分：同一故障的四个角色轨迹不跨训练/验证，但两者共享同一严格208记忆；这只能评价固定记忆上的查询泛化，不能声称未见文档归纳泛化。最终再运行冻结脚本，使冻结清单单向绑定TeacherTrace/memory bundle哈希，避免冻结哈希与bundle哈希相互引用。

`build_rp3_evidence_memory.py` 仍保留为独立审计/重建入口；写训练包时必须显式给出覆盖全部Evidence ID的 `--split-map ... --purpose training`。冻结审计区分 `teacher_system_status`、`distillation_trace_status` 和最终训练bundle状态。当前本机缺少BGE索引与模型，也尚无该top-32轨迹，不得跳过。完整top-32教师轨迹和外部显式特征由有模型机器生成后，训练与ONNX入口分别为 `train_rp3_lec.py` 和 `export_rp3_onnx.py`；INT8量化、量化后校准和真实边缘测量必须另行完成。
