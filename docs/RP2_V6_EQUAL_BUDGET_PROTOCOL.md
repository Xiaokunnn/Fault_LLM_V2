# RP2 v6 等证据预算实验协议

## 1. 目标与边界

RP2 v6 研究的是本地大模型故障问答中的**证据预算问题**：在固定证据数量和低时延约束下，如何减少 Dense Top-k 中的角色错配、故障范围错配、来源重复和不可追溯证据，并向本地 Qwen2.5-7B 提供更有效的小规模证据集。

开发评价查询明确定义为：

\[
q=(x,f,r),
\]

其中，\(x\) 是自然语言问题，\(f\) 是已知故障类别，\(r\) 是所需证据角色（症状、原因/机理、检查或维护）。因此，当前实验是**结构化故障证据检索子系统**的评价，不是从任意用户问句自动识别 \(f,r\) 的端到端评价。自然语言意图解析不在本协议的声称范围内。

所有基准标签、引用质量和语义审计结论均为 **Silver only; never Gold**。它们表示与固定 Silver EvidenceBench 的一致性，不表示领域专家确认的事实正确性。

## 2. 主实验比较

主表只用相同的 \(K=3\) 证据预算比较：

| 方法 | 预算 | 作用 |
|---|---:|---|
| Dense K3 | 3 | BGE-M3 稠密检索基线 |
| Role K3 | 3 | 加入证据角色约束 |
| Role + Graph K3 | 3 | 加入角色约束与图传播 |
| Full K3 | 3 | 再加入故障实体亲和度和来源新颖性 |

Dense K4 只是**次要的跨预算质量—成本运行点**，不得用来归因图传播模块的效果。

## 3. 不可变协议

1. 检索排名先由历史结果构建不可变回放文件，并以哈希清单验证。JSON/JSONL 内容哈希在计算前统一 LF 换行，使 Windows CRLF 和 Linux LF 不会被误判为数据变更；任何非换行内容差异仍必须拒绝覆盖。回放文件只保存排名；历史 v3/v4 `elapsed_ms` 不得进入 v6 正式时延。
2. 正式时延使用现有 BGE-M3 索引重新执行检索，并要求每个新排名与不可变回放完全一致。
3. 每个方法—查询组合执行3次交错顺序测量。`repeat=0` 是唯一质量决策；3次运行都只是时延重复测量，不作多数票、集成或结果融合。
4. 新检索时延与生成阶段时延必须按 `(repeat, method, query_id)` 逐行配对。只有三次都配对成功时才计算该查询的端到端时延；配对不完整时不能用历史时延补值。
5. 所有方法使用同一 Qwen2.5-7B 验证器、回答渲染器、输出契约和拒答规则。在线阶段不得读取 `relevant_evidence_ids` 或 `fault_class_ids` Silver 标签。
6. 时延分解至少包含：检索、提示构造、第一阶段验证、召回导向复核、确定性渲染和端到端时延。模型与索引加载及显式预热不计入单查询时延。

## 4. Linux 服务器执行

从仓库根目录执行：

```bash
cd ~/08-zxk/Fault_LLM_V2
git pull --ff-only origin main
source .venv/bin/activate

bash scripts/run_rp2_equal_budget_v6_server.sh --limit 2
```

限量测试的派生配置、新检索时延、生成记录和摘要全部位于：

```text
.tmp/rp2_v6_equal_budget_smoke/limit_2/
```

它们仅用于联调，不能进入论文主表。限量测试通过后执行正式40问全量实验：

```bash
bash scripts/run_rp2_equal_budget_v6_server.sh
```

流水线依次完成：

1. 构建/验证不可变等预算检索回放；
2. CUDA 、PyTorch 与 BGE-M3 权重格式预检；
3. 重新运行 GPU 检索并验证排名；
4. 运行本地7B证据验证与确定性渲染；
5. 逐行合并检索/生成时延，生成论文表格与故障类簇 bootstrap 置信区间；
6. 报告图数据模型、图谱/向量索引存储规模、来源文档/来源族数量和 provenance 完整率。

### 断点续跑和覆盖开关

重新执行同一命令时：

- 已完成且通过结构、哈希和行数检查的新检索时延会复用；
- 7B生成从 `measurement_checkpoints.jsonl` 继续；
- 默认不覆盖正式产物。

仅在明确需要重跑时使用：

```bash
# 只重测新检索时延
bash scripts/run_rp2_equal_budget_v6_server.sh --force-retrieval

# 只重新调用7B（不复用生成缓存/检查点）
bash scripts/run_rp2_equal_budget_v6_server.sh --force-generation

# 两部分都重跑
bash scripts/run_rp2_equal_budget_v6_server.sh --force-retrieval --force-generation
```

## 5. 正式输出

```text
results/experiments/research_point_2/graphrag_v6_equal_budget/
├── retrieval_replay.jsonl
├── retrieval_replay_manifest.json
├── retrieval_latency/
│   ├── retrieval_latency_runs.jsonl
│   └── retrieval_latency_summary.json
├── measurement_checkpoints.jsonl
├── retrieval_results.jsonl
├── generation_results.jsonl
├── metrics.json
└── paper_summary/
    ├── metrics.json
    ├── table_equal_budget_main.md
    ├── table_cross_budget_secondary.md
    ├── table_latency_breakdown.md
    ├── table_paired_cluster_effects.md
    ├── data_system_footprint.json
    └── data_system_footprint.md
```

论文的主结果必须来自 `table_equal_budget_main.*`。`table_cross_budget_secondary.*` 仅用于跨预算运行点讨论。

## 6. 可选补充实验

以下命令不在主流水线中自动执行，避免无意增加 GPU 或 API 调用。

### 6.1 本地7B验证器消融

固定 Full K3 检索候选，比较直接渲染、第一阶段紧凑掩码、两阶段召回复核：

```bash
python -u scripts/run_rp2_equal_budget_v6.py \
  --config configs/rp2_graphrag_v6_verifier_ablation.json \
  --require-cuda \
  --resume

python -u scripts/summarize_rp2_v6_verifier_ablation.py \
  --config configs/rp2_graphrag_v6_verifier_ablation.json
```

### 6.2 自然语言改写检索稳健性

每个原问题生成2个确定性改写，保持 \(f,r\) 和 Silver 相关证据不变，只评价检索，不用改写数据调参：

```bash
python -u scripts/build_rp2_v6_paraphrase_benchmark.py

python -u scripts/run_rp2_graphrag_v2.py \
  --config configs/rp2_graphrag_v6_paraphrase_retrieval.json \
  --skip-generation \
  --require-cuda

python -u scripts/summarize_rp2_v6_paraphrase_robustness.py
```

### 6.3 same-model, dual-prompt consistency audit

该审计使用同一 `qwen3.7-max` 的两种独立提示词角色，只能称为 Silver 语义一致性审计，不是“两个独立模型”或“专家审核”。API Key 通过隐藏输入临时注入，不得写入命令、配置或日志：

```bash
# 先对少量审计项联调
bash scripts/run_rp2_v6_semantic_judge_secure.sh --limit 6

# 再对四种 K3 方法的完整回答执行正式审计
bash scripts/run_rp2_v6_semantic_judge_secure.sh
```

## 7. 可报告与不可报告的结论

可报告：

- 同预算 K3 方法在 Silver 检索、引用和拒答指标上的差异；
- 新检索与本地7B生成逐行配对后的端到端时延；
- 角色、图传播以及完整系统模块的逐步增益；
- 开发集上的措辞稳健性和可复现的 Silver 语义审计。

不可报告：

- 把 Silver 指标表述为 Gold 或专家事实正确率；
- 把 `repeat=1,2` 与 `repeat=0` 做多数票后称为单次在线时延；
- 把历史 v3/v4 `elapsed_ms` 与 v6 生成时延相加；
- 用 Dense K4 对 Full K3 的跨预算差异证明图模块的独立有效性；
- 将当前结果声称为任意自然语言输入的端到端故障诊断。
