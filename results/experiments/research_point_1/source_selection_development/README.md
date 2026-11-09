# 原生证据选择开发状态

2026-10-13：用户补充页面授权后，两次qwen3.8-max真实请求完成，33条输出全部保留。程序通过11/33（33.3%），全量源文AI支持13/33（39.4%）、有问题20条，联合通过3/33（9.1%）。本轮FAIL，不扩大抽取，不发布最终应用图。非盲开发页AI判断，不是专家准确率。

- `legacy_replay.jsonl`：224条旧输出全部保留，源文定位与未分配共享条件。
- `legacy_summary.json`：156条同时引用/两端点可定位，206条有未分配共享条件；不是合格知识统计。
- `local_examples.selection.json`及`local_examples.compiled.jsonl`：4条Codex阅读实际源文编写的条件归属示例，不是API输出。
- `local_examples.manifest.json`及`local_examples.verification.json`：示例来源、编写方式及前置健壮性修正后相同决定校验。
- `sources.jsonl`、`requests.jsonl`、`request_freeze.json`：两页目标/前页原文、模型载荷、调用前哈希。
- `api/`：两份完整原始响应、解析结果及用量；`api_authorization.json`为本次明确授权，原`api_approval_required.json`仅为已解决的历史拒绝记录。
- `selection_decisions.jsonl`及`metrics.json`：全部33条原程序决定、232次位置回读。
- `source_review.jsonl`、`coverage_review.jsonl`：全部33条源文AI判断及原18项清单的覆盖判断。
- `quality_metrics.json`、`records.csv`：逐条质量和数量汇总，可核查模型错误及程序拒绝原因。
- `verification_after_API.json`、`completion.json`：本轮重建与完成状态；原`verification.json`是调用前快照。

31项相关测试通过，其中21项针对新接口。旧10页实验与三个图源文件核验通过，旧响应、评价标签及图谱不变。

已执行目标MP005 p108（上下文p107）、MP021 p6（上下文p5），qwen3.8-max共2次，无重试或额外调用，不重新执行。两页是开发材料，不是新页验证。两份响应、33条决定/判断、232次位置及18项覆盖重建通过，合计56888词元。原图/教师和旧响应保留。

详细说明见[原生证据选择报告](../../../../docs/research/RP1_NATIVE_EVIDENCE_SELECTION.md)。
