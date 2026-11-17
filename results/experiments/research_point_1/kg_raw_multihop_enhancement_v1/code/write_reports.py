"""Render reports from measured artifacts; never fit, extract or relabel facts."""
import gzip
import platform
import subprocess
import numpy as np
from raw_io import *

def table(rows,cols):
    def fmt(x):
        if isinstance(x,(float,np.floating)):return f'{x:.6f}'
        return str(x).replace('|','/').replace('\n',' ')
    return '| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+''.join('| '+' | '.join(fmt(r.get(c,'')) for c in cols)+' |\n' for r in rows)
def csvrows(path):return list(csv.DictReader(path.open()))

def casebook(cat,edges):
    ranks=[json.loads(x) for x in gzip.decompress((EXP/'completion/query_ranks.jsonl.gz').read_bytes()).decode().splitlines()];lu={(x['method'],x['seed'],x['id'],x['task']):x for x in ranks};seed=SEEDS[0]
    rows=[x for x in ranks if x['method']=='P4_B3_full' and x['seed']==seed];cov={(x['id'],x['task']):x for x in csvrows(EXP/'analysis/target_path_coverage.csv') if x['bridge']=='B3'}
    z=dict(np.load(EXP/'paths/B3.npz'));views=read(EXP/'index/oriented_views.jsonl');sources=defaultdict(list)
    # Source quotes for held targets are evaluation-only. They never feed graph indexes.
    d=locked()
    for s in d['graph']['source_records']:sources[s['expanded_claim_id']].append(s)
    def delta(x,method='SimKGC_G2'):return 1/x['rank']-1/lu[method,seed,x['id'],x['task']]['rank']
    chosen=[];used=set()
    def pick(title,ss):
        for x in ss:
            if (x['id'],x['task']) not in used:chosen.append((title,x));used.add((x['id'],x['task']));break
    pick('自动参考命中/排名改善，仍需看路径语义',sorted(rows,key=lambda x:-delta(x)))
    pick('相对匹配raw-R3退化',sorted(rows,key=lambda x:delta(x,'transport_R3_raw')))
    pick('完整原始三跳业务路径',sorted([x for x in rows if x['real_target_path']],key=lambda x:x['id']))
    pick('只有单业务边的桥接目标迁移',[x for x in rows if int(cov[x['id'],x['task']]['target_path_count'])>0 and int(cov[x['id'],x['task']]['target_real2_path_count'])==0])
    pick('无答案路径，严格回退',[x for x in rows if cov[x['id'],x['task']]['any_answer_path']=='False'])
    pick('最终预测实体类型不合法',[x for x in rows if not x['type_legal']])
    text='# 路径案例：自动基图参考下的命中、退化和未证实假设\n\n以下是开发验证的事后解释，不是专家事实判定。头预测用inverse遍历；路径箭头不自动具有传递语义。目标引文只在此评价阶段读取。\n\n'
    records=[];R=len(cat['relations']);dest=np.take_along_axis(z['nodes'],z['length'][...,None],axis=2)[...,0]
    def label(i):return cat['entities'][int(i)]['label_zh']
    for no,(title,x) in enumerate(chosen,1):
        h=x['h'];r=x['r'];target=x['target'];pred=x['top1'];ki=x['key_index'];L=z['length'][ki];rr=z['relations'][ki];ns=z['node_score'][ki];rs=z['relation_score'][ki];score=.5*ns+.5*rs-.05*(rr==-1).sum(-1)
        jj=np.where((L>=2)&(dest[ki]==pred))[0];basis='filtered top1'
        if not len(jj):jj=np.where((L>=2)&(dest[ki]==target))[0];basis='reference target, not top1'
        jj=sorted(jj,key=lambda j:-score[j])[:8];selected_paths=[]
        text+=f'## {no}. {title}\n\nID `{x["id"]}`，{x["task"]}，seed {seed}。查询：**{label(h)} — {"inverse:" if r>=R else ""}{cat["relations"][r%R]} → ?**。自动基图目标：{label(target)}；过滤后top1：{label(pred)}。\n\n'
        text+=f'排名：G2={lu["SimKGC_G2",seed,x["id"],x["task"]]["rank"]}，raw-R3={lu["transport_R3_raw",seed,x["id"],x["task"]]["rank"]}，full={x["rank"]}。\n\n'
        s=sources[x['id']][0];quote=s['evidence_text'].replace('\n',' ')
        text+=f'目标来源（不在路径输入中）：{s["doc_id"]} 物理p{s["pdf_page_number"]}，`{s.get("triple_id")}`。\n\n> {quote}\n\n'
        if not jj:text+='top1与目标均没有可用的两/三跳答案路径；该预测由文本分数或其他答案的重排产生，不能伪造支持路径。\n\n'
        for j in jj[:2]:
            le=int(L[j]);nn=z['nodes'][ki,j,:le+1];relseq=rr[j,:le];eids=z['edge_ids'][ki,j,:le];items=[label(nn[0])];ss=[]
            for step,(rel,eid) in enumerate(zip(relseq,eids)):
                if rel<0:items+=[' —[虚拟语义桥]→ ',label(nn[step+1])]
                else:
                    items+=[' —['+('inverse:' if rel>=R else '')+cat['relations'][int(rel)%R]+']→ ',label(nn[step+1])]
                    edge=edges[views[int(eid)]['edge_index']];src=edge['sources'][0]
                    ss.append(dict(edge_id=edge['edge_id'],is_base=edge['is_base'],source=src))
            mass=float(np.exp(np.clip((score[j]-.65)/.1,-10,10)))
            text+=f'实际路径 `{j}`（用于{basis}，节点语义={ns[j]:.4f}，关系序列={rs[j]:.4f}，合分={score[j]:.4f}，未归一化支持质量={mass:.4f}）：\n\n'+''.join(items)+'\n\n'
            for src in ss:
                q=src['source'];frag=q['evidence_text'].replace('\n',' ')[:220]
                text+=f'- `{src["edge_id"]}`，{"基础支持边" if src["is_base"] else "未确认候选边"}，{q["doc_id"]} p{q["pdf_page_number"]}：{frag}\n'
            text+='\n上述来源只支持各自记录的原主张，未独立证明组合后的预测；设备范围、条件、否定或替代分支不由向量相似度保证。\n\n'
            selected_paths.append(dict(path_index=int(j),nodes=nn.tolist(),relations=relseq.tolist(),edge_ids=eids.tolist(),node_score=float(ns[j]),relation_score=float(rs[j]),path_score=float(score[j]),source_edges=ss))
        records.append(dict(title=title,query=x,prediction_path_basis=basis,used_topm_path_indices=[int(j) for j in jj],displayed_paths=selected_paths,target_source=s))
    save(EXP/'PATH_CASEBOOK.md',text);save(EXP/'analysis/case_records.jsonl',records)

def plots(base,abl):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=['SimKGC_G2','transport_R3_raw','P3_joint_real','P4_B1','P4_B2','P4_B3_full','random_degree_matched'];dd={x['method']:x for x in base+abl}
    fig,ax=plt.subplots(figsize=(8,4.6));ys=np.arange(len(names));ax.barh(ys,[float(dd[n]['MRR_mean']) for n in names],xerr=[float(dd[n]['MRR_seed_sd']) for n in names],capsize=3,color=['#879fb0','#2c6b85','#879fb0','#8caba3','#719a8d','#287c62','#bc9385']);ax.set_yticks(ys,names);ax.invert_yaxis();ax.set_xlabel('Validation MRR (bar: three-seed mean; error: seed SD)');ax.set_xlim(.225,.275);fig.tight_layout();(EXP/'figures').mkdir(exist_ok=True);fig.savefig(EXP/'figures/validation_mrr.svg');plt.close(fig)
    diag=read(EXP/'analysis/diagnostic_freeze.json')['path_coverage'];nn=['B0','B1','B2','B3'];a=[diag[n]['target_reached_with_2plus_real'] for n in nn];b=[diag[n]['target_reached_only_virtual_single_real'] for n in nn]
    fig,ax=plt.subplots(figsize=(6,4));ax.bar(nn,a,label='At least two business edges');ax.bar(nn,b,bottom=a,label='Only one business edge + virtual bridges');ax.set_ylabel('Directions with reference target reached / 374');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(EXP/'figures/target_path_coverage.svg');plt.close(fig)

def main():
    if (EXP/'verification/reports_complete.json').exists():print('REUSE reports');return
    cat=read(EXP/'data/catalogue.json');edges=load_graph();graph=read(EXP/'data/freeze.json')['summary'];st=read(EXP/'analysis/raw_structure.json');seq=read(EXP/'analysis/sequence_freeze.json');path=read(EXP/'paths/freeze.json');idx=read(EXP/'index/freeze.json');cf=read(EXP/'completion/freeze.json');diag=read(EXP/'analysis/diagnostic_freeze.json');rand=read(EXP/'completion/random_degree_matched/freeze.json');checks=read(EXP/'verification/checks.json')
    base=csvrows(EXP/'BASELINE_RESULTS.csv');abl=csvrows(EXP/'ABLATION_RESULTS.csv');dd={x['method']:x for x in base+abl};seedrows=csvrows(EXP/'completion/seed_results.csv');cfg=read(EXP/'config.json')
    premise='日期：2026-11-17。仅expanded1456、8003规范化候选及15份构建手册；本轮未重新抽取、未调用外部LLM、未写正式图谱或RP2/RP3。全部排名是内部开发验证代理指标，不是事实准确率或独立测试。\n\n'
    save(EXP/'RAW_GRAPH_REPORT.md','# 8000级原始候选研究图：实测结构\n\n'+premise+f'8007行导出仅用于血缘；8003条规范化记录全部保留，计算图按有向(h,r,t)去重为{graph["full_dedup_edges"]}条边。以类型+NFKC/casefold中文名称定义实体，保留型号字符，不做语义合并。全目录{graph["all_entities"]}个实体均在完整raw图活跃。\n\n'+table([dict(view=name,**{k:v for k,v in s.items() if not isinstance(v,dict)}) for name,s in st.items()],['view','edges','active_entities','active_components','single_semantic_edge_components','largest_component','base_answer_zero_degree','undirected_simple_node_paths_2','undirected_simple_node_paths_3','directed_simple_node_paths_2','directed_simple_node_paths_3'])+'\n度分布（按不同邻居，不按Assertion或平行关系重复计）：\n\n'+table([dict(view=k,**v['degree_counts']) for k,v in st.items()],['view','0','1','2','ge3'])+'\n完整raw图的度1实体仍占'+f'{st["full"]["degree_counts"]["1"]/graph["all_entities"]:.2%}。最大组件显著增长说明更多候选确实带来结构；它不证明这些候选正确，更不证明这些路径对留出目标有用。组件不包含Claim/Evidence/Document节点；self-loop留在记录图，节点简单路径与度数统计不把它当新邻居。全图和训练视图各有1条self-loop。\n\n有向统计只沿存储箭头；无向路径按反向等价除2；inverse遍历计数=无向计数×2，仅为计算视图。端点相同但关系不同的边在节点路径统计不重复，在关系序列统计可区分。各文档分布见`analysis/full_documents.json`和`train_documents.json`，关系分布见`analysis/raw_structure.json`。\n\n比较边界：正式expanded1456旧审计最大语义组件为54个实体；这里只沿用该已存在结果定位规模变化，没有重新审计或读入其他历史图谱。不能把raw新增候选当作已确认知识。\n')
    save(EXP/'GRAPH_BUILD_PROTOCOL.md','# 记录图、计算图与遮蔽协议\n\n'+premise+f'领域Git对象：`{I.REV}`。读取器复用`kg_enhancement_task_comparison/code/inputs.py`；身份并查集与20字元引文片段函数复用原pilot代码。冻结989/187/224 Claim划分不变；测试事实只用于行政屏蔽，不生成测试排名。\n\n1. 以现有7177项模型实体顺序为前缀，补全全部规范化记录的端点，得到9021项目录；前2150项为固定答案目录。原始surface/type/relation、条件、适用范围、来源和旧状态保存在记录层。\n2. 所有8003条记录先进入记录层；相同有向三元组映射到一条计算边，保留所有record ID和各来源。Schema不兼容、隔离及拒绝状态不被用于图筛选或路径打分。\n3. 复用冻结行政屏蔽：留出别名无序端点对（任何关系及反向）、来源页、原生单元、20字元相同引文、长端点引用。图先遮蔽，桥和路径后建立。\n4. 额外保守副本筛查：同类型端点中，两端BGE余弦≥.95，或一端已有别名相等且另一端≥.90；关系无关、允许反向。它只作行政copy-risk屏蔽，不将近义风险当成真实同义标签，也不合并实体。新增屏蔽{graph["new_copy_risk_records"]}条记录；阈值先于模型排名结果固定。\n5. 训练基础边也必须有不被屏蔽的来源；不是只删引文而保留同页上下文边。保留{graph["safe_base_context_edges"]}条基础上下文边，与{graph["train_raw_dedup_edges"]}条raw边合并为{graph["train_union_edges"]}条边。训练监督元数据989条原样保留，但不把所有989条当作可见邻接。\n6. 每条计算边生成两个遍历视图；inverse关系具有独立向量和方向标记，不发布为第二条事实。\n\n'+table([dict(item='all normalized records',n=8003),dict(item='visible normalized records',n=graph['train_visible_records']),dict(item='visible Schema-incompatible records retained',n=graph['visible_schema_illegal_records']),dict(item='visible all-status deduplicated raw edges',n=graph['train_raw_dedup_edges']),dict(item='safe base contexts',n=graph['safe_base_context_edges']),dict(item='union context edges',n=graph['train_union_edges'])],['item','n'])+f'\n旧状态的可见分布：`{canonical(graph["visible_statuses"])}`。屏蔽原因可重叠，不能相加当不同记录总数。\n\n血缘：ID/legacy/previous/parent链可确定连接7991条规范化记录至7991行原导出；12条规范化记录没有该ID链，16行原导出未被该链覆盖。它们没有被删除，保留独立PDF/页/引文来源和未决血缘，不用语义猜测补齐。详见`verification/raw_export_lineage.jsonl(.gz)`。\n\n**模型缓存边界**：复用历史G1/G2权重及特征，未声称它们已对本轮更强屏蔽“反学习”。旧模型的989训练标签中543条没有符合本轮要求的安全上下文，另20条触发新的近义风险（有重叠）；它们仍可能影响历史权重。旧保守候选中9条计算边也命中新近义风险。因此主表是相同历史底座上的严格上下文遮蔽开发对照，不是重新训练后无任何隐性副本风险的基准。另有无标签训练的冻结BGE sanity面板隔离这一影响。该限制使正增益也不能直接升级为独立泛化结论。\n\n**权重与内容不同**：索引仅使用允许的实体标签和(h,r,t)短文本；没有编码留出原引句。未确认raw记录只作上下文，未转作新的正确监督。conditions/polarity保存在来源中，本轮打分未实现其跨边逻辑合取。\n')
    support=path['exact_real_support'];loo=seq['training_loo'];covrows=[dict(bridge=k,**v) for k,v in diag['path_coverage'].items()]
    save(EXP/'MULTIHOP_PATH_ANALYSIS.md','# 多跳结构是否覆盖待补全目标\n\n'+premise+f'完整raw图有{st["full"]["directed_simple_node_paths_2"]}条原向2跳、{st["full"]["directed_simple_node_paths_3"]}条原向3跳节点路径；训练图分别{st["train"]["directed_simple_node_paths_2"]}/{st["train"]["directed_simple_node_paths_3"]}。允许inverse遍历后训练图有30620/92732条无向节点简单路径。关系标签平行边单独计数时见`analysis/full_relation_sequences.csv`、`train_relation_sequences.csv`，不能与节点路径数混用。\n\n'+table([dict(view=view,length=L,**v) for view,ls in seq.items() if view in ['full','train'] for L,v in ls.items()],['view','length','all_oriented_labelled_paths','schema_compatible_paths','original_direction_only'])+f'\n合法序列指每条原边满足原有Domain/Range，不保证组合语义成立。诊断关系共现见`analysis/diagnostic_role_cooccurrence.csv`。\n\n验证187条关系：0条残留直接目标边，0条有真实2跳连接目标，只有{support["three_hop"]}条有真实3跳连接目标。端点分层：{canonical(support["endpoint_status"])}。精确覆盖在任何Beam/TopK截断前计算，说明目标覆盖不足不只由搜索上限导致。\n\n训练989条在逐组去除自身端点对、来源页和相同引文后，0条有直接边，{loo["two_hop"]}条有2跳目标连接、{loo["three_hop"]}条有3跳目标连接；两类可重叠，不能相加。来源`analysis/training_leave_group_out.jsonl`。这些是训练诊断，不是新监督标签。\n\n有界搜索后374个头/尾方向的目标可达性：\n\n'+table(covrows,['bridge','directions','any_answer_path','target_reached','target_reached_with_2plus_real','target_reached_only_virtual_single_real'])+'\n“any_answer_path”表示到某个目录答案，不表示到真实目标。B3的90个可达方向中87个只有一条业务边加虚拟桥；这接近端点迁移而非多关系组合。包含≥2条业务边的目标方向只有3个。该事实是判断多跳必要性的主要约束。\n\n本轮已额外执行4跳有界诊断：328个查询key能生成含至少2条业务边的4跳路径；没有据此追加验证调参或宣称覆盖真实目标。这仍不能把“有路径”当“有用路径”。\n\n结论：8000级候选确实增加非平凡图结构，未相应覆盖当前严格来源遮蔽的恢复目标。全图路径数量增加和有效补全信号增加是两件需要分别测量的事。\n')
    bridge_rows=[dict(kind=k,**s) for k,s in idx['bridges'].items()]
    save(EXP/'BRIDGE_DISCOVERY.md','# 跨组件虚拟关联桥\n\n'+premise+'冻结BGE实体向量复用7177项；桥候选节点仅含训练活跃实体及固定2150答案标签，共7165项。其他因留出屏蔽失活的raw-only端点不进入桥索引。每源节点先取跨组件语义Top24，余弦下限.60，再取Top4；语义相似节点不合并ID。\n\n- B0：无桥。\n- B1：实体余弦。\n- B2：.75×余弦+.15×同类型指示+.10×有向关系角色profile余弦。\n- B3：.65×余弦+.15×同类型+.10×角色profile+.10×相邻节点profile均值的余弦。\n\nprofile使用全部遮蔽后候选，原关系方向与inverse分开计数，再L2归一化。没有旧状态权重。冷节点结构profile为0，同类型只作软排序。桥记录包含两端原组件ID、分项评分、来源方法；不是确认等价或业务关系。\n\n'+table(bridge_rows,['kind','directed_proposals','unique_undirected_pairs','source_nodes','mean_semantic_cos','type_match_fraction'])+f'\n原随机对照匹配28286条有向提议、源节点和目标类型，但对称去重后边数不同，故另执行**有效边数+每节点度数+类型对分布严格匹配**的随机重连：{rand["unique_bridges"]}条，与B3完全相等；成功交换{rand["successful_swaps"]}次，仍保留{rand["remaining_original_pairs"]}条原配对。其MRR={rand["result"]["MRR_mean"]:.6f}，目标可达{rand["target_reached"]}/374。实际负对照以此为主；原随机行也完整保留。\n\n桥被双向遍历后，单节点可被他人的Top4指向，不能声称遍历度≤4；实际搜索每节点最多展开16条候选，Beam48、最多3跳、每查询384条保存上限、最多2条虚拟边、禁止连续虚拟边及节点环。所有截断数和成本保留在`paths/freeze.json`。\n\nB1/B2均未预设弱于B3：实际MRR分别0.253101/0.253271，B3为0.252335，增加局部pattern没有收益。桥记录及其原组件ID证明虚拟跨组件检索，不证明语义同一或因果推导。\n')
    save(EXP/'PATH_SCORING_METHOD.md',r'''# 路径表示与轻量评分

本实现是独立的无参数路径特征/重排适配，不是PCCA、Bi-GAT或Prob-CBR的作者代码复现，也不宣称原创算法已经成立。

设路径p=(e0,l1,e1,...,lL,eL)，L≤3。业务边标签含原向/逆向遍历；虚拟桥另记为v，不映射成业务关系。

1. 冻结BGE节点分数：

   N(p,q)=0.5 cos(E(e0),E(e1))+0.5/L Σ(i=1..L) cos(E(ei),Q_BGE(h,r))。

2. 去掉虚拟桥标签，保留k个有向业务关系，按真实次序形成：

   R(p)=normalize(Σ(j=1..k) j·V(lj))，C(p,q)=cos(R(p),V(r))。

   位置系数j使其非交换，但这只是向量启发式，不是已学习的逻辑组合；单业务边路径根本无法检验关系顺序。

3. 联合分数：

   s(p,q)=0.5N+0.5C−0.05×虚拟边数。

4. P0不使用路径；P1仅N；P2仅C；P3在B0真实路径上联合N/C；P4允许桥接后联合N/C。每种bridge的候选池固定，消融重排使用同一池，不向搜索器传递隐藏答案。候选Beam本身使用该联合启发式，因此“重排去关系”不等于“整个搜索过程从未使用关系”；结论限于同池的评分贡献。

5. 控制：统一分数.65；最佳单路径；真实两/三业务边；仅桥接；2跳或3跳；保持原池但反转业务关系次序；将终点替换为固定答案目录中的同类型随机实体。合成控制不是已证实错误事实。

6. `no_relation_sequence`是重新定标的node-only基线，会同时去掉桥罚，不能单独用于严格因果归因。因此另运行`no_relation_fixed_scale`：0.5N+0.5×0.65−0.05×虚拟边数，其余候选池、节点系数、桥罚和聚合完全相同。

表中所有方法无新的路径训练参数，未给不确定候选赋“正确”标签。只有在同池强对照和顺序负对照显示可信正信号时才训练小评分器；本轮未满足，故未启动新的神经网络训练。

主函数：`path_search.Paths.search`、`relation_feature`、`run_completion.path_support`、`controlled_relation_ablation.main`。实际路径ID和分项分数在`paths/*.npz`；使用索引见`completion/*_support.npz`和`analysis/case_records.jsonl`。
''')
    save(EXP/'COMPLETION_METHOD.md',r'''# 多路径协同补全：实际计算流程

固定2150答案目录，以相同冻结SimKGC G2双塔特征为底座。先构图和行政遮蔽，再建桥/生成路径。未确认候选既不转为监督正例，也不作为事实发布。

对查询(h,r,?)，文本分数b(t)=Q_SimKGC(h,r)^T E_SimKGC(t)。对每个可达目录终点t，取同一路径池中评分最高的至多8条不同节点/边/有向关系序列路径，定义

    a(p)=exp(clip((s(p,q)−0.65)/0.1,−10,10))
    A(t)=Σ_p a(p),    U(t)=A(t)/(1+A(t))
    f(h,r,t)=b(t)+λU(t)

无路径时U(t)=0；整查询没有目录终点路径时所有文本分数及排序严格不变。U是有界支持特征，不是事实正确概率；共享证据路径仍可能相关，因此设置Top8，未声称统计独立。原始Assertion重复不产生重复计算路径。

λ∈{0,.05,.1,.2}。每方法只选一个三种子平均验证MRR最优λ，平局取最小值；全部网格和所有种子保留。另给同一full λ=.1的消融，防止各消融独立选参造成比较误读。没有用测试选模型。

匹配raw transport_R3保留原查询端点迁移：u_i=E(b_i)−E(a_i)+E(h)，带null的softmax(s_i/.1)加权，q'=normalize(q+αΣw_i u_i)，分数q'^T E(t)。原R3的类型/角色掩码仅在查询检索阶段应用，不删除研究图的非法边；另保留不应用该硬掩码的raw_soft对照。结构距离及profile均来自相同5055边raw训练池。普通semantic kNN按.6×短边文本相似+.4×锚点相似检索，在目录终点上进行概率记忆插值。

历史R3使用另一套4660边合法索引，仅作明确标记的重放参考；不能用它与新路径池的差分声称算法增益。G1/G2使用原作者SimKGC模型/对比logits、本地BGE与采样适配，本轮复用三种子缓存，没有伪称重新训练或完整原论文复现。

```mermaid
flowchart LR
  A[8003记录与来源] --> B[先屏蔽留出副本/页/单元]
  B --> C[有向原始边与inverse遍历视图]
  C --> D[独立虚拟桥层]
  C --> E[有限真实路径]
  D --> F[含虚拟桥的路径]
  E --> G[同池节点/有向序列评分]
  F --> G
  G --> H[Top8终点支持]
  I[冻结SimKGC文本分数] --> J[有界加性重排]
  H --> J
```

评价：374个头/尾方向、334个查询key，平均处理1e-8数值并列；按989训练+187验证已知答案过滤其他真项，保留当前目标。候选答案不做强制Schema裁剪，以便报告top1类型合规。95%区间来自133个事实/来源组的2000次成对重采样；先跨种子平均RR，再按组重采样。它不校正验证选参，也不是事实准确率的置信区间。
''')
    chosen_names=['SimKGC_G1','SimKGC_G2','transport_R3_historical','transport_R3_raw','transport_R3_raw_soft','semantic_knn_raw','P3_joint_real','P4_B1','P4_B2','P4_B3_full','best_single_path','real_multiedge_only','shuffle_relation_order','random_degree_matched','no_relation_fixed_scale']
    summaryrows=[{k:(float(v) if k!='method' else v) for k,v in dd[n].items()} for n in chosen_names]
    save(EXP/'ERROR_ANALYSIS.md','# 失败机制与评价限制\n\n'+premise+'1. **真实目标路径稀缺**。187条验证关系仅1条有真实三跳连接；增加raw图的非目标路径无法替代目标支持。B3真实多业务边到目标只有3/374方向。\n2. **虚拟桥主要是语义端点迁移**。B3可达目标90方向中87方向只有一个业务关系，不能称多关系推理。\n3. **关系顺序证据弱**。保池反转后MRR0.252098，full0.252335，差0.000237。大部分有效路径只有一个业务标签，本来就不受顺序反转影响。\n4. **多路径聚合未增益**。最佳单路径0.252659略高于full；候选路径共享来源且可能重复语义。Top8上限并未证明能解决相关路径累积。\n5. **额外结构特征未增益**。B1/B2均略高于B3。精确度数/有效桥数匹配的随机对照0.245381，说明语义桥有一定非随机作用，但仍没超过同池R3。\n6. **条件/型号/否定没有跨路径一致性解码**。原字段保留不代表模型已经使用。相同类型、相似语义与可定位引文不能证明组合主张；未给任何新边事实认证。\n7. **角色风险仍在**。最终top1类型不合规率见CSV，各种子full为28/374、28/374、31/374；不合规是可执行类型错误，合规不等于语义正确。排名退化不等同事实错误。\n8. **截断与桥数量**。TopK/Beam会漏掉路径；但全图精确可达性也只支持1条验证关系，故不能把主要问题都归于Beam。随机提议数匹配与有效边数匹配分开报告。\n9. **数据和权重不独立**。15份手册和旧验证页已反复分析；复用权重不能消除新声明的近义副本风险。冻结BGE sanity面板无领域标签训练，其结果不能替代强模型新独立验证。\n10. **无Gold的新增预测**。334个查询的未过滤top1中74个基础图已有、1个raw精确键已出现、259个超出两者精确键。该分类未做语义等价闭包；259不是新事实。20个高分新键仅做离线词面证据检索，0条被本轮认证为事实；同训练来源片段明确标记，未冒充独立证据。\n\n对应逐查询记录：`completion/query_ranks.jsonl.gz`；路径分层：`analysis/path_strata.csv`；来源案例：`PATH_CASEBOOK.md`；证据检索清单：`analysis/novel_prediction_evidence.jsonl`。没有以增加输出数量证明质量提升。\n')
    full=dd['P4_B3_full'];fixed=csvrows(EXP/'completion/ablations_shared_alpha.csv')
    save(EXP/'FINAL_REPORT.md','# RP1原始候选图—虚拟桥—多路径补全：实际实验结论\n\n'+premise+'**本阶段已完成代码实现和三种子实测。raw图结构显著增强，语义桥改善部分恢复排名；完整多路径原型未优于相同候选池的transport_R3，尚不支持把有向多关系组合或多路径协同认定为有效的独立算法创新。**\n\n## 实验范围与数据\n\n8003记录→7583完整计算边→5279遮蔽后记录→5050raw边，合并安全基础上下文为5055边；9021全实体，固定2150答案。保留950条Schema不兼容可见记录，无旧状态准入筛选。15份构建手册，领域对象和输入哈希见`verification/domain_inputs.json`。\n\n冻结989/187/224任务不变，主实验仅187验证Claim的374个预测方向，不生成新测试结果。三种子为16112026/27/28。复用历史作者模型适配版SimKGC G1/G2的权重和特征，路径原型新训练参数0；所有主对照在相同缓存底座与固定答案目录比较。历史缓存具有比本轮上下文更宽的训练边界，详见`GRAPH_BUILD_PROTOCOL.md`，不能声称已彻底消除近义训练副本风险。\n\n## 实际量化结果\n\n'+table(summaryrows,['method','alpha','MRR_mean','MRR_seed_sd','Hits1_mean','Hits3_mean','Hits10_mean'])+'\n完整原型相对同池raw-R3：ΔMRR='+f'{float(full["transport_R3_raw_delta_MRR"]):.6f}，成对组重采样95%区间[{float(full["transport_R3_raw_ci_low"]):.6f},{float(full["transport_R3_raw_ci_high"]):.6f}]。区间跨0，不能宣称超过；也不把此区间当独立检验或证明二者等效。\n\n'+table([{k:(float(v) if k in ['MRR','Hits1','Hits10'] else v) for k,v in x.items()} for x in seedrows if x['method'] in ['SimKGC_G2','transport_R3_raw','P4_B3_full']],['method','seed','MRR','Hits1','Hits10'])+'\n种子26的full高于raw-R3，但另两种子低于它，不能只展示种子26。\n\n## 路径是否提供真正组合\n\n完整raw图最大组件3082实体；严格遮蔽后1820实体。全图确实增加结构，但验证目标仅1/187有真实三跳连接，0/187有真实两跳。B3把到真实目标的方向数提升到90/374，其中87只有单业务边迁移、3涉及至少两条业务边。关系顺序反转、单路径和无关系重排控制不支持稳定的组合增益；详见`MULTIHOP_PATH_ANALYSIS.md`及`ABLATION_RESULTS.csv`。\n\n## 本阶段决策\n\n不追加大型GNN、Transformer或小神经路径评分器训练。本轮正信号是“语义桥与原始候选上下文可改善部分文本排名”，尚未通过更强的匹配R3与顺序控制检验；没有足够证据证明扩大网络会解决瓶颈。保留完整负结果、代码和三种子，而不是选出最优种子作创新结论。\n\n下一次算法修改若继续，应首先在**训练事实留组外**统计关系序列的选择性（同一序列对不同目标关系的区分，和类型/节点相似基线相比），并只对至少两业务边且设备/条件一致的路径学习贡献；当前训练留组外也仅4条有2跳、19条有3跳，评价支持不足，不能立即宣称足以训练或复现Prob-CBR。单业务边桥接支路作为transport强对照保留，不能再包装成多跳。该判断保持既定补全方向，不回退A～E任务排名，也不产生未经验证的新图谱版本。\n\n## 结果边界与交付\n\n无新增确认知识，模型分数不是真实概率；基图和自动参考不是专家Gold。条件/时序未实现跨边合取，虚拟桥不是实体同一关系。全部图/路径/评分/融合和阴性对照已实际运行；本阶段未进行外部LLM调用或新的神经训练。\n\n'+f'9项不变量检查通过；保全核对{checks["preservation"]["prior_files_checked"]}个既有文件尺寸与mtime无变化，使用的缓存和24个领域输入另作SHA256复核。正式图谱、RP2/RP3、旧模型均未修改。详细复现命令见`REPRODUCE.md`，逐查询、逐路径、分层和成本文件均保留。\n\n![MRR与三种子标准差](figures/validation_mrr.svg)\n\n![目标路径组成](figures/target_path_coverage.svg)\n')
    save(EXP/'RELATED_WORK.md','# 方法身份及与已有研究的区别\n\n2026-11-17定向核对原论文页面。\n\n- [SimKGC, ACL 2022](https://aclanthology.org/2022.acl-long.295/)：文本对比知识补全。复用仓库既有作者模型适配缓存；本轮未重训，不以换底座或缓存复用主张创新。\n- [Probabilistic Case-based Reasoning, Findings EMNLP 2020](https://aclanthology.org/2020.findings-emnlp.427/)：从相似实体收集推理路径、估计路径对于关系查询的效果。相似实体＋路径＋关系预测不是新范式。本轮没有复现其统计概率模型，只做BGE虚拟桥与位置加权向量、终点有界加性重排的轻量启发式适配。\n- PCCA/Bi-GAT只作为用户指定的研究思想参照；本轮没有声称使用其公式或作者实现，也没有以模块命名证明创新。\n\n潜在差异在于带状态但不以状态门控的多来源raw图、先屏蔽来源副本再建桥、显式区分单边语义迁移与多业务边组合的适配与评价。本轮实验不支持把这些适配认定为已经有效的新核心算法；尚无超过同池R3的稳定收益。没有开展穷尽查新，也没有声称优于未实际运行的公开方法。\n')
    commands=['build_graph.py','vector_bridges.py','path_search.py','sequence_audit.py','run_completion.py','matched_random_control.py','controlled_relation_ablation.py','diagnose.py','prediction_traces.py','verify.py','write_reports.py','package.py']
    save(EXP/'REPRODUCE.md','# 复现、缓存与保全\n\n服务器仓库根目录运行，使用已有`.venv/bin/python -B`。没有外部API依赖；需要Git锁定对象、15份解析页、本地BGE和历史SimKGC特征缓存。GitHub不上传模型权重或147MB可重建向量；它们保留在服务器，不删除。\n\n核对既有结果：\n\n```bash\nOPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/verify.py\n```\n\n在新的独立子目录完整重算（先指定未使用过的名字，不覆盖本次结果）：\n\n```bash\nexport RP1_RAW_RUN_DIR="$PWD/results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/replays/your_unique_run"\n'+''.join('OPENBLAS_NUM_THREADS=4 .venv/bin/python -B results/experiments/research_point_1/kg_raw_multihop_enhancement_v1/code/'+x+'\n' for x in commands)+'```\n\n阶段完成标记会复用自身结果；不同输出不会静默覆盖。`run_pipeline.py`可按上述顺序执行并保留新运行stdout日志。磁盘保留两种大表副本：本地完整JSONL、Git压缩JSONL.gz；读取器支持后者回退。路径NPZ和用于重算排名的小型支持矩阵随成果提交；大向量/旧模型用来源路径与SHA256清单复用。\n\n主要输入：`kg_query_aware_completion_v1/features/G1_s{seed}.pt`、`G2_s{seed}.pt`、`index/vectors.pt`、冻结data与administrative blockers。本地encoder=`data/model/BAAI-bge-small-zh-v1.5-r7999e1d`。锁定领域读取器来源对象为833c8040058055434c7f6a9595ec524c3935755f。作者SimKGC CustomBertModel来源提交97cc43e488f19ca5b0f6fbf60ffefd2ee56c0693，作者文件与原适配代码原样保留。\n\n`logs/environment.json`记录执行环境；阶段wall time来自各自完成元数据，分别含数据读取/加载/检索等，不是在线延迟或独占硬件吞吐。初次交互工具stdout未逐条转写为伪造日志，已保留实际逐阶段完成摘要；未来新运行使用pipeline保存stdout。\n\n结构数复查：`build_graph.stats`与`sequence_audit.seq_counts`，独立枚举小循环图/平行边/self-loop交叉校验。早期辅助`analysis/relation_sequences_2.csv`未排self-loop，保留作生成记录；正式序列统计统一使用`analysis/{full,train}_relation_sequences.csv`，已排self-loop。它们不参与任何模型打分。\n')
    casebook(cat,edges);plots(base,abl)
    for svg in (EXP/'figures').glob('*.svg'):
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()).rstrip()+'\n')
    # Only hashes/versions and resource summary, never environment credentials.
    import torch
    env=dict(python=platform.python_version(),platform=platform.platform(),torch=torch.__version__,cuda=torch.version.cuda,cuda_available=torch.cuda.is_available(),cpu=platform.processor(),source_checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader'],text=True).strip())
    save(EXP/'logs/environment.json',env)
    save(EXP/'logs/stage_completion_summary.json',dict(build=graph,index=idx,paths=path['summaries'],completion_seconds=cf['wall_seconds'],completion_cost_seconds=cf['cost_seconds'],random_matched=rand,external_api_calls=0,new_neural_training_runs=0,description='measured completion metadata; not fabricated original stdout'))
    save(EXP/'verification/reports_complete.json',dict(required_reports=12,scientific_figures=2,actual_data_only=True))
    print('Rendered all required reports and 2 standalone scientific figures',flush=True)

if __name__=='__main__':main()
