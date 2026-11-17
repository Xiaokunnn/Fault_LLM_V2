"""Deterministic post-test recovery/negative-transfer cases with real sources."""
from collections import defaultdict
from collab_io import *


def main():
    cases=[]
    for dataset in ['cold','structured']:
        root=STUDY/dataset;cat=read(root/'data/catalogue.json');sources=defaultdict(list)
        for r in read(root/'audit_only/base_source_records.jsonl'):sources[r['expanded_claim_id']].append(r)
        full=read(root/'evaluation/collab_full_s14112026/rankings.jsonl')
        base=read(root/'evaluation/simkgc_G2_s14112026/rankings.jsonl');lookup={(r['id'],r['task']):r for r in base}
        for category,predicate in [('recovery',lambda a,b:a['rank']==1 and b['rank']>1),('negative_transfer',lambda a,b:b['rank']==1 and a['rank']>1),('schema_violation',lambda a,b:not a['top1_schema_valid'])]:
            selected=sorted([r for r in full if r['task']!='relation' and predicate(r,lookup[r['id'],r['task']])],key=lambda r:(r['id'],r['task']))[:3]
            for r in selected:
                h,rel,t=r['triple'];old=lookup[r['id'],r['task']]
                cases.append(dict(dataset=dataset,category=category,claim_id=r['id'],task=r['task'],target=[cat['entities'][h]['label_zh'],cat['relations'][rel],cat['entities'][t]['label_zh']],
                    full_rank=r['rank'],G2_rank=old['rank'],full_prediction=cat['entities'][r['top1']]['label_zh'],G2_prediction=cat['entities'][old['top1']]['label_zh'],
                    full_prediction_type=cat['entities'][r['top1']]['entity_type'],source=[{k:x.get(k) for k in ['doc_id','pdf_page_number','evidence_text','applicability_scope','head_surface','tail_surface','source_family_id']} for x in sources[r['id']]],
                    interpretation='Exact automatic-label recovery/transfer, not verified factual correctness of an unlabelled alternative'))
    save(STUDY/'analysis/ranking_cases.jsonl',cases)
    lines=['# 真实排名收益与失败案例\n','固定第一种子，按记录ID选每类最多3例，不改变模型或分母。源文属于自动目标的出处，不自动证明所有替代预测为假。\n']
    for c in cases:
        lines += [f"## {c['dataset']} / {c['category']} / {c['claim_id']} / {c['task']}",
                  f"目标：{' → '.join(c['target'])}。G2 rank={c['G2_rank']}，full rank={c['full_rank']}。G2首选：{c['G2_prediction']}；full首选：{c['full_prediction']}（{c['full_prediction_type']}）。"]
        for src in c['source']:lines.append(f"原文：{src['doc_id']}物理页{src['pdf_page_number']}，{src['evidence_text']}。适用范围：{src['applicability_scope']}。")
    save(STUDY/'analysis/CASEBOOK.md','\n\n'.join(lines)+'\n')
    print('Saved',len(cases),'source-linked ranking cases',flush=True)


if __name__=='__main__':main()
