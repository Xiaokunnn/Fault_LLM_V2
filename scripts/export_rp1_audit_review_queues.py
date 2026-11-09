"""Export pending adjudication queues from the completed, additive RP1 AI audit.

These queues expose the first-pass labels and are for adjudication, not blind
second annotation. A fresh page reviewer should use pages_source_only.jsonl.
Existing outputs are never overwritten; no original research inputs are edited.
"""
from collections import Counter
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/experiments/research_point_1/loss_page_audit_v1"


def rows(name):
    return [json.loads(line) for line in (OUT / name).read_text().splitlines() if line]


def write_csv(name, records):
    with (OUT / name).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main():
    findings = rows("record_findings.jsonl")
    breakdown = []
    for kind in ("probability", "coverage_supplement"):
        for decision in ("qualified", "quarantined", "rejected"):
            subset = [r for r in findings if r["sample_kind"] == kind
                      and r["original_decision"] == decision]
            for flag in sorted({f for r in subset for f in r["original_failure_flags"]}):
                flagged = [r for r in subset if flag in r["original_failure_flags"]]
                counts = Counter(r["semantic_support"] for r in flagged)
                breakdown.append(dict(
                    sample_kind=kind, original_decision=decision, original_flag=flag,
                    n=len(flagged), **{s: counts[s] for s in ("supported", "unsupported", "unresolved")},
                    additive_across_flags=False,
                ))
    write_csv("record_failure_flag_breakdowns.csv", breakdown)

    record_queue = []
    for r in findings:
        concern = r["primary_audit_explanation"]
        priority = "P1"
        if r["original_decision"] == "qualified" and concern in {
            "semantic_or_relation_error", "scope_mismatch"
        }:
            priority = "P0"
        elif concern == "valid_retained_source_relative":
            priority = "P2_control"
        record_queue.append(dict(
            audit_id=r["audit_id"], priority=priority, doc_id=r["doc_id"],
            physical_page=r["pdf_page_number"], triple_id=r["triple_id"],
            sample_kind=r["sample_kind"], first_pass_label=r["semantic_support"],
            first_pass_concern=concern, first_pass_note=r["review_note"],
            adjudication_status="pending", reviewer="", source_support="",
            scope_valid="", relation_and_conditions_valid="", evidence_contract_valid="",
            false_rejection_confirmed="", adjudication_note="",
        ))
    write_csv("record_adjudication_queue.csv", record_queue)

    page_queue = []
    known_scope_pages = {"MP001:p0014", "MP002:p0121"}
    for r in rows("page_match_findings.jsonl"):
        page_queue.append(dict(
            atom_id=r["atom_id"], page_key=r["page_key"], head=r["head"],
            relation=r["relation"], tail=r["tail"], source_anchor=r["source_anchor"],
            conditions=r["conditions"], first_pass_match=r["match_status"],
            candidate_ids=";".join(r["candidate_ids"]),
            first_pass_stage=r["strict_path_stage"],
            known_original_task_scope_disagreement=r["page_key"] in known_scope_pages,
            adjudication_status="pending", reviewer="", reference_atom_valid="",
            task_scope_valid="", semantic_match="", adjudication_note="",
        ))
    write_csv("page_reference_adjudication_queue.csv", page_queue)

    candidate_queue = []
    for r in rows("page_candidate_findings.jsonl"):
        candidate_queue.append(dict(
            candidate_id=r["candidate_id"], page_key=r["page_key"],
            triple_id=r["triple_id"], first_pass_label=r["semantic_support"],
            original_decision=r["original_decision"],
            adjudication_status="pending", reviewer="", source_support="",
            relation_and_conditions_valid="", adjudication_note="",
        ))
    write_csv("page_candidate_adjudication_queue.csv", candidate_queue)
    assert len(record_queue) == 97 and len(page_queue) == 245 and len(candidate_queue) == 210
    assert sum(r["known_original_task_scope_disagreement"] for r in page_queue) == 7
    print(json.dumps({"record_queue": len(record_queue), "reference_queue": len(page_queue),
                      "candidate_queue": len(candidate_queue), "review_status": "all pending"}))


if __name__ == "__main__":
    main()
