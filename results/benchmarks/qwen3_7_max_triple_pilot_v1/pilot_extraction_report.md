# qwen3.7-max 船舶机舱泵系三元组试抽取报告

## 运行边界

- 模型：`qwen3.7-max`
- 提示词版本：`marine_pump_triple_prompt_v2`
- 后处理版本：`marine_pump_triple_postprocess_v3`
- 文档划分：`marine_pump_document_split_pilot_v1`
- 数据属性：Silver候选，未进行完整人工标注
- API密钥：未写入任何配置、结果或日志
- 运行状态：已完成全部选定页面
- 百炼用途：仅用于离线Silver候选数据构建；其云端API时延不作为低算力在线检索时延指标

## 页面选择

| 文档 | 划分 | 解析页数 | 本轮选定PDF页 |
|---|---|---:|---|
| MP001 | build_train | 122 | 52（印刷页52） |
| MP004 | build_train | 37 | 11（印刷页10） |
| MP005 | build_train | 152 | 60（印刷页59） |
| MP008 | development | 36 | 26（印刷页26） |

试抽取页先由词法故障线索、故障表结构和检查/维护提示词筛选，再冻结为4份代表文档各1页，并逐页渲染核对版面。词法命中只用于选页，不直接构成三元组或Silver标签。

## 抽取结果

- 选定页面：4
- 已完成API页面：4
- API失败页面：0
- 待运行页面：0
- 候选三元组：31
- 模型原始提议：56
- 候选阈值前拒绝：25
- 去重移除：0
- Schema及原文跨度校验通过：31
- 高置信Silver候选：23
- 待复核候选：8
- 二次AI语义抽样审计明确降审：1
- 构建集高置信Silver候选：22
- 开发集候选（不计入覆盖门槛）：1
- 未映射到故障类的高置信候选：16
- 离线API调用时延：均值 28526 ms，中位数 23439 ms，最大 39410 ms

### 逐文档抽取漏斗

| 文档 | 原始提议 | 保留候选 | 高置信Silver候选 | 待复核 | 阈值前拒绝 | 模型页级警告 | 保留率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| MP001 | 7 | 7 | 7 | 0 | 0 | 2 | 100% |
| MP004 | 14 | 12 | 12 | 0 | 2 | 0 | 85.7% |
| MP005 | 12 | 10 | 3 | 7 | 2 | 2 | 83.3% |
| MP008 | 23 | 2 | 1 | 1 | 21 | 0 | 8.7% |

拒绝原因分布：`{"evidence_span_not_verified":25,"below_candidate_confidence":25}`。模型返回的页级警告已原样保存在运行清单和逐条候选中，只用于质量审计，不直接替代本地校验。MP008开发页只保留 2/23 条原始提议，说明当前跨厂商表格抽取规则尚未稳定；其结果只用于暴露迁移问题，不能据此声称已通过跨厂商验证。

## 构建集试抽取覆盖

| 故障类 | 症状 | 原因/机理 | 检查/维修 | 文档数 | 来源族数 | 试抽取门槛 |
|---|---:|---:|---:|---:|---:|---|
| cavitation | 1 | 2 | 0 | 1 | 1 | 未通过 |
| air_ingress_or_loss_of_prime | 2 | 2 | 0 | 1 | 1 | 未通过 |
| hydraulic_blockage | 1 | 2 | 0 | 1 | 1 | 未通过 |
| impeller_or_wear_part_damage | 0 | 0 | 0 | 0 | 0 | 未通过 |
| mechanical_seal_failure | 0 | 0 | 0 | 0 | 0 | 未通过 |
| bearing_or_lubrication_failure | 0 | 1 | 0 | 1 | 1 | 未通过 |
| pump_motor_misalignment | 0 | 0 | 0 | 0 | 0 | 未通过 |
| motor_electrical_drive_failure | 0 | 0 | 0 | 0 | 0 | 未通过 |
| pipe_or_valve_integrity_failure | 0 | 0 | 0 | 0 | 0 | 未通过 |
| dry_running_or_maintenance_induced_failure | 0 | 0 | 0 | 0 | 0 | 未通过 |

计数按节点类型和“文档-PDF页-规范化实体”去重，MP008开发集仅用于跨厂商迁移检查，不补足构建集门槛。即使某类在试抽取中显示“通过”，仍须在完整构建集上按去重后的“文档-页码-原文主张”重新执行正式覆盖门槛，未通过前不得批量构图。

## 四文档抽样结果

### MP001：PDF p. 52；印刷页 52

- 三元组：Metal-to-metal contact — `causes` → wear
- 来源：[原始PDF](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/design_and_analysis/224-GN-EquipCndMonitoring/Equipment_Condition_Monitoring_GN_e.pdf)
- 原文连续跨度：

```text
metal-to-metal contact is a source of wear
```

### MP004：PDF p. 11；印刷页 10

- 三元组：The pump is not filled with liquid — `causes` → The pump does not prime
- 来源：[原始PDF](https://www.desmi.com/media/4num3fbn/t1345uk.pdf)
- 原文连续跨度：

```text
The pump does not                      1. The pump is not filled       Fill pump casing with liquid
     prime                                     with liquid
```

### MP005：PDF p. 60；印刷页 59

- 三元组：Cavitation — `causes` → Heavy erosion
- 来源：[原始PDF](https://www.desmi.com/media/dx1lnug1/t1542uk.pdf)
- 原文连续跨度：

```text
In the pump,
the impeller may show signs of heavy erosion caused by cavitation (corrosion) which may at times
render an impeller unfit for use in a very short time.
```

### MP008：PDF p. 26；印刷页 26

- 三元组：Pump stressed by the pipework — `causes` → Leakage from pump
- 来源：[原始PDF](https://api.grundfos.com/literature/Grundfosliterature-2965227.pdf)
- 原文连续跨度：

```text
3. Leakage from pump.        a) Pump stressed by the pipework.
```
