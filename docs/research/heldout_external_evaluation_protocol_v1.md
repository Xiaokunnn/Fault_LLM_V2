# MP010–MP013 外部保留集一次性处理协议 v1

## 冻结与首次接触顺序

研究点二检索协议 `marine_pump_rp2_budget_retrieval_v1@1.0.0` 已于 2026-08-01 冻结，随后才首次解析 MP010–MP013。四份文档共 103 个物理页，经与构建集一致的确定性规则排除空白、封面、目录、索引和精确重复页后，保留 94 个抽取页。该处理顺序由版本文件、输入哈希和提交记录共同审计。

## 一次处理、两篇论文使用

同一批外部页面只调用一次冻结的 `marine_pump_full_corpus_prompt_v4`，并保留原文、PDF 页码、URL、文档哈希和页面哈希。输出仍为 Silver，未经人工专家审核，不称为 Gold。

- 研究点一仅评价冻结构图流程在新来源族 MAIB 上的结构合法率、页码落地率、证据支持率、隔离率和来源信息完整性。
- 研究点二仅把外部 Silver 作为查询/相关性评价来源，评价冻结检索器的迁移表现。主检索语料仍是冻结的 `KG_v1_validated`。

## 防回流约束

MP010–MP013 的记录不得合并进 `KG_v1_validated`，不得修改抽取提示词、本体、关系映射、术语表、校验阈值、索引、候选预算、K 值、来源族奖励或冗余惩罚。外部结果无论好坏均须完整报告；若后续提出改进，只能作为新版本和新的实验，不得覆盖 v1 外部结果。

## 执行命令

先做不调用 API 的检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_heldout_external_evaluation_secure.ps1 -LocalOnly -Limit 2
```

再执行 94 页冻结外部抽取与双重自动裁决：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_heldout_external_evaluation_secure.ps1
```

密钥采用隐藏输入，不写入文件和命令历史；中断后重复同一命令即可使用响应缓存续跑。所有外部输出位于 `data/interim/heldout_external/`，与主图谱目录隔离。
