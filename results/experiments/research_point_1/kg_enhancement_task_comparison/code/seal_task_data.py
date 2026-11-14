"""Freeze task-comparison evidence before final research-task recommendation."""
import json
from pathlib import Path
from inputs import TASK, REV, save, digest
from run_baselines import OUT, read
from evaluate_review import EVAL


def main():
    summary=read(EVAL/"summary.json");assert summary["primary_items"]==60
    paths=[OUT/"mapping/summary.json",OUT/"baselines/summary.json",EVAL/"summary.json",EVAL/"cases.jsonl",
        EVAL/"population_units.json",EVAL/"source_propositions.jsonl",EVAL/"source_proposition_summary.json",
        EVAL/"supplementary_conflict_probe.json",OUT/"controls/dictionary_summary.json",
        OUT/"controls/bounded_action_proposals_v2.jsonl",TASK/"review_labels.json",TASK/"source_propositions.json"]
    save(OUT/"comparison_data_seal.json",dict(input_git_commit=REV,sole_base_graph="expanded1456",
        data_analysis_complete_before_new_literature_comparison=True,
        primary_sample_items=60,distinct_primary_and_supplementary_opportunities=66,
        full_graph_semantically_labelled=False,independent_reference=False,
        file_hashes={str(p.relative_to(TASK).as_posix()):digest(p.read_bytes()) for p in paths},
        models_trained=0,formal_graph_modifications=0))
    print(json.dumps(dict(data_sealed=True,primary_items=60,source_frames=10),indent=2))


if __name__=="__main__":main()
