# 关系语义可辨识性（字段修正后）

初版错读column_role，真实字段为evidence_units.role。去重114个已分类原生单元、220关系/440有向视图已补入文本与字段标记。47条显式条件和1824行组等原盘点不变。初版完整文档在analysis/initial_document_archive/，初版输出没有覆盖。

175对的可辨识分类：{"already_observable_object_or_direction":89,"newly_observable_not_semantically_verified":39,"still_identical_after_truncation":47}。留一来源文档读出AUC=0.534416、balanced accuracy=0.528571；旧标量0.599804/0.588571。补入真实role仍未改善代理辨识。47对被192词元截断抹平；字段有值不是语义理解，模型没有用户工况输入。

原四条固定probe样本不足，完整留文档结果与每fold样本在native_role_correction/proxy_lodo_results.csv。扰动仅代理，分类器不参与KGC训练；相同确定性三种子不是三份独立证据。原文缺失、跨设备适用、长片段截断和多语言编码均为限制。
