# RP1硕士论文研究成果包

整理日期：2026-11-11。定位：**面向船舶机舱泵系故障诊断的证据驱动知识图谱构建与质量治理方法**。

本包落实本次用户确定的最终研究主线：**RP1 expanded1456 → 新版RP2证据选择 → 基于新版RP2教师的RP3蒸馏**。这是后续研究的版本政策；现有RP2/RP3运行配置及历史strict208教师未切换。较早AGENTS/交接文档中的strict208默认教师说明，仍用于解释历史结果，不代表本次论文规划的默认图谱。

研究主图谱经实际文件核数为1456条记录、1400项Claim、2150个实体。主图谱是当前论文研究对象，不代表已完成全图事实核验或满足生产部署质量。既有条件、极性和角色缺陷不因“定稿”而消失。

## 交付导航

| 文件 | 内容与使用方式 |
| --- | --- |
| [01_METHOD_SYSTEM.md](01_METHOD_SYSTEM.md) | 完整方法、13类实体、15类关系、真实代码索引及数学化边界 |
| [02_GRAPH_VERSION_LINEAGE.md](02_GRAPH_VERSION_LINEAGE.md) | 三版图谱用途、记录谱系、计数单位与ID变化 |
| [03_EXPERIMENT_RESULTS.md](03_EXPERIMENT_RESULTS.md) | 七类已完成实验、结果表、版本和解释范围 |
| [04_CONTRIBUTIONS_AND_RELATED_WORK.md](04_CONTRIBUTIONS_AND_RELATED_WORK.md) | 三层贡献、已有工作差异、可用与禁用的贡献表述 |
| [05_CHAPTER3_OUTLINE.md](05_CHAPTER3_OUTLINE.md) | 第3章详细提纲、论证关系及图表安排 |
| [06_CHAPTER3_DRAFT.md](06_CHAPTER3_DRAFT.md) | 按3.1—3.8撰写的完整章节初稿，可直接修改 |
| [07_FIGURES_AND_TABLES.md](07_FIGURES_AND_TABLES.md) | 框架/证据建模图、版本图及实验图表清单 |
| [08_RP2_RP3_MIGRATION_INTERFACE.md](08_RP2_RP3_MIGRATION_INTERFACE.md) | 已有字段与缺项、ID对照、索引/参考/教师迁移说明 |
| [09_LIMITATIONS_AND_WRITING_NOTES.md](09_LIMITATIONS_AND_WRITING_NOTES.md) | 局限性、数值口径纠错及论文写作检查 |
| [tables/](tables/) | 由现存JSONL/报告确定性导出的CSV和JSON |
| [source_manifest.json](source_manifest.json) | 109个相关输入的SHA256及当前检出版本 |
| [verification.json](verification.json) | 本次只读核数、父记录链接和文件保全检查 |
| [package_checks.json](package_checks.json) | 章节、图源、链接、补充来源及图谱指针检查 |
| [future_default_graph.json](future_default_graph.json) / [interface_examples.json](interface_examples.json) | 后续默认图谱的规划指针和实际记录字段示例 |
| [delivery_manifest.json](delivery_manifest.json) | 本成果包各文件的SHA256，用于交付核对 |

## 结果优先级

1. 规模以实际图文件计数、记录链接及冻结结果为依据；历史论文解释以`papers/ICSMD_2026/RP1_ICSMD2026_English_Final.tex`为起点。
2. 扩展谱系、130条新增及80条抽样质量，以`graph_expansion_v1_20261012`目录为依据，不把旧论文的1698准入契约套到扩展记录上。
3. 章节明确标记实验对应strict208、standard1326、历史1698记录集或expanded1456。未完成expanded1456版CQ、RP2与RP3实验，不能搬用旧数值。
4. 7B/27B复杂语义研究仅作为局限性与研究取舍依据；原全语料生成模型和20页API模型是DashScope别名`qwen3.7-max`。

## 复算与保全

在仓库根目录执行：

```bash
.venv/bin/python docs/thesis/rp1_finalization_20261111/reproduce_tables.py --verify
.venv/bin/python docs/thesis/rp1_finalization_20261111/reproduce_tables.py
.venv/bin/python docs/thesis/rp1_finalization_20261111/render_figures.py
.venv/bin/python docs/thesis/rp1_finalization_20261111/verify_package.py
```

`reproduce_tables.py`读取现存结果，首次运行生成本包表格；重复运行只允许相同内容，不覆盖不同的已封存输出。脚本没有模型客户端调用，不构图、不生成新评价、不训练。`source_manifest.json`中的当前检出提交是编写时快照，**不是所有历史实验的执行提交**；历史配置、原始manifest和模型别名分别保留在来源目录中。

上述命令分别检查输入保全、复算表格、重绘本包实验图和核对交付文件。`render_figures.py`仅写本包的两幅实验图。方法框架与证据图的Mermaid源文件保留在`figures/`，初稿也内嵌可预览版本。正式论文排版前可直接编辑章节Markdown和图源；修改后旧交付哈希不再匹配属于正常变化，应另存修订版本。

本次未删除或覆盖旧图谱、API响应、7B/27B模型、论文或冻结实验。新增记录级跨版本对照只用于论文和接口规划，不替换任何历史索引与教师。
