# 主实验复现与资产入口

从仓库根目录执行。无需外部大模型API，不重新抽取、重训编码器或修改正式图谱。依赖当前`.venv`、原模型和特征缓存；不清空已有目录，训练器遇到已完成项会复用，遇到未完成同名模型会停止以保护记录。

```bash
P=results/experiments/research_point_1/kg_completion_algorithm_pilot
export RP1_ROLE_VERSION=20261116_role_contribution_clean_v2
export RP1_ROLE_ARMS=gate_kgc,absolute_only,full,shuffled

# 基于完整保留的初始代理账本作训练副本歧义排除；不需要重跑初始48模型。
.venv/bin/python "$P/code_role_contrast_v1/clean_supervision.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/clean_supervision.py"

.venv/bin/python "$P/code_role_contrast_v1/train.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/train.py"

# 各场景所有处理训练完成并封存后才评分，last只作机制检查。
.venv/bin/python "$P/code_role_contrast_v1/evaluate.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/evaluate.py"
.venv/bin/python "$P/code_role_contrast_v1/parent_probe.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/parent_probe.py"
.venv/bin/python "$P/code_role_contrast_v1/report.py"
.venv/bin/python "$P/code_role_contrast_v1/posthoc_diagnostics.py"
.venv/bin/python "$P/code_role_contrast_v1/casebook.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/casebook.py"
.venv/bin/python -m pytest -q "$P/code_role_contrast_v1/test_role.py"
RP1_COLLAB_DATASET=structured .venv/bin/python -m pytest -q "$P/code_role_contrast_v1/test_role.py"
.venv/bin/python "$P/code_role_contrast_v1/verify.py"
RP1_COLLAB_DATASET=structured .venv/bin/python "$P/code_role_contrast_v1/verify.py"
```

原始代理准备和utility扫描命令见相邻`20261116_role_contribution_v1/REPRODUCE.md`；初始48模型不属于清理后主比较。主数据、utility、输出保护采用确定性同内容复用，禁止以覆盖旧结果修正方法。`casebook.py`增加训练目标来源后的输出为`CASEBOOK_WITH_TARGETS.md`，早期不带目标来源的案例文件另行保留。

输出导航：

- `PROTOCOL.md`：执行前约束及训练源文歧义修正说明；`code_freeze_before_test.json`：评分前代码哈希。
- `cold/`、`structured/`：相同历史拆分；其中`data/`为源文指针、候选使用原因、原始/筛后对照及冻结utility。
- `models/role_*`：24个适配器的配置、best、last_diagnostic、历史、成本和哈希；编码器和100962参数主体沿用原版本，只训练545参数门。
- `evaluation/`：24项新结果＋48项历史模型引用，共72项。保存全部三种子，不将复用结果算成新训练。
- `tables/`：MRR/Hit/关系与类型指标、配对区间、门probe、实际训练成本；`figures/`为独立PNG/SVG论文图。
- `analysis/CASEBOOK_WITH_TARGETS.md`：来源角色/扰动/训练目标原文并列；`analysis/proxy_feature_shift.json`：明确字段的代理域偏移诊断。
- `verification/checks.json`、`verification/`总清单及`logs/`：旧资产保全、排名重放和执行记录。

初始48训练和主实验24训练合计72个唯一新适配器；48个旧模型比较在两轮重复引用，不能将两轮96＋72评价当168个独立实验。任何代理监督或程序标签都不是人工Gold。末轮检查点禁止按测试挑选。

本次首次utility扫描的索引越界错误日志保留；案例补充曾触发禁止覆盖保护，随后采用新增案例文件。索引使用完整8754实体别名目录；没有删除或覆盖源资产。
