# 研究点二：面向大模型回答的预算约束 GraphRAG

研究点二以研究点一冻结的中文可追溯 Silver 图谱为输入，研究在候选评分数、图访问量、返回证据数和端到端时延约束下，如何为 Qwen2.5-7B-Instruct 组织相关、来源独立且低冗余的证据包。减少 Token 不是主要目标，主要目标是质量—多样性—时延的综合优化。

## 方法链路

1. `dense_index.py` 使用本地 BGE-M3 建立中文证据向量索引。
2. `graph_rag_v2.py` 以稠密召回结果作为锚点，执行可计量的有限跳图扩散。
3. 在关系角色门控后，联合稠密相似度、图接近度、来源族奖励和冗余惩罚选择 K 条证据。
4. `generation.py` 将证据交给本地 Qwen2.5-7B，并强制输出带证据 ID 的结构化中文回答；证据不足时必须弃答。
5. `evaluation.py` 分别评价检索质量、来源族覆盖、端点重叠、引用 ID 有效性、回答/弃答行为以及模型真实推理时延。

在线排序不得使用 `fault_class_ids`、`relevant_evidence_ids` 等答案字段。MP009–MP013 在开发协议冻结前不得用于调参。所有自动生成的查询、路径、答案和评价标签均为 Silver，不能称为 Gold。

## 当前 v2 修订

- Ours 已加入真实、可审计的预算图扩散，并记录访问节点数和边数。
- 增加 `no_graph`、`no_source_family` 模块消融。
- 引用有效率只统计实际产生的引用；合法弃答不再被误记为无效引用。
- 缓存命中时复用原始模型推理时延，并单独报告缓存读取耗时。
- 正式服务器入口要求 CUDA，禁止静默退回 CPU或发生模型磁盘卸载。
- 提示词哈希进入缓存键，提示词修改后不会误用旧回答。

完整执行方式见 `docs/RUN_RP1_RP2_NEXT_EXPERIMENTS.md`。

## v3核心假设实验

v2主要用于证明全链路可运行及检索模块消融。论文的核心有效性实验升级为v3：在同一7B模型、2048输入Token、256输出Token和确定性回答契约下，比较最终Silver回答效用与端到端p95时延。只有回答效用提高且时延不超过Dense RAG的105%，才判定方法有效。

协议见 `docs/research/RP2_BUDGET_EFFECTIVENESS_V3_PROTOCOL.md`，服务器入口为 `scripts/run_rp2_budget_effectiveness_v3_server.sh`。

开发实验完成后的交错重复时延、双提示词Silver语义Judge、冻结门和MP010–MP013隔离外部评价见 `docs/research/RP2_V3_FINALIZATION_AND_EXTERNAL_PROTOCOL.md`。外部脚本只有在冻结清单已经提交到Git且冻结文件哈希未变化时才允许运行。
