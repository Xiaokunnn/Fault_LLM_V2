# 第一轮受控验证入口

当前状态：固定样本和原始资产核对完成，等待人工参考；没有正式召回率或新机制有效性结论。

## 先读源文并标注

按以下固定顺序读取。每份材料同时提供上下文、目标页正文和原生块/单元格地址；只有目标页关系进入本页分母。

1. [MP017 p10](source_only/01_MP017_p0010.md)
2. [MP022 p27](source_only/02_MP022_p0027.md)
3. [MP005 p99](source_only/03_MP005_p0099.md)
4. [MP022 p26](source_only/04_MP022_p0026.md)
5. [MP001 p57](source_only/05_MP001_p0057.md)
6. [MP018 p18](source_only/06_MP018_p0018.md)
7. [MP005 p57](source_only/07_MP005_p0057.md)
8. [MP001 p48](source_only/08_MP001_p0048.md)
9. [MP015 p9](source_only/09_MP015_p0009.md)
10. [MP005 p6](source_only/10_MP005_p0006.md)

标注规范见仓库`docs/research/RP1_CONTROLLED_ANNOTATION_GUIDE.md`。
填写[逐页人工参考模板](annotations/page_annotations.jsonl)，不将旧AI参考直接复制为人工完成标注。
允许目标关系及端点类型见[冻结关系定义](private/relation_registry.json)，可在读源文时查阅。
标注源文期间暂不打开private中的模型候选，以减少候选对参考清单的提示。

## 资产核对

- 固定输入提交：`bd1e7c60972bbc5f34e408cd69f542b10a4ad566`。
- 完整API原始记录162条，已逐条核对保存的响应和编译记录。
- 原编译器保留107条；最近完整规则链B0保留116条。两者不混为一个方法。
- 最近B0载荷可变换，单独评价，不直接继承原候选的语义标签。
- 历史10次请求合计输入119611、输出22737词元。本轮仅离线准备，新增模型调用0。
- 旧图、旧响应、旧评价、RP2/RP3教师均未改写。

**162/107/116是程序计数，不是正确知识数。**

## 后续执行

人工逐页参考完成后，在仓库根目录运行：

```bash
python scripts/run_rp1_controlled_validation.py seal
```

程序先检查每页已完成声明、目标关系、类型方向和原文锚点，再封存参考并生成匿名候选判读表。
继续填写`annotations/candidate_reviews.jsonl`后运行：

```bash
python scripts/run_rp1_controlled_validation.py audit
```

正式损失账本和召回表才会写入audit目录。参考为空时上述阶段会阻塞，不生成伪指标。

候选恢复和角色评分的实现/对照待损失账本确定瓶颈后开展；当前不增加规则，不扩图，不做联合训练。
全部工具测试使用合成标签，11项通过；这些测试不是10页真实标注质量结果。
