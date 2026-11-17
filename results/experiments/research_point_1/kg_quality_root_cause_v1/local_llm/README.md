# 可选本机独立AI复核

本轮使用显式标明身份的助手源文阅读代理，没有调用外部LLM，也不需要用户人工标注。这里的任务包用于未来可选交叉核查，不是已完成的独立评价。

`review_packets.jsonl`只含冻结源文单元、位置、Schema及待回答维度，不含本轮A—U判断、旧AI答案、图谱视图名称或各方法得分。它包含原始手册片段，发送前须取得对应资料/服务/输入ID的明确外传授权，不能继承历史任务对其他页面的授权。

运行工具复用上一轮服务器硬禁、默认关闭、环境变量取Key、逐输入SHA授权、缓存、请求和重试上限机制；所有新缓存强制在本目录，不能写入旧实验。当前模型服务器主机、SSH及作业环境不允许调用。主统计程序不导入此工具。

```bash
.venv/bin/python -B results/experiments/research_point_1/kg_quality_root_cause_v1/local_llm/run_optional.py --check-only
```

应返回`allowed:false, network_calls:0`。需要独立模型复核时，把已授权的少量任务包和同版本仓库放在有VPN的本机；按上一轮`local_llm/README.md`的权限文件格式显式启用。未收到回传前，不得把现有助手判断改称独立AI评估或专家Gold。
