# RP3 服务器实验执行说明（更新于 2026-09-18）

当前续跑已完成构建集证据移除增强、增强组train/route/export/quantize；增强组校准同样失败关闭，
40条MP008输入全部原始路由为abstain。不要再次执行本指南的augment或增强组训练命令。
先读 [`RP3_AUGMENTED_V1_RESULTS_20260917.md`](RP3_AUGMENTED_V1_RESULTS_20260917.md)，
后续已完成B0/M0离线diagnose、R0–R3重放和三种子A1–A4逐头消融；结果见
[`RP3_DIAGNOSTICS_V1.md`](RP3_DIAGNOSTICS_V1.md)及
[`../results/experiments/research_point_3/head_ablation_v1/summary.md`](../results/experiments/research_point_3/head_ablation_v1/summary.md)。
字段监督审计及三种子归一化对照也已完成，见
[`RP3_FIELD_NORMALIZATION_V1_RESULTS_20260917.md`](RP3_FIELD_NORMALIZATION_V1_RESULTS_20260917.md)。
新臂欠填与Pointer F1改善，但一枚种子新增教师空集误填，未通过整体改善条件；不要重跑或将其直接用于部署。
后续联合门控审计及W1/J1三种子实验也已完成，见
[`RP3_JOINT_CONTRACT_V1_RESULTS_20260917.md`](RP3_JOINT_CONTRACT_V1_RESULTS_20260917.md)。
两臂消除观测误填却使Pointer F1降至0.0750，未实现整体优化。
支持可分性审计及G1正支持更新保护三种子也已完成，见
[`RP3_POSITIVE_GUARD_V1_RESULTS_20260917.md`](RP3_POSITIVE_GUARD_V1_RESULTS_20260917.md)：
G1 F1恢复到0.1972且空集误填仍为0/12，但低于C0的0.3472；正、负支持均过门，整体优化未成立。
候选集合上下文S0/S1现已完成，仍未改变validation选集；见
[`RP3_SET_CONTEXT_V1_RESULTS_20260917.md`](RP3_SET_CONTEXT_V1_RESULTS_20260917.md)。
已暂停本条结构/损失试探，转入[`RP3范围评审`](research/RP3_SCOPE_REASSESSMENT_20260917.md)，
E1语义特征与H512对照也已完成，两项总体判据失败；最新结果见
[`RP3_SEMANTIC_V1_RESULTS_20260918.md`](RP3_SEMANTIC_V1_RESULTS_20260918.md)。
下一步先做任务/监督/数据与研究范围评审；不要重跑G1/S0/S1/E1/H512，没有部署证书时不得evaluate。

## 先看边界

核心链路已经在服务器实际执行；当前既有成功产物，也有必须保留的基线校准失败结果。
服务器的 7B 应为冻结 RP2 实际使用的 `Qwen2.5-7B-Instruct`，还需要 `BAAI-bge-m3`。
仅有任意一个 7B 模型不足以精确复现教师；不能把另一款 7B 改目录名冒充原教师。
学生是四头 LEC，不是训练 7B。边缘工具可以由 LLM 调用，也可以直接用 JSON 调用。

本次默认可运行版本使用 256 维字符 n-gram 哈希查询特征、288 维证据特征。
该编码器不需要另下模型、没有可学习参数，能够处理新问题；它是**轻量特征基线**，不是已验证的语义编码器创新。
后续与小型语义编码器比较时，必须把编码器参数、时延与内存一并计入，不能只计算 LEC。

## 1. Git同步与远程接手

当前服务器目录已确认为 `~/08-zxk/Fault_LLM_V2`，后续代码统一通过Git同步，不再把白名单补丁包作为常规更新方式：

```bash
cd ~/08-zxk/Fault_LLM_V2
git status -sb
git pull --ff-only origin main
git log -1 --oneline
```

当前工作分支为 `codex/rp3-augmented-v1-results`；接手时残留rebase已备份后以 `--quit` 退出，原main提交保留。
从本地提交 `9370860` 恢复了691个缺失实验文件，并备份后恢复6个旧版本；
详见 `logs/rp3_asset_recovery_20260917T000825/recovery_manifest.json`。
同步前须保留这些恢复差异和新增结果，不要直接切回旧main或批量还原受跟踪产物。

本轮整理分支`codex/rp3-augmented-v1-results`收录代码、协议及可审阅结果，
入口见[`RP3结果索引`](../results/experiments/research_point_3/README.md)。尚未合入main时，在其他干净检出通过
`git fetch origin`获取该分支，不要把`origin/main`误认为已包含本轮结果。

服务器的模型、教师缓存、MP008原始响应、训练checkpoint、ONNX、特征bundle及日志不进入本次提交；
JSON/CSV/Markdown报告、逐行预测、训练/量化清单及校准失败报告随本轮结果提交。
Git同步时不得使用 `git reset --hard` 或 `git clean` 删除这些资产。若旧补丁造成受跟踪文件存在本地修改，
先用 `git stash push -m "rp3-server-code-before-pull"` 保存，再执行fast-forward pull；远端已包含对应修复时无需pop。

远程开启新对话时，先让助手阅读根目录 `AGENTS.md`、`docs/RESEARCH_HANDOFF.md`、
`docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md` 和本文件，
再检查当前日志与结果目录，不要从teacher阶段重新开始。

## 2. 环境和模型

```bash
cd ~/08-zxk/Fault_LLM_V2
source .venv/bin/activate
python -m pip install -r requirements-rp3-server.txt
nvidia-smi
python -c 'import torch; print(torch.__version__, torch.cuda.is_available())'
bash scripts/run_rp3_experiments.sh preflight
python -m pytest tests/unit/test_research_point_3_*.py -q
```

必须存在：

```text
data/model/Qwen2.5-7B-Instruct/config.json + 模型权重、tokenizer 文件
data/model/BAAI-bge-m3/config.json + 模型权重、tokenizer 文件
data/kg/marine_pump/triples/KG_v1_validated/               # 208/203/281
data/interim/parsed_pages/corpus_v2/MP008.pages.v2.jsonl  # 仅校准
```

依赖文件沿用 RP2 的 torch 2.6.0 约束。已工作的 CUDA 环境不要盲目替换；若安装后 CUDA 不可用，
先按服务器驱动选择兼容的 PyTorch wheel，再继续。脚本不下载模型，也不会把教师偷偷退回 CPU。
上面的专项测试包含纯合成 CPU 训练/ONNX/INT8 联调，不会加载 7B/BGE，亦不产生正式实验结果。

### 2026-09-16 已解决的服务器阻塞

若其他新环境的预检列出 `missing/mismatched RP2 frozen input`，说明检出中缺少论文冻结清单依赖，
不是 7B、CUDA 或 BGE 故障。先确认已经拉取最新 `origin/main`；若受跟踪的冻结小文件被本地改写，
只对预检明确列出的路径从远端提交恢复，不要重算论文资产，也不要对整个工作区执行破坏性重置。
同步后必须先单独执行并确认：

```bash
bash scripts/run_rp3_experiments.sh preflight
echo $?  # 必须为 0
```

若仍有条目，不要继续 `teacher-smoke` 或 `all`，也不要在服务器上重算、改写这些论文资产；
应从本地冻结副本重新同步。新版审计会在小型先决条件失败时跳过大型模型哈希。

资产齐全后，首次 `teacher-smoke` 会对 Qwen2.5-7B、BGE-M3 和索引执行逐字节 SHA-256 清点。
终端会打印 `[RP3 inventory]` 进度；这是一次完整性绑定，不是模型推理卡死，请勿中断。

若 7B 对某个**辅助尾候选**未返回合法的严格 JSON/掩码，新版代码会保留原始响应，
将该候选标记为 `not_assessed`，并在支持损失中使用 `IGNORE_INDEX`；它不会被伪装成负样本，
也不会改变冻结 RP2 K3 的选择。若原始 K3 核验本身无效，流程仍会失败关闭。

RP2 的故障范围采用可见中文语义亲和度与直接支持核验，不把自动 `fault_class_ids`
当作专家真值。若一条原文能直接支持相邻故障范围、但自动本体仅给出一个标签，导出器保留
原标签并记录跨标签证据 ID；在线工具仅对冻结教师已选中的这些 ID 放行，不对整个候选池放宽。

诊断角色严格复现 RP2 v6 的关系语义映射（例如 `indicates`属于“症状”）。严格 208 图中有
5 条记录保留了与关系语义不一致的早期 `evidence_role`；RP3 不改写冻结图，而是按 RP2
关系语义构建轻量证据内存，并在内存元数据中显式保留原字段及冲突标记。

严格 208 图中有 4 个故障×角色问题没有任何候选证据。这不是数据损坏，而是有效的“主动欠填”
和路由监督：轨迹保留故障场景分组，但不伪造来源文档 ID。固定证据内存的训练/验证协议允许这种空候选轨迹；
真正声称文档隔离的归纳实验仍强制要求文档组。边缘运行时，空候选桶不调用 ONNX，而是按教师可用性执行回退或弃答。

MP008 的 PDF 表格提取文本包含大量对齐空格和换行。校准候选的 v2 跨度策略允许模型对这些空白做规范化，
但所有非空白字符仍必须在页面的一个连续区间中按原顺序匹配；最终存储的是映射回原页面后的精确字符串和偏移。
省略号、跨段拼接、表格重排和改写仍会被拒绝。v2 模型响应缓存与旧策略分开，原始响应与所有拒绝理由继续保留。

## 3. 先跑两题联调

```bash
bash scripts/run_rp3_experiments.sh teacher-smoke
```

只写 `.tmp/rp3_smoke/limit_2/`。若 BGE 索引缺失则建立；若已存在则只读加载，不覆盖。
每题要求新检索的 K≤3 ID 顺序与冻结 RP2 replay 一致；不同则立即停止。
不会把两题联调输出冻结成正式 40 题实验。

## 4. 核心流程与当前进度

截至2026-09-17，服务器已经完成teacher、MP008、features、基线train/route/export/quantize，
以及第5节增强组的augment/train/route/export/quantize。
两组MP008校准都失败关闭，均没有部署校准证书；这是需要保留的实验结果，
不能删除报告或降低门槛伪造成功。不要再次运行 `all` 或已完成阶段。

以下仅供全新环境首次复现使用。

建议在 `tmux` 或其他持久终端中执行：

```bash
tmux new -s rp3
mkdir -p logs
bash scripts/run_rp3_experiments.sh all 2>&1 | tee logs/rp3_core_20260906.log
```

或按下表分阶段运行 `bash scripts/run_rp3_experiments.sh 阶段名`：

| 阶段 | 实际工作 | 主要产物 |
|---|---|---|
| teacher | 208 图索引/精确 K3 重放；完整实际候选打分轨迹；原 K3 两阶段核验；尾候选辅助支持标签；最终冻结 | `teacher_traces/strict208_base_top32/`、主 trace/memory bundle、teacher freeze |
| mp008 | 7B 从 MP008 原页面抽取逐字证据跨度绑定的校准候选；独立重放冻结核验策略 | MP008 原始响应、拒绝原因、独立开发 trace/memory |
| features | 训练和 MP008 分开导出确定性哈希特征 | `features/*_features.json` |
| train | 构建集 train 更新参数，组隔离 validation 早停；MP008 只登记哈希 | `lec_v1/bootstrap/` |
| route | 固定非路由模块，观察当前学生与冻结教师的差异，只训练 route head | `lec_v1/routed/route_rollouts.jsonl`、新 checkpoint |
| export | 导出 FP32 ONNX 和独立 MP008 代表性输入 | `lec_v1/onnx/` |
| quantize | 真正执行静态 INT8 QDQ，检查实际 INT8 权重及输出数值 | `controller.int8.onnx`、量化清单 |
| calibrate | 在量化后的 MP008 输出上联合选择 support/route 阈值 | `calibration_manifest.json` |
| diagnose | 不读取开发/外部样本，诊断现有FP32/INT8各头、路由策略和服务器CPU控制器时延；不可部署 | `diagnostics_v1/` |
| evaluate | 冻结阈值后报告构建集 validation 的教师一致性和 ORT 耗时 | `lec_v1/evaluation/` |

上述路径省略前缀：实验为 `results/experiments/research_point_3/`，bundle 为
`data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/`。

教师生成和 MP008 提取保留模型响应缓存，可重新执行同阶段续跑；缓存身份不匹配时拒绝复用。
训练、量化、校准输出不静默覆盖。需要重跑学生时使用新的 `RP3_RUN_DIR`，不要删除教师缓存：

```bash
export RP3_RUN_DIR=results/experiments/research_point_3/lec_repeat2
bash scripts/run_rp3_experiments.sh train
bash scripts/run_rp3_experiments.sh route
bash scripts/run_rp3_experiments.sh export
bash scripts/run_rp3_experiments.sh quantize
bash scripts/run_rp3_experiments.sh calibrate
bash scripts/run_rp3_experiments.sh evaluate
```

如果校准找不到满足默认“至少 5 个接受答案、教师集合不一致率≤0.1”的工作点，脚本停止，不生成可部署校准证书。
这不是软件报错就可以删除的限制：应检查样本覆盖、学生质量与校准集规模，记录失败。
该阈值只是预设经验工作点，不是工程安全保证，也没有有限样本统计风险保证。

## 5. 证据集合干预实验（独立增强组）

本节已完成，以下命令仅供新环境复现。当前服务器保留165条轨迹（40原始+125派生；129 train/36 validation），
`lec_augmented_v1` 已量化但校准失败，未执行evaluate。原始查询非空集合一致成功数为train 3/32、validation 0/8。
MP008原始路由40条全部为abstain；仅有3条教师非空回答还使预设最低5个答案/不一致率≤10%的门槛不可行。
下一实验不能通过放宽门槛或改变既有增强配置伪装成功，须另立协议和输出目录。

首次复现时先完成正式 teacher 冻结，再执行：

```bash
bash scripts/run_rp3_experiments.sh augment
```

派生样本继承原始故障场景的 train/validation 分组。干预包括移除全部证据、逐条移除已选证据、
移除首条未选证据；重新执行原 RP2 来源约束选择和真实 7B 核验，不直接复制受影响的标签。
尾部未重新选入 K3 的支持标签仍为原查询—单证据辅助标签，这不等于整图重检索干预。

增强配置已固定为 `configs/research_point_3/lec_train_augmented_v1.json`，除预先声明的构建集干预输入外，
模型、训练超参数和 MP008 边界与基线完全相同。使用独立结果目录执行：

```bash
export RP3_CONFIG=configs/research_point_3/lec_train_augmented_v1.json
export RP3_RUN_DIR=results/experiments/research_point_3/lec_augmented_v1
bash scripts/run_rp3_experiments.sh train
bash scripts/run_rp3_experiments.sh route
bash scripts/run_rp3_experiments.sh export
bash scripts/run_rp3_experiments.sh quantize
bash scripts/run_rp3_experiments.sh calibrate && \
  bash scripts/run_rp3_experiments.sh evaluate
```

原 40 题冻结 bundle 和主图不变。派生数量不能当作新增独立故障案例数量。

## 6. 边缘工具调用

```bash
python scripts/run_rp3_tool.py \
  --memory data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/evidence_memory/training \
  --traces data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/training \
  --export-dir results/experiments/research_point_3/lec_v1/onnx
```

标准输入每行一个 JSON 请求，字段以 `select_pump_evidence_tool_schema()` 为准。
故障 ID、诊断角色从冻结查询元数据中取实际值；不要凭空填写未知故障。
该命令不加载 LLM：执行哈希编码 → LEC → ID 证据恢复 → 确定性建议卡。
默认未连接教师服务，fallback 请求降为 abstain；它不会假装已经调用服务器 7B。
工具函数具备三动作协议，但自动调用远端教师的传输/服务层仍需部署时接入。

## 7. 不能提前宣布完成的实验

- `evaluate` 当前是参与过模型选择的构建集 validation 检查，不是独立泛化成绩。
- 正式外部评价 MP009–MP013、620/1326 层迁移、语义改写/干扰扩充、系统消融矩阵仍需另行执行与审核。
- 默认 route 拟合是固定学生输出对冻结教师结果的效用学习，不是多轮 DAgger，也不把教师一致性叫作诊断准确率。
- 默认成本 1/8/12/50 是申明的无量纲效用；实测时延、能耗和成本敏感性分析是后续实验。
- ONNX 计时仅统计 ORT 控制器；完整边缘实验还要计入编码、证据访问、渲染、LLM 壳、网络/回退。
- RTX 5880 上的实验不能替代 Jetson 等目标边缘硬件的实际内存、功耗、热稳态测量。
- MP008 自动抽取候选只通过跨度/模式检查，不是 RP1 新的证据合格记录，不进入主图或梯度数据。

## 8. 已完成的离线诊断和逐头消融

`diagnose`不需要部署证书，但不会生成证书，也不绕过`evaluate`。读取现有模型，不重训。
B0/M0已经各运行一次，报告为`lec_v1/diagnostics_v1/`、`lec_augmented_v1/diagnostics_v1/`，
统一比较为`results/experiments/research_point_3/diagnostic_comparison_v1/`。
执行及指标口径见[`RP3_DIAGNOSTICS_V1.md`](RP3_DIAGNOSTICS_V1.md)。同目录再次运行会拒绝覆盖。

三种子逐头消融的已执行命令为：

```bash
.venv/bin/python -u scripts/run_rp3_head_ablations.py
```

协议为`configs/research_point_3/head_ablation_v1.json`，完整说明见
[`RP3_HEAD_ABLATION_V1_PROTOCOL.md`](RP3_HEAD_ABLATION_V1_PROTOCOL.md)。输出为
`results/experiments/research_point_3/head_ablation_v1/`，包含9次独立bootstrap、3次Route拟合、12份checkpoint诊断及统一JSON/CSV/Markdown。
A4复用同种子A3 bootstrap，不重复训练。三个种子的全部非Route权重和指针均经校验不变。
该命令本机已完成，不应再次运行；新假设须用新协议和目录。没有重新运行teacher、MP008、features、B0或M0。

A3/A4三个种子原始validation非空成功均为0/8。所有消融只用build-train/validation，未附加MP008。
尚未完成去可用性观测/去派生监督、外部评价及目标硬件实验；E1特征对照已于后续完成但总体失败，不能把当前诊断说成完整论文实验或已部署系统。

## 9. 已完成的字段监督审计与归一化对照

执行前固定协议为[`RP3_FIELD_NORMALIZATION_V1_PROTOCOL.md`](RP3_FIELD_NORMALIZATION_V1_PROTOCOL.md)，
配置为`configs/research_point_3/field_normalization_v1.json`。
以下入口已执行完成，仅供审查或新环境复现；现有结果目录不允许覆盖：

```bash
.venv/bin/python scripts/audit_rp3_field_supervision.py
.venv/bin/python scripts/run_rp3_field_normalization.py
```

输出分别位于`field_supervision_audit_v1/`和`field_normalization_v1/`（RP3结果根目录下）。
后者含执行前协议/源码快照、全部三种子配置、控制引用哈希、新臂训练历史/最佳模型、逐行预测及JSON/CSV/Markdown。
C0引用旧A3，不重训；C1仅将请求/非请求两组字段CE由0.25/0.75改为0.5/0.5，保持教师、数据和其他训练设置不变。

原始validation场景宏三种子均值：raw非空目标零预测91.67%→37.50%，raw请求基数准确率16.67%→37.50%，
Pointer F1 0.0556→0.3472。7042027完整validation教师空集误填由0/12升至3/12，故预声明整体改善规则失败。
最佳epoch为2/1/1，后期任务指标仅诊断，不用于事后换checkpoint。114项RP3测试通过，1160个原研究文件原样保留。
本轮没有MP008输入、Route拟合、导出/量化或校准，不生成部署证书。

## 10. 已完成的联合证据契约实验

执行前协议：[`RP3_JOINT_CONTRACT_V1_PROTOCOL.md`](RP3_JOINT_CONTRACT_V1_PROTOCOL.md)；
理论说明：[`research/RP3_JOINT_CONTRACT_METHOD.md`](research/RP3_JOINT_CONTRACT_METHOD.md)。
以下命令已经执行，现有输出目录拒绝覆盖，不要再训练这些臂：

```bash
.venv/bin/python scripts/audit_rp3_joint_gating.py
.venv/bin/python -u scripts/run_rp3_joint_contract.py
.venv/bin/python scripts/verify_rp3_joint_contract.py \
  --inventory logs/rp3_joint_contract_before_20260917T060325Z/asset_hashes.json
```

`joint_gating_audit_v1`保存只读错误定位；oracle标签替换不是方法成绩。
`joint_contract_v1`保存C0模型引用、W1/J1各三种子的独立配置/模型/日志、执行前快照、汇总与校验。
C0复用上一轮模型；W1增加困难空集支持监督；J1仅在W1上增加跨头概率契约正则。
两臂最佳epoch均1/1/2，完整validation空集误填每种子0/12，但原始validation F1均值由0.3472降到0.0750。
J1只比W1改善概率违约质量及raw数量指标，validation最终选集完全相同；两者均不可替换既有模型。
123项测试通过，目标函数重建误差<2e-7，1265个既有研究和日志文件保持原样。
没有读取MP008/外部数据，也没有Route拟合、量化、阈值校准或部署；不以当前负结果开启外部集调参。

## 11. 已完成的支持审计与正支持更新保护

协议：[`RP3_POSITIVE_GUARD_V1_PROTOCOL.md`](RP3_POSITIVE_GUARD_V1_PROTOCOL.md)。
以下命令已完成；审计、训练和核验均拒绝覆盖既有产物，不再执行：

```bash
.venv/bin/python scripts/audit_rp3_support_separability.py
.venv/bin/python -u scripts/run_rp3_positive_guard.py
.venv/bin/python scripts/verify_rp3_positive_guard.py \
  --inventory logs/rp3_support_audit_before_20260917T070955Z/asset_hashes.json
```

`support_separability_v1`保留输入冲突、候选分数和全train局部梯度；未改教师标签。
`positive_guard_v1`复用C0/W1，新增三个G1及全部预冻结配置/源码、预测、历史、校验报告。
G1保护包含AdamW动量、预条件和weight decay后的实际参数位移，全train正支持损失下降才接受。
原始validation F1均值0.1972，高于W1的0.0750但低于C0的0.3472；完整validation误填仍每种子0/12。
正支持召回100%同时负支持15/15过门；不推广G1，不降低门槛或按后期指标换checkpoint。
三个最佳epoch均1，129项测试与独立训练核验通过，1331个既有研究文件/日志原样保留。
后续候选集合上下文对照也已执行，见第12节；排序目标/模型选择和语义特征继续分开研究。
本轮未读取MP008/外部数据，没有新的量化、阈值校准或部署证书。

## 12. 已完成的集合上下文控制与研究范围评审

执行前协议：[`RP3_SET_CONTEXT_V1_PROTOCOL.md`](RP3_SET_CONTEXT_V1_PROTOCOL.md)。以下入口已经完成，不再执行：

```bash
.venv/bin/python -u scripts/run_rp3_set_context.py
.venv/bin/python scripts/verify_rp3_set_context.py \
  --inventory logs/rp3_set_context_before_20260917T122236Z/asset_hashes.json
.venv/bin/python scripts/audit_rp3_scope_feasibility.py
```

S0为同容量单候选控制，S1读取可用集合均值/数量，均1,409,222参数，C0复用不重训。
六次新训练最佳epoch均2/1/1，全部validation选集与C0逐条相同，原始F1均值0.3472。
S1负支持误接受场景宏均值由0.6333升到0.6500，两项预定比较失败；不调参追加运行。
独立机制检查证明上下文路径生效，但未改善任务质量。
137项测试通过，六次训练目标重建误差<2.44e-7，1388个旧研究/日志文件保持原样。

理想路由审计`scope_feasibility_v1`只使用保存预测，未训练策略或拟合阈值。
原始validation为7条教师非空任务，C0/S1本地精确2/2/0条；即使oracle也至少回退5/5/7次才能完整服务。
当时据此预注册E1特征可行性对照；该步骤现已完成但未通过门槛，见下一节。具体收窄范围见
[`research/RP3_SCOPE_REASSESSMENT_20260917.md`](research/RP3_SCOPE_REASSESSMENT_20260917.md)。
本轮不改MP008校准门槛、不读取外部集，不把范围调整写成已验证创新或部署完成。

## 13. 已完成的E1语义特征可行性对照

协议：[`RP3_SEMANTIC_V1_PROTOCOL.md`](RP3_SEMANTIC_V1_PROTOCOL.md)；
结果：[`RP3_SEMANTIC_V1_RESULTS_20260918.md`](RP3_SEMANTIC_V1_RESULTS_20260918.md)。
以下命令已执行，输出拒绝覆盖；不要重新训练或重新生成已完成特征：

```bash
.venv/bin/python -u scripts/run_rp3_semantic.py
.venv/bin/python scripts/verify_rp3_semantic.py \
  --inventory logs/rp3_semantic_before_20260917T125834Z/asset_hashes.json
.venv/bin/python scripts/summarize_rp3_semantic.py
```

`semantic_v1`保存C0只读引用、H512/E1各三个新模型、独立特征、执行前快照、逐条预测与组件计时。
另已逐臂执行`audit_rp3_semantic_memory.py --arm C0|H512|E1`，保留原峰值读数并补充`/proc`进程内存。
主日志`logs/rp3_semantic_v1_20260918.log`；独立核验通过日志`logs/rp3_semantic_verification_retry1_20260918.log`。
首次核验因旧清单缺省字段兼容而停止，原失败日志也保留；没有重训。

C0/H512/E1原始validation F1均值为0.3472/0.2819/0.2792。
E1种子7042027空集误填4/12高于C0的3/12；正确非空提案2/1/0未超过C0的2/2/0。
E1共25,411,621参数，含查询编码的服务器CPU组件时延82.342 ms，C0为4.812 ms。
141项测试及独立目标/早停/输入核验通过，1457个旧研究/日志文件原样保留。
按预设停止本轮encoder搜索；先评审任务、监督、独立组数及论文贡献，不直接训练新路由。
没有新增量化、MP008校准、外部评价或部署，旧校准不可行事实不变。

静态 QDQ 与量化后精度回归的接口依据：[ONNX Runtime 量化文档](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)。
