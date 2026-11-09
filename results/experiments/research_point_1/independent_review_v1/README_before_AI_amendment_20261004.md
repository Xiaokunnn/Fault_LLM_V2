# 独立复核填写入口

当前状态：待真实评审填写；29个保留页正文未打开。表格使用UTF-8 BOM，可用Excel或LibreOffice打开。请保留ID、页哈希和原候选列，仅填写空白评审列。无需重审全部8003条。

1. **先看源文**：[六页源文](../adjudication_targeted_v2_1/expert_source_only.md)。暂不打开03、04表。填写[01_page_inventory.csv](01_page_inventory.csv)，将自己独立整理的知识清单保存到该表指定的submissions文件。每条写对象、关系/动作、条件、适用范围和原文证据；空目标页写明理由。`source_first_confirmed`填`yes`。
2. 填写[02_scope_decisions.csv](02_scope_decisions.csv)的5个口径问题；不知道的写明未决及如何保留，不能强行判错。
3. 打开[03_candidate_review.csv](03_candidate_review.csv)，检查22条候选。前三个质量列填`yes/no/uncertain`；最终裁定填`supported/unsupported/unresolved`；补原文位置和理由。没有显示旧AI判定或保留决定。10条定向变更样本加12条哈希抽样对照，不能用它估计整体准确率。
4. 打开[04_reference_review.csv](04_reference_review.csv)，把独立清单与85项旧暂定参考比较。裁定填`valid/invalid/needs_revision/unresolved`；有效/需改条目写独立清单ID或修订文本；所有条目写理由。清单中新发现而原参考没有的知识保留在独立清单中，不能漏记。
5. 在[reviewer.json](reviewer.json)填写评审人及专业背景。`reviewer_kind`为`domain_expert`或`independent_technical_reviewer`，据实选择。完成后填写ISO时间、独立性/源文优先声明。`submissions/disagreement_resolution.md`汇总残余争议、参考修订及处理口径。若保持当前方法进入一次固定评价，`method_disposition`填`evaluate_current_method`；需要改方法则填`revise_before_freeze`，暂不开保留页。

不能用AI生成的签名或裁定冒充独立人工交付。另一个模型可提供辅助意见，但不满足当前正式人工评价条件。程序只能检查表格和文件完整性，无法自动验证人员身份、专业资格或语义判断。

```bash
python scripts/check_rp1_independent_review_v1.py
# 真实评审完成、检查通过后：
python scripts/check_rp1_independent_review_v1.py --freeze
python scripts/check_rp1_independent_review_v1.py --prepare-heldout-sources
```

前一命令仅检查，不打开保留页。后两步会拒绝未完成评审或被改动的封存方法。保留页来源包只用于先独立列参考；不是已完成抽取/准确率/召回率。

[完整流程及最小保留页设计](../../../../docs/research/RP1_INDEPENDENT_REVIEW_AND_HOLDOUT_V1_20261003.md)。`candidate_method_seal.json`是候选方法封存，不是正式冻结；`holdout_plan.json`只是29页身份清单。`private_mapping.json`含内部候选对照，评审前不要查看。
