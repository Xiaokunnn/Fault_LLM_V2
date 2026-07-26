# Scripts

## 研究点一：24页定向抽取

解析冻结的24页计划，并在终端逐文档打印进度：

```powershell
python -u scripts/run_targeted_page_ingest.py
```

两页真实API联调（安全提示输入密钥，不写入文件）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_targeted_extraction_secure.ps1
```

两页检查通过后执行完整24页抽取：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_targeted_extraction_secure.ps1 -Full
```

严格校验并输出中文图谱就绪数与类别覆盖：

```powershell
python -u scripts/run_targeted_strict_validation.py
```

## 研究点一：11份文档全库候选发现与抽取

单命令执行全库解析、SQLite索引、候选页筛选、Qwen抽取、严格校验和覆盖统计：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_corpus_pipeline_secure.ps1
```

只运行本地解析、索引和候选池构建，用于先查看候选页数量与模型耗时预估：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_corpus_pipeline_secure.ps1 -LocalOnly
```

所有阶段均支持本地进度输出；PDF解析和模型响应可断点续跑。

保存面向用户的流水线命令入口。研究点一的核心逻辑应实现于 `src/research_point_1_graph_evidence/`，脚本只负责参数解析和模块调用；后续研究点使用独立命令前缀，避免入口混淆。

- `run_bailian_triple_pilot.mjs --dry-run`：解析4份代表性PDF并冻结候选页，不调用模型。
- `run_bailian_triple_pilot.mjs`：从当前进程的 `DASHSCOPE_API_KEY` 读取密钥，调用 `qwen3.7-max` 抽取页级Silver候选三元组；密钥不得写入仓库文件。
- `run_document_ingest.py`：运行坐标保持的正文/表格双通道PDF解析。
- `run_strict_pilot_revalidation.py`：不调用外部模型，按严格v2规则回放旧试抽取候选。
- `build_fault_coverage_matrix.py`：合并严格证据覆盖与构建集词法候选页，生成类别缺口矩阵。

其中 `run_bailian_triple_pilot.mjs` 只用于复现历史四页试抽取。下一轮24页正式抽取必须先完成 `layout_v2` 解析，并遵循 `stage02_triple_extraction/chinese_extraction_contract.py` 的“原文surface + 中文规范名候选”契约；当前尚未提供或运行正式API传输脚本。
