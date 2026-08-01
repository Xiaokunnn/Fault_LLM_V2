# 船舶机舱泵系能力问题 CQ v1 冻结与评价规程

## 1. 目的与边界

`marine_pump_cq_v1@1.0.1` 将研究点一的“图谱规模”评价转化为“图谱能够支持哪些可追溯诊断问题”的结构评价。它冻结：

- 10类泵系故障；
- 症状、原因或机理、检查、维护4种证据角色；
- 40个“故障类别 × 证据角色”任务单元；
- 每种角色可使用的实体类型、关系方向和合法元路径；
- 3个Claim—EvidenceAssertion—来源谱系追溯CQ；
- 构建集、开发集和保留测试集的隔离政策。

本规程评价的是**可追溯结构可回答率**，不是答案准确率、诊断准确率或工程有效性。所有参与评价的自动生成记录仍为Silver，不得称为Gold；当前也没有人工专家审核。

CQ v1是在当前图谱构建完成之后、**正式对照实验、消融实验和保留测试之前冻结**。因此，当前构建集上的34/40结果属于冻结时的结构描述性基线，不能倒写成在图谱构建前完成的预注册结果；冻结后不得根据正式对照实验或MP009–MP013的结果修改CQ、元路径和门控。

冻结配置为：

```text
configs/competency_questions_marine_pump_v1.json
```

当前冻结文件SHA-256为：

```text
9d00fffa69022a99f9f92fd32cb0bb7c129966f923048973aece627578ee8de7
```

后续如果修改故障类别、角色、元路径、划分或门控条件，必须发布新的CQ版本，不能覆盖v1并继续引用该哈希。

## 2. CQ结构

### 2.1 四种任务角色

| 角色 | 自然语言任务 | 冻结合法关系 |
|---|---|---|
| 症状 | 某故障有哪些故障表现、症状或信号特征？ | `manifests_as`、反向解释的`indicates` |
| 原因或机理 | 哪些原因、机理或工况与某故障形成可追溯因果证据？ | `causes`、`evolves_to` |
| 检查 | 针对某故障可采用哪些检查或诊断方法？ | `diagnosed_by`、`inspected_by` |
| 维护 | 针对某故障可采取哪些维护、缓解或预防措施？ | `mitigated_by`、`prevented_by`、`maintained_by` |

配置中的每条元路径同时冻结Domain、Range、关系方向和答案端点。例如：

```text
(FaultMode|FailureMechanism)-[manifests_as]->(Symptom|SignalFeature)=>tail
```

脚本启动时将CQ注册表与`provenance_schema_v3.json`中的13类节点和15类关系逐项核对。CQ中出现未注册关系、超出Domain/Range的端点类型或缺失的任务组合时，评价立即失败。

### 2.2 来源追溯CQ

除40个任务CQ外，v1还冻结3个谱系问题：

1. 每个结构答案能否沿`CanonicalEntity—Claim—EvidenceAssertion`回溯到至少一条合格Silver证据断言；
2. 计入评价的证据断言能否回溯到构建集文档、PDF物理页、来源URL、文档哈希和页面哈希；
3. 每个答案能否枚举其支持文档和来源族，且没有将开发集或保留测试集计入主图。

## 3. 可追溯结构可回答率

对任务CQ \(q\)，设冻结的合法元路径集合为 \(\mathcal{M}_q\)。若规范答案实体 \(x\) 至少存在一条满足下列条件的路径，则称 \(x\) 是该CQ的可追溯结构答案：

\[
x \leftrightarrow c
\rightarrow a
\rightarrow (d,p,u,h_d,h_p,f)
\]

其中：

- \(c\)为属于目标故障类别且符合某条 \(m\in\mathcal{M}_q\) 的Claim；
- \(a\)为支持Claim的E1或E2 EvidenceAssertion；
- \(d,p,u,h_d,h_p,f\)分别为构建集文档、PDF物理页、URL、文档哈希、页面哈希和来源族；
- 证据断言必须为Silver、可进入中文发布图且不是推断边；
- 源记录必须明确满足`relation_type_valid=true`；
- `evidence_validation.valid`和`evidence_validation.silver_eligible`必须同时为`true`；
- `relation_entailment_valid`和`relation_entailment_validation.silver_eligible`必须同时为`true`。字段缺失不能按通过处理。

令 \(\mathcal{X}_q\) 为通过以上全部门控的唯一规范答案实体集合，则：

\[
I_q=
\begin{cases}
1,&|\mathcal{X}_q|\ge 1\\
0,&|\mathcal{X}_q|=0
\end{cases}
\]

40个冻结任务单元的总体可追溯结构可回答率为：

\[
A_{\mathrm{traceCQ}}
=
\frac{1}{40}\sum_{q=1}^{40} I_q
\]

每个角色 \(r\) 包含10个故障任务，其角色可回答率为：

\[
A_r=\frac{1}{10}\sum_{q\in\mathcal{Q}_r}I_q
\]

四角色宏平均为：

\[
A_{\mathrm{role\text{-}macro}}
=
\frac{1}{4}\sum_{r\in
\{\mathrm{symptom,cause,inspection,maintenance}\}}
A_r
\]

由于每个角色恰好包含10个任务，v1中的总体值与角色宏平均数值相同，但报告仍分别保留二者，以便未来版本的任务数量发生变化时继续可比。

结构可回答只表示“存在合法、有来源证据的图路径”。一条结构合法路径仍可能存在事实或翻译错误，因此上述公式不能写成Accuracy、Precision、Recall或诊断正确率。

## 4. 数据划分硬约束

主图评价只允许：

```text
MP001–MP007、MP015–MP022，document_split=build_train
```

以下文档不得计入主图CQ答案：

- MP008：开发集；
- MP009–MP013：保留测试集；
- MP014：正式语料排除项。

执行器会先检查`source_records.jsonl`。如发现开发集、保留测试集、排除项、非冻结文档或错误split，记录不会进入答案统计，并且命令默认以非零状态退出。保留测试集只能在Schema、CQ、阈值和图谱冻结后用于一次性外部结构泛化评价，不能反向修改CQ v1。

## 5. 执行方法与产物

在仓库根目录运行：

```powershell
python scripts/evaluate_cq_v1.py
```

该命令不调用外部模型，通常数秒内完成。默认同时检查`KG_v1_validated`的分层JSONL和GraphML拓扑一致性，输出：

```text
results/experiments/research_point_1/cq_v1/
├── cq_v1_evaluation.json
├── cq_v1_task_summary.csv
└── cq_v1_report.md
```

每个任务CQ均输出：

- 唯一规范答案数和答案实体；
- 冻结合法元路径及实际被实例化的元路径；
- 支撑Claim和EvidenceAssertion；
- 支持文档数及ID；
- 来源族数及ID；
- 二值结构可回答状态；
- 可追溯结构可回答率。

JSON报告同时写入CQ配置SHA-256、各图谱层SHA-256、GraphML一致性结果和划分污染审计，便于复现。

## 6. 当前KG_v1_validated结果

在2026-07-30的冻结图谱上，结果为：

| 指标 | 结果 |
|---|---:|
| 可结构回答CQ | 34/40 |
| 可追溯结构可回答率 | 85.0% |
| 症状CQ | 7/10 |
| 原因或机理CQ | 10/10 |
| 检查CQ | 7/10 |
| 维护CQ | 10/10 |
| 每CQ平均规范答案 | 5.075 |
| 每CQ平均证据断言 | 6.150 |
| 每CQ平均支持文档 | 2.700 |
| 每CQ平均来源族 | 2.350 |
| GraphML/JSONL拓扑一致性 | 通过 |
| 主图划分审计 | 通过 |

未形成合法证据路径的6个任务为：

- 汽蚀—检查；
- 空气侵入或失去自吸—症状；
- 空气侵入或失去自吸—检查；
- 液压堵塞—症状；
- 电机电气驱动故障—症状；
- 电机电气驱动故障—检查。

这6项是正式CQ所揭示的**角色级结构空缺**。它与此前“10类故障证据覆盖10/10”并不矛盾：历史门槛将检查和维护合并，且按证据角色计数；CQ v1则要求四种任务角色分别存在本体类型合法、中文发布合格并具有完整来源谱系的答案路径。

当前3个来源追溯CQ均为100%，说明计入任务评价的194条证据断言能够完整回溯；这只证明发布图谱系结构完整，不能证明194条断言全部事实正确。

## 7. 论文报告原则

论文中可以使用以下表述：

> 在图谱构建完成之后、正式对照实验和保留测试之前冻结的40个“故障类别—证据角色”能力问题上，中文发布图谱的构建集结构描述性基线为34/40，可追溯结构可回答率为85.0%。其中原因机理和维护角色均达到100%，症状与检查角色均为70%。所有计入答案的图路径均能够回溯到构建集中的Silver证据断言、物理页、URL和来源族；该结果衡量结构功能和谱系完整性，不代表答案准确率。

不得使用以下表述：

- “CQ准确率为85%”；
- “图谱诊断准确率为85%”；
- “来源追溯100%证明三元组全部正确”；
- “MP008或MP009–MP013补足了主图覆盖”；
- “自动抽取结果为Gold”。
