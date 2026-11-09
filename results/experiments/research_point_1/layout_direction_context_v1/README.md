# RP1 布局、方向和条件修复：当前状态

2026-10-04。开发与8页验证均已完成，C对B预定比较 **FAIL**：核心S从5增至15，完整参考匹配3/45→6/45，但核心E/U从9/1增至22/2。布局模块恢复了知识，完整修复仍缺语义可靠性。当前不扩大抽取，不修改本轮规则追求通过。

完整说明见[结果报告](../../../../docs/research/RP1_LAYOUT_DIRECTION_CONTEXT_V1_RESULTS_20261004.md)。用户允许AI源文复核；这里没有人工专家真值或运行时人工逐条审批。

| 目录/文件 | 内容 |
|---|---|
| `development/` | 原六页233条缓存的B/L/D/C结果、逐项变化和开发评价，无新增API |
| `method_freeze.json` | 新页选择/读取前的方法依赖及取页规则 |
| `new_pages/source_only.jsonl` | 固定8页完整原文、原生行框及表格 |
| `new_pages/references.jsonl` | 抽取前AI源文参考45项 |
| `new_pages/reference_inventory.jsonl` | 每页核心数、辅助范围及实际语言 |
| `new_pages/reference_and_request_freeze.json` | 原文/参考/请求冻结身份 |
| `new_pages/public_source_evidence.json` | 四份本地PDF与厂商公开PDF的字节一致证据；原核验的SHA大小写误判另留原记录 |
| `api_run_001/` | 8份原始响应及请求、解析、用量、时延；全部成功，禁止重复调用 |
| `new_page_comparison/outputs.jsonl` | 141候选×5阶段=705项决定；raw为描述性审计，B/L/D/C为对照 |
| `new_page_comparison/source_quality_judgments.jsonl` | 146个不同载荷的S/E/U、理由与原文锚点 |
| `new_page_comparison/metrics.json` | 总指标、比较条件、用量 |
| `new_page_comparison/page_metrics.jsonl` | 8页×5阶段，共40项逐页结果 |
| `new_page_comparison/reference_allocations.jsonl` | 一对一完整匹配、部分触及和未匹配清单 |
| `new_page_comparison/correct_knowledge_losses.jsonl` | 原始支持记录被拒/受损的清单 |
| `new_page_comparison/independent_checks.json` | 独立匹配复算、反序纯函数重放及B→C成员变化 |

S=源文支持且表示完整；E=支持/关系/条件/类型/引用错误；U=未决。核心与非核心分开；部分匹配不进入完整匹配数。参考的组合粒度影响覆盖，不能把6/45读成实际页面知识的绝对召回率。

MP015 p106与MP021 p4为参数/结构页，核心参考0；没有换页。MP016 p12/p21虽元数据标en，实际包含法语/德语，未据此改选择。各页属于同四份已见构建文档，含邻近页，不宣称文档隔离外测。

核查：43项相关测试；196个旧冻结依赖；1,388次来源地址回读（含跨组重复）；40项页面指标及独立匹配复算；564次反序纯函数重放，均通过。旧233条、29页结果和RP2/RP3教师均未改变。

离线检查命令：

```bash
python scripts/run_rp1_ldc_new_pages.py
.venv/bin/python -m pytest -q tests/unit/test_rp1_layout_direction_context_v1.py tests/unit/test_rp1_clause_binding_v1.py tests/unit/test_rp1_automatic_contract_v4_1.py
```

第一个命令只核验冻结输入，不调用网络。实验生成脚本保留已完成文件，不允许覆盖；不要把重新运行生成脚本当作恢复步骤。`api_run_001/completion.json`是抽取结束时的历史快照，最终评价状态以本README和`metrics.json`为准。
