# 当前任务选择结论（2026-11-14）

> 后续任务已更新：用户现已正式确定E1潜在关系发现、E2可信关系补全、E3已有关系增强为RP1核心算法任务，不再进行A～E排名。服务器请优先阅读`docs/research/RP1_KGC_ALGORITHM_PILOT_SERVER_HANDOFF_20261114.md`，新结果写入`kg_completion_algorithm_pilot/`。下文保留为前置实验的历史结论，不作为本轮执行目标。

本轮实际增量实验后，优先推荐 **A：证据约束的候选知识恢复与上下文语义对齐**。E作为原文发现/关联扩展分支，B/C作为条件与对齐机制，D作为可靠性修复。

完整依据读 `runs/20261114_enhancement_v1/REPORT.md`。最终数字读该目录 `evaluation/FINAL_METRICS.json`，实际沙盒读 `sandbox_v2/`。

已经生成22条原文支持的试验Assertion、19个新增试验Claim，不等于通过原正式发布流水线。15个新增Claim来自A，4个来自E。正式图谱和RP2/RP3未改。

根目录旧`README.md`、`REPORT.md`及`task_selection.json`保留为上一轮封存记录，其中优先推荐B的意见不再作为当前结论。它们不被覆盖，以保留哈希和研究过程。
