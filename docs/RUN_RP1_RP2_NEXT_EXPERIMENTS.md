# 研究点一与研究点二下一阶段实验执行说明

更新日期：2026-08-03

## 1. 当前边界

- 研究点一是“可追溯证据型 Silver 知识图谱构建与质量治理”。
- 研究点二是“面向大模型回答的预算约束 GraphRAG 检索与证据组织”。
- 研究点二必须同时评价检索和生成，不再把纯字符串检索当作最终实验。
- 所有自动标签、查询、路径和回答评价都是 Silver，不是 Gold。
- MP009–MP013 在开发协议冻结前不得用于调参。

## 2. 研究点一剩余实验

### 2.1 已完成

- 8003 条全审计记录和 1698 条证据合格 Silver 断言。
- `KG_v1_raw` / `KG_v1_validated` 双图机制。
- CQ v1 十类故障四种任务类型查询。
- B0–Ours 离线治理对照、模块消融、敏感性和标准化约束报告。
- 来源族 ×1/×2/×4/×8 复制压力实验：来源族封顶指数保持不变，按文档计数的素朴基线出现虚假支持膨胀。
- 固定20页真实API B0–Ours对照已完成；详见 `results/experiments/research_point_1/api_prompt_comparison_v1/`。

### 2.2 已完成的真实 API 对照

目的是区分“后处理门控带来的改变”与“提示词/结构约束对模型原始输出的真实影响”。五种方法在同一批固定页面上调用 qwen3.7-max，再用同一校验器评价。

Linux：

```bash
cd ~/08-zxk/Fault_LLM_V2
source .venv/bin/activate
bash scripts/run_rp1_api_prompt_comparison_secure.sh
```

先做两页联调：

```bash
bash scripts/run_rp1_api_prompt_comparison_secure.sh --limit 2
```

脚本使用隐藏输入读取 API Key，不写入配置、文件或命令历史。输出会逐方法打印页面进度。

## 3. 研究点二 GraphRAG v2

### 3.1 模型目录

服务器需要保持以下精确路径：

```text
data/model/BAAI-bge-m3
data/model/Qwen2.5-7B-Instruct
```

`data/model/` 已加入 Git 忽略，不会把模型权重推送到 GitHub。

### 3.2 实验链路

```text
完整中文发布图谱
  -> BGE-M3 建立证据向量索引
  -> 稠密锦标召回
  -> 固定跳数 / 自适应扩散 / 元路径约束
  -> 来源族封顶与冗余抑制
  -> K=4 证据包
  -> Qwen2.5-7B-Instruct 生成带证据ID的中文回答
  -> 检索、引用、时延与显存评价
```

对照方法为 `closed_book`、`dense_topk`、`dense_fixed_hop`、`dense_adaptive`、`dense_metapath` 和 `dense_ours`。开发查询的相关证据ID只用于离线评价，不进入检索打分或模型提示词。

### 3.3 Linux 服务器命令

```bash
cd ~/08-zxk/Fault_LLM_V2
source .venv/bin/activate
python -m pip install -r requirements-server.txt
bash scripts/run_rp2_graphrag_v2_server.sh
```

由于当前 BGE-M3 使用 `pytorch_model.bin`，Transformers 的安全门槛要求 `torch>=2.6`。服务器当前驱动环境建议显式安装 CUDA 11.8 版 PyTorch 2.6，再安装其余依赖：

```bash
python -m pip install --upgrade --force-reinstall \
  torch==2.6.0 --index-url https://download.pytorch.org/whl/cu118
python -m pip install -r requirements-server.txt
```

流水线的第0阶段会同时检查 CUDA 和 BGE 权重格式/torch版本；版本不符合时会立即停止，不再等到敏感性实验加载模型后才报错。

该入口现在先执行 CUDA 强制检查，再依次构建开发基准、复用或建立 BGE-M3 索引、运行检索敏感性实验以及运行 Qwen 生成实验。正式入口禁止自动退回 CPU。

先做两个查询的真实模型联调：

```bash
bash scripts/run_rp2_graphrag_v2_server.sh --limit 2
```

建议联调时强制进行真实生成，避免旧缓存掩盖提示词或指标修改：

```bash
bash scripts/run_rp2_graphrag_v2_server.sh --limit 2 --methods dense_ours --force-generation
```

联调通过后执行完整主对照和两个关键模块消融：

```bash
bash scripts/run_rp2_graphrag_v2_server.sh --include-ablations --force-generation
```

只测试检索、暂不加载 Qwen：

```bash
bash scripts/run_rp2_graphrag_v2_server.sh --skip-generation
```

中断后重新执行同一命令。BGE 索引已存在时会复用，Qwen 的每个“方法×查询”回答也会从缓存恢复。

### 3.4 输出与预计时间

- 索引：`data/kg/marine_pump/vector_indexes/bge_m3_KG_v1_validated/`
- 生成缓存：`data/interim/rp2_model_cache/qwen2_5_7b_graphrag_v2_v2/`
- 指标：`results/experiments/research_point_2/graphrag_v2_development_v2/metrics.json`
- 方法对照图：`results/experiments/research_point_2/graphrag_v2_development_v2/method_comparison.png`
- 敏感性数据与图：`results/experiments/research_point_2/graphrag_v2_sensitivity_v2/`
- 逐查询检索与回答记录位于同一结果目录。

当前 208 条中文发布证据规模下，BGE 建索引通常是分钟级；主对照为6种方法×40个查询，共240次生成。加入两个消融后为320次生成。真实时间取决于生成长度和服务器负载，终端会打印进度和预估剩余时间。

v2 的开发配置位于 `configs/rp2_graphrag_v2_development_v2.json`。旧 v1 配置和结果保留用于审计，不覆盖、不删除。冗余惩罚在既有开发敏感性中以0取得更好的召回与nDCG，因此 v2 主配置将其设为0，并将“端点重叠率”保留为观测指标，而不把无效模块包装成贡献。

## 4. 冻结与外部评价顺序

1. RP1真实API对照已完成并冻结，不再使用外部数据回流修改该对照。
2. 在 CQ v1 开发查询上完成 GraphRAG v2 消融与参数选择。
3. 冻结提示词、本体、索引、K、来源族上限、扩散阈值和生成配置。
4. 冻结后才对 MP010–MP013 生成外部 Silver 查询/证据，只报告一次外部结果，不回流调参。

注：MP010–MP013 已做过机械性解析，因此对 GraphRAG v2 应称为“来源保留外部评价”，不声称为完全未触及的盲测。
