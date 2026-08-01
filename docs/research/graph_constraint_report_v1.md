# KG_v1 标准化约束报告

## 1. 用途与边界

`graph_constraint_report_v1` 用于在冻结知识图谱前，对
`KG_v1_raw` 和 `KG_v1_validated` 的五层 JSONL 资产执行一致性检查。
它将当前项目已有的关系注册表、Domain/Range 规则、稳定标识函数、
中文术语门控和冻结文档划分组合成一份可重复运行的 Python 约束配置。

该报告不应被描述为完整 JSON Schema 验证、RDF 验证或 SHACL 验证，
也不代表人工领域专家审核。报告中的自动与半自动记录仍然只能称为
Silver，不能称为 Gold。

## 2. 运行方法

在项目根目录执行：

```powershell
python scripts/generate_graph_constraint_report_v1.py
```

如需让发布阻断错误返回非零退出码，可执行：

```powershell
python scripts/generate_graph_constraint_report_v1.py --fail-on-blocked
```

默认产物位于：

- `results/experiments/research_point_1/constraint_report_v1/graph_constraint_report.json`
- `results/experiments/research_point_1/constraint_report_v1/graph_constraint_report.md`

JSON 是供流水线读取的主报告；Markdown 是同一结果的人读版本。

## 3. 当前约束范围

| 约束组 | 检查内容 |
|---|---|
| 图包结构 | 五层文件存在；实体、Claim、Evidence、源记录 ID 唯一；链接目标存在且不重复 |
| 图层闭包 | 每个 Claim 至少关联一条 Evidence；Evidence 不孤立；源记录与 Claim–Evidence 链接双向覆盖 |
| 治理状态 | 状态码合法；Validated 只含 Silver；Raw 中待审和拒绝记录仅用于审计 |
| 划分隔离 | 主图只允许 `build_train`；检查 MP008 开发集和 MP009–MP013 保留测试集泄漏 |
| 证据等级 | 发布记录只能为可定位的 E1/E2，且必须通过证据验证、关系蕴含检查并标记为非推断 |
| 关系约束 | 复用 `provenance_schema_v3` 的关系注册表与 Domain/Range |
| 溯源字段 | 文档 ID、发布者、来源族、物理 PDF 页、原文、URL、文档/页面哈希等必须存在且格式有效 |
| 稳定标识 | 实体、Claim、Evidence、Triple ID 可由当前确定性函数重新计算 |
| 分层投影 | 源记录与实体、Claim、Evidence 层的关键字段一致 |
| 中文发布 | Validated 端点具有中文规范名、术语 ID、合格治理状态并保留受保护术语；关系和类型有中文显示名 |
| Raw–Validated 关系 | Validated 必须是 Raw 的可追溯子集，原语言实体表面、原文、页码、URL和哈希不得改写 |

## 4. 严重度和发布结论

- `error`：当前发布约束的硬失败。至少一个此类检查失败时，
  `release_blocked=true`。
- `warning`：审计质量缺口，不自动否定已经合格的发布子集。例如，
  Raw 中因缺失原文而被拒绝的记录可以保留用于误差分析。
- `info`：通过项或只用于描述分布的审计项。

`release_blocked=false` 只表示上述项目级结构、溯源和治理约束未发现
硬错误；它不证明三元组在领域事实层面达到人工专家确认质量。

## 5. 复现实验时应保留的输入

每次报告都会记录以下输入文件及其 SHA-256：

- `provenance_schema_v3.json`
- `entity_terminology_zh_marine_pump_v4_silver.json`
- `document_split_marine_pump_v4.json`
- Raw/Validated 五层 JSONL 文件

因此，同一图谱版本的约束结论可以与其具体模式、术语表和数据划分绑定，
避免只保留一句无法复核的“校验通过”。
