# 复现与产物导航

从仓库根运行。全部写入隔离pilot；已有20261114_controlled_v1不覆盖，不删除任何正式图或旧模型。`.venv`及本地BGE与已保存作者依赖可离线复用；第三方下载不是模型调用，不曾向外发领域源文。

## 仅复算已有结果（不训练）

```bash
.venv/bin/python results/experiments/research_point_1/kg_completion_algorithm_pilot/code/summarize.py
.venv/bin/python results/experiments/research_point_1/kg_completion_algorithm_pilot/code/assemble_delivery.py
.venv/bin/python results/experiments/research_point_1/kg_completion_algorithm_pilot/code/review_sources.py
.venv/bin/python results/experiments/research_point_1/kg_completion_algorithm_pilot/code/write_report.py
.venv/bin/python -m pytest -q results/experiments/research_point_1/kg_completion_algorithm_pilot/code/test_pilot.py
.venv/bin/python results/experiments/research_point_1/kg_completion_algorithm_pilot/code/verify_delivery.py
```

`review_sources.py`只是序列化本次AI实际阅读后的明示判断，重跑不是第二次语义评估。`enhance_claims.py`使用已冻结模型推理写1400项侧表，不训练；发现候选`discover.py`同样只推理，原结果已保存，无须重跑。

## 新目录完整实验复现（此说明不自动执行）

已有作者SimKGC仓库及AnyBURL JAR/JRE保留在`pilot/dependencies`。JAR SHA d1977ee0ffae3f715e48e32e91e8d46d0c5c243941a5a430fd132086160d06b5，SimKGC commit 97cc43e488f19ca5b0f6fbf60ffefd2ee56c0693。Java的官方Azul下载元数据在`dependencies/java_download.json`，并非系统安装；PyTorch/编码器哈希在configs。

```bash
export RP1_KGC_RUN=replay_20261114_new
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
P=results/experiments/research_point_1/kg_completion_algorithm_pilot
.venv/bin/python "$P/code/prepare.py"
.venv/bin/python "$P/code/export_tasks.py"
.venv/bin/python "$P/code/refine_safety.py"
.venv/bin/python "$P/code/text_features.py"
.venv/bin/python "$P/code/run_grid.py" --family complex_core
.venv/bin/python "$P/code/run_grid.py" --family complex_stress
.venv/bin/python "$P/code/run_grid.py" --family anyburl
.venv/bin/python "$P/code/run_grid.py" --family simkgc
.venv/bin/python "$P/code/run_auxiliary_controls.py"
.venv/bin/python "$P/code/run_prototype.py"
.venv/bin/python "$P/code/final_evaluation_driver.py"
.venv/bin/python "$P/code/postprocess_driver.py"
.venv/bin/python "$P/code/summarize.py"
.venv/bin/python "$P/code/enhance_claims.py"
.venv/bin/python "$P/code/assemble_delivery.py"
```

完整新实验的源文评判需重新读取其review_packets，不可机械复制本轮24个ID判断（随机作者规则/验证选择可能不同）。`write_report.py`本轮叙述含固定已观测分析，只适用于本轮封存数值，不是任意新实验的自动结论生成器。以上新跑可能与作者AnyBURL随机运行、CUDA非完全确定性有差异；固定数据SHA及评分重放优先于声称逐位训练复现。

完整运行只有全部78模型封存后才释放测试。若新跑技术中断，保留失败目录并选新suffix/新run，不用reset或清理。现有主run的GPU OOM恢复、AnyBURL正常rc1和ComplEx首次报错记录全部保存。

## 文件入口

- `data/freeze.json`、`task_exports_freeze.json`、`safety_refinement_freeze.json`：输入Git对象、有效分层候选、文本和噪声冻结。
- `configs/`：原型测试前决策、身份过滤策略、环境、编码器与测试释放清单。
- `models/`：78个成功模型、配置、检查点/作者规则快照、逐轮历史、作者原始预测及日志。旧预检和技术失败也保留，不算成功模型数。
- `evaluation/*/test/{metrics.json,rankings.jsonl,scores.npz}`：同一213目标及2150/15答案的原始评分；`document_holdout`另50目标。
- `tables/`：全78行、26个条件组、G1—G4、候选合并、规模/噪声、成本、冷端点、文档留出、配对组区间。
- `discovery/`：全部26,328推断、选择依据、24源文包、私有新颖性/独立性映射、AI逐例判断、五层分类。绝非正式图。
- `enhancement/`：1400现有Claim的证据/范围/模型一致性侧表，不回写图。
- `analysis/`、`figures/`、`verification/`：8个排名案例、3幅科学图（PNG+SVG）、原输入不变与评分重放报告、交付哈希清单。

本任务未执行commit/push；不将GB级模型和第三方依赖直接推入Git。如何归档由后续明确仓库操作要求决定。
