# RP3 构建集实验结果索引

更新日期：2026-09-18。当前原型、消融和优化可行性实验已完成；总体改善条件未通过，尚无部署校准证书。
教师一致性不代表专家诊断准确率，服务器计时不代表目标边缘设备结果。

## 阅读顺序

1. [当前交接](../../../docs/RESEARCH_HANDOFF.md)与[基线和待办](../../../docs/RP3_EXPERIMENT_BASELINES_AND_TODO.md)。
2. [B0/M0对照](diagnostic_comparison_v1/comparison.md)与[增强组结果](../../../docs/RP3_AUGMENTED_V1_RESULTS_20260917.md)。
3. 以下按预声明协议完成的构建集对照，及[最新E1结果](../../../docs/RP3_SEMANTIC_V1_RESULTS_20260918.md)。
4. [研究范围评审](../../../docs/research/RP3_SCOPE_REASSESSMENT_20260917.md)与[服务器接手说明](../../../docs/RP3_SERVER_EXPERIMENT_GUIDE.md)。

| 目录 | 内容 | 当前结论 |
|---|---|---|
| [diagnostic_comparison_v1](diagnostic_comparison_v1/comparison.md) | B0/M0、FP32/INT8、固定路由策略的内部比较 | 不生成部署证书 |
| [head_ablation_v1](head_ablation_v1/summary.md) | A1–A4三个固定种子逐头消融 | 字段/数量退化未解决；简化头不等于可部署替代 |
| [field_supervision_audit_v1](field_supervision_audit_v1/audit.md) | 标签频率、损失份额和早停审计 | 零标签多不等于非请求字段损失主导 |
| [field_normalization_v1](field_normalization_v1/summary.md) | 请求/非请求字段分别归一化 | F1恢复，但一个种子新增误填，总体失败 |
| [joint_gating_audit_v1](joint_gating_audit_v1/audit.md) | 支持/字段/数量联合门控定位 | 只读诊断，oracle替换不是方法成绩 |
| [joint_contract_v1](joint_contract_v1/summary.md) | W1困难负例及J1联合契约 | 误填下降但覆盖/F1下降，总体失败 |
| [support_separability_v1](support_separability_v1/audit.md) | 输入冲突、支持可分性、局部梯度 | 不能据局部梯度证明唯一失败原因 |
| [positive_guard_v1](positive_guard_v1/summary.md) | G1实际更新的正支持保护 | 优于W1，未优于C0，正负支持同时饱和 |
| [set_context_v1](set_context_v1/summary.md) | S0容量控制与S1集合上下文 | 上下文生效，验证选集未改善 |
| [scope_feasibility_v1](scope_feasibility_v1/audit.md) | 固定提案oracle回退下界 | 理想可行性审查，不是实际路由收益 |
| [semantic_v1](semantic_v1/summary.md) | H512与冻结BGE-small E1，计入编码器成本 | 相对C0/H512总体判据均失败 |

## Git收录范围

本次提交保留原始路径下的JSON/CSV/Markdown结果、逐行预测、训练历史、逐种子配置、
模型/量化清单、校准搜索失败报告、独立核验、执行前协议和源码快照。
它们支持核对结果、分母、早停依据和资产身份。失败结果与成功执行记录一并保留。

以下资产留在模型服务器，**不随本次提交上传，也没有删除或重算**：

- 7B/BGE权重、LEC checkpoint、FP32/INT8 ONNX。
- 教师及MP008原始响应、模型缓存、逐任务断点、恢复备份和执行日志。
- `data/kg/marine_pump/rp3/`的trace、memory和特征bundle，E1/H512特征数组及量化代表输入NPZ。

少量教师缓存曾在历史提交中被跟踪；本次不改写这些历史记录，服务器恢复后的本地差异继续保留。
仓库中的教师冻结清单和各模型manifest是身份记录，不意味着大文件已随Git分发。
源码快照/完成清单中的文档哈希描述实验当时版本；后续交接更新不会回写已冻结清单。

## 复核边界

新检出可以阅读结果并运行合成测试：

```bash
python -m pytest -q tests/unit/test_research_point_3*.py
```

重建已有实验的逐模型核验还需要服务器保留的对应checkpoint、bundle、日志清单和编码器；
缺少这些资产时不要伪造文件或重跑已完成教师来填补。目录含已有结果，训练入口会拒绝覆盖。
任何新假设须另立协议和输出目录。

仅有2个原始验证场景，派生行不是独立场景。MP008只用于规定的阈值与量化后校准，
MP009–MP013仍保留最终外部评价用途。当前所有部署限制继续生效。
