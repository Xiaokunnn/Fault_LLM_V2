# 实际运行入口

全部命令从仓库根运行，现有`.venv`、本地BGE和上一轮作者SimKGC依赖可直接复用。输出固定在新研究目录，不改原20261114_controlled_v1。已有完整模型自动复用；失败的半成品必须独立备份，不能用删除或覆盖来恢复。

新数据准备（本轮已完成，不重复执行训练）：

```bash
P=results/experiments/research_point_1/kg_completion_algorithm_pilot
.venv/bin/python "$P/code_collab_v1/prepare_collab.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_collab_v1/prepare_collab.py"
.venv/bin/python "$P/code_collab_v1/controls.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_collab_v1/controls.py"
```

已实际执行的训练/特征/评价入口如下。冷基线G1/G2/G3从前次检查点和分数复用，结构底座从预训练权重重新训练。各进程自行用同一GPU锁序列化，可分别启动，但不要手动绕开锁。

```bash
.venv/bin/python "$P/code_collab_v1/baselines.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_collab_v1/baselines.py"
.venv/bin/python "$P/code_collab_v1/cache_text.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_collab_v1/cache_text.py"
.venv/bin/python "$P/code_collab_v1/fit_collab.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_collab_v1/fit_collab.py"
.venv/bin/python "$P/code_collab_v1/evaluate_collab.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_collab_v1/evaluate_collab.py"
.venv/bin/python "$P/code_collab_v1/postprocess.py"
```

评价脚本等待全部48个方法封存，才释放该场景测试；postprocess等待两个场景完成后汇总96结果、执行18个冻结权重干预并输出新预测。神经seed14112026/27/28，所有条件和预算见DESIGN_FROZEN、METHOD、各模型config/history/complete。原测试已曝光，此限制不因复现而消失。没有调用外部LLM或用户人工标注。

仅重算统计/检查（不训练）：

```bash
.venv/bin/python "$P/code_collab_v1/summarize_collab.py"
.venv/bin/python "$P/code_collab_v1/diagnose.py"
.venv/bin/python "$P/code_collab_v1/write_report.py"
.venv/bin/python -m pytest -q "$P/code_collab_v1/test_collab.py"
RP1_COLLAB_DATASET=structured .venv/bin/python -m pytest -q "$P/code_collab_v1/test_collab.py"
.venv/bin/python "$P/code_collab_v1/verify_collab.py"
```

语义核查脚本中的明确AI判断只对应本轮已阅读的源文包，重新序列化不是新增独立评价。当前脚本固定本轮研究目录；完整再训练若需新版本，应先改为独立新目录并冻结版本，不能强行覆写本轮结果。`cache_text`保存2150×30查询向量，属闭合实体目录预计算，非输入测试答案。训练算法主要成本为底座，约10万参数适配器成本另列，不冒称全模型仅10万参数或边缘设备结果。
