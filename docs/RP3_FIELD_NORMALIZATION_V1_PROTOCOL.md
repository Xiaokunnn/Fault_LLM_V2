# RP3 请求字段归一化 v1：执行前固定协议

日期：2026-09-17。对应用户要求：核查监督/损失、固定三种子单因素对照、只依据构建集判断效果。

## 先验审计与假设

审计记录：`results/experiments/research_point_3/field_supervision_audit_v1/audit.json`和`audit.md`。
129条train的请求字段零数量为37/129，非请求字段387/387，全字段424/516（82.17%）。
36条validation对应12/36、108/108、120/144（83.33%）。原始/派生子集分别报告。
非请求标签数量占75%，但已保存A3最佳checkpoint的非请求cardinality CE仅占约29%–35%，
不能直接声称空字段损失占主导，更不能把标签频率当成参数梯度贡献。

九次A1/A2/A3训练的最佳epoch均为1。A1/A2没有字段损失也出现此现象；
A3从epoch1到epoch6的validation排序损失上升约0.74–0.81，超过support/field/cardinality损失下降，
解释了总损失早停选择epoch1的数值原因。后续epoch的任务质量未被旧checkpoint保存，不能补造。
本轮仅检验请求字段在联合目标中的相对权重是否不足；不同时修改早停目标或排名损失。

## 固定单因素对照

- 种子：7042027、7042028、7042029，与A3配对，不挑选最好种子。
- C0（all_fields）：直接引用`head_ablation_v1/seed_{seed}/A3/bootstrap/`及其原配置、历史、checkpoint；校验哈希，**不重跑**。
- C1（requested_balanced）：从相同种子A3配置派生，只改字段CE归一化；独立输出`field_normalization_v1/seed_{seed}/requested_balanced/`。
- 控制数据完全相同：40原始+125派生，129 train/36 validation；冻结208教师、特征、模型、batch、LR、dropout、30 epochs、patience=5、seed、损失权重、分组、解码阈值均不变。
- 沿用A3的rank=1、support=1、field=0.6、cardinality=0.6，route/intervention/Brier辅助权重均0。
  本实验检验A3的字段损失，不代表复跑M0复合目标。
- 不附加MP008；不训练Route、不导出/量化、不校准、不读取外部评价；固定full_local诊断解码和support=0.5。

对字段状态和数量两个CE分别应用以下定义。每行只有1个请求字段和3个非请求字段：

```text
C0 = mean(四个字段CE) = 0.25 * mean(请求字段CE) + 0.75 * mean(非请求字段CE)
C1 = 0.50 * mean(请求字段CE) + 0.50 * mean(非请求字段CE)
```

两组先各自归一化，再等权平均；不是删除非请求监督，也不是把两组直接相加使总权重翻倍。
掩码来自冻结query.requested_role，只作用于损失，不进入模型输入、不改变教师标签和availability。
该模式要求每行恰好一个请求字段、其余字段及全部标签有效；full-card/缺失掩码必须报错。
默认`all_fields`路径保持旧CE计算；支持、排序等目标不变。

早停仍使用本臂预声明总validation loss，不按下述任务指标选择checkpoint。
额外记录分组CE和逐epoch构建集任务指标，仅供解释；记录过程不得影响优化、随机状态或模型选择。
旧C0仅有最佳checkpoint，C1逐epoch指标不能当作C0逐epoch重放，不能据此选取另一个C1 epoch。

## 评估与判断规则

分别报告original、derived、all的train/validation，不将派生样本当独立病例；按故障场景聚合再报告三种子均值、SD及描述性区间。

1. 教师请求字段非空时，原始数量argmax=0的比例；另报完整解码后选集为空的比例，区分基数、字段状态和支持门控。
2. 请求字段基数准确率：raw与decoded均报告。
3. Pointer P/R/F1及非空精确成功，不用回答数量代替正确性。
4. 教师空选集时的误填率；零可用候选时的误填率另列；同时给出分子/分母。
5. 保留原始与非请求字段质量和所有种子失败结果。

只在配对的原始validation三种子平均Pointer F1提高、非空目标raw零预测率降低、基数准确率不降低，
并且每种子validation-all的教师空集误填率不升高、零可用证据误填保持0时，标记为本轮内部改善。
不满足则标记未证实或存在权衡，不改协议/种子/阈值重试。本规则不是统计安全保证；validation只有2个基础场景。

## 保存与复现

执行入口：`scripts/run_rp3_field_normalization.py`。
输出根目录：`results/experiments/research_point_3/field_normalization_v1/`，执行前冻结全部三种子配置、控制文件哈希及源码快照。
保留原teacher、MP008、features、B0/M0/A1–A4及所有缓存、checkpoint、报告；新目录存在时拒绝覆盖。
结果无论好坏都写JSON/CSV/Markdown和最新交接。MP008校准不可行问题独立保留，不降低门槛。
