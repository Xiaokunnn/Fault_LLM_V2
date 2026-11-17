# 逐预测路径与分数

`analysis/predictions_with_paths.jsonl.gz`保存完整B3原型全部374方向×3种子的过滤后top1、三元组分数、文本分数、路径支持和实际TopM路径索引/分数。reference字段仅作事后评价，不进入路径生成。

`completion/path_usage.npz`对每个原始路径方法保存实际采用的picked掩码、端点及评分；终点打乱对照逐种子分开保存。与`paths/{B0,B1,B2,B3,random}.npz`联接后恢复每条路径的节点、原向/逆向关系及来源边。匹配随机和固定标度无关系补充控制各自有独立代码、支持矩阵及冻结摘要。

R3和普通kNN的实际检索ID/分数保存在`completion/{R3,R3_soft,knn}_retrieval.npz`。全方法排名保存在`completion/query_ranks.jsonl.gz`，补充随机控制的排名位于其独立目录。无路径查询严格回退文本基线已通过测试。
