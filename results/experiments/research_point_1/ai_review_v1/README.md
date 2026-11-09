# RP1 AI复核与29页评价入口

2026-10-04按用户“无法人工复核，AI复核即可”的要求推进。当前已完成开发AI裁定、AI评价方法冻结、29页源文优先参考与请求准备；**29次新抽取尚未执行，保留页对照指标尚未产生**。当前缺少执行环境的`DASHSCOPE_API_KEY`。

- [协议及指标口径](../../../../docs/research/RP1_AI_REVIEW_AND_HOLDOUT_V1_20261004.md)
- [本轮结果说明](../../../../docs/research/RP1_AI_REVIEW_V1_RESULTS_20261004.md)
- [开发复审摘要](review_summary.json)：22条=13支持、4表示问题、5未决；这是定向样本，不能估计总体准确率。
- [逐条候选裁定](candidate_adjudications.jsonl)、[5项口径](scope_decisions.jsonl)、[85项参考复审](reference_review.jsonl)：全部是非盲AI技术判断，未填写任何人工评审表。
- [方法冻结](ai_method_freeze.json)：现有E1、机械筛查、v4.1 roles、clause_binding_v1 repair及评价口径已固定；不是专家确认或发布证书。
- [29页源文](heldout_sources/source_only.jsonl)与[首次打开记录](heldout_sources/opening_record.json)：在冻结之后导出，历史候选未用于这次参考构建。
- [逐页清单](heldout_materials/page_inventory.jsonl)、[118项源文优先AI参考](heldout_materials/source_first_references.jsonl)、[辅助/范围/未决说明](heldout_materials/auxiliary_and_limits.json)：11页含核心参考，18页因目录、结构、图示、背景或范围不符等原因无核心参考。不是18页没有任何知识。
- [参考与请求冻结](heldout_materials/reference_and_request_freeze.json)、[29次实际请求载荷](heldout_materials/requests.jsonl)：模型qwen3.8-max，每页一次E1；含完整冻结解析文本、原生表格及适用范围。6张PDF目视检查图只供评价者审查，没有注入文本抽取输入。

当前Codex助手已知开发标签与方法；29页参考制作发生在任何新抽取输出之前，但不是方法盲法或统计独立评估者。参考是AI工作清单，不保证穷尽全部物理页面知识。所有源文原字符、页哈希、原生表格和存在的bbox保持原样，未修复倒序解析或填补缺失坐标。旧开发79项分母及其结果不重算。

继续命令：

```bash
# 只读核验，不调用API，不输出密钥
python scripts/prepare_rp1_ai_review_v1.py check
python scripts/run_rp1_ai_holdout_v1.py

# 在执行环境安全配置DASHSCOPE_API_KEY后，运行已固定的29页抽取
python -u scripts/run_rp1_ai_holdout_v1.py --execute
```

新执行器会保存原始响应、用量、时延和失败；已成功请求只读复用，未决/失败请求停止，不自动计费重试，不自动更换模型。启动前再次核验方法、参考、请求和源文哈希。已有六页233条、22条本地第二意见及RP2/RP3教师均不重跑。

抽取完成后仍须：同一批输出上生成原始/机械筛查/最终修复三组，按本轮冻结口径做AI逐条支持判定与一对一参考匹配，报告完整有效量、问题/未决放行、正确知识损失和逐页覆盖。不能把“准备好参考”写成“已经测得保留页准确率/召回率”。
