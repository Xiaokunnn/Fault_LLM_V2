# RP1复杂语义绑定受控基线

结论：实验或有效交叉评价尚未全部完成，暂不作算法立项结论。

生成已完成20/168试次。评价为另一实际权重模型的AI交叉核验，不是专家Gold。下面错误数量只统计已有效评价的输出，未评价不等于零错误。

| 集合 | 组 | 已生成 | 有效原始/验证后评价 | 候选/准入 | 原始S/E/U | 验证后S/E/U | 原始S被拒 | 总token | 调用 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| development | B0 | 3/30 | 2/2 | 8/1 | 6/0/0 | 0/1/0 | 5 | 16619 | 3 |
| development | B1 | 3/30 | 1/1 | 19/5 | 5/2/0 | 5/0/0 | 1 | 19107 | 3 |
| development | B2 | 2/30 | 2/1 | 0/0 | 0/0/0 | 0/0/0 | 0 | 6412 | 2 |
| development | B3 | 2/30 | 1/2 | 9/0 | 0/0/0 | 0/0/0 | 0 | 16637 | 4 |
| independent | B0 | 2/12 | 0/2 | 8/1 | 0/0/0 | 0/1/0 | 0 | 5822 | 2 |
| independent | B1 | 4/12 | 3/4 | 6/1 | 0/0/0 | 0/1/0 | 0 | 13286 | 4 |
| independent | B2 | 0/12 | 0/0 | 0/0 | 0/0/0 | 0/0/0 | 0 | 0 | 0 |
| independent | B3 | 4/12 | 3/4 | 20/2 | 10/4/0 | 1/1/0 | 10 | 32273 | 8 |

T01–T17逐条历史归因见../../trace/TARGET_ATTRIBUTION.md；本轮逐靶点和七维评价见focus_assessments.jsonl，具体失败理由、输出引用及源文引用均保留。两次重复逐项一致性见repeat_stability.jsonl。

独立样本为6个按源文线索预选的构建页、各1个焦点；不是全页穷尽参考、正式召回率或来源族独立外测。语义线索分层不等于已证实每段都属于可表达关系；NA必须单列。T01/T02/T16另列辅助要求。

B0是同一7B上的前瞻性旧提示与规则对照，另有通用公共输出约束，不冒充历史Qwen-max原结果。B1加通用结构约束，B2加复杂语义提示，B3分配两次阅读；相同源文与资源上限不等于相同实际token消耗。B3重复输入已计费。

模型：本地Qwen2.5-7B-Instruct BF16；评审为本地qwen3.8:27b别名，实际qwen35架构27.3B Q4_K_M，以resources.json摘要为准，不是DashScope qwen3.8-max。同家族相关偏差不能排除。

设置预检的两条空输出和中断试次保留在complex_binding_controlled_v1_20261110，不计正式方法结果。最初评审把源文支持误作输出保留，原记录留在evaluation/且全部排除；cross_evaluation/通过空/正确/改错三组合成控制并要求输出引用。任何评价失败都保留为未评，不自动重试或回填标签。

运行时生成与评审共享GPU，耗时不是隔离的模型延迟基准；报告token及调用的实际成本。全部工作不发布图谱、不改strict208/RP2/RP3。

复现：.venv/bin/python scripts/run_rp1_complex_binding_baselines.py prepare；execute读取冻结配置，只续未开始的试次；.venv/bin/python scripts/rp1_complex_binding_cross_evaluation.py执行有效匿名评价；.venv/bin/python scripts/summarize_rp1_complex_binding.py确定性复算。保留已有结果，不重新运行已完成试次；遇不确定中断先审计，不自动重试。
