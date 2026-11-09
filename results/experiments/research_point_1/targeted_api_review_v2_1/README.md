# RP1 六页 API 对照结果

12 个 Qwen3.8-max 响应已完成，含一次超时后的人工补试；累计 13 次网络尝试。无自动循环重试，旧教师、主图和原研究记录均未更改。

当前结论：E1 有局部结构改善，也仍有语义错误；整体推进规则未证实。独立专家准确率/召回率和完整参考匹配仍未完成。

- [详细报告](../../../../docs/research/RP1_TARGETED_API_V2_1_RESULTS_20261002.md)
- [汇总 JSON](completion_summary.json)
- [机械指标（修正后）](mechanical_summary_corrected.jsonl)
- [16 组技术案例](technical_case_findings.jsonl)
- [定位器修正记录](native_subspan_correction.json)
- [233 条独立候选裁定队列](candidate_expert_review_queue.jsonl)
- [170 项一对一匹配队列](reference_match_review_queue.jsonl)
- [隐藏臂名的原始输出包](arm_masked_review_packets.jsonl)
- [复核独立性说明](review_execution_note.json)
- [完成与保全核验](verification.json)

专家队列必须复制到新的 review 子目录再填写，保留真实身份、时间及理由。操作者曾看过臂名映射，本轮 AI 技术复核不能称独立盲审。

原运行位于 ../adjudication_targeted_v2_1_qwen38；响应复用及传输恢复位于 ../adjudication_targeted_v2_1_qwen38_timeout180。复制缓存不能重复计数为新的模型调用。只读验证命令：python scripts/verify_rp1_targeted_api_completion.py。
