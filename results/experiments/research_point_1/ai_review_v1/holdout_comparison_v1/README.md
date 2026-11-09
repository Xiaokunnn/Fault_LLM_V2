# RP1 29页对照：已完成

2026-10-04。29份`qwen3.8-max`响应、322条原始assertions、三组966项处理决定、328个不同载荷的源文判断均已完成。复用已保存响应，后处理和评价没有新增API调用。

| 核心指标 | 原始 | 机械筛查 | 源文约束修复 |
|---|---:|---:|---:|
| 全通道保留 | 322 | 165 | 168 |
| 核心S/E/U | 24/95/4 | 16/22/3 | 16/25/3 |
| 原正确核心知识损失 | 0 | 8 | 8 |
| 完整参考匹配 | 20/118 | 14/118 | 14/118 |

**扩大条件FAIL。** 修复没有增加支持核心知识或覆盖，新增3条问题放行。下一步先处理开发材料中的证据定位和关系/条件表示，不直接扩大抽取，也不在这29页上修改方法追求通过。

详细解释见[完整结果报告](../../../../../docs/research/RP1_HOLDOUT29_RESULTS_20261004.md)。数字采用源文支持及固定参考口径；E包括表示/条件问题，不能一概解释为事实虚构。

- `outputs.jsonl`：三组完整输出、处理决定与过程记录。
- `quality_review_packets.jsonl`、`private_arm_mapping.jsonl`：唯一载荷及原候选映射。
- `source_quality_judgments.jsonl`、`review_freeze.json`：328项S/E/U、源文锚点、完整/部分参考关系。
- `metrics.json`、`page_metrics.jsonl`：总体和全部29页指标；核心与背景/结构分开统计，空分母为null。
- `reference_allocations.jsonl`：每组逐页的一对一分配及未匹配参考。
- `correct_knowledge_losses.jsonl`：有支持原候选被筛除/损坏的清单。
- `filter_repair_deltas.jsonl`：六项改动及其中三项新放行。
- `extraction_sidecars.jsonl`：60项原响应辅助内容，独立保留，不混入主指标。
- `evaluation_verification.json`、`independent_numeric_verification.json`：冻结依赖、原文锚点、响应状态、页面合计及独立最大匹配核验。

生成阶段的`completion.json`是当时“质量复核待完成”的快照；当前最终状态以`metrics.json`为准。上级准备阶段README和原始响应completion同样是历史状态，不代表需要重跑。

只读复核与重算命令（不会发送API请求，不覆盖不同版本的文件）：

```bash
python scripts/run_rp1_ai_holdout_v1.py
python scripts/review_rp1_holdout_v1.py
python scripts/summarize_rp1_holdout_v1.py
```

不得再次执行`postprocess_rp1_holdout_v1.py --generate`覆盖本目录。旧教师、图谱、六页开发响应、模型和日志均保留。
