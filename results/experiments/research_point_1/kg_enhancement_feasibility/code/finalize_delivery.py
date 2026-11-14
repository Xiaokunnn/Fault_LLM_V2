"""Seal this completed investigation, without training or changing a formal KG."""
import json
from pathlib import Path
import re
import subprocess
import sys

from investigate import ROOT, TASK, REV, read, save, sha


RUN = TASK / "runs/20261113_v1"


def main():
    before = read(TASK / "decision_before_literature.json")
    seal = read(RUN / "verification/data_phase_seal.json")
    literature = read(TASK / "literature_routes.json")
    assert before["status"] == "INCONCLUSIVE" and not before["beyond_simple_rules_demonstrated"]
    assert seal["step4_literature_search_not_yet_started"] and literature["data_phase_completed_before_this_search"]
    assert len(literature["sources"]) == 15 and len(literature["route_comparison"]) == 8
    assert len({r["url"] for r in literature["sources"]}) == 15
    known = {s["id"] for s in literature["sources"]}
    assert all(set(r["sources"]) <= known for r in literature["route_comparison"])
    assert sha((TASK / "problem_register.json").read_bytes()) == seal["problem_register_sha256"]
    for relative, expected in seal["evidence_hashes"].items():
        assert sha((RUN / relative).read_bytes()) == expected

    # Re-read pinned Git objects rather than silently assuming a different local checkout.
    expected = {}
    for path in sorted(RUN.glob("*_manifest.json")) + [RUN / "deeper/manifest.json", RUN / "case_review/manifest.json"]:
        for source, digest in read(path)["input_sha256"].items():
            if source in expected:
                assert expected[source] == digest
            expected[source] = digest
    expected.update(seal["extra_graphml_input_sha256"])
    for source, digest in expected.items():
        actual = subprocess.check_output(["git", "show", REV + ":" + source], cwd=ROOT)
        assert sha(actual) == digest, source
    for row in read(RUN / "verification/source_preservation.jsonl"):
        assert row["preserved"] and sha((ROOT / row["path"]).read_bytes()) == row["sha256"]

    command = [sys.executable, "-B", "-m", "pytest",
               str(TASK / "code/test_investigate.py"), str(TASK / "code/test_review_and_artifacts.py"),
               "-q", "-p", "no:cacheprovider"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr)
        raise RuntimeError("Investigation tests failed")
    count = re.search(r"(\d+) passed", result.stdout)
    assert count and int(count.group(1)) == 21

    modified = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines()
    previously_modified_papers = {
        "papers/ICSMD_2026/RP1_ICSMD2026_English_Revised_R1.tex",
        "papers/ICSMD_2026/RP1_ICSMD2026_references_v5.bib",
    }
    assert set(modified) <= previously_modified_papers, "Unexpected tracked changes outside investigation"
    decision = {
        **before,
        "investigation_execution_status": "complete",
        "semantic_corpus_exhaustively_labelled": False,
        "literature_comparison_completed": True,
        "literature_primary_sources": 15,
        "candidate_technique_classes_compared": 8,
        "literature_changed_local_decision_to_go": False,
        "most_worthwhile_problem_now": "Preservation and binding of source meaning and applicability, after excluding engineering/interface defects",
        "independent_human_or_model_reference": False,
        "why_not_just_cleaning": "Not established. Several observed defects have plausible transparent engineering controls; stable residual failures were not measured.",
        "data_sufficient_for_engineering_regression": True,
        "data_sufficient_for_new_algorithm_and_credible_efficacy_claim": False,
        "existing_RP1_entire_contribution_rejected": False,
        "formal_graph_repaired": False,
        "automatic_git_commit_or_push": False,
        "await_user_decision": True,
    }
    save(TASK / "decision.json", decision)
    files = [p for p in sorted(TASK.rglob("*")) if p.is_file() and p.name != "completion_manifest.json"
             and not any(part in {"__pycache__", ".pytest_cache"} for part in p.relative_to(TASK).parts)]
    manifest = {
        "status": "completed_problem_discovery_and_feasibility_report_not_algorithm_development",
        "date": "2026-11-13",
        "input_git_commit": REV,
        "rechecked_pinned_input_files": len(expected),
        "original_PDFs_preserved_and_rehashed": 15,
        "tests": {"passed": 21, "failed": 0, "exit_code": 0,
                  "command": "python -B -m pytest <TASK>/code/test_investigate.py <TASK>/code/test_review_and_artifacts.py -q -p no:cacheprovider"},
        "problem_categories": 10,
        "diagnostic_propositions": 20,
        "source_only_probe_packets": 48,
        "visual_PDF_page_checks": 8,
        "literature_primary_sources": 15,
        "technique_classes_compared": 8,
        "model_training_or_new_inference_calls": 0,
        "new_knowledge_edges_inferred": 0,
        "formal_graph_or_RP2_RP3_modifications": 0,
        "tracked_modifications_are_preexisting_papers_only": sorted(modified),
        "new_task_files_scoped_to": TASK.relative_to(ROOT).as_posix(),
        "file_hashes_sha256": {p.relative_to(TASK).as_posix(): sha(p.read_bytes()) for p in files},
        "stop_and_wait_for_user": True,
    }
    save(TASK / "completion_manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "file_hashes_sha256"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
