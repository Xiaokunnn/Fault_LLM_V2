# 实现与相关工作边界

查阅日2026-11-14；只据原论文/作者实现作定向比较，不是穷尽查新。当前没有对下列未运行方法的性能优劣结论。

| 原始研究 | 已有机制及本轮区别 | 本轮身份 |
| --- | --- | --- |
| [AnyBURL作者发布页](https://web.informatik.uni-mannheim.de/AnyBURL/) | 随机游走规则学习与规则补全；本轮直接使用作者23-1x JAR，领域输入及状态谓词适配。不是自写路径统计 | 真作者学习/应用实现；短预算 |
| [SimKGC原论文](https://aclanthology.org/2022.acl-long.295/) / [作者仓库](https://github.com/intfloat/SimKGC) | 文本双塔、对比学习和负例；沿用作者模型，换本地小BERT、数据/监督适配，关闭pre-batch | 作者模型适配，不是完整论文复现 |
| [ComplEx原论文](https://proceedings.mlr.press/v48/trouillon16.html) | 复数向量可表非对称关系；本轮保持score，采用固定logistic采样训练及文本投影适配 | 自行适配原score |
| [NBFNet作者仓库](https://github.com/DeepGraphLearning/NBFNet) | 神经Bellman-Ford关系路径表示；依赖未就绪，未运行 | 不用自写路径算法冒名 |
| [MusKGC，EMNLP2025](https://aclanthology.org/2025.emnlp-main.508/) | 结合关系模板、类型和多源知识，LLM生成开放世界补全。本轮限定2150实体，仅用15构建文档且不作LLM生成 | 任务更窄；无直接性能对照 |
| [NAAER，2025](https://link.springer.com/article/10.1007/s44443-025-00148-6) | 规则体/头嵌入评分差衡量质量、表现引导降噪、规则与嵌入迭代。本轮未迭代规则/嵌入 | 状态分层或置信筛查本身不是新思想 |
| [UKGE，AAAI2019](https://ojs.aaai.org/index.php/AAAI/article/view/4210) | 不确定图嵌入及软逻辑；本轮四档自动状态并非真实边置信标签 | 未复现UKGE，不主张置信学习首创 |
| [FocusE，IJCAI2021](https://www.ijcai.org/proceedings/2021/395) | 数值边属性调节嵌入学习；本轮经验权重不等同其模型 | 固定权重需实证，不能凭公式认创新 |
| [Learning without Forgetting原论文](https://arxiv.org/abs/1606.09282) | 用旧模型响应作蒸馏约束以减少遗忘；本轮基础批KL锚定沿用这一类思想 | 领域化最小原型，非新KL理论 |
| [Reliable Rule-Guided Augmentation for KGC，2026](https://www.mdpi.com/2227-7390/14/16/2984) | 已研究训练图生成候选的可靠性及影响控制；本轮候选来自历史抽取及来源合同 | 不能将可靠候选加权当独立新颖点 |

另查2026 Neurocomputing PPENet（[出版商条目](https://www.sciencedirect.com/science/article/pii/S0925231226023799)，DOI10.1016/j.neucom.2026.134981），只获得出版社摘要层面信息，全文访问受限。仅作为需避免对潜在路径增强宣称首创的提醒，不据此作逐机制或性能断言。

实际机制对应代码：`train_complex.Complex.forward`为ComplEx score；`train_simkgc.author_class/objective`引用作者对比学习；`run_anyburl.fit/apply`调用作者JAR；`views.build`控制候选状态/规模/扰动；`prepare/export_tasks/refine_safety`隔离标签与文本；`eval_core.Evaluator`全目录过滤并列；`discover`只产生推断层；`enhance_claims`只输出既有Claim审计侧表。

原型精确定义：L_base是作者in-batch+self-negative CE；L_aux是在另一个候选批逐例CE上乘固定w后取均值，系数0.3。KL是基础批内query→tail softmax分布的单向KL（frozenG1→current），排除已知正例混淆项。不是全图边概率、没有条件逻辑求解、没有新来源独立性学习。

P1相对C0有均值改善但区间跨零；P2去权重不差。现有实证不支持“新置信建模贡献”。可能的领域价值在可追踪不确定候选与严格遮蔽下的实证边界，而独立方法贡献仍需更强且不由测试反复调出的证据。暂不把原型包装为硕士论文章节中的已成立原创算法。
