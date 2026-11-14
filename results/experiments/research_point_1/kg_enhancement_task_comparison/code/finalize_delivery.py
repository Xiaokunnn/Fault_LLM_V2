"""Verify and seal the task-selection delivery, without a new model or KG write."""
import json
from pathlib import Path
import re
import subprocess
import sys

from inputs import ROOT, TASK, REV, ALLOWED, GRAPH, save, digest
from run_baselines import OUT, read
from evaluate_review import EVAL


def main():
    seal=read(OUT/"comparison_data_seal.json")
    for relative,expected in seal["file_hashes"].items():
        if digest((TASK/relative).read_bytes())!=expected:
            raise ValueError("Sealed data changed: "+relative)
    selection=read(TASK/"task_selection.json")
    assert selection["recommended_primary_task"]=="B"
    assert selection["knowledge_enhancement_is_an_established_RP1_stage"]
    assert not selection["overall_enhancement_direction_go_no_go_evaluated"]
    assert selection["no_GNN_or_other_architecture_selected"] and selection["no_new_model_or_loss_designed"]
    labels={r["id"] for r in read(TASK/"review_labels.json")["labels"]}
    assert all(row["case"] in labels for row in selection["cross_task_binding_instances"])
    assert len(selection["cross_task_binding_instances"])==10
    assert len(read(TASK/"literature_context.json")["sources"])==5

    expected={}
    paths=[OUT/"mapping/input_manifest.json",OUT/"baselines/input_manifest.json",OUT/"review/preparation_manifest.json",
        OUT/"controls/manifest_v2.json",OUT/"controls/policy_manifest_v2.json",OUT/"controls/dictionary_manifest.json",EVAL/"manifest.json"]
    for path in paths:
        manifest=read(path);assert manifest["input_git_commit"]==REV
        assert set(manifest["input_sha256"])<=ALLOWED
        for source,h in manifest["input_sha256"].items():
            if source in expected:assert expected[source]==h
            expected[source]=h
    graph_paths=[p for p in expected if p.startswith("data/kg/") and not "/schema/" in p]
    assert graph_paths and all(path.startswith(GRAPH) for path in graph_paths)
    for source,h in expected.items():
        data=subprocess.check_output(["git","show",REV+":"+source],cwd=ROOT)
        assert digest(data)==h,source

    test=[sys.executable,"-B","-m","pytest",str(TASK/"code/test_task_comparison.py"),"-q","-p","no:cacheprovider"]
    run=subprocess.run(test,cwd=ROOT,capture_output=True,text=True)
    print(run.stdout)
    if run.returncode:raise RuntimeError(run.stderr or "Task comparison tests failed")
    count=re.search(r"(\d+) passed",run.stdout);assert count and int(count.group(1))==34
    summary=read(EVAL/"summary.json")
    assert summary["current_graph_ID_and_GraphML_consistency"] and summary["original_PDFs_preserved"]==15
    for pdf in read(EVAL/"source_pdf_preservation.jsonl"):
        assert digest((ROOT/pdf["path"]).read_bytes())==pdf["sha256"]
    modified=subprocess.check_output(["git","diff","--name-only"],cwd=ROOT,text=True).splitlines()
    prior={"papers/ICSMD_2026/RP1_ICSMD2026_English_Revised_R1.tex","papers/ICSMD_2026/RP1_ICSMD2026_references_v5.bib"}
    assert set(modified)<=prior,"Unexpected tracked edits outside experiment"
    assert (TASK/"REPORT.md").exists() and (TASK/"CASEBOOK.md").exists()
    figures=list((OUT/"pdf_qa").glob("*.png"));assert len(figures)==7
    files=[p for p in sorted(TASK.rglob("*")) if p.is_file() and p.name!="completion_manifest.json"
        and not any(part in {"__pycache__",".pytest_cache"} for part in p.relative_to(TASK).parts)]
    manifest=dict(status="complete_task_comparison_and_task_selection_not_algorithm_development",date="2026-11-13",
        input_git_commit=REV,sole_base_graph="expanded1456",other_graphs_loaded=0,pinned_input_files_rehashed=len(expected),
        raw_occurrences=8007,normalized_candidate_core_groups=7588,
        primary_review_items=60,distinct_primary_and_supplementary_opportunities=66,source_pages_in_review_material=79,
        source_only_pages_selected=30,source_propositions=10,source_omission_probes_under_bounded_review=8,
        supplementary_conflict_probe=1,PDF_pages_visually_checked=7,original_PDFs_rehashed_and_preserved=15,
        tests={"passed":34,"failed":0,"exit_code":0},recommended_task="B",
        no_independent_reference=True,no_full_graph_semantic_accuracy_claim=True,
        new_model_calls=0,models_trained=0,new_formal_assertions=0,formal_graph_or_RP2_RP3_edits=0,
        preexisting_tracked_paper_changes_preserved=modified,automatic_git_commit_or_push=False,
        final_results_directory="runs/20261113_v1/evaluation_v2",await_user_next_decision=True,
        task_files=len(files),total_task_file_bytes=sum(p.stat().st_size for p in files),
        file_hashes_sha256={p.relative_to(TASK).as_posix():digest(p.read_bytes()) for p in files})
    save(TASK/"completion_manifest.json",manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!="file_hashes_sha256"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
