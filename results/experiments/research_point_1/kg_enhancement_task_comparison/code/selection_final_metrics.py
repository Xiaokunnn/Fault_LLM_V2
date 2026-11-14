"""Conservative final verdicts, final metrics, and a source-linked delta casebook."""
from collections import Counter
import copy
import json
import sys

from inputs import ROOT,load,save,norm
from selection_screen import OUT,read
from selection_overlay import SANDBOX
from selection_evaluate import summary_rows


def main():
    sys.stdout.reconfigure(encoding='utf-8');d=load()
    a=read(OUT/'review/A_decisions.jsonl')
    amendments=[]
    for r in a:
        if r['case_id']=='A-RAW-00670':
            amendments.append({'case_id':r['case_id'],'previous_support':r['support'],'final_support':'insufficient_evidence',
                'reason':'A definition does not establish the inspected_by interpretation with sufficient certainty, but does not explicitly negate it. Conservative unresolved verdict rather than a proved error.'})
            r['support']='insufficient_evidence';r['reason']=amendments[-1]['reason']
    save(OUT/'evaluation/final_A_decisions.jsonl',a)
    save(OUT/'evaluation/conservative_verdict_amendments.json',amendments)
    comparison=read(OUT/'evaluation/task_comparison.json');comparison['A']=summary_rows(a)
    save(OUT/'evaluation/FINAL_TASK_COMPARISON.json',comparison)
    snapshot=read(OUT/'evaluation/quantitative_snapshot.json');snapshot['A']=comparison['A']
    snapshot['original_publication_loss']=read(OUT/'evaluation/publication_loss_summary.json')
    snapshot['stronger_endpoint_control']=read(OUT/'evaluation/endpoint_control_summary.json')
    additions=read(SANDBOX/'delta_assertions.jsonl')
    new={r['sandbox_claim_id']:r for r in additions if r['new_claim_relative_to_base']}
    snapshot['new_claims_by_relation']=dict(Counter(r['relation'] for r in new.values()))
    snapshot['trial_assertion_support_counts']=dict(Counter(r['source_support'] for r in additions))
    snapshot['final_sandbox_directory']='sandbox_v2'
    snapshot['all_additions_pending_original_chinese_publication_and_full_pipeline']=True
    save(OUT/'evaluation/FINAL_METRICS.json',snapshot)
    manifest={r['doc_id']:r for r in d['manifest']}
    lines=['# 本轮试验增量逐案证据','',
      '22条试验Assertion对应19个新增Claim和2条现有Claim的新增证据；同一新增Claim可能有多条来源Assertion。',
      '这是当前AI非盲原文审查后的沙盒结果，不是专家Gold，也不是已通过完整正式发布流程的图谱。',
      '读取规则：先看条件，再看关系；原有文档/页哈希与原始候选保留在JSONL中。','']
    for r in additions:
        file=(ROOT/'data/source_docs/marine_pump/raw'/manifest[r['doc_id']]['file_name']).as_posix()
        lines += ['## '+r['case_id'],'',
          f"关系：{r['head_canonical_zh']} —{r['relation']}→ {r['tail_canonical_zh']}。",'',
          f"来源：[{r['doc_id']}，物理页 {r['pdf_page_number']}](<{file}>)；Claim `{r['sandbox_claim_id']}`。",'',
          '计数：'+('新增试验Claim的来源Assertion' if r['new_claim_relative_to_base'] else '现有Claim新增来源，不计新Claim')+'。','',
          '适用条件：`'+json.dumps(r['qualifiers'],ensure_ascii=False)+'`','',
          '原文依据：','']
        for p in r['source_proofs']:
            s=p['proof'];ws=s.get('witnesses',[s])
            text=' '.join(w['text'].strip() for w in ws)
            lines.append(f"- {p['doc_id']} 物理页 {p['page']}：{text}")
        lines+=['','程序保留的原生单元ID/字符偏移见 `sandbox_v2/delta_assertions.jsonl`。','']
    save(OUT/'CASEBOOK.md','\n'.join(lines))
    print('Final A source verdicts:',comparison['A']['support_status_counts'])
    print('New Claims by relation:',snapshot['new_claims_by_relation'])


if __name__=='__main__':main()
