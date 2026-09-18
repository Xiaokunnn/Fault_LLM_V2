# RP3 构建集证据移除增强组结果（2026-09-17）

## 结论和继续入口

`lec_augmented_v1` 已完成 augment、train、route、FP32 export 和 INT8 quantize。
MP008 校准失败关闭：40 条输入的原始 Route argmax 全部为 abstain，可接受回答数为 0。
未生成部署用 `calibration_manifest.json`，未执行 evaluate、外部评价或部署。
此次增强未显示改善；保留负结果，不重复已有阶段，不降低校准门槛。

下一步应先制定新的构建集实验协议，诊断 requested-role cardinality 为零及模型选择目标的问题。
新实验须使用独立配置和目录，仅以构建集 train/组隔离 validation 做学习和选择。
MP008 的回答覆盖不足是另一项独立的校准协议限制；不得据此调学生超参数，
也不得把 MP009–MP013 用于补充校准。当前两组均不可部署。

## 实际执行与数据边界

- 代码起点：`a3b01d6`。完整阅读了根目录 AGENTS、研究交接和服务器指南。
- 冻结资产只读审计通过，图、模型权重、索引、教师轨迹、训练 bundle 均与原冻结记录一致；教师系统身份为 `5b9efc51f82c70fee7ae04115fef1f08a42496c38736f0a7431be17d1a794594`。
- 未重跑原始 teacher、MP008、原始 features 或基线训练；只新增增强数据特征。
- 原始 40 条查询保持不变，增加 125 条证据移除派生轨迹，合计 165 条：train 129、validation 36。仍为 10 个原始故障场景，不能称作 165 个独立病例。
- 派生轨迹继承父轨迹 split；组隔离、可用性掩码和选中证据可用性已核验。
- 模型、训练超参数和 tensorization 配置与基线相同；MP008 未参与梯度或模型选择。
- 基线运行记录为 PyTorch `2.6.0+cu124`，当前服务器实际环境为 `2.6.0+cu118`，CUDA 可用。未替换依赖；因此这不是运行环境完全一致的单因素比较。

## 学生与教师的一致性

下表来自保存的路由 rollout，采用 support threshold 0.5。
“成功”指学生选集非空且与教师选集完全相同，空集与空集一致不算成功；不是专家诊断准确率。

| 样本 | 基线成功数 | 增强组成功数 |
|---|---:|---:|
| 原始 build-train | 11/32 | 3/32 |
| 原始 build-validation | 1/8 | 0/8 |
| 派生 build-train | 不适用 | 8/97 |
| 派生 build-validation | 不适用 | 0/28 |
| 增强全部 build-train | 不适用 | 11/129 |
| 增强全部 build-validation | 不适用 | 0/36 |

增强 bootstrap 在第 1 epoch 获得最佳 validation loss 2.630968，按原 patience 于第 6 epoch 停止。
Route 拟合完成 100 epochs；目标动作分布为 train：11 answer、81 fallback、37 abstain；
validation：0 answer、24 fallback、12 abstain。这些是效用监督目标，不是最终路由预测。

保存 checkpoint 的只读构建集前向诊断显示：validation 全部 36 条学生选集为空。
其中教师非空的 24 条，requested-role cardinality 预测均为 0；24 条均存在同角色、可用、
支持分数至少 0.5 的候选。字段状态中 15 条为 supported、9 条为 insufficient。
因此单独放宽支持阈值不能解决这些轨迹的零数量预测。该诊断未更改模型、训练设置或阈值。

## 量化与校准

控制器参数量 1,261,093；INT8 文件 1,342,926 bytes，40 个 QDQ 节点，40 个 MP008 代表输入完成数值检查。
各输出最大绝对误差为 0.01709、0.02039、0.02574、0.02990、0.02405。
量化数值检查不代表任务精度或部署门槛通过。

| MP008 结果 | 基线 | 增强组 |
|---|---:|---:|
| 原始 answer argmax | 0 | 0 |
| 原始 fallback argmax | 26 | 0 |
| 原始 abstain argmax | 14 | 40 |
| 最大可接受答案数 | 0 | 0 |
| 部署校准证书 | 无 | 无 |

校准集原冻结教师输出为 37 条空集、3 条单证据回答。当前解码器禁止空选集作为 answer，
因此最多只有 3 个非空回答能与教师集合相同。若接受至少 5 个答案，至少 2 个必然不一致，
即不一致率至少 2/5=40%，超过预设 10%。接受更多答案的最低不一致率还会增加。
这证明当前固定校准集与门槛组合不可行，即使选择器完美也不能通过；它与学生全弃答是两项不同限制。
本次未改候选、标签、门槛或 MP008 数据，也未生成伪校准证书。

## 资产恢复与 Git

接手时 HEAD 为 `a3b01d6`，残留未完成 rebase；reflog 显示此前存在 reset 到 origin/main 的操作。
691 个实验文件在工作树缺失，6 个文件为较早版本。原始本地提交 `9370860` 仍保存完整记录。
从该提交恢复了这 697 个文件；替换 6 个旧版本前逐一备份，所有恢复文件均核对 SHA-256。
checkpoint 和 ONNX 二进制仍在盘上，均通过原清单哈希检查，没有重训或重导出基线。

备份 rebase 元数据后执行 `git rebase --quit`，退出残留操作而不重置工作树，
创建本地工作分支 `codex/rp3-augmented-v1-results`。原 `main` 提交保留，未推送研究产物。
工作区中的 6 个受跟踪产物差异来自上述恢复，不能当作缓存清除或还原。

实验结束时，697 个恢复资产，以及额外清点的 24 个基线/原始数据 bundle 文件均保持校验一致。
RP3 单元测试 93 项通过，有 10 条现有 ONNX tracer warnings；只读服务器预检无阻塞。

## 证据入口

- [机器可读汇总](../results/experiments/research_point_3/lec_augmented_v1/experiment_summary.json)
- [构建集前向诊断](../results/experiments/research_point_3/lec_augmented_v1/build_diagnostics.jsonl)
- [增强组校准失败报告](../results/experiments/research_point_3/lec_augmented_v1/onnx/calibration_search_report.json)
- [路由 rollout](../results/experiments/research_point_3/lec_augmented_v1/routed/route_rollouts.jsonl)
- 派生数据lineage（服务器）：`data/kg/marine_pump/rp3/TeacherGraph_RP3_v1/traces/augmented_training/lineage.json`
- 恢复清单及旧文件备份（服务器）：`logs/rp3_asset_recovery_20260917T000825/recovery_manifest.json`
- 资产保护清单（服务器）：`logs/rp3_resume_inventory_20260917.json`
- 只读冻结审计（服务器）：`logs/rp3_freeze_validation_20260917.log`
- 增强日志（服务器）：`logs/rp3_augment_20260917.log`，后续各阶段为 `logs/rp3_augmented_{train,route,export,quantize,calibrate}_20260917.log`。

2026-09-18归档说明：上方可点击的报告和清单随精选结果提交，标注“服务器”的原始产物及日志仍只保留服务器；
详见[收录范围](../results/experiments/research_point_3/README.md)。RTX 5880 实验不是目标边缘硬件测量；本报告不提供专家事实或诊断正确率。
