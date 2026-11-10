# RP1 下一轮受控验证：服务器接续说明

日期：2026-11-10。

## 1. 当前状态，先不要混淆两轮工作

**上一轮六项离线核查已经完成；用户截图中的下一轮模型验证尚未执行。** 不能把已保存的离线回放、17个AI初审靶点或159项单元测试写成四组模型对照结果。

上一轮核心提交为 `cbf0119e`，输入版本锁定为 `bd1e7c60972bbc5f34e408cd69f542b10a4ad566`。后续同步提交补齐此前本地的审计记录及本接续文件，不改变冻结的原始候选、图谱、论文或教师。

本机没有模型权重、torch或可用模型API环境变量；已配置的实验服务器SSH连接未成功。因此没有启动新模型请求，也没有选定四组实验的最终模型、token预算或阈值。服务器此前的7B模型是可检查的执行资源，不等于该实验已经完成。

## 2. 六项任务的真实进度

| 下一轮任务 | 状态 | 服务器上需要完成的工作 |
| --- | --- | --- |
| 明确17个靶点的任务范围 | 待完成 | 逐条给出适用范围、必保留原子关系及条件/时序/极性/替代或联合分支；先处理T01、T02的范围/Schema边界 |
| 检查完整原始输入与输出 | 待完成 | 查实际提示、源文输入、主候选、辅助/未决项、截断和结束元数据及后处理；不得只搜索8007条主候选 |
| 冻结四组通用方法对照 | 待完成 | 输出明确的方法定义和冻结配置；统一模型、页面、Schema、总token预算、候选上限、重试规则与评价接口 |
| 执行同预算模型实验 | 未开始 | 保存真实请求/响应、模型版本、种子、token使用和失败；重复运行检查稳定性，不利用靶点答案修改提示 |
| 建立独立小样本评价 | 评价方式已确认，尚未执行 | 用户已选择另一个独立评审模型；生成少量新样本及盲评包，实施AI交叉评价，不称人工或专家Gold |
| 算法立项或终止决策 | 尚不能判定 | 基于前述真实对照和独立评价决定；通用方法已解决则不新增RP1专门机制 |

这里的“待完成”不是负结果。现阶段只能说专门算法必要性未证，不能声称某个算法已被实验否定。

## 3. 必读资料和数据入口

按以下顺序读取，避免将历史版本描述当作当前状态：

1. `docs/research/RP1_SIX_CHECKS_REPORT_20261110.md`：上一轮最终结论，包括修复、图谱分层、残留错误和下一道验证门槛。
2. `results/experiments/research_point_1/six_checks_final_v1_20261110/completion_summary.json`、`completion_seal.json`、`verification.json`：汇总和版本哈希。
3. 同目录的 `frequency/representation_targets.jsonl`、`page_reviews.jsonl`、`source_sample.jsonl`：17个源文靶点、30页取样及原生页面。
4. 同目录的 `frequency/representation_candidates.jsonl`、`native_baseline_replays.jsonl`、`representation_judgments.json`：现有候选、规则回放及AI判断；它们不是新模型响应或独立参考。
5. `configs/research/rp1_six_checks_source_review_v1.json` 与 `rp1_six_checks_representation_judgments_v1.json`：保留字面完整/部分/主候选缺失的定义；仅作开发性证据，不作为盲测标签。
6. `docs/research/RP1_A3_OMISSION_AUDIT_PROTOCOL_20261110.md` 和 `RP1_P0_P1_SAME_INPUT_AUDIT_20261110.md`：更早的候选遗漏及同输入回放审计。它们的样本/候选ID与本轮17个靶点不同，不能直接套用结论。

此前本地、现随代码同步的研究记录包括：

- `results/experiments/research_point_1/controlled_validation_v1_20261109/`：受控源文标注材料；人类标注尚未提供，不要自动填成AI标签后称作人工真值。
- `results/experiments/research_point_1/a3_omission_audit_v1_20261110/`：24页源文AI审计及逐条判断。
- `results/experiments/research_point_1/p0_p1_same_input_audit_v1_20261110/`：历史候选/当前流程回放与错误血缘。
- `results/experiments/research_point_1/six_checks_final_v1_20261110/`：上一轮正式六项核查；本地旧试算目录不作为最终结果，也没有上传为另一套“正式结果”。

## 4. 模型实验开始前的约束

本轮不是立即重构整个项目。先闭合原始输入/输出证据，排除范围外内容、接口损失和辅助字段已生成的关系，再冻结四组通用方法。

“主候选缓存未见”不等于“LLM完整输出未生成”；“独立字段缺失”不等于“证据中的条件已经丢失”。必须分别检查原子关系保留和复杂语义绑定。缺失或截断的原始资产应明确列出，不允许补造历史请求或用后来重构的提示冒充当时的实际输入。

使用服务器7B时，四组新方法应共用同一个明确模型版本。历史Qwen3.7-max输出只能作历史诊断，不能与新7B输出直接形成“同模型方法改进”的因果结论。模型是否支持当地语言、上下文长度与结构化输出都须先检查，不因已有权重就省略预检。

总token预算应同时计算所有阶段的输入、输出和重试；二次读源文也计入。不能给恢复组额外源文访问和额外请求，再把提升归功于算法。应在看新结果前冻结候选上限、去重规则、随机种子/重复数及异常处理。若统一模型或独立评价资源缺失，记录未完成原因，不降低质量门槛，也不伪造数值。

30页与17个靶点已经被开发性审阅过，不是独立外测。独立小样本应另行固定，不用这17项同时调提示和报告独立泛化。MP008及MP009–MP014不进入本轮调试/模型设计；继续沿用构建语料边界，不向外部评估集借样本。

用户已明确选择**另一个独立评审模型，仅作AI交叉评价**。评审模型应记录实际模型/版本及推理配置，不能将同一模型换一个提示或同一位助手复判冒充独立模型。给评审者提供必要源文、任务定义及匿名候选，隐藏方法名、旧AI判断、期望答案和本轮靶点命中结果；随机化呈现次序并封存映射。记录分歧、无法判定和证据地址，不以多模型一致代替事实真值。评审者不可参与方法调参或回填标准答案；若服务器只有一个模型入口，先解决独立评审资源，不将同模型自评包装成独立评价。

本轮不得替换strict208冻结教师，也不得将1326/1456图的规模差直接解释为RP2或RP3效果提升。已经披露的两条历史语义误放仍保留；不能通过删除坏例来美化评价。

## 5. 安全拉取和本地检查

在服务器项目目录先查看状态，再快进拉取：

```bash
cd ~/08-zxk/Fault_LLM_V2
git status --short
git pull --ff-only origin main
```

如果服务器有本地提交、修改或文件冲突，先保留这些工作再处理，不使用 `reset --hard`、`git clean` 或覆盖实验目录的方式强制同步。不要删除教师缓存、检查点、模型、ONNX、校准报告或日志。

在服务器现有可用Python环境中运行核心审计工具测试：

```bash
PYTHONUTF8=1 PYTHONPATH=.:src:scripts python -m pytest tests/unit/test_rp1_native_evidence_binding_v2.py tests/unit/test_rp1_six_checks.py tests/unit/test_rp1_layout_direction_context_v1.py tests/unit/test_rp1_native_fragment_completion_v1.py tests/unit/test_rp1_native_evidence_selection.py tests/unit/test_rp1_clause_binding_v1.py tests/unit/test_rp1_batch_evidence_repair_v1.py tests/unit/test_rp1_automatic_contract_v4_1.py tests/unit/test_rp1_automatic_contract_v4.py -q
```

这组此前本地通过118项。同步整理后，连同另三份旧审计测试，在同一工作树下重新验证共159项通过；这是本地测试结果，不是已在服务器运行。需要时可在上述测试列表中追加 `tests/unit/test_rp1_a3_omission_audit.py tests/unit/test_rp1_p0_p1_replay.py tests/unit/test_rp1_controlled_validation.py`。

不要直接重跑旧P0/P1回放并覆盖归档。其脚本优先使用 `.tmp/main-review-20261109` 历史工作树，不存在时会回退到当前检出目录；而当前代码已修复引句接口，不再与旧审计的“当时当前版本”完全相同。若需要重现旧回放，应先恢复锁定提交的只读代码环境，并指定新的输出位置，不为了复现改变旧结果。

以下命令只复算**上一轮离线审计**，不运行7B，也不执行本轮四组模型实验。换平台时用新输出目录，保留已上传的Windows来源哈希与原结果：

```bash
python scripts/run_rp1_six_checks.py all --out results/experiments/research_point_1/six_checks_replay_server_20261110
```

本轮四组模型执行器和冻结配置尚未生成，因此当前没有可据实提供的“运行四组实验”命令；请勿把上面这条复算命令当作模型实验。先在服务器完成第1–3项并实现/测试执行器，再启动第4项。

## 6. 可直接交给服务器对话的接续请求

> 请先读取AGENTS.md及 `docs/research/RP1_ROUND2_SERVER_HANDOFF_20261110.md`，继续完成RP1下一轮受控验证。不要重做已经完成的六项离线审计，不要把17个AI初审靶点当成Gold，也不要立即重构图谱。先核定靶点范围和完整原始输入输出，再冻结四组同模型、同预算通用对照并实现执行器，随后运行重复实验和独立小样本评价，最后据结果作算法立项或终止判断。独立评价按用户已确认的方式：使用另一个独立评审模型，仅作AI交叉评价，隐藏方法身份和既有AI答案。服务器已有7B权重，请先核验实际模型及可用运行环境。冻结图谱、RP2/RP3教师和既有实验结果只读；缺少历史资产或独立评审资源时明确报告，不造数据、不降低门槛。
