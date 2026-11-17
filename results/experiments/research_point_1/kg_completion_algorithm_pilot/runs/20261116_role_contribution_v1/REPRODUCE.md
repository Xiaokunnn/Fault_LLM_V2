# 复现

本轮新代码在`code_role_contrast_v1`，输出仅在本目录。旧`code_collab_v1`和两轮历史模型完全复用/只读，正式图谱及RP2/RP3不变。没有外部大模型调用，没有重抽文档、重训文本编码器或新GNN层。

从仓库根运行，当前已完成的输入/模型应复用，不清空目录。冷与结构场景用独立进程，避免Python模块级数据路径缓存混用。

```bash
P=results/experiments/research_point_1/kg_completion_algorithm_pilot
.venv/bin/python "$P/code_role_contrast_v1/prepare.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/prepare.py"
.venv/bin/python "$P/code_role_contrast_v1/build_aliases.py"
.venv/bin/python "$P/code_role_contrast_v1/utility_scan.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/utility_scan.py"
.venv/bin/python "$P/code_role_contrast_v1/train.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/train.py"
.venv/bin/python "$P/code_role_contrast_v1/evaluate.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/evaluate.py"
.venv/bin/python "$P/code_role_contrast_v1/report.py"
.venv/bin/python -m pytest -q "$P/code_role_contrast_v1/test_role.py"
RP1_COLLAB_DATASET=structured .venv/bin/python -m pytest -q "$P/code_role_contrast_v1/test_role.py"
```

三种子14112026/27/28；每场景8处理，共48个新适配器训练（主要处理仅545参数）。另48个旧强比较结果直接复用，不重训。分数及rank在evaluation，best用于历史补全比较，last_diagnostic只用于机制诊断，不能据后者选择部署或论文最优模型。

输入和角色原型在data；utility日志保留未通过方向筛选的全部样本；N+/N-原文指针在train_evidence_registry。不可观察的条件控制单列。候选未使用原因有逐条互斥主分类及可重叠次要次数。

第一次utility扫描仅支持2150基础别名索引，遇到8754上下文实体越界，未产生训练结果；已改为完整行政别名闭包，错误日志保留。修复不改变原图、候选或任务标签。跨种子训练不保证逐字节硬件确定性，以保存检查点/输入哈希和分数重放为复现依据。
