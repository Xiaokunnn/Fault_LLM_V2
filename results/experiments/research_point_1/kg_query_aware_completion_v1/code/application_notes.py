"""Explicit AI analytical notes; no training labels, graph edits or Gold claims."""
from io_utils import *


NOTES={
 'PRED-597e6791bd4a010af3bc':('possible_alias_duplicate','“端盖o型圈或垫片”与“端盖o型圈或端盖垫片”可能只是省略重复修饰语；有限字符串闭包未合并不等于语义新知识。当前没有新源文确认，不能计作已恢复事实。',None),
 'PRED-9e36c7f9c8d76b44e852':('local_support_with_unresolved_test_scope','MP003 p518确有接头组件目视检查，但位于金属管路机械接头试验程序，要求在规定试验上下文检查损伤和泄漏风险。泛化成所有接头日常检查会丢失试验适用范围；该段与训练引文重叠，不是独立证据。',('MP003',518)),
 'PRED-0d78c735747a1e31c935':('local_atomic_wording_support','MP019 p20有“Check for open circuit.”。它支持检查动作的局部文字，但查询的开路实体可能是故障或检查对象角色，原表分支仍需保留；本页已见，不能称独立新事实确认。',('MP019',20)),
 'PRED-05b57e1a6182099b8cef':('remedy_supported_relation_choice_unresolved','MP019 p74电机轴承过热的故障表给出“Diámetro de polea demasiado pequeño / Utilice poleas más grandes.”。措施有原文依据，但属于该过热原因分支；prevented_by与mitigated_by的精确语义及条件完整性未由模型证明。',('MP019',74)),
 'PRED-9c7a6fc965b28b10f9bf':('unsupported_causal_or_alias_restatement','MP022 p22的“Motor overloaded”是故障表的现象，列出的原因是黏液/高密度液、低出口压力等，不能从该词条推出“过载导致电机过载”。这是同义重述/角色混淆风险，未见页也不能作为支持。',('MP022',22)),
 'PRED-17a128c2751da37f757f':('unsupported_direction_and_temporal_relation','MP002 p62描述functional failure是failure mode对系统的影响，p14也说failure mode可能导致functional failure；不支持“功能故障 evolves_to 故障模式”，更不能把概念定义自动变成时序演化。',('MP002',62)),
 'PRED-a2995f59f475ffdee075':('local_support_but_missing_equipment_scope','MP003 p794的冷却故障报警要求属于半导体变流器组件冷却装置，并同时要求自动降低输出电流。局部故障—报警有文字支持，但不能把省略设备/工况后的关系当成已经确认的泵系普适事实。',('MP003',794)),
 'PRED-2b2c352c9b00e0cca3d7':('already_initial_candidate_not_new_discovery','该关系在初始池已有，MP003 p893原引句为its failure is to be alarmed；旧状态candidate_needs_review，semantic contract为undetermined。重复输出不能称模型发现新知识。',('MP003',893)),
}


def main():
    predictions={x['prediction_id']:x for x in read(EXP/'ENHANCEMENT_CASES.jsonl')};d=I.load();out=[]
    for pid,(grade,reason,loc) in NOTES.items():
        p=predictions[pid]
        out.append(dict(prediction_id=pid,head=p['head'],relation=p['relation'],tail=p['tail'],assessment=grade,reason=reason,
            source_location=list(loc) if loc else None,page_hash=d['pages'][loc].get('page_text_sha256') if loc else None,
            evaluator='Codex assistant source-reading analysis, not an independent reviewer model or domain expert',
            expert_Gold=False,used_for_training=False,changes_existing_labels=False,confirmed_new_fact=False))
    save(EXP/'enhancement/ai_case_notes.jsonl',out)
    lines=['# 潜在增强关系：源文回读与边界\n','从150条保存预测中选取八例作AI分析，覆盖字面支持、范围缺失、重复、错误方向和无证据。是定性失败解释，不是随机准确率样本，也不是独立专家裁定；不用于调参或修改标签。\n']
    for x in out:lines += [f"## {x['prediction_id']}",f"{x['head']} → {x['relation']} → {x['tail']}。",x['reason']]
    lines+=['\n131条没有本次有限字面源匹配、18条只有局部共现、1条初始候选匹配，不代表131条必错或18条正确。仅3条命中未见页且引文不与训练文本重叠，其中的因果/演化例已经显示未见证据不等于支持。',
        '当前没有完成独立语义确认的新事实；输出150条是待验证推断数，不是新增图谱知识数。149条“模型独有”只是未被有限别名闭包识别为旧事实/候选，可能包含近义重复。保留这类例子，避免把字符串新颖性当学术发现。']
    save(EXP/'ENHANCEMENT_REVIEW.md','\n\n'.join(lines)+'\n')


if __name__=='__main__':main()
