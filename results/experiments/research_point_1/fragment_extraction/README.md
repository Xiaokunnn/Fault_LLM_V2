# 完整源文片段抽取

2026-10-13已完成缓存开发和10页真实验证，整体FAIL。138条收到候选、19程序通过、49源文/关键条件/主图目标范围AI支持、18联合通过（13.0%）。精确去重计数19/49/18，不是净新增或完整语义去重，没有发布图。

`development/`：旧10页224条全量菜单兼容诊断、源文菜单/输入、7条本地接口示例；173条两端点有候选，字符覆盖100%，3028次位置回读。不是模型效果。

`validation/`：

- `method.json`、`selection.json`、`sources.jsonl`、`requests.jsonl`、`catalogs/`、`request_freeze.json`：调用前方法、10个固定新目标页/前页与载荷。无输出后改代码/判据。
- `source_reference.jsonl`：调用前56项源文参考，53主图项、3范围控制。
- `api/`：10次qwen3.8-max完整原始响应、解析结果、用量，无重试。
- `decisions.jsonl`、`automatic_summary.json`：全部138条原始程序决定。
- `source_review.jsonl`、`coverage_review.jsonl`：全量非盲源文AI判断及参考覆盖，不是专家真值。
- `quality_metrics.json`、`records.csv`、`verification.json`、`completion.json`：可复算数量/质量与完成状态。

参考完整17/53、部分31、遗漏5，不是正式召回率；联合完整3/53，7个预定有知识页仅1页有联合通过。三个扩图条件均失败。结构清晰的MP015 p47有18/19联合通过，但不能代表整体。

55项相关测试通过。两批调用前QC准备页已排除并归档到`logs/rp1_fragment_preflight_20261013/`；没有响应，不是质量实验。没有剩余未见英文原生故障表，本批为6维护/4正文，不声称未见表格泛化。所有旧图、教师与响应保留。

`prepare/seal/execute/collect`已经完成，不重新调用或覆盖。只读重建入口是`python scripts/summarize_rp1_fragments.py`。

详见[实现与结果](../../../../docs/research/RP1_FRAGMENT_EXTRACTION.md)。
