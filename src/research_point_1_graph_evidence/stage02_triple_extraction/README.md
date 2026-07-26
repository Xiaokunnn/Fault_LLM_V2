# Stage 02 - 候选三元组抽取

`bailian_qwen_pilot.mjs` 是已经冻结的四页历史试抽取实现，只用于复现旧结果。它直接调用 `pdftotext`、使用 pilot v1 划分和 Schema v1，不作为下一轮正式抽取入口。

下一轮24页定向抽取必须使用 `chinese_extraction_contract.py` 定义的输出契约：

- `head_surface`、`tail_surface` 和 `evidence_text` 保持来源原语言；
- 同时提出 `head_canonical_zh` 和 `tail_canonical_zh`；
- 类型和关系使用稳定英文机器码；
- E2候选必须返回 Stage 01 的单元格ID；
- 模型翻译默认 `needs_review`，只有命中冻结术语词典或通过独立复核后才能进入中文语义图；
- 中文译文不能参与原文跨度、关系蕴含、证据哈希或覆盖门槛。

Python传输层现已接到 `targeted_24_v2` 页级JSON，支持逐页进度、原始响应缓存、断点续跑、规范化拒绝记录和两页联调。API Key只从当前进程的 `DASHSCOPE_API_KEY` 读取，不写入项目文件。尚未完成真实API联调和24页正式调用。
