# RP1 scope_repair_v2

实验运行于 2026-09-30，2026-10-02 完成中断后的汇总与交付核验。包含构建集内的范围协议、定位修复/关系筛查技术试验，以及本地模型第二意见。

报告：[RP1 v2 结果](../../../../docs/research/RP1_SCOPE_REPAIR_V2_RESULTS_20260930.md)。
执行前协议：[范围与评价口径](../../../../docs/research/RP1_SCOPE_AND_EVALUATION_V2_20260930.md)。

## 结论边界

304 条不同开发候选上，技术准备度 A/B/C/D=142/167/111/131；新增 25 条可重建定位建议。
这不是新增合格量或正式抽取准确率/召回率。没有自动放行新记录，没有修改图谱。
记录样本上的有利信号未在页面候选中一致成立，不推广组合筛查规则。
本地模型 26/26 条已完成，与初审 13 条一致、13 条分歧。模型意见不是领域专家真值；其分数不是校准置信度。所有专家裁定状态保持 pending，原标签不变。

## 产物索引

| 文件 | 内容 |
|---|---|
| `protocol_snapshot.md` | 运行前固定的协议；原目标 30 页的抽样短缺另行披露 |
| `experiment_freeze.json` | 四组技术试验运行前输入、代码哈希和时间 |
| `engine_snapshot.py`、`experiment_runner_snapshot.py` | 运行前代码快照 |
| `development_candidates.jsonl`、`development_pages.jsonl` | 来自 v1 已阅材料的 304 条候选与原页 |
| `four_arm_probes.jsonl` | 每条定位建议、警示、四组技术状态；未产生自动合格决定 |
| `new_source_witnesses.jsonl` | 18 个连续原文上下文和 7 个原生同表同行绑定 |
| `old_qualified_recheck_queue.jsonl` | 7 条旧合格记录的待重审警示，不是删除名单 |
| `summary.json`、`four_arm_diagnostic_summary.csv` | 分主样本/补样/页面候选的诊断汇总 |
| `reference_readiness_diagnostic.json` | 固定 v1 参考中有技术候选对应的项数，不能称正式召回 |
| `reference_scope_overlay.jsonl` | 7 项 background；其余待 v2 范围裁定。v1 原清单不改写 |
| `holdout_eligible_frame.jsonl` | 排除已阅、相邻及完全重复文本后，1652 页的 metadata 抽样框 |
| `holdout_manifest.jsonl` | 冻结 29 页 ID/哈希，尚未标注或比较输出 |
| `holdout_sampling_report.json` | MP017 表格层无剩余页，保留 30→29 缺口，未放宽排除 |
| `suspected_rejection_mechanism_audit.json` | 14 条疑似误拒的机械状态、英文词形触发遗漏；事后机制诊断，不属于四组算法 |
| `preservation_before.json`、`verification.json` | 2770 个旧文件保全；v1 的 88 文件及定位/抽样独立重建 |
| `second_opinion/freeze.json` | 固定 26 条样本、提示和 S/N/U 单 token 受限分类方式 |
| `second_opinion/blind_inputs.jsonl` | 不含旧决策和标签的模型输入；保存截取标记 |
| `second_opinion/private_mapping.jsonl` | 仅聚合时使用的 Bxxx→Rxxx 对应；模型推理不读 |
| `second_opinion/runtime.json`、`execution.log` | CPU FP32、依赖、原权重哈希与实际运行日志 |
| `second_opinion/B*.json` | 逐条 logits、标签、无约束首 token、时间和提示哈希 |
| `second_opinion/completion.json` | 26 条已完成，2026-09-30 03:38:34 UTC，总用时约 1532 秒 |
| `second_opinion/summary.json`、`comparison.csv` | 完成后的意见分歧汇总；不是精度 |
| `second_opinion/adjudication_packets.jsonl`、`disagreement_review.md` | 需要独立裁定的原引用、上下文与两种 AI 意见 |
| `delivery_verification_20261002.json` | 续接时核验旧文件保全、26 个提示/token 数、抽样及分歧汇总，无模型推理 |
| `report_before_completion_20261002.md` | 补全第二意见之前的报告备份，其相对链接按原 docs/research 路径解释 |
| `delivery_manifest.json` | 本次交付文件的最终哈希清单 |

## 已执行入口

以仓库根目录为工作目录：

```bash
python scripts/run_rp1_v2_blind_second_opinion.py prepare
.venv/bin/python -u scripts/run_rp1_v2_blind_second_opinion.py run
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_rp1_repair_probe_v2.py -q
python scripts/run_rp1_scope_repair_v2.py prepare
python scripts/run_rp1_scope_repair_v2.py run
python scripts/run_rp1_scope_repair_v2.py summarize
python scripts/verify_rp1_scope_repair_v2.py
```

2026-10-02 已执行 `python scripts/summarize_rp1_v2_second_opinion.py` 和 `.venv/bin/python scripts/verify_rp1_v2_delivery.py` 完成收尾。没有重复运行上述推理和对照命令。
目录采用独占创建，不得覆盖重跑；如果中断，先看 completion、日志和进程，不能直接启动第二份模型推理。
所有已完成代码/规则均冻结；补充分析应另存并说明时间顺序，不能把看结果后的规则修改归到预定试验。

这批页面原本来自构建文档，已经存在历史抽取输出；“保留”只针对本轮开发流程，不代表源文/模型全局未见。
第二意见采用有目的抽样和页面文本，本批 26 条文本未截断；没有独立专家或页面图视觉评阅，不能替代正式评估。

续接时终端与 apply_patch 的沙箱包装因 `mountinfo path is not absolute` 无法启动；通过获准的沙箱外命令完成只读检查和限定于本目录/本轮新报告的写入。没有自动审批拒绝，也没有修改系统沙箱配置。
