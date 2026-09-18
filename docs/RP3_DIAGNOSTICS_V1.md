# RP3 构建集离线诊断 v1

`diagnose`为未通过部署校准的基线保留学术诊断入口，不替代`evaluate`。
协议：[`../configs/research_point_3/diagnostics_v1.json`](../configs/research_point_3/diagnostics_v1.json)。
执行只读取现有构建集bundle和ONNX，不训练、不读取MP008/外部样本、不拟合阈值、不生成部署证书。

## 已生成结果

- [B0/M0比较表](../results/experiments/research_point_3/diagnostic_comparison_v1/comparison.md)
- [机器可读比较及原有MP008网格](../results/experiments/research_point_3/diagnostic_comparison_v1/comparison.json)
- [B0全部指标](../results/experiments/research_point_3/lec_v1/diagnostics_v1/summary.json)
- [M0全部指标](../results/experiments/research_point_3/lec_augmented_v1/diagnostics_v1/summary.json)

两臂均输出`predictions.jsonl`、`summary.json`、`summary.csv`、`summary.md`；比较目录另有`quality.csv`、`routing.csv`。
结果包含代码/配置/模型哈希，不覆盖先前报告。跨臂比较先核验诊断协议、教师、记忆和原始查询/划分/教师标签一致。
本次两臂诊断目录及逐头消融根目录还保存了经清单哈希核对的`source_snapshot.zip`，保留实际运行源码与协议。

## 指标口径

- Pointer：选集Precision/Recall/F1；空集对空集的F1为0，另报含空集精确一致和非空精确成功数。
- Rank：可用候选中预算K内排序的NDCG，以教师最终选集作二值相关性；教师空集时记NA，不将其混入平均。
- Support：只计算可用且已核验候选；填充、不可用、not_assessed不进入分母。AP按同分组计算，ECE为10个等宽概率分箱。
- Field：同时报告全部四槽和所需角色的原始/解码后状态与基数准确率，单列空目标和非空目标，防止大量空字段掩盖失败。
- 契约：检查输出ID属于候选/记忆、可用、角色正确、不重复、未超过预算。**未完整运行文本渲染，不能称已测完整引用闭包。**
- Route：按当前精度的实际选集构建效用目标，不直接复用过时bootstrap标签；成本口径与既有Route拟合一致。
- 风险—覆盖：只接受符合指针约束的非空提案，按最小已选支持置信度分组同分点；没有回答时风险为NA。
  AURC只积分可达覆盖范围，并另报归一化面积；零可达覆盖时为NA，禁止当作完美零风险。
- 干预：父子选集数量变化符号是否与教师一致（包括零变化），同时报告移除ID泄漏；不是方向一致性训练目标。
- 统计：原始/派生/全部train和validation分别汇总，基础场景宏平均和1000次场景组重采样区间；validation仅2组，区间不稳定。

## 路由对照

所有对照复用同一精度、同一学生提案；选集阈值固定0.5，不选择最优工作点。

| 策略 | 固定规则 |
|---|---|
| R0 | 有符合当前指针约束的非空提案就本地answer，否则abstain |
| R1 | 全部fallback，回放冻结教师结果；不实际调用7B |
| R2 | 全部abstain |
| R3-confidence | 最小已选支持概率≥0.8则answer，否则fallback |
| R3-entropy | 已选支持概率的平均归一化二值熵≤0.5则answer，否则fallback |
| cost-sensitive | 当前模型Route解码结果，仍执行非空和可用性边界 |

R3两种规则都要求非空且通过指针约束；门槛是固定诊断常数，不是MP008校准结果。
成本为local=1、teacher=8、review=12、error=50；local失败成本51，fallback成本9加教师无非空结果时的50惩罚，abstain成本12。
这是既有无量纲效用，不是实际毫秒/能耗。回退率和教师调用避免率须同时报告覆盖，不能用全弃答宣称有效节省。

## 量化与服务器时延

同一构建输入比较FP32/INT8各输出绝对偏差；rank/support排除填充与不可用位置的掩码极值。
5次warmup、每输入30次，CPUExecutionProvider单线程，仅计ORT控制器调用。
不含特征、记忆、渲染、LLM壳、网络或教师；不报告边缘实机、峰值内存、能耗或热稳态。

原始validation中B0 Pointer F1=0.35，M0=0；两种精度一致。
基数原始准确率B0为0.25、M0为0.125。B0 FP32/INT8约1.40/1.76 ms，M0约1.42/1.78 ms（本次p50）。
INT8体积缩小但本机CPU上没有控制器加速；不能从小模型体积推断更快。

## 命令（本机已运行，勿覆盖结果）

```bash
PYTHON=.venv/bin/python bash scripts/run_rp3_experiments.sh diagnose
RP3_CONFIG=configs/research_point_3/lec_train_augmented_v1.json \
RP3_RUN_DIR=results/experiments/research_point_3/lec_augmented_v1 \
PYTHON=.venv/bin/python bash scripts/run_rp3_experiments.sh diagnose

.venv/bin/python scripts/summarize_rp3_diagnostics.py \
  --baseline results/experiments/research_point_3/lec_v1/diagnostics_v1/summary.json \
  --augmented results/experiments/research_point_3/lec_augmented_v1/diagnostics_v1/summary.json \
  --output-dir results/experiments/research_point_3/diagnostic_comparison_v1
```

若新协议确有必要，使用新的`RP3_DIAGNOSTIC_DIR`和比较目录，保留旧报告；不为得到更好数字重复计时选优。
