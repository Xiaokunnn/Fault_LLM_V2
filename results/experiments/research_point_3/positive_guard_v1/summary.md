# 正支持更新保护三种子结果

仅构建集内部诊断；C0/W1未重训。

| 臂 | seed | 最佳epoch | 原始val Pointer F1 | 非空目标最终为空 | 正支持召回@0.5 | 完整val教师空集误填 |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 7042027 | 2 | 0.4750 | 1/7 | 0.8000 | 3/12 |
| W1 | 7042027 | 1 | 0.0000 | 7/7 | 0.0000 | 0/12 |
| G1 | 7042027 | 1 | 0.2708 | 4/7 | 1.0000 | 0/12 |
| C0 | 7042028 | 1 | 0.3333 | 4/7 | 1.0000 | 0/12 |
| W1 | 7042028 | 1 | 0.0000 | 7/7 | 0.0000 | 0/12 |
| G1 | 7042028 | 1 | 0.2708 | 3/7 | 1.0000 | 0/12 |
| C0 | 7042029 | 1 | 0.2333 | 4/7 | 0.6500 | 0/12 |
| W1 | 7042029 | 2 | 0.2250 | 5/7 | 0.1500 | 0/12 |
| G1 | 7042029 | 1 | 0.0500 | 5/7 | 1.0000 | 0/12 |

G1_vs_W1: 预声明整体改善=True；条件={'pointer_f1_strictly_improved': True, 'support_recall_not_lower': True, 'decoded_empty_not_higher': True, 'decoded_cardinality_not_lower': True, 'all_seed_false_fill_safeguards': True}。

G1_vs_C0: 预声明整体改善=False；条件={'pointer_f1_strictly_improved': False, 'support_recall_not_lower': True, 'decoded_empty_not_higher': False, 'decoded_cardinality_not_lower': True, 'all_seed_false_fill_safeguards': True}。

分母按每种子计，不把多种子或派生轨迹合并为独立病例；原始validation只有2个场景。
