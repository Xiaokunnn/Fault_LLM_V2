# 8000级原始候选研究图：实测结构

日期：2026-11-17。仅expanded1456、8003规范化候选及15份构建手册；本轮未重新抽取、未调用外部LLM、未写正式图谱或RP2/RP3。全部排名是内部开发验证代理指标，不是事实准确率或独立测试。

8007行导出仅用于血缘；8003条规范化记录全部保留，计算图按有向(h,r,t)去重为7583条边。以类型+NFKC/casefold中文名称定义实体，保留型号字符，不做语义合并。全目录9021个实体均在完整raw图活跃。

| view | edges | active_entities | active_components | single_semantic_edge_components | largest_component | base_answer_zero_degree | undirected_simple_node_paths_2 | undirected_simple_node_paths_3 | directed_simple_node_paths_2 | directed_simple_node_paths_3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full | 7583 | 9021 | 2215 | 1589 | 3082 | 0 | 57470 | 166214 | 8763 | 5128 |
| train | 5055 | 5935 | 1469 | 1034 | 1820 | 1230 | 30620 | 92732 | 4425 | 1647 |

度分布（按不同邻居，不按Assertion或平行关系重复计）：

| view | 0 | 1 | 2 | ge3 |
| --- | --- | --- | --- | --- |
| full | 0 | 7037 | 1084 | 900 |
| train | 3086 | 4551 | 741 | 643 |

完整raw图的度1实体仍占78.01%。最大组件显著增长说明更多候选确实带来结构；它不证明这些候选正确，更不证明这些路径对留出目标有用。组件不包含Claim/Evidence/Document节点；self-loop留在记录图，节点简单路径与度数统计不把它当新邻居。全图和训练视图各有1条self-loop。

有向统计只沿存储箭头；无向路径按反向等价除2；inverse遍历计数=无向计数×2，仅为计算视图。端点相同但关系不同的边在节点路径统计不重复，在关系序列统计可区分。各文档分布见`analysis/full_documents.json`和`train_documents.json`，关系分布见`analysis/raw_structure.json`。

比较边界：正式expanded1456旧审计最大语义组件为54个实体；这里只沿用该已存在结果定位规模变化，没有重新审计或读入其他历史图谱。不能把raw新增候选当作已确认知识。
