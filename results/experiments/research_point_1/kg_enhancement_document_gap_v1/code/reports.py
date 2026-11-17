"""Write the final research deliverables from actual, sealed CPU results."""
from common_local import *


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(str(v).replace('|','/') .replace('\n',' ') for v in row)+' |\n' for row in rows)


def main():
    p=read(OUT/'potential/complete.json');g=read(OUT/'gaps/complete.json');lim=read(OUT/'support_limits/complete.json');run=read(OUT/'mechanism/complete.json')
    rr=list(csv.DictReader((OUT/'TRANSPORT_COMPARISON.csv').open()));cover=list(csv.DictReader((OUT/'mechanism/context_coverage.csv').open()));strata=list(csv.DictReader((OUT/'diagnostics/stratified_results.csv').open()))
    primary={x['method']:x for x in rr if x['k']=='16' and x['subset']=='all_validation'}
    observed={x['method']:x for x in rr if x['k']=='16' and x['subset']=='source_observable_directions'}
    metric=lambda x,k:f"{float(x[k]):.6f}"
    main_table=table(['方法（K16）','MRR均值','种子标准差','Hits@1','Hits@10'],[[m,metric(x,'MRR'),metric(x,'MRR_seed_sd'),metric(x,'Hits1'),metric(x,'Hits10')] for m,x in primary.items()])
    observe_table=table(['方法','来源可观测107方向MRR','未知来源267方向MRR'],[[m,metric(observed[m],'MRR'),metric(next(x for x in rr if x['method']==m and x['k']=='16' and x['subset']=='source_unknown_directions'),'MRR')] for m in primary])
    quantity_table=table(['类别','数量','解释'],[['A',p['categories'].get('A',0),'初始候选已经表达；不作为算法新发现'],['B',p['categories'].get('B',0),'三个既有关系前提的局部类比，保留未核实条件'],['C',p['categories'].get('C',0),'当前支持不足；未知不等于错误或文档不存在'],['D',p['categories'].get('D',0),'已有AI源文分析指出具体语义角色/方向问题；非专家裁定']])
    save(OUT/'COMPLETION_OPPORTUNITIES.md',f'''# 存量知识支持的实际增强机会

2026-11-16。已实际运行潜在关系生成、冻结CPU迁移对照及原文线索定位。没有调用外部LLM、GPU编码或训练，没有发布新知识。

## 已产生的结果

输入是原transport_R3的150条已存预测，加上本轮从完整基础图生成的11个有界关系类比组合，去除重复后得到**{p['delivered']}条研究候选**。它们都不在基础图的有限名称/保守逆向排除闭包中；其中160条也未在初始候选的同一闭包中找到，但这只是新组合判定，不是真正语义新事实的证明。

{quantity_table}

已确认新增正确事实=0；这是没有事实确认/发布，不是把所有未知候选判错。没有把模型分数解释为概率，也没有把11条B计为11条正确补全。

生成器先按共享关系角色建立三个前提：(h,s,z)、(a,s,z)、(a,r,t)，或前两条的同一入边角色版本。要求h/a类型相同、冻结文本余弦≥0.85、目标Schema合法、无已识别的字面冲突、三前提声明设备类别有交集，才提出(h,r,t)。不使用关系传递闭包，不把causes作传递边。每条保存三个原Claim及原文位置；这是一项类比启发式，**不是逻辑蕴含规则**。300上限事先固定，本轮只有11项，不存在按得分择优隐藏其余项。

## 类比是否产生了跨文档新知识

严格生成器的11项全部同文档：MP015机械密封4项、MP016异常噪声5项、MP001无损检测2项。前两组尤其可能涉及端点别名、编号粒度或同一手册多语言副本。无损检测两项仍有表面/近表面与材料边界，不能无条件互换检测方法。

另有17条**跨文档结构前提成立、声明设备类别未建立兼容性**的线索，保存于`support_limits/scope_unresolved_pattern_attempts.jsonl`，不混入B或计为错误。代表是MP004的“泵流量不稳定”与MP005的“泵无流量或流量过低”共享原因/结构片段后，尝试迁移清洗、查漏或核对Q/H/NPSH措施。SA自吸离心泵与NSL离心泵的pump_type字符串不同，不等于实际冲突；本轮保守生成器因此暂缓，不能由0条跨文档B推出跨文档关系不可迁移或必须增文档。

这17条附有完整三前提和来源，不只是语义相似结果，但相同原因、相似症状仍不足以证明每项措施适用于目标泵型。下一步应从原有段落的条件和操作对象判断兼容性；不能简单放宽类别以提高数量。

## 关系迁移对照实际说明了什么

{main_table}

T0相对冻结G2纯文本的验证MRR从0.244716升到0.259757。T5简单语义检索只有0.250808，提示R3的结构/角色检索组合有用；这不是将类型、关系、结构三个因素单独隔离的因果消融。T0已有94.45%同有向关系，T3提高到99.17%，平均MRR仅多0.000155，三个种子分别+0.001103、−0.000387、−0.000250，没有稳定额外收益。

{observe_table}

同/跨文档只依据**训练可见索引中与查询锚点关联的文档集合**，不是反查验证答案来源。334个查询键只有83个来源可观测，对应374个预测方向中的107个；其余267个方向T1/T2都退回纯文本。可观测子集上T1相对T0提高0.006882，T2降低0.024728。跨文档有个案排名改善，但整体不支持把跨文档限制当作性能改进。

原图分量只复用既有CSV。281个方向的T0迁移权重主要在查询完整图分量之外，MRR 0.241547→0.248553；其余93个方向0.254292→0.293610。这是分层关联分析，不是分量距离的因果证明，不能把文本相似迁移称为多跳图推理。

## 适用范围与尚未解决的问题

T4仅能利用可观察的明确型号或前后阶段；本轮排除0项，和T3逐项一致。它没有证明条件控制有效。MP015的M7N/MD1、X/X1等限制在页面章节中，却未充分进入查询及候选条件字段，是下一步的具体输入瓶颈。

13个验证方向被“同一答案端点+同向关系+锚点余弦≥0.9+同来源族/长引文重叠”的有限风险检查命中；0个是完全相同长引文，存在多语言/近义副本风险。未命中361个方向上T0仍比纯文本0.237050→0.250922，但这不是严格无泄漏证明或新的独立测试。所有原分数保留，风险检查未用于改参数或筛选候选。

全记录见`POTENTIAL_RELATIONS.jsonl`；源文补充表见`potential/context_provenance.jsonl`；11项类比的条件说明见`support_limits/pattern_source_notes.jsonl`。应用提议可以读取完整1400 Claim，这与遮蔽评价严格分开：这些完整图类比没有被喂回T0～T5验证索引。
''')
    requests=read(OUT/'gaps/document_requests.jsonl')
    docs=['# 有具体证据的文档补充需求\n\n2026-11-16。没有下载、上传或重新抽取文档。优先级来自明确引用和关系缺口，不来自文档短或图边少。\n']
    for x in requests:
        docs.append(f"## {x['priority']}：{x['request_id']}\n\n需要：{x['kind']}。\n\n范围：{x['scope']}。\n\n依据：{x['doc']}物理p{x['page']}，page SHA256 `{x['page_text_sha256']}`。原文片段：\n\n> {' '.join(x['exact_context'].split())}\n\n补什么：{x['need']}。\n\n关联缺口ID：{'、'.join(x['related_gap_ids'][:12]) or '这是现有方法适用条件缺口，非缺少一个固定Schema槽位'}。完整ID清单见`gaps/document_requests.jsonl`。\n\n先排重：检索15份已有手册的具体型号/配置和数值表，确认是否已有可用段落。仅引用到配套资料不证明整个语料都没有相同知识。不要购买/下载另一份通用维护概述来替代型号资料。\n")
    docs.append('''## 不应据此补文档的情况

MP022 p22已有过载、汽蚀、轴封泄漏的原因/处理表；图内断连不说明该手册缺少故障排查知识。MP019各语言版是同一来源家族的副本，不属于新增独立来源。MP006安装指南没有完整诊断表，也不能据此断言其他14份文档没有该知识。MP001 p93–95已经有检测限制；应先关联现有材料，只有特定泵部件的验收标准仍不足时才考虑P2。

## 缺口统计的正确解释

`KNOWLEDGE_GAPS.csv`检查365个FaultMode/Symptom节点，形成886个“实体×Schema允许但当前缺少的诊断角色”机会：原因226、检查281、措施136、部件243。它不是886个真实缺失事实，也不是召回率分母；如“故障模式”之类抽象概念本身未必需要每个槽位。

互斥归因：16项有同声明范围的旧自动证据/语义契约记录；819项只有部分/未核实来源线索；26项只匹配其他声明设备类别，可迁移性未知；25项有限原文别名检索未定位。它们均有原图来源记录；25项甚至可能是PDF断行/粘连导致的精确短语漏检，尤其不能认定原文不存在。11项B只是向已有角色增加新组合，本次没有填补一个全空诊断槽位，pattern_slots=0。

**全语料已证实不覆盖的事实数量未测，不能填0代表已经证明全覆盖。**统计文件中的confirmed_document_absences=0表示本轮没有证实任何全语料缺失；不等于证明没有缺口。当前有两项明确的配套资料查找需求，另有一项条件化标准需求。先查配套资料是否已有，再决定是否补充。
''')
    save(OUT/'DOCUMENT_PRIORITIES.md','\n'.join(docs))

    cases=read(OUT/'diagnostics/cases.jsonl');book=['# 实际案例：排名恢复、条件类比与负迁移\n\n所有新增分数都来自187项开发验证关系及应用候选；没有重评分224项测试。排名改善只相对既有自动构图事实，不代表现场诊断准确率。源文解释属于Codex助手阅读分析，不是专家Gold。\n']
    for x in cases:
        q=x['query'];h=x['head']['label_zh'];t=x['tail']['label_zh']
        book.append(f"## {x['tag']}：{x['claim']['claim_id']}\n\n目标：{h} → {x['claim']['relation']} → {t}；预测方向={q['task']}。查询可见文档={q['metadata']['query_source_documents']}；这里展示的参考文档只用于事后说明，没有作为检索输入。\n\n"+table(['方法','三个种子的正确实体排名'],[[m,','.join(str(v) for v in ranks)] for m,ranks in x['seed_ranks'].items()]))
        for s in x['target_sources'][:1]:book.append(f"参考：{s['doc_id']}物理p{s['pdf_page_number']}，原文 `{s.get('evidence_text','')}`。\n")
        for c in x['contexts'][:2]:
            book.append(f"迁移片段：{c['anchor']['label_zh']} → {'inverse_' if c['inverse_view'] else ''}{c['relation']} → {c['neighbor']['label_zh']}，来源{c['documents']}，检索分数={c['score']:.6f}。\n")
            for s in c['sources'][:1]:book.append(f"原始证据：{s.get('evidence_text','')}\n")
        if x['tag']=='transport_win':book.append('解释：润滑剂/润滑脂迁移的同族多语言近义记录使目标更接近已出现的盘车措施；它说明检索运输可恢复排序，同时暴露有限别名屏蔽的残留风险。不能作为新故障机理发现或独立跨来源泛化案例。\n')
        if x['tag']=='transport_loss':book.append('解释：原本纯文本已排第1，迁移到泛化“报警监测”后一个种子退到第3。对冷却介质这一相近词组，目标设备类别/章节范围仍重要。单个种子退化不是所有候选语义错误的证明。\n')
        if x['tag']=='cross_document_win':book.append('解释：MP021的转速/驱动核查提供相近InspectionAction形式，对MP019启动负载检查有部分种子排名改善。但该片段不是“转速异常就等于启动负载过高”的事实依据，不能直接发布目标关系。\n')
        if x['tag']=='cross_document_loss':book.append('解释：MP003蒸汽供汽管路防积水与MP018/MP005停泵、阀门控制抑制水锤处于不同设备/阶段。虽然prevented_by及端点类型一致，近义水锤仍会造成负迁移；这是单靠类型与同关系不足的真实例子。T4因查询缺少这些范围字段而没有拦住。\n')
    book.append('## 同文档条件类比也不是已确认新知识\n\n')
    for x in read(OUT/'potential/pattern_supported_relations.jsonl'):
        if x['relation_id'] not in ['GAPREL-e79ed689a457a0aee0ed','GAPREL-14d14f0c219ea9145116','GAPREL-5b316df91b13a1671219']:continue
        note=next(v for v in read(OUT/'support_limits/pattern_source_notes.jsonl') if v['relation_id']==x['relation_id'])
        book.append(f"### {x['relation_id']}\n\n{x['head']['label_zh']} → {x['relation']} → {x['tail']['label_zh']}。分数{x['transport_R3_score']:.6f}，全2150目录未过滤排名{x['raw_rank']}；都不是事实概率。\n\n三个前提：\n")
        for c in x['pattern_support'][0]['premises']:
            s=c['sources'][0];book.append(f"- `{c['claim_id']}`，{s['head_canonical_zh']} → {s['relation']} → {s['tail_canonical_zh']}；{s['doc_id']}物理p{s['pdf_page_number']}，原文 `{s.get('evidence_text','')}`。\n")
        book.append('\n限制：'+note['source_reading_note']+'\n')
    attempts=read(OUT/'support_limits/scope_unresolved_pattern_attempts.jsonl');x=next(a for a in attempts if a['relation']=='inspected_by')
    book.append(f"## 跨文档暂缓线索：{x['attempt_id']}\n\n{x['head']['label_zh']} → {x['relation']} → {x['tail']['label_zh']}。原关系模式来自{', '.join(x['documents'])}，同角色共享{x['shared_neighbor']['label_zh']}。源文前提如下；不同pump_type字符串不直接当作冲突，也不默认为可互换。\n\n")
    for c in x['premises']:
        s=c['sources'][0];book.append(f"- `{c['claim_id']}`：{s['head_canonical_zh']} → {s['relation']} → {s['tail_canonical_zh']}；{s['doc_id']}物理p{s['pdf_page_number']}，`{s.get('evidence_text','')}`。\n")
    book.append('\n判定：需要核实共享原因是否确属同一机制、Q/H/NPSH核查是否适用SA/NSL双方、源段是否仅限特定泵配置；目前只保留前提，不称新增正确事实。其余16条见同一JSONL。\n')
    book.append('## 原始候选已有与具体方向问题\n\n')
    for x in read(OUT/'POTENTIAL_RELATIONS.jsonl'):
        if x['primary_category'] not in ['A','D']:continue
        book.append(f"- `{x['relation_id']}`，{x['head']['label_zh']} → {x['relation']} → {x['tail']['label_zh']}：{x['primary_category']}，{x['support_explanation']}。来源与原预测ID均在JSONL保留。\n")
    book.append('\nA不算算法新发现；D的两项沿用已有AI源文分析，不能改称独立专家核验。所有C保持未知。\n')
    save(OUT/'CASEBOOK.md','\n'.join(book))
    save(OUT/'EXPERIMENT_PROTOCOL.md',f'''# 本轮实测与后续文档扩充的公平评价协议

## 本轮已经执行

输入锁定Git对象`{I.REV}`，只读expanded1456、8007条原始导出行/8003条规范化审计记录、1934页构建文档。原始行数与可用知识数量不是一回事。复用`../kg_query_aware_completion_v1/`的G2三种子向量、9320有向索引、冻结R3/R1检索、验证答案/过滤集；不读224测试目标做新打分。完整1400 Claim应用类比在另一路径运行，未注入任何验证候选。

种子16112026/27/28，187条验证关系、374个方向、334个不同查询键，2150固定答案。只做CPU前向和检索，不训练、编码或选择新参数。alpha=0.2、检索softmax温度0.1、null logit=0，K=8/16/32全部报告，主K16沿用原设置。

迁移计算与旧代码一致：w=softmax([s_i/0.1,0])；m=Σ w_i(e_bi−e_ai+e_h)；q'=normalize(q+0.2m)；候选得分=q'·e_t。原始无效项mask，实体总数/ID不变。三个种子T0 K16 CPU MRR与原验证缓存差值全部为0。

T0原R3；T1/T2按训练可见查询锚点文档集合相交/不相交检索；无来源则两组都退回文本。该集合是代理，不是查询真实目标文档标签。多文档实体只要有交集就算同来源侧。T3先按端点类型兼容裁剪，再优先同有向关系；T4再处理可观察的明确型号/阶段冲突；T5原R1简单语义检索+完全相同的迁移公式。T1～T4从同一训练可见池重新补足K，T0/T5直接复用缓存前K。

排名双向、filtered，仅过滤冻结train+validation已知答案，平均并列阈值1e-8。验证微平均按374方向，种子标准差ddof=0。2000次bootstrap按133个冻结事实组抽样、跨种子先汇总，不是把重复种子当独立事实；子集66组。记录query-mean与group-macro两个估计量，CI对应后者。没有测试选参、自动更换最优K或最优种子。

后续有限检查发现13个验证方向有同族近义副本风险；原有别名闭包不能当成完全无泄漏证明。风险检查只做事后诊断，未改变分数或方法。未命中也不保证无泄漏。该187验证集已被历史模型选择使用，本轮只能作为机制开发证据，不是新的独立测试。

## 后续G0～G3：未执行，不虚构文档扩充收益

| 组 | 原15份文档基础图 | 额外文档确认知识 | 同一补全算法 |
| --- | --- | --- | --- |
| G0 | 是 | 否 | 否 |
| G1 | 是 | 否 | 是 |
| G2 | 是 | 是 | 否 |
| G3 | 是 | 是 | 是 |

这里的G0～G3是未来文档扩充协议，不是历史pilot的G1～G4候选组，也不是本轮G2向量缓存的含义。

1. 在新增文档进入抽取、索引、语义向量或规则设计前固定共同事实组、实体答案目录及评测任务。原224测试已暴露，不再用于调参或作为新独立结果；新独立留出须另存版本。共同主任务始终同一2150实体答案范围；新增实体单独冷启动/开放目录任务，不能只给G2/G3更多答案。
2. 相同事实组闭包覆盖同义名、方向等价、重复证据、多语言、同族版本及额外候选。先建立训练可见划分，再建四组索引；目标原引句、同页/共享来源副本及其嵌入不得进入任一共同遮蔽上下文。若新增文档直接陈述共同答案，四组都排除该陈述及副本，或从共同主任务去掉该事实并披露数量，不允许只增强G2/G3的答案可见性。
3. 冷端点、有结构支持端点分开报告；相同问题和方向在四组配对，不能用扩图后变温的样本替换更难样本。文档选择不能依据共同测试的答案缺失，应依据本轮公开的具体资料需求和独立训练/开发覆盖。
4. 无算法的G0/G2使用相同架构、初始化、超参数、更新次数和验证选择规则的SimKGC基线，分别只利用本组允许的训练事实；不要把G2也强行冻结成G0向量而预设文档收益为0。G0/G1共用原语料文本检查点，G2/G3共用扩充语料检查点，组内只开关同一补全算法；G1/G3的实现、候选上限和额外计算预算一致。主因子效应分别为G1−G0（原语料算法）、G2−G0（文档知识）、G3−G2（扩图算法）；交互为(G3−G2)−(G1−G0)，不能把G3−G0全部归于算法。可另报告四组均用旧向量的缓存分析，但不得用它替代上述正式对照。
5. 新文档独有事实另建来源支持覆盖评价，保留AI评价身份；能直接检索原句重建的任务另列“文档检索重建”，不混入间接关系推断。ML分数不当事实概率。
6. 结构指标独立于事实支持指标：新边连接多少**原先已有组件**、是否只是新孤立边、语义端点身份是否可靠，另报告来源、条件、语义支持与冲突。未来必要时才计算扩图结构变化，本轮不重跑既有全图稀疏性审计。
7. 文档须合法可用、明确匹配设备/配置、可引用页/单元/哈希，先去重复厂家版本和语言副本。保存额外资料成本、LLM token/调用预算和来源家族独立性。AI核验不冒充人工Gold。
''')

    allK=table(['方法','K','MRR（三种子）','Hits1','Hits10'],[[x['method'],x['k'],metric(x,'MRR'),metric(x,'Hits1'),metric(x,'Hits10')] for x in rr if x['subset']=='all_validation'])
    save(OUT/'FINAL_DECISION.md',f'''# 本轮结论与下一阶段决策

2026-11-16。**实际执行54组CPU验证对照、生成11条新类比组合、归集161条潜在关系，并形成两项明确配套资料需求。没有得到足以宣称“可靠跨文档新事实补全”的证据。**下一阶段以去副本并保留适用范围的关系迁移改进为主，仅定向补配套资料；不扩大神经网络、不重走发布门控或动态BCE/KL路线。

## 1. 实际得到多少潜在关系

{quantity_table}

原预测150+新有界模式11=161。160条是有限别名闭包外且初始候选未定位的新组合，不等于160项真实新知识。11条B局部类比的有效范围未完成确认：机械密封4、异常噪声5、无损检测2，都在同文档。已证实新增正确事实0、正式发布0。已有1条A不作为创新收益，2条D保留旧AI分析身份，147条C不擅自判错。

## 2. 哪些可通过跨文档模式迁移

有17条跨MP004/MP005等文档的三前提结构线索，详见`support_limits/scope_unresolved_pattern_attempts.jsonl`和CASEBOOK。其中“泵流量不稳定”与“无流量/低流量”的共享故障片段，可提出核对Q/H/NPSH、查漏和清洗的条件假设。声明泵型不同使严格生成器暂缓；不同标签并不证明冲突。**本轮没有完成跨文档B的充分适用性证明，不能给出已确认成功条数。**这也不是宣布现有文档不够，因为这些源文片段已经存在。

验证集T2有个案改善，如MP019启动负载检查借助MP021驱动检查形式，但平均不如T0/T1。它是代理排序收益，不是目标关系事实确认。

## 3. 哪些缺口当前支持不足

365个故障/症状的886个缺角色机会中：16有旧自动契约记录线索，819只有部分或未核实来源，26仅其他声明泵型，25有限短语检索未定位。它们不是886个“手册缺失事实”，旧契约也不是Gold。共同原因/相似症状并不保证措施适用；同族多语言副本也不是独立证明。

现有材料无法给出“全文语义上确实没有”的可靠全量统计；确认全语料未覆盖的事实数量未测。可明确的是MP005 p13引用型号产品文献提供运行数值、MP017 p18引用配套维修手册提供故障排查。MP001 p93–95已有检测限制，应先绑定现有范围，不急于增加通用文档。

## 4. transport_R3增益主要来自哪类迁移

{main_table}

纯文本G2 MRR=0.244716，T0=0.259757，T5=0.250808。R3相对简单语义迁移改善0.008949；但R3同时包含类型/关系/结构信号，这个对照不能把改善单独归于某一个因素。

来源可观测107个方向：T0/T1/T2=0.229698/0.236580/0.204970，支持更保守的同来源侧检索，**不支持把跨文档使用量增加本身当成改进**。267个未知来源方向两种限制方法都回退，因此全样本的T1/T2结果不能直接解释为纯同/跨文档因果效应。一个文档集合可包含多个来源，同文档代理仍不等于同型号同工况。

T3相对T0平均+0.000155，只有一个种子正向；事实组bootstrap增益区间跨0。T4阻断0、与T3完全相同，没有证据证明精确条件机制已生效。T5有56.61%查询端点角色类型不匹配，原三元组本身并不一定Schema非法。T0/T3该指标为0。角色裁剪有用但T0已基本饱和，继续仅优先同关系不够。

跨完整图分量占主要权重的281个方向，纯文本→T0 MRR 0.241547→0.248553；另93个方向0.254292→0.293610。该分层没有重新统计完整图，不构成结构推理因果结论。13个方向还有同族近义副本风险；其余361方向T0仍提升，但有限风险排除不构成独立无泄漏测试。

## 5. 应补哪些资料

P1：DESMI NSL具体型号的产品数据、Q/H/NPSH与允许运行包络；P1：与OM-04760对应泵型号的Gorman-Rupp配套维修与故障排查手册。先在现有文档内检查同型号资料是否已附录，确认缺少再补。P2：仅当需要把无损检测落实到具体泵轴/泵壳时补相应材料工艺与验收标准，通用ABS指南不用重复补充。

这不是要求用户扩充几十份文档，没有自动下载。具体缺口ID、原文、哈希及去重要求在`DOCUMENT_PRIORITIES.md`。

## 6. 下一步具体机制

主线优先“**保留设备/章节阶段的检索与有向关系迁移**”：先把现有可用的型号、机封变体、蒸汽/液体管路、运行/停机阶段与候选绑定，再在查询有范围时匹配；范围不可观察时保留未知与null回退，不能将未知当兼容。首先隔离同族近义副本，避免用字面恢复解释新知识发现。

原因是水锤负迁移、M7N/MD1跨配置调整以及检测材料边界均不能由相同关系类型解决，而T4当前根本看不到这些条件。先在CPU固定向量上验证有无这些源文范围的差异，再决定是否有必要训练；这不是新一轮复杂门控模型计划。资料扩充只补上述具体缺口，不能代替算法的配对评价。

本轮没有立项新的原创算法或宣称创新增益。未完成项是跨文档17条的兼容性确认、11条B的完整条件支持、严格近义/来源闭包后的独立评价，以及未来G0～G3文档扩充实验；它们与已完成的54组实测分开。

## 所有K结果：不挑最优设置

{allK}

K16为既有主设置；不因表中K8更高而改口为新的最优结果。完整逐种子、逐方向、过滤规则、模型成本和配对区间均在`mechanism/`。本轮GPU用量0、编码器训练0、外部LLM调用0；主54组CPU流程耗时{run['seconds']:.2f}秒（不含后续来源分析和文件核验），不冒充端到端生产时延。
''')
    save(OUT/'REPRODUCE.md','''# CPU复现与资产定位

本研究可仅依赖已保存向量、Python/NumPy/PyTorch在CPU完成。不要启动GPU或重新编码。当前输出已存在时脚本校验/复用，拒绝覆盖不同内容；历史图谱、实验和缓存只读。

```bash
cd /home/hengshan10/08-zxk/Fault_LLM_V2
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/transport_cpu.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/potential.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/gaps.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/diagnostics.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/support_limits.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/reports.py
.venv/bin/python -B results/experiments/research_point_1/kg_enhancement_document_gap_v1/code/verify.py
```

完整重新计算可在独立checkout还原同一锁定Git对象与父实验资产，复制本目录的`code/`、`local_llm/`和`RUN_PROTOCOL.md`，保持同一父级路径但不复制本轮结果，再按以上顺序运行；不要删除本研究输出以强制重跑。时间数字会随环境变化，排名和统计应保持一致/数值容差内一致。

输入读取器：`../kg_enhancement_task_comparison/code/inputs.py`，仅允许expanded1456及15份构建文档，Git对象833c8040058055434c7f6a9595ec524c3935755f。

父模型/索引：`../kg_query_aware_completion_v1/features/G2_s{16112026,16112027,16112028}.pt`，`index/vectors.pt`、`index/edges.jsonl`、`index/oriented_views.jsonl`、`retrieval/R3_all_global.npz`、`R1_all_global.npz`。领域原始导出8007行与规范化审计8003条分开计，不把其中所有记录当合法融合样本。

遮蔽评价只用父目录`data/validation_targets.jsonl`和`validation_truth.json`中的实际187验证关系。没有调用测试目标评测函数。原完整图分量来自`../kg_structure_cross_document_audit_v1/node_degrees.csv`，没有再次计算全图稀疏性。

输入SHA256在`potential/input_hashes.json`、`gaps/input_hashes.json`和`verification/input_hashes.json`。父实验868个和结构审计61个封存文件的SHA256再次核验；本轮自己的文件清单在`delivery_manifest.json`。源文位置按物理PDF页，不能与印刷页混用；连续offset与表格单元不同，不伪造bbox。

输出顺序：先读取FINAL_DECISION，再看TRANSPORT_COMPARISON/CASEBOOK；逐记录潜在关系见POTENTIAL_RELATIONS，初始来源与条件另有context_provenance/pattern_source_notes；缺口CSV一行是一个待检查的诊断角色，详细来源见gaps/gap_sources.jsonl。

全部默认流程都不需要API Key或网络。可选本机LLM工具单独列在`local_llm/README.md`，本次未启用，当前模型服务器主机硬拒绝。没有新的GPU计算需求或必须提交的服务器任务；本机资源不足时也不得自动把API程序送到服务器。
''')
    save(OUT/'README.md','''# 存量知识增强与文档缺口联合实验

入口：[最终结论](FINAL_DECISION.md)。实测54组CPU对照；161条潜在关系=1条已有候选+11条条件类比+147条未知+2条已有AI语义问题分析；确认新增事实0，不发布正式图谱。

- [现有知识增强机会](COMPLETION_OPPORTUNITIES.md)
- [文档补充依据](DOCUMENT_PRIORITIES.md)
- [真实排名与源文案例](CASEBOOK.md)
- [共同测试与文档扩充协议](EXPERIMENT_PROTOCOL.md)
- [复现步骤](REPRODUCE.md)

不重训、不重抽、不重跑发布门控、不重跑全图稀疏性、不调用外部LLM。所有历史图谱、模型、响应、RP2/RP3保持原样。新结果均为开发诊断和推断假设，非专家Gold或最终事实准确率。
''')
    print('all deliverable reports written',flush=True)


if __name__=='__main__':main()
