# Research Point 3: Lightweight Evidence Controller

> 2026-09-06 implementation update: see `docs/RP3_SERVER_EXPERIMENT_GUIDE.md`
> and `docs/RP3_COMPLETION_AUDIT_20260906.md`. Actual RP2 pools contain 0–26
> candidates; 32 is the tensor capacity, not a mandatory evidence count.
> The runnable baseline now includes teacher replay, MP008 preparation, CPU
> hashing features, fixed-student route fitting, INT8 quantization and threshold
> fitting. Historical “top-32” below means the complete bounded pool. Real model
> experiments and target-hardware measurements are not completed by code generation.

## Training and calibration split contract

- Build-set `train` traces are the only rows that may contribute gradients.
- Group-disjoint build-set `validation` traces are used for early stopping and
  model selection.
- MP008 is loaded through a separate `development` trace, memory, and explicit
  feature bundle. It is reserved for answer/abstain thresholds, cost-sensitive
  routing, and post-quantization recalibration. It is never used for gradients,
  early stopping, or model selection.
- A training manifest records the attached MP008 hashes and leaves all calibration
  metrics and artifacts as `pending_not_run`; merely attaching MP008 is not a
  calibration result.

## Four-head online contract

`ControllerPrediction` is the backend-neutral boundary used by rule, PyTorch,
and ONNX Runtime adapters.  It contains exactly four kinds of output:

1. one rank/support/selected decision per candidate ID;
2. exactly one `(state, cardinality)` prediction for each of the four frozen
   card slots;
3. the LEC three-action `answer | fallback | abstain` decision;
4. the calibrated confidence of that selected route action.

The runtime validates that selected pointers are available, directly supported,
within budget, and assigned to a concrete card role.  Context evidence remains
addressable but cannot be selected into a diagnosis card.  Per-role selected
counts must equal the field head's cardinalities.  A cardinality of zero is the
field head's STOP/active-underfill decision; the deterministic renderer must not
fill that slot merely because more evidence is available.

The route head is authoritative.  Runtime evidence, safety, availability, route-
confidence, and deployment-cost guards may only downgrade `answer -> fallback ->
abstain`; they can never upgrade an LEC `fallback` or `abstain` into `answer`.
`ControllerPrediction.from_decoded(...)` is the intended ONNX adapter bridge:
numeric tensors are decoded into this symbolic contract before entering the
tool boundary.

## ONNX runtime and public tool boundary

`OnnxEvidenceController` loads an ONNX model only when its exact byte hash,
query/evidence dimensions, fixed candidate width, four output heads, teacher
graph, compact memory, feature encoder, and controller version all match.  Its
support and route thresholds are read exclusively from a post-quantization
calibration manifest bound to MP008 and to the quantized model hash.  Runtime
callers cannot pass replacement thresholds.  Text embedding is outside this
adapter: a `FeatureProvider` supplies vectors and declares the same frozen
encoder identity. The executable baseline computes deterministic CPU hash
features for new questions; evidence features can be precomputed.

The public `select_pump_evidence` facade accepts only the question, known fault,
diagnostic role, scenario, optional `max_points`, and an optional subset of
currently available evidence IDs.  A server-owned frozen fault-by-role bucket
registry injects candidate order, availability mask, memory identity, graph
identity, and hashes into the low-level audit request.  This prevents an LLM
caller from inventing artifact hashes or triggering online full-memory ANN/graph
search.  `select_pump_evidence_audit_schema()` remains available for deterministic
replay and audit, not as the LLM-facing schema.

## TeacherTrace bundle bridge

`scripts/export_rp3_teacher_traces.py` is the fail-closed bridge from the full
top-32 RP2 candidate export to the final trainable bundle. It requires the
teacher-system and candidate-trace gates to pass, then writes 40 original
single-role traces plus the strict-208 ID-addressed memory. Every manifest binds
the immutable graph identity, teacher-system identity, RP2 replay, candidate data
hash, and candidate-manifest hash. Bootstrap rows have explicitly unlabelled
zero cost placeholders and all route losses are masked. The subsequent fixed-
student rollout stage fits the route head with declared dimensionless utilities,
not measured latency or diagnostic-error costs. For `fallback` and `abstain`, ranking/support decisions remain
available as supervision but the rendered local card is fact-free.

The default split is explicitly
`fixed_memory_query_generalization`: all four roles for the same fault scenario
stay together, while the strict-208 memory is shared. Candidate evidence IDs are
not split keys because overlapping top-32 lists would collapse all 40 queries into
one giant component. This estimates new-query behavior over a fixed local memory,
not unseen-document generalization. A genuine inductive claim requires holding
out documents/source families before rebuilding retrieval candidates and local
memory, then using the stricter grouped split.

The trainable card has exactly four evidence-backed slots: symptom,
cause/mechanism, inspection, and maintenance. `safety_warning` remains a reserved
enum only. RP2 v6 supplies no safety labels, so static system safety boundaries
must not be presented as distilled diagnostic facts.

研究点三正式定位为：**面向边缘端泵系故障辅助诊断的证据控制策略蒸馏与选择性回退方法**。

## 用一句话说明

训练一个可由LLM或确定性编排器调用的轻量证据控制器（Lightweight Evidence Controller，LEC）：

```text
问题 + 已知故障范围 + 诊断角色 + 本地候选可用性
→ LEC选择证据ID、判断直接支持、主动欠填并决定路由
→ 只读证据记忆按ID恢复原文与来源
→ 确定性组合证据辅助卡
→ 可选3B LLM只负责工具调用与不增事实的语言表达
```

研究点三不重新做故障识别，也不训练小模型背诵图谱或教师答案。它继承研究点二的输入边界：故障范围和诊断角色是已知结构化输入。研究对象是如何把研究点二教师系统的证据决策压缩成小型、可量化、可校准和可回退的工具。

## 教师与学生

教师是研究点二完整系统，而不是单个7B模型：BGE-M3宽召回、一跳候选信号、预算选择、7B两阶段二值支持核验、主动欠填/拒答和确定性渲染。

学生主体是目标参数量小于50M的四头LEC：

1. Rank/Pointer头蒸馏候选排序并输出证据ID；
2. Support头蒸馏最终二值直接支持掩码；
3. Field/Underfill头预测字段状态、0到K有效基数和STOP；
4. Route头选择 `answer / fallback / abstain`，并计入错误、时延、能耗和教师调用成本。

Qwen2.5-3B INT4只是可选边缘对话壳，不是主蒸馏对象。权威卡片由规则组合器生成；LLM不得新增证据包之外的原子诊断主张。

## 主教师冻结边界

- `TeacherGraph_RP3_v1` 必须绑定研究点二v6真实使用的严格208条证据、203项Claim和281个实体；
- 620条和1326条层仅在主模型、阈值和路由冻结后做 `TierShift-620` / `TierShift-1326` 压力测试，不能替换主教师；
- 当前配置所声明的BGE索引目录在本机缺失，因此冻结入口必须失败关闭。当前可以生成代码与清单，不能声称教师索引已重建或精确重放完成；
- MP008只用于支持/路由阈值与量化后校准，不参与梯度、早停或模型选择；构建集内部组隔离validation用于早停和模型选择；MP009–MP013只用于最终外部评价；MP014排除。

## 在线证据工具

核心工具接口为：

```text
select_pump_evidence(question, fault_id, role, available_evidence_ids?, max_points<=3)
  -> selected_evidence_ids
  -> controller_rank + support_probability + support_verdict
  -> field_state
  -> stop_reason
  -> action: answer | fallback | abstain
  -> controller_version + memory_hash
```

以上为LLM/编排器看到的高层接口。候选ID、可用性掩码、候选签名以及模型、记忆与校准哈希均由服务端冻结注册表注入，不能交给LLM伪造；包含这些字段的底层请求仅用于重放和审计。Route头在线执行的是经实际教师纠错收益和动作代价监督的三分类策略，期望代价计算属于离线路由标签与后悔评价，运行时防护只能把动作推向更保守的方向。

本地证据记忆按 `fault_id × role` 分桶。LEC不在线运行BGE-M3、不做ANN全库搜索和大图遍历，但会按ID恢复原文、页码、URL、哈希和可用的定位信息，所以应称“有界本地证据访问”，不能称为完全免检索。当前strict208源记录均没有bbox；代码保留字符偏移并显式标记bbox缺失，论文不得声称208条已完整保留bbox。

## 诊断辅助卡边界

冻结卡严格与RP2 v6的四类教师查询对齐：症状、可能原因/机理、检查和维护，并附限制/冲突、证据来源和路由结果。每个原子项必须绑定合法证据ID和Claim ID。RP2没有独立的安全警示教师查询或正例，因此安全警示不得伪装为第五个蒸馏字段；只能作为系统静态使用边界，或在未来新增独立安全教师资产后另行研究。该卡仍是“已知故障范围下的证据建议卡”，不是开放式故障识别结论。

## 代码分层

```text
contracts.py       类型、轨迹、卡片、证据和路由契约
artifacts.py       不可变JSON/JSONL、哈希与bundle校验
splits.py          Claim/文档/来源族/场景组级防泄漏切分
teacher_freeze.py  208教师图、索引和重放清单的失败关闭校验
trace_export.py    RP2教师结果到top-32蒸馏轨迹的适配
evidence_memory.py 有界只读证据记忆编译
interventions.py   证据集合干预、学生rollout与教师纠错重放请求
dataset.py         显式特征、冻结轨迹与防泄漏切分的张量化
model.py           四头LEC
losses.py          排序、支持、欠填、路由、干预与校准损失
training.py        确定性训练、早停、checkpoint与运行清单
decoding.py        可用掩码约束与安全指针解码
routing.py         代价敏感三动作路由
renderer.py        不增事实的确定性卡片组合
evaluation.py      蒸馏、契约、选择性风险和系统指标
onnx_export.py     动态batch/固定候选宽度ONNX与INT8校准输入
calibration.py     MP008量化后阈值及模型/记忆/特征身份冻结
onnx_runtime.py    绑定模型/特征/MP008校准哈希的ONNX Runtime控制器
tool_api.py        冻结分桶注册表、高层LLM外观与底层审计协议
```

## 实施门槛

1. G0：完成schema、配置、静态代码和失败关闭校验；
2. G1：在有模型机器上重建208图BGE索引并精确重放RP2；
3. G2：冻结卡片和工具契约；
4. G3：导出top-32教师轨迹，先分组再生成改写/干预；
5. G4：训练四头LEC；
6. G5：学生rollout、教师纠错和价值路由校准；
7. G6：ONNX/INT8导出并重新校准阈值；
8. G7：208内部、620/1326层迁移及MP009–MP013外部评价；
9. G8：在Jetson Orin Nano或Orin NX测量时延、内存、能耗与热稳态。

当前机器不具备LLM运行条件，因此本阶段只生码、写配置与契约，不下载模型、不运行教师或学生模型。

## 有模型机器上的顺序

1. 重建冻结BGE索引，精确重放RP2，并导出40×top-32完整候选决策；
2. 用 `export_rp3_teacher_traces.py` 生成40条训练TeacherTrace和strict-208只读记忆，再用 `freeze_rp3_teacher_graph.py` 完成三重终审；
3. 导出显式查询/候选特征，运行 `train_rp3_lec.py`；
4. 用 `export_rp3_onnx.py` 导出ONNX与MP008量化校准输入，在量化完成后拟合阈值，并用 `freeze_rp3_calibration.py` 冻结校准身份；
5. `OnnxEvidenceController + FrozenCandidateBucketRegistry + SelectPumpEvidenceFacade` 组成面向LLM/编排器的边缘调用链。
