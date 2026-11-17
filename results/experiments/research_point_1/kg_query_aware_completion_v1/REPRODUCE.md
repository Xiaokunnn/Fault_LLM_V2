# 复现与交付导航

从仓库根目录运行：

```bash
RP1_QUERY_EXP=results/experiments/research_point_1/kg_query_aware_completion_v1
.venv/bin/python "$RP1_QUERY_EXP/code/reproduce.py"
```

完成感知入口复用所有已有阶段，**不会重新训练已完成模型或覆盖分数**。本轮已完成，因此通常只显示REUSE。低层评分/统计脚本是首轮执行器，部分直接写NPZ；不要绕过完成入口在已完成目录重复执行。需要从零复跑时，将本独立模块源码放入同层新实验目录再运行，保留本目录全部资产；不得清空旧目录。

脚本与真实执行顺序：

1. `prepare_data.py`：锁定域对象、新事实/证据组划分、别名/逆向/来源/引文屏蔽、训练候选和记录级排除账本。
2. `train_baselines.py`：9个新SimKGC底座和完整目录特征缓存。原作者模型/旧采样与损失代码从相邻pilot只读导入，新任务从预训练开始。
3. `build_index.py`、`retrieval.py`：冻结语义索引和R0—R3；`retrieval_audit.py`补充可用邻接分层与角色/型号风险，避免把训练目标自身邻接误当可用上下文。
4. `feature_analysis.py`、`feature_lodo.py`：来源代理与文档留出线性读出，不给KGC增加损失。
5. `train_adapters.py`：旧LAN/Full 6个、新残差/消融24个；`fixed_baselines.py`选择固定融合系数和kNN记忆插值，全部只用验证集。
6. `evaluate.py`：全部选定模型封存后评分；`knn_numeric_check.py`保留原概率结果并纠正绝对并列容差压缩，额外6套评分。
7. `summarize.py`：初版主表/区间；`transport_diagnostic.py`：9套明确标为事后的同公式迁移成分对照。没有据此改变主模型或划分。
8. `enhance.py`、`application_notes.py`：验证选择应用方法，输出150条未发布推断及AI源文解释。
9. `verify_delivery.py`：四轮历史资产/输入/15PDF保全、分数重放、初版运行成本。
10. `native_role_correction.py`：发现真实列角色字段为`role`后，只修正源文语义向量/标记；新增21个受影响适配器，无证据控制3个经特征完全一致证明复用。不重训文本底座/检索/旧结构，不换模型或超参数，不改任何原评分。`native_role_probe.py`复算同一来源代理诊断。
11. `finalize.py`：修正后主表、配对区间、分层和验证；原说明文档完整归档后更新FINAL_REPORT。旧CSV、检查点、原始预测全部保留。

三种子16112026、16112027、16112028；新拆分固定hash`query-aware-split-20261116`。域对象833c8040058055434c7f6a9595ec524c3935755f。参数/早停等见每模型config.json及METHOD.md。PyTorch/CUDA/GPU和仓库HEAD见verification/runtime.json。没有外部LLM调用或新的大模型训练。

主要资产：

- `DATA_PROTOCOL.md`、`data/freeze.json`：执行前设置与输入哈希；`audit_only/`仅供行政屏蔽/评价/回读，模型不读其目标文件。
- `index/`、`retrieval/`：初版语义缓存、所有查询的top32、训练自排除缓存、覆盖和错配记录。原始R1—R3检索未因字段修正改变。
- `native_role_correction/BASELINE_RESULTS.csv`、`ABLATION_RESULTS.csv`、`ALL_PRIMARY_SEEDS.csv`：**当前主表**。根目录同名CSV是初版保留记录，不能与修正主模型混作同特征消融。
- `models/`、`features/`：60个实际拟合的检查点与9套新文本缓存；无训练的固定/记忆对照只有配置。所有自动标签均非人工Gold。
- `evaluation/`：93套分数/排名，包括57套最终主比较、21套初版受影响结果、6套概率数值诊断及9套事后迁移诊断。不是93份独立验证。
- `native_role_correction/paired_comparisons.json`、`stratified_results.csv`：最新统计；`analysis/`保留初版。测试仅5项温端点、1项丰富基础结构，不能夸大结构泛化。
- `ENHANCEMENT_CASES.jsonl`、`ENHANCEMENT_REVIEW.md`：模型候选与源文边界。150是推断输出数，不是新增正确图谱知识数。
- `verification/checks.json`与`native_role_correction/verification.json`：保全和程序验证；后者含无证据控制一致性与新增原始分数重放。
- `analysis/initial_document_archive/`：字段纠正前说明文档原样归档。发生问题和更正均披露，不覆盖旧结论或伪造独立验证。

初版7项测试入口：

```bash
.venv/bin/python -m pytest -q results/experiments/research_point_1/kg_query_aware_completion_v1/code/test_query_completion.py
.venv/bin/python -m pytest -q results/experiments/research_point_1/kg_query_aware_completion_v1/code/test_native_roles.py
```

固定随机种子不承诺跨硬件逐字节训练相同；保存输入、检查点、原始分数的哈希及精确排名重放才是本交付复算依据。实际检索/评分延迟是预加载有限目录任务，不含新文本编码、启动和磁盘加载，也不是边缘端测量。
