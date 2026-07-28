# 在其他计算机运行全量知识图谱流水线

## 1. 本次运行的边界

主图谱只使用MP001—MP007和MP015—MP022，共15份构建文档、1934个物理页。MP008是开发集，MP009—MP013是保留测试集，均不得进入主图谱。

MP010—MP013已经下载并完成文件级封存，但在主图谱、提示词、Schema、阈值和检索协议冻结前不得解析或查看其内容来调整方法。MP014继续排除。

## 2. 环境准备

建议使用Python 3.11或3.12。克隆仓库后，在项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

检查项目：

```powershell
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -Python .\.venv\Scripts\python.exe -LocalOnly -Limit 2
```

`LocalOnly`只验证页面清单、解析数据和提示词，不调用百炼。

## 3. 两页真实联调

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -Python .\.venv\Scripts\python.exe -Limit 2
```

程序会隐藏读取新的`DASHSCOPE_API_KEY`。两页抽取、严格校验、自动裁决和图构建均成功后，再执行正式任务。

## 4. 正式全量运行

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -Python .\.venv\Scripts\python.exe
```

当前确定性页面计划为：

- 15份构建文档；
- 1934个物理页；
- 1889个模型抽取页；
- 45个空白、封面、目录、索引或完全重复页面。

流水线依次执行：

1. 重建并核验全量页面清单；
2. 使用`qwen3.7-max`逐页抽取；
3. 严格验证页码原文、E1/E2/E3、表格同行、Domain/Range、关系蕴含、泵型范围和中文术语状态；
4. 对符合条件的未确定关系执行双轮拒绝优先自动裁决；
5. 构建`KG_v1_raw`和中文发布就绪的`KG_v1_validated`。

每页都会打印当前页、累计耗时和ETA。按历史单页约15—30秒估算，1889页顺序抽取约需8—16小时；自动裁决和本地验证可能再需2—8小时。因此应预留约12—24小时，实际时间取决于网络、限流和待裁决数量。

## 5. 中断恢复

直接重新运行同一命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -Python .\.venv\Scripts\python.exe
```

程序按提示词哈希、模型名和页面编号复用`raw_responses`缓存，不会重复调用已经成功且配置一致的页面。自动裁决也使用独立缓存。不要删除以下目录：

```text
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/raw_responses/
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_auto_adjudicated/adjudication_cache/
```

若配置、提示词或页面文本发生变化，哈希不一致的缓存不会被错误复用。

## 6. 关键输出

```text
data/interim/candidate_pages/full_extraction_v1/
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_strict_v3/
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_auto_adjudicated/
data/kg/marine_pump/graph_versions/KG_v1_raw/
data/kg/marine_pump/graph_versions/KG_v1_validated/
data/kg/marine_pump/triples/KG_v1_raw/
data/kg/marine_pump/triples/KG_v1_validated/
```

`KG_v1_raw`用于完整审计。`KG_v1_validated`只接收Silver、非推断且中文规范实体通过发布门槛的记录。

如果程序警告中文发布图谱为空或覆盖不足，说明证据抽取完成但中文术语治理尚未完成。不得为了得到非空图谱而直接把英文surface当作中文规范实体，也不得把待审核记录手工批量晋升为Silver。

## 7. Linux服务器上的增量发布修复

若1889页全量抽取已经完成，但中文术语首轮治理尚未达到10/10，不需要重跑逐页抽取。在仓库根目录更新代码后运行：

```bash
chmod +x scripts/run_full_graph_release_repair_secure.sh
./scripts/run_full_graph_release_repair_secure.sh
```

该入口只会重算本地证据修复、复用首轮术语缓存、对实际阻塞发布门槛的少量术语执行两路独立保守复核，并在中文覆盖达到10/10后重建图谱。密钥使用隐藏输入，不写入文件或命令历史。

关键增量输出为：

```text
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_governed/
data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_reconciled/
configs/entity_terminology_zh_marine_pump_v4_silver.json
```

若两路复核未对同一冻结候选名以不低于0.9的置信度达成一致，程序会继续隔离该术语并停止构图，不会降低门槛。

## 8. 完成判定

全量运行结束后应同时满足：

- 所有计划页面均为成功或进入明确失败页清单；
- 严格校验摘要存在；
- 自动裁决摘要存在；
- Raw图谱及统计文件存在；
- 中文发布就绪记录数量已报告；
- 原文、页码、URL、文档哈希和适用范围仍可追溯；
- 全部产物继续使用Silver口径。

主图谱和检索协议冻结后，才允许解析MP009—MP013并构造持出来源查询、外部Silver主张和跨来源等价映射。
