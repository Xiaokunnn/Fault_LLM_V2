# 候选集合上下文三种子结果

仅构建集内部诊断；C0未重训；S0/S1容量及初始化配对。

| 臂 | seed | 最佳epoch | 原始val F1 | 非空最终为空 | 支持正例召回 | 负支持误接受 | 完整val空集误填 |
|---|---:|---:|---:|---:|---:|---:|---:|
| C0 | 7042027 | 2 | 0.4750 | 1/7 | 0.8000 | 8/15 | 3/12 |
| S0 | 7042027 | 2 | 0.4750 | 1/7 | 0.8000 | 9/15 | 3/12 |
| S1 | 7042027 | 2 | 0.4750 | 1/7 | 0.8000 | 9/15 | 3/12 |
| C0 | 7042028 | 1 | 0.3333 | 4/7 | 1.0000 | 13/15 | 0/12 |
| S0 | 7042028 | 1 | 0.3333 | 4/7 | 1.0000 | 14/15 | 0/12 |
| S1 | 7042028 | 1 | 0.3333 | 4/7 | 1.0000 | 13/15 | 0/12 |
| C0 | 7042029 | 1 | 0.2333 | 4/7 | 0.6500 | 7/15 | 0/12 |
| S0 | 7042029 | 1 | 0.2333 | 4/7 | 0.6500 | 7/15 | 0/12 |
| S1 | 7042029 | 1 | 0.2333 | 4/7 | 0.6500 | 7/15 | 0/12 |

S1_vs_C0: 通过=False，条件={'pointer_f1_strictly_improved': False, 'support_recall_not_lower': True, 'decoded_empty_not_higher': True, 'decoded_cardinality_not_lower': True, 'all_seed_false_fill_safeguards': True, 'negative_false_accept_not_higher': False}。

S1_vs_S0: 通过=False，条件={'pointer_f1_strictly_improved': False, 'support_recall_not_lower': True, 'decoded_empty_not_higher': True, 'decoded_cardinality_not_lower': True, 'all_seed_false_fill_safeguards': True, 'negative_false_accept_not_higher': True}。

上下文增益整体判定=False；停止本条架构试探=True。原始validation仅2个场景。
