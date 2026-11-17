# RP1 潜在关联增强与补全算法预实验

当前研究任务由用户于2026-11-14确定：E1潜在关系发现、E2可信关系补全、E3已有关系增强。比较G1～G4、不确定候选的信号与噪声，再根据基线缺陷实现最小算法改进原型。

完整要求与接续状态见：`docs/research/RP1_KGC_ALGORITHM_PILOT_SERVER_HANDOFF_20261114.md`。

**2026-11-14执行完成**：独立数据冻结，AnyBURL作者JAR、SimKGC作者模型适配、ComplEx适配三类实际训练，78个模型/消融及全部测试评分；最小KL锚定原型、候选规模/噪声、50项来源文档留出、26,328条推断与24例AI源文核查。不是上一轮22条试验Assertion或61项测试。

完整结果：[实测报告](runs/20261114_controlled_v1/REPORT.md)、[复现命令](runs/20261114_controlled_v1/REPRODUCE.md)、[方法与相关工作](runs/20261114_controlled_v1/METHOD_AND_RELATED_WORK.md)、[逐例源文核查](runs/20261114_controlled_v1/discovery/SOURCE_REVIEW.md)。

主要结论：SimKGC测试MRR G1/G2/G3/G4=0.230977/0.240410/0.227763/0.201151。最小原型有小幅均值改善但组区间跨零，未证明稳定原创算法收益；没有确认可直接发布的新完整事实。自动图标签恢复、源文AI支持与事实准确率严格分开。

此目录用于服务器后续新实验。只使用原始expanded1456为基础图；不改正式知识图谱或RP2/RP3，不覆盖前置调查/任务比较结果。
