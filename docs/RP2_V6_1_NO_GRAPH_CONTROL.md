# RP2 v6.1 公平无图对照

## 目的

v6.1 专门回答“Full K3 的收益是否能归因于图传播”。两种方法共享：

- 同一个 BGE-M3 向量索引；
- 同一个最大证据预算 K=3；
- 同一角色门控、故障实体亲和度、来源族新颖性和主动欠填；
- 同一 Qwen2.5-7B 两阶段二进制验证器与确定性渲染器；
- 同一交错顺序、三次独立时延测量协议。

`FullNoGraph_v6_1_k3` 仅关闭一跳图传播和图接近度分数。该设计不使用保留测试文档，不改写已冻结 v6 资产。

## 服务器命令

```bash
cd ~/08-zxk/Fault_LLM_V2
git status --short
git pull --ff-only origin main
git rev-parse --short HEAD

source .venv/bin/activate
export RP2_V6_CONFIG=configs/rp2_graphrag_v6_1_no_graph_control.json

# 两条查询的隔离冒烟测试，不进入正式结果。
bash scripts/run_rp2_equal_budget_v6_server.sh --limit 2

# 正式全量对照；中断后重复同一命令即可续跑。
bash scripts/run_rp2_equal_budget_v6_server.sh
```

流水线会先从已冻结 v6 复用 Full K3 排序，再用 GPU 生成新的 Full-NoGraph K3 排序并冻结为 v6.1 replay。随后对两种方法执行交错检索时延和本地7B验证。

## 进度和预估时间

- replay 准备会按 `query/40` 打印候选数、累计时间和 ETA；
- 检索时延阶段共 `2 methods × 40 queries × 3 repeats = 240` 次调用；
- 7B 验证阶段同样为240个交错测量任务，支持检查点续跑；
- 在 RTX 5880 48 GB 且无其他 GPU 抢占时，建议预留30–60分钟。实际时间受首阶段否决数和第二阶段复核调用数影响。

## 输出

```text
results/experiments/research_point_2/graphrag_v6_1_no_graph_control/
├── retrieval_replay.jsonl
├── retrieval_replay_manifest.json
├── retrieval_latency/
├── generation_results.jsonl
├── metrics.json
└── paper_summary/
```

结果推送时只添加 v6.1 目录，不要修改旧 v6 冻结文件。

```bash
git status --short
git add results/experiments/research_point_2/graphrag_v6_1_no_graph_control
git commit -m "Add RP2 v6.1 fair no-graph control results"
git push origin main
```

## 论文表述边界

- 应用目标可称为“资源受限的船舶机舱本地问答平台”。
- RTX 5880 应称为“用于排除卸载和设备差异的可控实验平台”，不称为资源受限硬件。
- 本实验证明固定本地7B和证据预算下的相对质量—时延收益；真实嵌入式硬件部署是后续工程验证，不是当前实验的已完成主张。
