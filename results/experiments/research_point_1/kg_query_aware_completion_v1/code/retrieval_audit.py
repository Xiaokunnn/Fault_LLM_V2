"""Supplement raw adjacency with eligible-query strata and mismatch diagnostics."""
from collections import Counter,defaultdict
import numpy as np
from io_utils import *
from build_index import edge_sources


def main():
    cat=read(EXP/'data/catalogue.json');n=cat['nbase'];R=len(cat['relations']);edges=read(EXP/'index/edges.jsonl');views=read(EXP/'index/oriented_views.jsonl');examples=read(EXP/'retrieval/train_example_keys.json');registry=read(EXP/'data/training_source_registry.json')
    old=np.load(EXP/'retrieval/R0_all_train.npz')['ids'];empty=old[:,0]<0;used0={int(v)//2 for v in old.ravel() if v>=0 and not edges[int(v)//2]['is_base']}
    table=[];cases=[]
    anchor_scopes=defaultdict(set)
    for e in edges:
        if e['is_base'] or e['conservative']:
            for s in edge_sources(e,registry):
                scope=I.norm(s.get('pump_type'))
                if scope:
                    for h in [e['triple'][0],e['triple'][2]]:anchor_scopes[h].add(scope)
    for strategy in ['R0','R1','R2','R3']:
        ids=np.load(EXP/'retrieval'/f'{strategy}_all_train.npz')['ids'][:,:16]
        use={int(v)//2 for v in ids.ravel() if v>=0 and not edges[int(v)//2]['is_base']};nz=ids[:,0]>=0
        mismatch=0;direction_different=0;same_relation=0;total=0;scope_known=0;scope_mismatch=0;address=0;cand=0
        for ex,row in zip(examples,ids):
            h,r,y,cid=ex;range_=cat['registry'][cat['relations'][r%R]]['domain' if r>=R else 'range']
            for view in row[row>=0]:
                v=views[int(view)];e=edges[v['edge_index']];total+=1
                bad=cat['entities'][v['anchor']]['entity_type']!=cat['entities'][h]['entity_type'] or cat['entities'][v['neighbor']]['entity_type'] not in range_
                mismatch+=bad;same_relation+=v['relation']==r;direction_different+=(v['relation']>=R)!=(r>=R)
                ss=edge_sources(e,registry);possible={I.norm(s.get('pump_type')) for s in ss if s.get('pump_type')}
                if len(anchor_scopes[h])==1 and possible:
                    scope_known+=1;scope_mismatch+=not bool(anchor_scopes[h]&possible)
                if not e['is_base']:
                    cand+=1
                    address+=any(s.get('native_address',{}).get('exact_contiguous_offset') or s.get('native_address',{}).get('all_provided_cells_match') or s.get('native_address',{}).get('all_native_witnesses_match') for s in ss)
                if bad and len([c for c in cases if c['strategy']==strategy])<3:
                    cases.append(dict(strategy=strategy,query_anchor=cat['entities'][h]['label_zh'],query_relation=cat['relations'][r%R],query_inverse=r>=R,view=v,edge=e,source=ss[:1],explanation='Schema role incompatible with this query; not proof the candidate itself is false'))
        table.append(dict(strategy=strategy,training_queries=len(examples),eligible_R0_empty=int(empty.sum()),nonempty_rate_among_eligible_R0_empty=float(nz[empty].mean()),nonempty_rate_among_eligible_R0_nonempty=float(nz[~empty].mean()),used_candidates_not_used_by_R0=len(use-used0),selected_slots=total,query_role_type_mismatch_fraction=mismatch/max(1,total),different_direction_fraction=direction_different/max(1,total),same_directed_relation_fraction=same_relation/max(1,total),unique_training_scope_comparable_slots=scope_known,scope_signature_disjoint_fraction=scope_mismatch/max(1,scope_known),candidate_exact_address_check_fraction=address/max(1,cand)))
    csvsave('retrieval/eligible_strata_and_mismatches.csv',table);save(EXP/'retrieval/role_mismatch_cases.jsonl',cases)
    save(EXP/'retrieval/audit_notes.md','''# 检索统计口径补充

主RETRIEVAL_RESULTS.csv的no_direct_adjacency是未作查询自排除的原始邻接；每个训练事实自身构成邻接，所以该列为0，不能据此说所有查询都有可用邻域。eligible_strata_and_mismatches.csv改用相同查询自排除后的R0空上下文分层，才对应可用直接邻接不足。

same_directed_relation是检索一致性诊断，不是相关性真值；不同关系也可能有帮助。query_role_type_mismatch表示候选方向下端点类型不能直接充当该查询角色，亦不表示候选事实为假。scope_signature_disjoint只针对训练可见查询锚点恰有一个型号签名且候选有型号签名的情况，不使用目标来源；跨型号知识可能可迁移，所以不是已确认范围错误。location/entailment合同及原生地址检查都不是人工事实正确率。
''')
    print(table,flush=True)


if __name__=='__main__':main()
