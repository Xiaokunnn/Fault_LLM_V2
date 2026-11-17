# 复现、缓存与保全

服务器仓库根目录运行，使用已有`.venv/bin/python -B`。没有外部API依赖；需要Git锁定对象、15份解析页、本地BGE和历史SimKGC特征缓存。GitHub不上传模型权重或147MB可重建向量；它们保留在服务器，不删除。

核对既有结果：

```bash
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/verify.py
```

在新的独立子目录完整重算（先指定未使用过的名字，不覆盖本次结果）：

```bash
export RP1_RAW_RUN_DIR="$PWD/results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/replays/your_unique_run"
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/build_graph.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/vector_bridges.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/path_search.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/sequence_audit.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/run_completion.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/matched_random_control.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/controlled_relation_ablation.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/diagnose.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/prediction_traces.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/verify.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/write_reports.py
OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/package.py
```

阶段完成标记会复用自身结果；不同输出不会静默覆盖。`run_pipeline.py`可按上述顺序执行并保留新运行stdout日志。磁盘保留两种大表副本：本地完整JSONL、Git压缩JSONL.gz；读取器支持后者回退。路径NPZ和用于重算排名的小型支持矩阵随成果提交；大向量/旧模型用来源路径与SHA256清单复用。

主要输入：`kg_query_aware_completion_v1/features/G1_s{seed}.pt`、`G2_s{seed}.pt`、`index/vectors.pt`、冻结data与administrative blockers。本地encoder=`data/model/BAAI-bge-small-zh-v1.5-r7999e1d`。锁定领域读取器来源对象为833c8040058055434c7f6a9595ec524c3935755f。作者SimKGC CustomBertModel来源提交97cc43e488f19ca5b0f6fbf60ffefd2ee56c0693，作者文件与原适配代码原样保留。

`logs/environment.json`记录执行环境；阶段wall time来自各自完成元数据，分别含数据读取/加载/检索等，不是在线延迟或独占硬件吞吐。初次交互工具stdout未逐条转写为伪造日志，已保留实际逐阶段完成摘要；未来新运行使用pipeline保存stdout。

结构数复查：`build_graph.stats`与`sequence_audit.seq_counts`，独立枚举小循环图/平行边/self-loop交叉校验。早期辅助`analysis/relation_sequences_2.csv`未排self-loop，保留作生成记录；正式序列统计统一使用`analysis/{full,train}_relation_sequences.csv`，已排self-loop。它们不参与任何模型打分。
