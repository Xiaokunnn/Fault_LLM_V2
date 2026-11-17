"""Completion-aware reproduction. Never overwrite a completed experiment."""
import subprocess
from io_utils import *


def main():
    steps=[
        ('prepare_data.py','data/freeze.json'),
        ('train_baselines.py','configs/foundations_complete.json'),
        ('build_index.py','index/freeze.json'),('retrieval.py','retrieval/freeze.json'),
        ('feature_analysis.py','feature_analysis/complete.json'),('feature_lodo.py','feature_analysis/lodo_notes.md'),
        ('retrieval_audit.py','retrieval/eligible_strata_and_mismatches.csv'),
        ('train_adapters.py','configs/adapters_complete.json'),('fixed_baselines.py','configs/fixed_complete.json'),
        ('evaluate.py','evaluation/complete.json'),('knn_numeric_check.py','verification/knn_numeric_notes.md'),
        ('summarize.py','analysis/summary_complete.json'),('transport_diagnostic.py','analysis/transport_retrieval_diagnostic.csv'),
        ('enhance.py','enhancement/complete.json'),('application_notes.py','ENHANCEMENT_REVIEW.md'),
        ('verify_delivery.py','verification/checks.json'),('write_report.py','FINAL_REPORT.md'),
        ('native_role_correction.py','native_role_correction/complete.json'),('native_role_probe.py','native_role_correction/probe_complete.json'),
        ('finalize.py','verification/final_complete.json')]
    for script,receipt in steps:
        if script=='evaluate.py':
            # Protocol fixtures now exist. Test before releasing target scoring.
            log=EXP/'tests.log'
            if not log.exists():
                with log.open('x') as f:subprocess.run([sys.executable,'-m','pytest','-q',str(EXP/'code/test_query_completion.py')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
            assert '7 passed' in log.read_text(),'Preserve failing test log; fix before scoring'
        if (EXP/receipt).exists():print('REUSE',script,flush=True);continue
        target=EXP/'logs'/('reproduce_'+script+'.log');target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x') as f:subprocess.run([sys.executable,'-u',str(EXP/'code'/script)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
        assert (EXP/receipt).exists(),script
        print('COMPLETE',script,flush=True)
    regression=EXP/'native_role_tests.log'
    if not regression.exists():
        with regression.open('x') as f:subprocess.run([sys.executable,'-m','pytest','-q',str(EXP/'code/test_native_roles.py')],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    assert '2 passed' in regression.read_text()
    print('Completed immutable experiment reused; see FINAL_REPORT.md.',flush=True)


if __name__=='__main__':main()
