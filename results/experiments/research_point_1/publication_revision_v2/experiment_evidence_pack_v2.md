# RP1 ICSMD 中文初稿 v2 实验证据包

本文件冻结论文 v2 实验部分使用的数字、解释边界和来源文件。所有自动或半自动产物均为 Silver 内部状态，未经领域专家事实审核。

## 1. 全量构图

- 原始候选：8071。
- 审计记录：8003。
- 通过全部自动证据门控：1698，其中 E1 为 1550、E2 为 148。
- 隔离：881；拒绝：5424。
- 1698 条断言对应 1650 个 Claim、2613 个实体。
- 中文发布图：208 条 EvidenceAssertion、203 个 Claim、281 个实体。
- 来源：`results/experiments/research_point_1/rp1_graph_quality_summary_v1.json`、`data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl`。

## 2. 关系支持来源

- E1 确定性关系词形规则：784。
- E2 已验证表格结构：98。
- 同一 `qwen3.7-max` 双提示一致裁决：816。
- 合计：1698。
- 双提示裁决不是独立模型验证；抽取与裁决的相关误差须在局限性中披露。
- 来源：`data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl`、`scripts/run_automatic_silver_adjudication.py`。

## 3. 固定 20 页提示契约对照

| 方法 | 原始候选 | 规范化候选 | 门控合格 | 输入 token | 输出 token | 总 token |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 162 | 0 | 0 | 106171 | 38271 | 144442 |
| B1 | 312 | 184 | 50 | 108019 | 70245 | 178264 |
| B2 | 226 | 97 | 31 | 109119 | 53258 | 162377 |
| B3 | 254 | 120 | 32 | 110615 | 59940 | 170555 |
| Ours | 367 | 367 | 148 | 125223 | 91848 | 217071 |

- 每种方法均处理相同 20 个证据富集页，使用相同模型、temperature、JSON 模式和重试策略；每种方法 22 个实际请求，全部首次成功。
- 未统一最大候选数、系统提示长度和输出 token 上限。
- B0 的 162 条输出全部因作者白名单契约被规范化拒绝，因此该实验只能解释为提示契约服从与门控产出，不能解释为事实质量基线。
- 20 页流程没有调用双提示关系裁决。
- 来源：`results/experiments/research_point_1/api_prompt_comparison_v1/`。

## 4. 来源族与 CQ

- 真实多文档精确 Claim：3；三者均为单一来源族。
- 自然跨至少两个来源族的精确 Claim：0。
- 同族复制从 1 倍扩展到 8 倍时，来源族封顶指数均值保持 0.461058，最大绝对变化为 0；素朴文档计数均值从 0.461877 上升至 0.922116。
- 40 个 CQ 中 34 个具有合法、中文发布合格且溯源完整的结构路径；该 85.0% 不是问答或诊断准确率。
- 来源：`results/experiments/research_point_1/source_family_support_v1/`、`results/experiments/research_point_1/source_family_replication_pressure_v1/`、`results/experiments/research_point_1/cq_v1/`。

## 5. 来源留出外部评价

- 文档：MP010–MP013；103 个物理页，94 个抽取页。
- 审计记录：287；外部门控合格断言：81。
- 81 条记录的页面定位率和溯源完整率均为 100%。
- 四份文档均属于 MAIB 来源族；结果不能评价来源族多样性收益。
- 无人工事实标签，不能报告外部事实准确率。
- 来源：`results/experiments/heldout_external_v3/rp1_external_quality.json`、`docs/research/heldout_external_evaluation_protocol_v1.md`。

## 6. 贯穿实例

- Claim：入口压力不足—导致—汽蚀。
- 原文：`Insufficient inlet pressure will cause the pump to cavitate leading to low performance, noise and short pump life.`
- 文档与页面：MP016，第 3 物理页。
- Claim ID：`MPC-2d81d1a8a58ad41b218d`。
- EvidenceAssertion ID：`MPA-6756db8e6fc06eb12ec7`。
- 来源族：`XYLEM__JABSCO`；E1；非推断；中文发布就绪。
- 头实体术语状态：`secondary_ai_verified`；尾实体“汽蚀”：`dictionary_approved`。
- `human_expert_reviewed=false`。
- 来源：`data/kg/marine_pump/triples/KG_v1_validated/source_records.jsonl`。

## 7. 术语审核边界

- 当前术语表共 337 项：22 项冻结词典条目，315 项 `secondary_ai_verified`。
- `human_approved` 实际数量为 0；没有三元组事实经过人工批准。
- `approval_status` 只描述中文实体端点术语状态，不批准 Claim 或关系事实。
- 来源：`configs/entity_terminology_zh_marine_pump_v4_silver.json`。
