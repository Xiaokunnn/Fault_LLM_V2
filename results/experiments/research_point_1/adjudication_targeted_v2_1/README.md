# RP1 v2.1：争议技术复核与六页定向抽取对照

当前状态：13 条争议已完成 AI 技术复核；六页开发参考和 12 个配对请求已冻结。执行预检因缺少 DASHSCOPE_API_KEY 停止，真实 API 调用为 0。独立专家裁定和正式准确率/召回率仍未完成。

- [完整报告](../../../../docs/research/RP1_ADJUDICATION_TARGETED_V2_1_20261002.md)
- [逐条争议与原文](dispute_review.md)
- [可读参考清单](reference_review.md)
- [专家源文先行入口](expert_source_only.md)
- [固定实验协议](experiment_protocol.json)
- [预检状态](execution_preflight.json)
- [旧资产和原文核验](verification.json)

专家填写时复制 expert_*_queue.jsonl 到新的 expert_reviews 目录，保留真实评审身份、时间、来源和理由；不得改写冻结模板，AI 不得代签。

从仓库根目录运行 `python scripts/run_rp1_targeted_v2_1.py` 只读核验。密钥由环境安全提供后，以 `--execute` 执行固定请求；不把密钥写入文件或命令参数。首轮共 12 次请求，无自动重试。发生不确定调用、截断或模型变化时保留响应并停止。新 API 输出必须进入本目录 api_run_001，不能回写旧实验或主图。
