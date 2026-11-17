"""Actual source-backed proxy examples and reproducible exposure subcategories."""
from collections import Counter
import json
from role_io import *


def main():
    cat=read(RUN/'data/catalogue.json')['entities'];sources=read(OUT/'data/train_evidence_registry.json');cases=[];seen=set()
    for seed in SEEDS:
        for p in read(OUT/f'data/utility_{seed}.jsonl'):
            if not p['strong_contrast'] or p['negative_kind'] in seen:continue
            seen.add(p['negative_kind']);cases.append(dict(p,query_head=cat[p['h']]['label_zh'],positive_prototype=cat[p['neighbor']]['label_zh'],
                negative_prototype=cat[p['negative_neighbor']]['label_zh'],training_answers=[cat[i]['label_zh'] for i in p['positive_tail_ids']],
                original_evidence=sources[p['edge_id']],donor_evidence=sources.get(p['donor_edge_id'],[]),
                training_target_evidence=sources.get(p['training_id'],[])))
    save(OUT/'analysis/source_target_cases.jsonl',cases)
    lines=['# 来源角色与贡献对照的真实样本\n','以下是强对照的源文实例，不是专家标注或真实错误清单；N+是有证据的关系原型而不是待预测答案，N-是受控代理。\n']
    for c in cases:
        lines += [f"## {c['pair_id']} / {c['negative_kind']}",f"查询头：{c['query_head']}。监督尾集合：{c['training_answers']}。N+：{c['positive_prototype']}；N-：{c['negative_prototype']}。边/关系方向编号{c['edge_relation']}→{c['negative_relation']}。冻结贡献：{c['reference_u_plus']:+.6f}/{c['reference_u_minus']:+.6f}。"]
        for label,records in [('参考源',c['original_evidence']),('扰动对象源',c['donor_evidence']),('自动训练目标源',c['training_target_evidence'])]:
            for x in records[:2]:lines.append(f"{label}：{x['doc_id']}物理页{x['pdf_page_number']}：{x['evidence_text']}。原生单元{x.get('evidence_unit_ids',[])}；范围{x.get('applicability_scope')}。")
    lines+=['## 假负例与不可辨识限制',
        '同一故障可有多种有效措施，其他表行的动作并非世界中必然错误。例如“过载—电机振动”可能是未记录的真实机理，仅当前表行不对应；本实验负utility也只表示旧模型下对已知训练尾的不利影响。原型不能因此充当事实真假裁判。',
        '同义答案副本的疑似样本在clean_v2被排除，不改变原事实标签；最大/最小、数值编号和否定不同者不按相似字符串直接合并。仍可能漏掉远距离语义转述，不宣称完美语义去重。',
        '纯条件归属/型号交换若不改变输入，任何新损失都无法区分；该类控制不训练。需要输入可观察性改进时，应独立做输入消融，而不是说本轮已学会条件绑定。']
    save(OUT/'analysis/CASEBOOK_WITH_TARGETS.md','\n\n'.join(lines)+'\n')
    edges={e['edge_id']:e for e in read(RUN/'data/context_edges.jsonl')};counts=Counter();status=Counter();n=read(RUN/'data/catalogue.json')['nbase']
    for x in read(OUT/'data/candidate_exposure_ledger.jsonl'):
        e=edges[x['edge_id']];status[x['primary_reason'],e.get('bucket')]+=1
        if x['primary_reason']=='not_incident_to_supervised_anchors':counts['both_endpoints_outside_base_catalogue' if min(e['triple'][0],e['triple'][2])>=n else 'base_catalogue_endpoint_but_no_training_query_anchor']+=1
    value=dict(counts=counts,status_cross_tab=[dict(reason=k[0],status=k[1],n=v) for k,v in status.items()],interpretation='Adjacency/query coverage causes; statuses are automatic labels and overlap, not truth errors')
    save(OUT/'data/nonincident_detail.json',json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('Saved real source cases and usage subcategories',DATASET)


if __name__=='__main__':main()
