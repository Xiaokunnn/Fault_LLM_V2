# RP1完整原生片段补全与局部关系重构

日期：2026-10-30。当前为开发对照及盲态核验阶段，尚无可报告的语义增益，不扩图。

## 方法及实现

- 片段补全：`src/research_point_1_graph_evidence/stage02_triple_extraction/native_fragment_completion_v1.py`。使用真实单元格、表头、行列与正文句子生成完整名词、事件、动作和方法片段；显示去断行、重复印字规范化与原生证据分开保存。没有按候选ID列正确答案。
- 局部重构：`src/research_point_1_graph_evidence/stage03_schema_validation/native_local_reconstruction_v1.py`。复用现有方向、上下文、分句、布局和批量证据规则；同池选择仅使用有限原生结构证明，不引入学习分数或整数规划。
- 对照与盲核验入口：`scripts/run_rp1_native_fragment_completion.py`；独立验证：`scripts/verify_rp1_native_fragment_completion.py`；报告：`scripts/report_rp1_native_fragment_completion.py`。

本轮不修改旧解析器、旧图谱、旧实验标签、RP2/RP3教师或论文主张。新生成的源语关系仍需中文规范化，不能直接计为中文应用图入库量。

## 正式开发对照

产物：`results/experiments/research_point_1/native_fragment_completion_v1/development/`。

| 组 | 输入 | 选择 |
| --- | --- | --- |
| B0 | 全部484条已有原始输出，保留重复记录 | 声明的完整可复用规则链 |
| B1 | 同一批原始输出及补全产生的结构关系假设，共503条 | 同一规则链 |
| B2 | 读取与B1完全相同的候选文件 | 同一规则加有限局部证据选择 |

B0是本轮明确组合的`normalize → context → clause → layout → batch`流程，不等于历史29页后处理或10页编译器；不能直接套用它们的旧指标。B1/B2源文件、候选ID集合和哈希相同。

程序选择B0/B1/B2为317/332/330条。**这些数字不是完整正确知识数。** 6651次生成位置回读及9558次含条件/表头/关系证明的位置回读通过。48项新旧单元测试通过，另以随机小模型检查了共享前缀缓存不会污染其他核验任务。

显示层已能生成完整`reverse rotation`片段、独立监测方法以及部分维护列动作。原生解析已经合并且无法可靠拆列的维护单元保持未决，不能靠文本共现强行恢复。

## 盲态源文核验

使用本地已有Qwen2.5-7B-Instruct CPU FP32。核验器只看完整源文、Schema、匿名关系或端点池，不看组名、放行标记、旧S/E/U或参考答案。493个去重关系载荷重新核验，包含拒绝项；不把旧S继承给新关系。另有34条D类记录旧池/新池共68项端点充分性诊断。

关系核验后，再按各组“程序选择且源文S”的集合，单独评估191项既有AI参考的完整覆盖，参考不会进入候选生成。限定S/N/U的下一词元判断是AI诊断，不是校准概率或专家真值；上下文超限保留U，不裁剪源文、不删除难例。

状态文件：`generation_complete.json`、`review_progress.log`、`review_complete.json`、`metrics.json`。在`review_complete.json`出现之前，不报告新增正确关系、错误放行增减、误拒或参考覆盖。可读状态为`STATUS.md`；完成后程序生成`RESULTS.md`。

本地CPU全量核验需要数小时。实际执行链已包含核验完成后的指标汇总、独立校验和结果报告生成。若切换外部API，必须另记评价模型和原始响应，不混合两种评价者挑选有利判断；本轮尚无API调用。

## 决策与停止条件

按批次同时要求：完整源文支持的有效关系数量增加、问题放行数量不增加、完整参考覆盖不下降。75%支持比例另外报告，不用程序放行率代替。精确源语/条件键的去重不能宣称语义去重或与旧图合并后的净增。

开发通过后，才能冻结此前未参与规则设计/错误分析的30–50个构建页，覆盖正文和表格；本轮尚未选择这些页面。若只有B1有效，方向应归于结构感知片段恢复；B2无额外收益不能声称新关系选择贡献。若两者均无有效提升，停止本路线，不继续追加规则追逐本批结果。

## 预检记录保留

实验根目录的早期生成文件及`preflight_before_structural_checks/`是预检，不是正式结果。前者发现重复候选分母和推理缓存接口问题；后者在未读取盲态判断前，由结构自查发现名词`check valve`及零件清单误判。相应原文件、模型中断记录和方法快照均保留，修正是通用语法/表型判定，不是按ID补答案。正式开发数据只读`development/`，不挑选预检结果混入。

```bash
# 生成已完成，禁止覆盖重跑。
.venv/bin/python scripts/verify_rp1_native_fragment_completion.py

# 只有确认当前核验进程已退出，才恢复中断任务；完成结果不重跑。
.venv/bin/python -u scripts/run_rp1_native_fragment_completion.py review
.venv/bin/python scripts/report_rp1_native_fragment_completion.py
```
