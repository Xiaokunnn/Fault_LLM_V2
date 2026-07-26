# 7/10覆盖结果的最终语义缺口审计

审计日期：2026-07-26  
输入结果：`qwen3_7_max_source_v4_gap_v1_combined_auto_adjudicated`

## 结果复核

MP022补充后共有535条严格Silver、187条自动待判/隔离和1085条拒绝，仍为7/10类通过。三类未通过项为：

- 机械轴封故障：症状3/5，其余门槛已通过；
- 管路或阀件完整性故障：检查/维护1/2，其余门槛已通过；
- 干运转或维护引入故障：症状4/5，其余门槛已通过。

因此，MP022已经补齐干运转类的第二来源家族和检查/维护证据。决策脚本继续输出`add_1_or_2_dry_running_maintenance_sources`，是因为它只看到症状仍缺1条；这不等于必须立即新增第二份文档。

## 系统性原因

1. MP022第22页“Leaking shaft seal — Running dry”被正确规范为“Running dry causes Leaking shaft seal”，但`Leaking shaft seal`被模型标为`FaultMode`，覆盖器只把`Symptom`节点计为症状证据。
2. MP022第11页“Ensure that the pipelines are routed correctly”已经是Silver检查动作，但故障类别映射v1.2只识别管路泄漏、破裂、卡滞和损坏词，没有识别直接的管路预防检查表达。
3. 既有MP005第54、55、65页包含轴封少量滴漏、轻微或不可见蒸汽泄漏、初始滴漏或小股流等表现；此前模型把物理部件直接作为`manifests_as`头实体，导致Domain/Range不合规。

## 修复原则

- 不新增文档；
- 不降低5/3/2、双文档和双来源家族门槛；
- 不把`FaultMode`普遍计作症状；
- 不手工把待审核记录直接晋升为Silver；
- 对MP022第22页执行单记录、精确ID、预期字段校验和失败关闭的类型修复，修复后仍需严格校验和双通道自动语义裁决；
- 将管路类别映射升级为v1.3，只增加含`pipe/piping/pipeline/valve`与明确检查、确认、布置、支撑、紧固、维修或更换动作的规则；名词“check valve”不得触发；
- 使用qwen3.7-max只重抽MP005第54、55、65页的症状关系，禁止`Component -> manifests_as -> Symptom`。

## 偏差披露

上述类型规则、类别映射和提示词均是在构建集覆盖缺口可见后调整，只能用于构建集Silver治理，不能包装为预先冻结规则或盲测性能。开发集和保留测试集仍不得参与覆盖补门槛。
