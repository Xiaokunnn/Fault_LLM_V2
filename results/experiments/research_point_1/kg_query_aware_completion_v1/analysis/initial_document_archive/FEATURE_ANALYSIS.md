# 最小关系语义表示与可辨识性实测

字段盘点：{"caution":"Distinct native IDs make inputs observable, not semantically proven. Query h,r lacks user operating conditions; no applicability certification.","condition_labels_are_not_gold":true,"edges":4660,"embedding_truncation_tokens":192,"full_provenance_retained":true,"native_features_present":{"column_role":0,"evidence":4117,"explicit_condition":47,"modality":47,"native_address_verified":3018,"native_location":1855,"pump_metadata":4117,"row_group":1824},"views":9320}。

| 类别 | 对照对数 |
| --- | --- |
| already_observable_object_or_direction | 89 |
| still_identical_after_truncation | 47 |
| newly_observable_not_semantically_verified | 39 |

| seed | 表示 | 留出源文档AUC | balanced accuracy |
| --- | --- | --- | --- |
| 16112026 | old_scalar | 1.0000 | 1.0000 |
| 16112026 | new_binding_text | 1.0000 | 0.5000 |
| 16112027 | old_scalar | 1.0000 | 1.0000 |
| 16112027 | new_binding_text | 1.0000 | 0.5000 |
| 16112028 | old_scalar | 1.0000 | 1.0000 |
| 16112028 | new_binding_text | 1.0000 | 0.5000 |

诊断分类器是独立的小线性读出器，不参与KGC训练，不构成新的门损失。来源按文档固定留出；同一固定特征/划分下三次确定性读出可能完全相同，不能视为三份独立泛化证据。
condition_owner/native_owner只改变条件或地址拥有者，旧15维门输入必然相同。新字段/词元不同表示可观察，不等于模型已正确理解。192词元截断后仍同输入者如实单列。
正例为现有自动证据合同支持的原候选，负例为保持类型合法的代理扰动；其他行的动作可能同样有效。原生行组字段不代表列角色可靠，当前明确列角色均缺失。不得将AUC当真实候选正确率。
输入不同但监督不足：没有对这些代理进行独立事实标注，尤其条件/型号语义可能未由当前查询h,r提供。原始证据/字段缺失者只记录缺失，不编造条件；全部缺失率见index/feature_inventory.json。
所有关系与对象替换仅作诊断，不写入候选索引/训练事实/正式图谱；训练仍只有KGC交叉熵。
