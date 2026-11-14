"""Readable evidence casebook generated from the disclosed final review."""
from collections import defaultdict
import json
from inputs import TASK, ROOT, save
from evaluate_review import EVAL
from run_baselines import read


def main():
    rows=read(EVAL/"cases.jsonl");byid={};cohorts=defaultdict(list)
    for row in rows:byid.setdefault(row["id"],row);cohorts[row["id"]].append(row["task"])
    lines=["# 五类知识增强任务逐案证据册","",
        "66个不同机会ID，含固定主样本和单列补充对照。部分案例共享原文，不能当66个独立事实。",
        "当前AI非盲源文审查；不是人工Gold或独立模型评审。原始完整载荷见evaluation_v2/cases.jsonl。","",
        "状态针对每例明确的被审命题，不是统一准确率标签。下述源文仅供知识表示调查，不构成运行/维护授权。",""]
    for case in byid.values():
        item=case["candidate"]
        lines.extend(["## "+case["id"],"",case["target"],"",
            "样本组："+", ".join(cohorts[case["id"]]),
            f"来源判断：{case['support']}；结果：{case['result']}；基线：{case['baseline']}；范围：{case['domain']}","",case["reason"],""])
        sources=item.get("source_records",[item.get("proposed_source",item.get("source",item))])
        for source in sources:
            aid=source.get("assertion_id") or item.get("assertion_id")
            cid=source.get("claim_id") or item.get("claim_id")
            lines.append(f"### {source['doc_id']} 物理页 {source['pdf_page_number']}")
            lines.append("")
            if aid:lines.append("Assertion："+aid)
            if cid:lines.append("Claim："+cid)
            if source.get("triple_id"):lines.append("记录："+source["triple_id"])
            if source.get("relation"):
                lines.append(str(source.get("head_canonical_zh"))+" —"+source["relation"]+"→ "+str(source.get("tail_canonical_zh")))
            quote=source.get("evidence_text",source.get("text",""))
            shown=quote[:1200]
            lines.extend(["",*[("> "+line) for line in shown.splitlines()]])
            if len(quote)>len(shown):lines.append("\n上文为显示节选，完整原文载荷未截断，保留于逐案JSONL。")
            if source.get("source_url"):lines.extend(["","[原始文档来源]("+source["source_url"]+")"])
            context=TASK/f"runs/20261113_v1/review/pages/{source['doc_id']}_p{source['pdf_page_number']:04d}.json"
            if context.exists():lines.extend(["","[完整原始解析页]("+context.as_posix()+")"])
            lines.append("")
    lines.extend(["## 来源优先命题分解","", "下列10个限定框架出自4个原先固定的来源单元，8个是有界检索的遗漏线索，2个是已有候选对照。不是10条新因果边。",""])
    for row in read(EVAL/"source_propositions.jsonl"):
        lines.extend(["### "+row["id"]+" / "+row["parent"],"",f"{row['doc_id']} 物理页 {row['page']} | {row['support']} | {row['coverage']}","",
            "```json",json.dumps(row["frame"],ensure_ascii=False,indent=2),"```","",row["reason"],""])
        for proof in row["source_proofs"]:lines.extend(["> "+proof["query"],""])
    cp=read(EVAL/"supplementary_conflict_probe.json")
    lines.extend(["## 维护周期表面冲突补充调查","",cp["proposition"],"",cp["reason"],"", "判定："+cp["support"]+"；不计入C的12项主样本。",""])
    save(TASK/"CASEBOOK.md","\n".join(lines))
    print(json.dumps(dict(unique_case_ids=len(byid),source_propositions=10),indent=2))


if __name__=="__main__":main()
