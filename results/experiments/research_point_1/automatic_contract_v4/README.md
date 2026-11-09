# RP1 automatic_contract_v4（首轮，保留FAIL）

233个父候选、P0/P1两个自动对照，共466个输出。生成运行时不读取v3裁定、候选ID或参考。

E1的是否检查句被错误继承为前提，首轮联合开发判据FAIL；另发现旋向条件被i.e.截断。原代码和所有结果保留，不改称成功。

有限补丁与最终报告见[结果说明](../../../../docs/research/RP1_AUTOMATIC_CONTRACT_V4_RESULTS_20261003.md)及[修订目录](../automatic_contract_v4_1/README.md)。

`automatic_outputs.jsonl`为真实自动输出与规则轨迹，`AI_source_review_466.jsonl`为分离的技术评价，不能作为运行输入或专家真值。`execution_freeze.json`、`evaluation_freeze.json`分别冻结生成和评价。原参考匹配340行、逐页/总计结果和FAIL判据均保存。
