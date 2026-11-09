"""Compare blinded local-model opinions with provisional v1 labels, not ground truth."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/experiments/research_point_1/scope_repair_v2'
V1 = ROOT / 'results/experiments/research_point_1/loss_page_audit_v1'


def read(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x]


def main():
    completion = json.loads((OUT / 'second_opinion/completion.json').read_text())
    mapping = read(OUT / 'second_opinion/private_mapping.jsonl')
    inputs = {r['blind_id']: r for r in read(OUT / 'second_opinion/blind_inputs.jsonl')}
    judgments = {r['audit_id']: r for r in read(V1 / 'record_findings.jsonl')}
    code = {'supported': 'S', 'unsupported': 'N', 'unresolved': 'U'}
    rows, enriched = [], []
    for m in mapping:
        opinion = json.loads((OUT / f"second_opinion/{m['blind_id']}.json").read_text())
        j = judgments[m['audit_id']]
        source = inputs[m['blind_id']]
        row = dict(blind_id=m['blind_id'], audit_id=m['audit_id'], stratum=m['stratum'],
                   doc_id=j['doc_id'], physical_page=j['pdf_page_number'],
                   first_pass_label=code[j['semantic_support']], second_opinion_label=opinion['label'],
                   model_called=opinion['model_called'], source_was_clipped=opinion['source_was_clipped'],
                   agreement=code[j['semantic_support']] == opinion['label'] if opinion['model_called'] else None,
                   unrestricted_next_token_in_choices=opinion.get('unrestricted_next_token_in_choices'),
                   expert_adjudication='pending')
        rows.append(row)
        enriched.append({**row, 'source': source, 'second_opinion': opinion,
                         'first_pass_note': j['review_note'], 'original_gate_explanation': j['primary_audit_explanation']})
    assert len(rows) == completion['n'] == 26
    assessed = [r for r in rows if r['model_called']]
    summary = dict(n=len(rows), assessed=len(assessed), not_assessed=len(rows) - len(assessed),
                   agreement=sum(r['agreement'] for r in assessed),
                   disagreement=sum(not r['agreement'] for r in assessed),
                   second_opinion_label_counts=dict(Counter(r['second_opinion_label'] for r in assessed)),
                   cross_tab=dict(Counter(r['first_pass_label'] + '->' + r['second_opinion_label'] for r in assessed)),
                   disagreements=[r['audit_id'] for r in assessed if not r['agreement']],
                   clipped_source_contexts=sum(r['source_was_clipped'] for r in rows),
                   unrestricted_next_token_outside_choices=sum(not r['unrestricted_next_token_in_choices'] for r in assessed),
                   model='Qwen2.5-7B-Instruct', method='forced S/N/U next-token classification',
                   api_calls=0, device='CPU FP32', wall_seconds=completion['wall_seconds'],
                   expert_review=False, resolved_ground_truth_disputes=0,
                   limitation='Another model opinion on 26 targeted cases, not an independent expert, full-page visual review, or accuracy estimate. No labels used to tune repair arms.')
    for name, value in [('second_opinion/summary.json', summary)]:
        with (OUT / name).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
    with (OUT / 'second_opinion/comparison.csv').open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (OUT / 'second_opinion/adjudication_packets.jsonl').open('x', encoding='utf-8') as f:
        for r in enriched:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with (OUT / 'second_opinion/disagreement_review.md').open('x', encoding='utf-8') as f:
        f.write('# 待裁定的模型分歧\n\nS=源文支持；N=关系/条件不成立；U=未决。两种 AI 意见均不是真值。\n')
        for r in enriched:
            if r['agreement'] is not False:
                continue
            c = r['source']['candidate']
            f.write(f"\n## {r['audit_id']} · {r['doc_id']} 物理页 {r['physical_page']}\n\n")
            f.write(f"原初审 {r['first_pass_label']}；本地第二意见 {r['second_opinion_label']}；专家裁定 pending。\n\n")
            f.write(f"{c['head_surface']} → {c['relation']} → {c['tail_surface']}\n\n")
            f.write(f"初审理由：{r['first_pass_note']}\n\n保存的原引用：\n\n```text\n{r['source']['proposed_quote']}\n```\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
