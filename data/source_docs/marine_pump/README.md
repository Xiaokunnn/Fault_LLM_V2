# Marine Pump Source Documents

该目录保存新主数据对象“船舶机舱泵系”的公开来源文档。

- `raw/`：未经修改的原始 PDF。
- `source_manifest.csv`：文档 URL、页数、大小、SHA256、来源等级和主要用途。
- `pending_sources.csv`：已核验公开、但尚未在本地落地的补充候选；当前只剩已排除的MP014。
- `heldout_archive_manifest_v1.json`：MP010—MP013保留测试PDF的文件级封存清单。

来源等级：

- A：船级社规范或船用设备厂商直接发布，作为主要 KG 来源。
- B：其他权威设备厂商资料，作为跨来源验证和补充。
- C：事故报告或公开数据集，主要用于查询、困难负例和案例验证。

后续解析必须保留页码、章节、段落和原始证据文本。不得只保存脱离上下文的三元组。

正式清单还必须保存稳定的 `source_family_id`、泵型、服务场景和适用范围。当前本地共有21份PDF、2096页。其中15份构建集文档共1934页；MP008为36页开发集；MP009—MP013共126页，为保留测试集。MP010—MP013当前只完成下载、页数、大小和SHA256封存，在主图谱与检索协议冻结前不得解析或用于调参。MP017–MP021是在326页大候选池审计后，为五类明确缺口新增的官方厂商文档；MP022是在六类角色补缺达到7/10后，为干运转独立来源及剩余三类角色缺口新增的官方厂商文档。这些事后构建集补充必须披露，不能包装为盲测资料。文档身份、划分和纳入理由见：

- `configs/document_split_marine_pump_v2.json`
- `configs/document_split_marine_pump_v3.json`
- `configs/document_split_marine_pump_v4.json`
- `docs/research/new_source_intake_v2.md`
- `docs/research/new_source_intake_v3.md`
- `docs/research/new_source_intake_v4.md`
