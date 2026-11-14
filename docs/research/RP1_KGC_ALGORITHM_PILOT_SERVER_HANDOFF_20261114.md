# RP1 潜在关联增强与补全算法预实验：服务器交接

更新日期：2026-11-14。当前任务由用户最新指令确定；不再沿用旧 A～E 排名或把初始候选重新发布作为主要成果。

## 1. 当前目标与优先级

RP1 的核心算法研究任务正式确定为：**已有知识图谱的潜在关系发现、可信关系补全和现有关系增强**。

- E1：以已有实体、关系、候选信息预测尚未表达的潜在关系，不限于两跳因果。
- E2：关系类型预测、可信性排序与补全；分别记录已有事实、模型推断和原文直接支持的新关系。
- E3：利用额外结构、候选和原文，提高已有关系的表示、适用范围表达及可信性。

不自动加入传递因果边。缺少直接原文支持但有合理推断依据的关系，保留在独立推断层，不能冒充原文明示事实。

用户要求先执行可运行基线，再依据真实缺陷实现最小改进原型；不是再次审计抽取/门控，也不是再次讨论增强是否必要。

## 2. 实际完成状态：不要误读旧结果

**本次算法预实验尚未实现训练或运行补全基线。** 中断前实际只完成了：

1. 检查本机计算资源和依赖；
2. 浏览并核对 AnyBURL、SimKGC、NBFNet、MusKGC、NAAER 的论文/官方代码入口；
3. 初步考虑在资源有限的本机使用作者 AnyBURL 与 CPU ComplEx 适配实现。该方案尚未落地，也不是服务器端必须沿用的最终选择。

尚未完成：严格遮蔽数据集、G1～G4 模型输入、AnyBURL/ComplEx/其他模型训练、关系预测指标、噪声对照、独立文档核验、消融及最小改进原型。没有下载 AnyBURL jar 或模型权重，没有产生本次 KGC 模型结果。

服务器应重新检查 GPU/内存/环境。在可行时优先使用至少两个机制不同的真实强基线，不受本机 CPU 备选限制。服务器曾有7B模型，但当前具体可用路径、显存与空闲资源需要现场确认。

### 已完成且本次上传的前置实验

- `results/experiments/research_point_1/kg_enhancement_feasibility/`：上一阶段问题调查及可行性记录。
- `results/experiments/research_point_1/kg_enhancement_task_comparison/`：统一映射、原文/表格对照及任务比较。
- 其中 `runs/20261114_enhancement_v1/` 已物化22条来源支持的试验Assertion、19个新增试验Claim；这些是当前AI非盲审查的沙盒增量，**没有通过完整正式发布流水线，也不是本次算法补全实验的性能结果**。
- 上一轮61项测试通过，原209个封存文件和15份PDF通过保全校验。该测试数只证明上一轮代码/证据契约检查通过，不证明本次 KGC 基线完成。
- 原先A优先、以及更早B优先的推荐均属历史任务选择意见，现已由用户新的 E1～E3 算法研究任务取代。

前置结果只作参考；本次基础图必须仍是用户指定的原始 expanded1456，不能把上述试验沙盒作为新的基础图。

## 3. 唯一允许的数据

领域数据固定在 Git 对象 `833c8040058055434c7f6a9595ec524c3935755f`，以下对象已在该提交中存在。保留该Git对象，不要合成缺失资产。

### 基础图

`data/kg/marine_pump/versions/expanded_v1_20261012/`

- `entities.jsonl`：2150个实体；
- `claims.jsonl`：1400个Claim；
- `evidence_assertions.jsonl`：1456个Assertion；
- `source_records.jsonl`：对应原证据、条件、来源及历史校验字段；
- `graph.graphml`：需要结构格式时使用。

该目录是本次唯一基础图，不读取、统计或比较其他历史图谱版本。不要改正式文件，不影响RP2/RP3。

### 初始候选及状态

- `data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl`：8007次出现、8004个原始ID；
- `data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl`：8003条审计记录，保留原状态及拒绝原因；
- `data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/candidate_triples.zh_local_full.jsonl`：8003条对应归一化记录。

上述记录不是8000条正确事实。不同出现、去重事实、证据支持和模型推断应分开。已有源字段中的历史状态名保留用于追溯，不以其命名当前研究方向。

### 文档和Schema

- 构建文档仅MP001～MP007、MP015～MP022，共15份、1934个物理页；
- 页解析：`data/interim/parsed_pages/corpus_v2/MPxxx.pages.v2.jsonl`；
- 原PDF：`data/source_docs/marine_pump/raw/`，文件名取`source_manifest.csv`；
- Schema：`data/kg/marine_pump/schema/provenance_schema_v3.json`。

不得使用MP008开发资料或MP009～MP013外部评价文档参与本轮设计和训练。原文、哈希、原生单元ID、真实偏移及原本存在的坐标均不改写，不虚构bbox。

可复用的只读输入工具：

`results/experiments/research_point_1/kg_enhancement_task_comparison/code/inputs.py`

它从锁定Git对象读取允许的输入，避免本地旧工作树或默认加载器误用其他图谱。原映射位于`runs/20261113_v1/mapping/`，可直接复用真实对应关系。

## 4. G1～G4 对照必须实际运行

| 视图 | 输入 |
|---|---|
| G1 | 仅基础图（遮蔽实验时为其训练部分） |
| G2 | 基础图＋经过保守检查的部分候选 |
| G3 | 基础图＋分层表示的全部可追踪候选 |
| G4 | G3＋来自15份原文的语义/证据信息 |

候选须去重并保留状态、置信信息、来源、条件；未知/错误风险不能因为参与训练而变成确认事实。加入“直接平铺合并候选”的对照，比较分层/不确定性参与是否优于简单合并。

报告不同输入规模、候选层、噪声水平下的补全表现、错误预测、覆盖及成本。噪声注入需要有固定随机种子和记录，不能把人工合成的扰动说成原数据已知错误。

## 5. 算法入口和真实性要求

以下论文/入口已在本机浏览核对；**未执行原模型**。

- AnyBURL：<https://web.informatik.uni-mannheim.de/AnyBURL/>。作者发布的当前jar名`AnyBURL-23-1x.jar`，来源包`AnyBURL-23-1x-sources.zip`；2025修复涉及noisy-or聚合。可按官方流程学习、应用规则；记录jar/源码哈希、版本、参数、随机性及规则文件。规则预测只进推断层。
- SimKGC：<https://github.com/intfloat/SimKGC>，<https://aclanthology.org/2022.acl-long.295/>。官方实现使用PyTorch/Transformers双编码器及对比学习；字符TF-IDF/LSA不能冒充SimKGC。
- NBFNet：<https://github.com/DeepGraphLearning/NBFNet>。官方实现依赖PyTorch、torch-scatter、TorchDrug；先验证服务器兼容性和预算，不能把简单路径统计称为NBFNet。
- MusKGC：<https://aclanthology.org/2025.emnlp-main.508/>，2025年EMNLP多源开放世界补全框架；本机已核对论文，未核实完成可直接运行的作者实现部署。领域外知识不得越过本任务15份手册边界。
- NAAER：<https://link.springer.com/article/10.1007/s44443-025-00148-6>，2025年论文《Knowledge graph completion based on iteratively learning embeddings and noise-aware rules》。已有规则质量评价、性能引导噪声过滤和规则/嵌入迭代；不能把简单加权重新宣称为全新思想。
- ComplEx可作为资源受限时机制不同的嵌入备选。若自己实现，必须明确“原打分函数的适配实现”，记录损失、负采样、优化器与原论文的差异，不称原作者代码复现。

至少运行两个可行、机制不同的强基线。不要因为本机未装依赖而跳过服务器能运行的算法，也不要在没有结果时写“已复现”。

## 6. 评价硬要求与防泄漏

1. **严格已知关系遮蔽**：以事实族而非某条Assertion随机拆分；处理同义端点、多语言/重复证据、逆向或等价关系及同一来源单元。遮蔽目标在额外候选中出现的副本也必须剔除。
2. 明确文本可见性。G4不能直接使用遮蔽目标的原引句、来源页或其重复片段来证明结构推断成功；若允许检索答案原文，应作为另一项“来源重建”任务单独报告。
3. 同一个测试任务在G1～G4使用一致的目标和候选答案集合；检查已知端点、孤立端点/冷启动比例，避免改变分母制造改进。
4. 训练过程不能读取测试来源ID、目标关系、目标证据或测试分数作模型选择。模型/阈值选择使用验证集。
5. 尾实体预测/关系类型预测分别报告，建议含filtered MRR、Hits@k及覆盖；规则未覆盖与平均并列排名要明确处理，不能把无预测当成满分。
6. 新预测分为：基础图已知、初始池已观察但未发布、真正超出二者的潜在关系。不能把训练中过的候选重新输出当作全新关系发现。
7. **独立文档核验**：预测与原文核验的输入隔离应事先定义。若文档用于G4训练，不能随后声称同一段是未见独立证据；可设置来源/文档保留分支，或诚实披露非独立性。
8. 对设备、工况、实体/关系类型做一致性检查。推断层与原文直接支持层严格分开，记录原生证据位置和理由。
9. 必须有候选规模/层次、噪声及改进模块的消融。无人工Gold部分使用自动标签恢复、来源支持和合成扰动等代理指标，不称真实事实准确率。

## 7. 最小改进原型的决策

候选研究方向是“可信基础图与不确定候选知识的联合关系增强”。双层表示、相互支持/冲突、文本结构联合预测、条件一致性、渐进利用、联合可信推断均是待验证假设，不要求同时实现。

先记录强基线在G1～G4上的真实结果和失败样本，再选择一个最小机制实现并消融。若置信加权或规则/嵌入迭代已属已有工作，必须写清与UKGE/FocusE/NAAER等相关方法的重叠风险，再查最新工作；不能仅换数据集或拼接模块就宣称算法创新。

至少给出一个有实际对照实验支持的改进方案；若原型无增益，如实报告并解释，不能靠测试集挑选、删负例或改分母制造胜出。

## 8. 新结果目录及交付

后续新建并只写入：

`results/experiments/research_point_1/kg_completion_algorithm_pilot/`

按不同run名保存新结果，不能覆盖原`kg_enhancement_feasibility/`或`kg_enhancement_task_comparison/`。应保留模型参数、日志、配置、输入哈希、预测、证据分类、消融和失败结果。

最终交付：算法可行性/实现身份比较；G1～G4实际表现；8000候选的贡献与噪声影响；新潜在关系及推断依据；原文/条件/未验证分类；正确与错误补全样例；改进方案、实测消融及创新性风险。

## 9. 服务器接续操作

```bash
cd ~/08-zxk/Fault_LLM_V2
git status --short
git pull --ff-only origin main
```

先阅读本文件；若拉取因本地改动冲突而失败，保留服务器检查点、缓存、日志和研究输出，不使用`reset --hard`、批量清理或覆盖。

可先检验已上传前置成果（不是本次算法训练命令）：

```bash
python -m pytest \
  results/experiments/research_point_1/kg_enhancement_task_comparison/code/test_selection_experiment.py \
  results/experiments/research_point_1/kg_enhancement_task_comparison/code/test_task_comparison.py -q
```

使用现有研究Python环境即可；不要求新建/激活`.venv`。随后检查`nvidia-smi`、PyTorch/CUDA、模型路径及Java，选择并实现本轮基线。此交接时还没有可运行的本次KGC训练脚本，因此不提供虚构的“一键训练”命令。

可直接发给服务器端助手：

> 先完整阅读 docs/research/RP1_KGC_ALGORITHM_PILOT_SERVER_HANDOFF_20261114.md。执行用户已确定的RP1 E1/E2/E3潜在关联增强与补全算法预实验。不要重做A～E排名，不把候选重新发布当主要成果。只用expanded1456、初始候选和15份手册，先完成严格遮蔽及至少两个机制不同的真实强基线，比较G1～G4和噪声，再根据真实失败实现一个最小原型并消融。新结果只写kg_completion_algorithm_pilot，不改正式图谱或RP2/RP3。已有61项测试是上一轮前置实验，不是本次KGC实验完成证明。请直接运行可执行工作，并如实区分已完成和未完成。
