# RP1 查询感知候选检索与关系补全

2026-11-16，已实际完成39个训练、三种子、主强比较与消融。简化的检索＋有向端点迁移取得部分基线正向内部证据；神经原型未胜简单方法，尚不足认定原创核心算法成立。

先读[FINAL_REPORT.md](FINAL_REPORT.md)。定义见[METHOD.md](METHOD.md)，拆分/屏蔽见[DATA_PROTOCOL.md](DATA_PROTOCOL.md)，强比较与消融见BASELINE_RESULTS.csv / ABLATION_RESULTS.csv，候选覆盖见RETRIEVAL_RESULTS.csv。源码、检查点、原始分数、各轮日志和全部种子均保留；复现见[REPRODUCE.md](REPRODUCE.md)。

150条潜在关系是未发布推断，不是新增正确知识。正式图谱、RP2/RP3和历史结果不变。
