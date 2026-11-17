"""Serialize actual executing-AI reading of the 12 fixed MP022 packets.

These explicit judgments were written after reading all native units and their
full pages. Re-running is deterministic serialization, not another evaluation.
"""
from collections import Counter
from collab_io import *


JUDGMENTS={
 'N01':('U','MP022 p15仅要求Always use two drain valves，且限配排液选项；两个阀门实例/位置未给出。Component与Equipment同名不能证明阀门位于另一阀门内，也不能只凭同名断定全局同一实体。','排液选项、两个排液阀及具体实例位置'),
 'N02':('U','p11要求管路正确布置、自支撑并避免对泵施加应力；没有区分两个同名管路实例的包含/位置。可能是名称粒度歧义，不可按名称相同确认或否认所有位置关系。','具体管路/管系实例和空间位置'),
 'N03':('E','p22汽蚀分支列出损伤、压降、噪声等；High liquid temperature位于Cause/result列，且未出现高温报警。把高液温词语替换成高温报警并作为汽蚀表现，当前证据不支持。','区分液体温度工况、报警信号及原因/表现角色'),
 'N04':('E','p28只有Remove screw(23) and safety guard(22)。该页不支持泛称防护罩位于安全防护罩(22)内部；把同页部件称谓当嵌套关系没有来源依据。','部件编号与物理位置关系'),
 'N05':('E','p17多次指同一预检查中的impeller(27)，要求拆叶轮检查转向并有启动禁令。没有叶轮位于另一叶轮内部的证据，泛称/编号称谓不能当作两端空间关系。','叶轮编号与安装前转向检查范围'),
 'N06':('E','p34是装safety guards(22)及螺钉，且说明无冲洗接口时护罩遮住adapter孔；源文没有防护罩包含安全防护罩这层部件关系。','护罩与适配器孔的角色不可改成护罩嵌套'),
 'N07':('E','p32单轴封装配主动作对象是complete shaft seal，stub shaft(7)是安装位置；泛称轴的维护方式不能仅凭onto共现确定为该安装动作。','动作对象/安装位置、单轴封阶段、Connex pin与驱动环缺口'),
 'N08':('E','p22Frequent cleaning对应电机过载下的液体沉积层分支；汽蚀分支对应提高入口压力、降低液温/压降或转速。当前预测跨表格问题分支错配。','维护动作必须绑定正确故障/原因行'),
 'N09':('U','p19是回收处置说明，仅提维修更换oil and wearing parts；没有两个磨损概念的演变时序。FaultMode/FailureMechanism两个同名ID不能证明时间演化。','不同磨损事件/阶段及时间方向'),
 'N10':('U','p22列汽蚀故障及其原因/后果，不给出两个汽蚀概念的演化关系。FailureMechanism/FaultMode类型差异也不是时间先后证据。','故障与机理角色不能直接等同演变时序'),
 'N11':('E','与N03同一p22来源，但头ID是FailureMechanism；类型不同仍不补足高温报警证据，不能把高液温变成汽蚀的报警表现。','实体类型合法不等于关系语义支持'),
 'N12':('E','p22电机过载分支列粘性/高密度液体、低出口压力、沉积物等；高液温属于汽蚀分支，且全文未出现高温报警。属于跨分支和信号语义不支持。','电机过载与汽蚀两行及温度/报警的区分'),
}


def main():
    packets=read(STUDY/'discovery/source_packets.jsonl');assert {x['review_id'] for x in packets}==set(JUDGMENTS)
    reviews=[]
    for packet in packets:
        p=packet['prediction'];grade,reason,required=JUDGMENTS[packet['review_id']]
        reviews.append(dict(review_id=packet['review_id'],prediction_id=p['prediction_id'],head=p['head'],relation=p['relation'],tail=p['tail'],
            grade=grade,reason=reason,required_scope_or_role=required,source_document=packet['source_document'],physical_page=packet['physical_page'],
            source_units=[dict(unit_id=x['unit_id'],text=x['text']) for x in packet['units']],applicability_scope=packet['applicability_scope'],
            score=p['score'],score_change=p['score_change'],novelty=p['novelty'],
            evaluator='Executing Codex AI, actual source reading; not independent-model/human/expert Gold',
            scope='Judgment about given source support, not global factual falsity; purposive changed-score sample',
            document_withheld=True,shared_entity_catalogue=True,known_pretraining_overlap_unknown=True,graph_publish=False))
    save(STUDY/'discovery/AI_source_review.jsonl',reviews)
    for name,grade in [('source_explicit','S'),('source_conditional','C'),('not_supported_by_given_source','E'),('unverified','U')]:
        save(STUDY/'discovery/layers'/(name+'.jsonl'),[r for r in reviews if r['grade']==grade])
    preds=read(STUDY/'discovery/predictions.jsonl')
    same_surface=[p['prediction_id'] for p in preds if I.norm(p['head'])==I.norm(p['tail'])]
    save(STUDY/'discovery/same_surface_diagnostic.json',dict(count=len(same_surface),prediction_ids=same_surface,
        automatic=True,meaning='Potential degenerate/generic-label pairs, not confirmed same physical entities. Original predictions/novelty labels are preserved, never counted as confirmed discoveries.'))
    save(STUDY/'discovery/source_review_summary.json',dict(records=len(reviews),grades=dict(Counter(r['grade'] for r in reviews)),
        complete_new_facts_confirmed=0,formal_graph_changes=0,source_doc='MP022',same_surface_proposals=len(same_surface),
        sampling='Priority beyond-both, largest absolute score changes among source same-page hits; includes negative changes, not a random precision sample',
        negative_score_change_cases=sum(x['score_change']<0 for x in reviews),positive_score_change_cases=sum(x['score_change']>0 for x in reviews),
        inference='Incorrect/unsupported source claims can remain in top3 despite lower score; do not attribute every such error as newly introduced by the adapter'))
    lines=['# 12条新模型预测的实际AI源文核查\n',
       'S=局部完整支持，C=补条件后可能支持，E=当前源文的关系/对象/表格分支不支持，U=实例或时序等证据不足。执行AI实际阅读源文，不是盲态独立模型/专家Gold。全部保留非船舶专用LKH Prime适用范围；不作为总体准确率。\n',
       '| ID | 预测 | 物理页 | 分数 / 相对G2变化 | 判断 | 原因 |','| --- | --- | --- | --- | --- | --- |']
    for r in reviews:lines.append(f"| {r['review_id']} | {r['head']} → {r['relation']} → {r['tail']} | {r['physical_page']} | {r['score']:.5f} / {r['score_change']:+.5f} | {r['grade']} | {r['reason']} |")
    lines += ['\n本组8项E、4项U，没有确认新完整事实。10条错误/未决主张的分数实际上比G2下降，N09/N10分数上升；不能把所有仍在top3的不支持项都归为本算法新引入错误。',
              '这是优先看分数变化且可同页检索的12例，不估计26,328条预测precision。18条全部提议呈现完全同名的两端，已单列自动诊断；不改原输出，不将可能别名当作专家同义真值，也不删除困难样本提高比例。']
    save(STUDY/'discovery/SOURCE_REVIEW.md','\n'.join(lines)+'\n')
    print('Saved12 actual AI source readings',Counter(r['grade'] for r in reviews),flush=True)


if __name__=='__main__':main()
