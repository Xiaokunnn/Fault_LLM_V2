# RP1图谱扩展：已完成数量和AI样本质量对照

最终入口：[结果报告](../../../../docs/research/RP1_GRAPH_EXPANSION_V1_RESULTS_20261012.md)；[实际图文件](../../../../data/kg/marine_pump/versions/expanded_v1_20261012/README.md)。

1326→1456条证据，1281→1400种规范化关系，净增130条证据/119种关系。复用既有8003条候选，全程离线。原图40条与新增40条固定样本的源文支持为36/40、38/40；条件合格为23/40、26/40。同一新增40条原始表示条件合格15/40。单AI非盲判断，非人工准确率；没有质量审查后删样本。

主要记录：

- `input_freeze.json`：输入及规则固定信息、抽样种子。
- `candidate_decisions.jsonl`：全部8003条决定。
- `added_records.jsonl`：130条新增及历史字段、修复理由。
- `counts.json`：构图完成当时的数量快照，其中pending状态是审查前历史状态。
- `graph_freeze.json`：审查前图文件哈希；`AI_review_not_yet_started`描述固定时刻。
- `quality_sample.jsonl`：原图/新增各40条，含完整源页、配对原候选。
- `quality_review.jsonl` / `quality_summary.json`：当前已完成的逐项判断与汇总。
- `verification.json`：来源回读、旧图保持、图关联、计数与样本重建结果。
- `completion.json`：最终交付状态及哈希。

已完成图不能原地重复构建。复算检查无需API：

```bash
python scripts/verify_rp1_graph_expansion_v1.py
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/test_rp1_batch_evidence_repair_v1.py \
  tests/unit/test_rp1_layout_direction_context_v1.py
```

生成入口是`scripts/build_rp1_graph_expansion_v1.py`（具有完成产物防覆盖保护）；质量标签由`scripts/review_rp1_graph_expansion_v1.py`归档，不由算法自动判定S/E/U。初次构建遇到的中文别名冲突处理记录位于`logs/rp1_graph_expansion_20261012/`；通过复用已有规范名解决，未降低术语阈值。
