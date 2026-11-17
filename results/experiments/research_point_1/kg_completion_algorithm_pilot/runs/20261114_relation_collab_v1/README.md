# RP1关系感知可信候选协同补全：已完成研究包

本轮已完成87个新训练模型、9个旧冷场景模型复用、96个主评价和18个冻结权重干预。三种子全保留。完整提出方法未稳定优于G2或LAN，可信门趋于全部打开；此负结果和下一次针对性修改完整保留。

- [实测报告](REPORT.md)：强基线、消融、规模/质量、冷与结构场景、区间及限制。
- [模型公式与计算流程](METHOD.md)、[公开研究区别](RELATED_WORK.md)、[失败机制与下一次单改动](FAILURE_MECHANISM.md)。
- [逐例源文核查](discovery/SOURCE_REVIEW.md)、[排名收益/负迁移案例](analysis/CASEBOOK.md)、[复现命令](REPRODUCE.md)。
- `tables/`：全96行、32个条件组、配对区间、18个冻结干预、候选曝光和门值诊断；`figures/`为PNG+SVG。
- `cold/`和`structured/`：各自数据、模型、逐轮日志、输入/测试释放哈希、原始分数与上下文贡献。
- `discovery/`：26,328条未校准推断、12条实际源文AI阅读、分层结果。两池外提议不等于正确新知识，当前确认新完整事实0。
- `verification/delivery_complete.json`为当前完成状态；较早postprocess/analysis完成文件里的source-review-pending只表示当时等待实际阅读，已由此最终记录替代。

正式expanded1456和RP2/RP3未修改。原20261114_controlled_v1的1896个封存文件及原始输入/PDF通过保全核验。本研究尚未commit/push。
