"""Verify preserved inputs, execute regression tests and seal this selection run."""
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys

from inputs import ROOT,TASK,REV,Inputs,digest,save
from selection_screen import OUT,OLD,read


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    old=read(TASK/'completion_manifest.json')
    for name,sha in old['file_hashes_sha256'].items():
        if digest((TASK/name).read_bytes())!=sha:raise ValueError('Prior sealed asset changed: '+name)
    frozen=read(OUT/'input_manifest.json')
    inputs=Inputs()
    for path,sha in frozen['data_hashes'].items():
        if digest(inputs.raw(path))!=sha:raise ValueError('Pinned source changed: '+path)
    pdfs=[]
    for r in read(OLD/'evaluation_v2/source_pdf_preservation.jsonl'):
        sha=digest((ROOT/r['path']).read_bytes())
        if sha.lower()!=r['sha256'].lower():raise ValueError('Source PDF changed: '+r['path'])
        pdfs.append({**r,'rechecked_sha256':sha})
    save(OUT/'verification/original_pdf_preservation.jsonl',pdfs)
    tests=subprocess.run([sys.executable,'-m','pytest',str(TASK/'code/test_selection_experiment.py'),
                          str(TASK/'code/test_task_comparison.py'),'-q','-o',f'cache_dir={OUT}/pytest_cache'],
                         cwd=ROOT,capture_output=True,encoding='utf-8',errors='replace')
    if tests.returncode:
        print(tests.stdout,tests.stderr);raise RuntimeError('Regression tests failed')
    passed=re.search(r'(\d+) passed',tests.stdout)
    save(OUT/'verification/test_result.json',{'command':'python -m pytest test_selection_experiment.py test_task_comparison.py -q',
        'exit_code':tests.returncode,'passed':int(passed.group(1)) if passed else None,'stdout':tests.stdout,'stderr':tests.stderr})
    file_hashes={p.relative_to(OUT).as_posix():digest(p.read_bytes()) for p in sorted(OUT.rglob('*'))
                 if p.is_file() and 'pytest_cache' not in p.parts and p.name!='completion_manifest.json'}
    code_hashes={p.name:digest(p.read_bytes()) for p in sorted((TASK/'code').glob('selection*.py'))}
    code_hashes['test_selection_experiment.py']=digest((TASK/'code/test_selection_experiment.py').read_bytes())
    code_hashes['finalize_selection.py']=digest(Path(__file__).read_bytes())
    result={'status':'completed_executed_task_selection_not_new_algorithm_development','date':'2026-11-14',
        'input_git_commit':REV,'sole_base_graph':'expanded1456','historical_graph_versions_loaded':0,
        'pinned_domain_input_files_rehashed':len(inputs.hashes),'prior_experiment_files_verified':len(old['file_hashes_sha256']),
        'original_PDFs_rehashed_preserved':len(pdfs),'original_base_assertions_preserved':1456,
        'actual_trial_assertions_added':22,'deduplicated_trial_claims_added':19,
        'formal_publication_pipeline_passed':False,'original_chinese_publication_gate_passed':False,
        'recommended_primary_task':'A_evidence_constrained_candidate_restoration_with_contextual_semantic_alignment',
        'E_role':'source_first_discovery_and_association_extension_not_equal_proven_algorithmic_innovation',
        'B_C_role':'qualifier_and_alignment_mechanisms','D_role':'reliability_engineering',
        'new_external_LLM_calls':0,'enhancement_neural_models_trained':0,
        'retrieval_TFIDF_LSA_fitted':True,'human_or_independent_model_reference':False,
        'known_relation_masked_recovery_experiment_run':False,'no_independent_precision_recall_claim':True,
        'formal_graph_RP2_RP3_paper_edits':0,'automatic_git_commit_or_push':False,
        'tests':{'passed':int(passed.group(1)) if passed else None,'failed':0,'exit_code':tests.returncode},
        'environment':{'python':sys.version,**{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','pytest']}},
        'final_report':'REPORT.md','final_metrics':'evaluation/FINAL_METRICS.json','final_comparison':'evaluation/FINAL_TASK_COMPARISON.json',
        'final_sandbox':'sandbox_v2','intermediates_preserved_not_mixed_into_final_metrics':True,
        'file_hashes_sha256':file_hashes,'code_hashes_sha256':code_hashes,
        'sources_of_literature_metadata':'verified_primary_publisher_arxiv_pages_in_REPORT_not_training_data',
        'semantic_scholar_api':'unavailable_via_tool_no_S2_verified_claim'}
    save(OUT/'completion_manifest.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['file_hashes_sha256','code_hashes_sha256','environment']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
