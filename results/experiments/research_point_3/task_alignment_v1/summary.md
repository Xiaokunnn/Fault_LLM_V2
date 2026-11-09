# RP3 构建集任务—监督对齐审计

只读既有教师记录；没有模型调用、训练、特征重算或阈值拟合。完整解释见独立结果报告。

| 子集 | 轨迹 | 可用已评估候选 | 正且入选 | 正但未选 | 负但入选 | 未评估 | 全池正标签取前3集合不一致 |
|---|---:|---:|---:|---:|---:|---:|---:|
| train_original | 32 | 199 | 52 | 59 | 0 | 6 | 10 |
| train_derived | 97 | 557 | 148 | 156 | 0 | 17 | 24 |
| train_all | 129 | 756 | 200 | 215 | 0 | 23 | 34 |
| validation_original | 8 | 35 | 15 | 5 | 0 | 2 | 1 |
| validation_derived | 28 | 91 | 33 | 16 | 0 | 3 | 7 |
| validation_all | 36 | 126 | 48 | 21 | 0 | 5 | 8 |

“全池正标签取前3”使用已保存教师标签，仅用于说明支持与选集目标的区别，不是新模型成绩。

| split | 点式输入冲突组 | 最少经验错误/出现项 | 原标签产生的提示词+位置冲突组 |
|---|---:|---:|---:|
| train | 10 | 10/756 | 0 |
| validation | 3 | 3/126 | 0 |

| 查询 | 证据ID | split | 正/负出现 | 不同第一阶段提示 | 正标签生成路径 |
|---|---|---|---:|---:|---|
| CQ-F06-CAUSE | MPA-038f63e885f8426341ae | train | 1/2 | 3 | {'first_stage_positive_skip_review': 1} |
| CQ-F08-MAINT | MPA-8e947ac6c11836ceff20 | train | 1/2 | 3 | {'first_stage_positive_skip_review': 1} |
| CQ-F06-SYM | MPA-be9a77914e63b936ffea | train | 1/2 | 3 | {'first_stage_positive_skip_review': 1} |
| CQ-F06-CAUSE | MPA-3af53607169f97a8540e | train | 1/2 | 3 | {'first_stage_positive_skip_review': 1} |
| CQ-F09-CAUSE | MPA-7bdaab4344122a94d3d4 | train | 1/2 | 3 | {'first_stage_positive_skip_review': 1} |
| CQ-F04-MAINT | MPA-fce4a35a32f4c0a1bf5d | train | 2/1 | 3 | {'first_stage_positive_skip_review': 2} |
| CQ-F05-CAUSE | MPA-31cfe61c3fab1eeb49c8 | train | 1/3 | 4 | {'first_stage_positive_skip_review': 1} |
| CQ-F08-CAUSE | MPA-fbb25461ec91239c345f | train | 4/1 | 2 | {'first_stage_positive_skip_review': 1} |
| CQ-F09-MAINT | MPA-8e947ac6c11836ceff20 | train | 2/1 | 3 | {'first_stage_positive_skip_review': 2} |
| CQ-F01-CAUSE | MPA-d81497235d4fb3ce2363 | train | 4/1 | 2 | {'first_stage_positive_skip_review': 1} |
| CQ-F03-MAINT | MPA-b9b7fad781ef2e3e035f | validation | 1/2 | 3 | {'first_stage_positive_skip_review': 1} |
| CQ-F03-CAUSE | MPA-071121ae17b49c3a80d6 | validation | 2/1 | 3 | {'first_stage_positive_skip_review': 2} |
| CQ-F10-INS | MPA-0a124fbf7c2df9e64ada | validation | 2/1 | 3 | {'first_stage_positive_skip_review': 2} |

核验记录317份，匹配模型响应缓存519份。
相同已保存用户提示词的检查不证明所有运行环境下教师确定性，亦不是因果实验。

| split | 原始查询 | 派生轨迹 | 故障类别场景 | 故障名替换后模板 | 非空运行上下文 |
|---|---:|---:|---:|---:|---:|
| train | 32 | 97 | 8 | 4 | 0 |
| validation | 8 | 28 | 2 | 4 | 0 |

故障类别场景不是独立现场病例；四种表面模板不是四个经过独立采样的临床/工程任务族。
仍采用固定共享证据记忆；文档/来源族交集见summary.json，不能声称未见语料泛化。
