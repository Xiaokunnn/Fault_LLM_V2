"""Seal this completed pilot without touching formal graphs or Git staging."""
from pathlib import Path
import subprocess
from common import PILOT,ROOT,RUN,read,save,file_sha


def main():
    assert read(RUN/'verification/checks.json')['passed']
    assert len(read(RUN/'verification/build_pdf_preservation.json'))==15
    assert read(RUN/'evaluation/complete.json')['models']==78
    assert read(RUN/'tables/summary_complete.json')['models']==78
    # Author model used here is unmodified relative to its recorded author commit.
    author=PILOT/'dependencies/SimKGC'
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=author,text=True).strip()
    assert commit=='97cc43e488f19ca5b0f6fbf60ffefd2ee56c0693'
    original=subprocess.check_output(['git','show',commit+':models.py'],cwd=author)
    assert original==(author/'models.py').read_bytes()
    changed=subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines()
    assert all(p.startswith(str(PILOT.relative_to(ROOT))+'/') for p in changed),changed
    required=['REPORT.md','METHOD_AND_RELATED_WORK.md','REPRODUCE.md',
              'discovery/AI_source_review.jsonl','enhancement/claim_overlays.jsonl',
              'analysis/FAILURE_CASES.md','tables/baseline_G1_G4.csv']
    assert all((RUN/p).exists() for p in required)
    # Exclude locks and this manifest; neither is experimental input/output data.
    paths=sorted(p for root in [PILOT/'code',RUN] for p in root.rglob('*')
                 if p.is_file() and p.suffix!='.lock' and '__pycache__' not in p.parts
                 and p.name not in ['delivery_manifest.json','delivery_complete.json'])
    paths+=[PILOT/'README.md',PILOT/'dependencies/AnyBURL-23-1x.jar',author/'models.py']
    manifest=[dict(path=str(p.relative_to(PILOT)),bytes=p.stat().st_size,sha256=file_sha(p)) for p in paths]
    save(RUN/'verification/delivery_manifest.json',dict(domain_input_object='833c8040058055434c7f6a9595ec524c3935755f',
        execution_git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        author_SimKGC_commit=commit,files=manifest,
        scope='All own code/run artifacts plus README and used author model/JAR. Java and encoder files have separate recorded manifests. No Git commit/push or graph publication.'))
    save(RUN/'verification/delivery_complete.json',dict(completed=True,trained_or_learned_models=78,
        test_claims=213,document_holdout_claims=50,document_holdout_models=45,
        source_review_records=24,existing_claim_overlays=1400,original_assertion_links=1456,
        new_complete_facts_confirmed=0,graph_publication=False,
        source_inputs_preserved=24,source_PDFs_preserved=15,unit_tests_passed=8,
        manifest_files=len(manifest),manifest_sha256=file_sha(RUN/'verification/delivery_manifest.json'),
        algorithm_gain_status='Small average prototype gain; paired group CI includes zero; no stable/novel algorithm gain claim'))
    print('Sealed completed delivery:',len(manifest),'files; no graph writes or Git staging')


if __name__=='__main__':main()
