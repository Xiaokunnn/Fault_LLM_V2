"""Continue actual diagnostics, held-document evaluation and inference generation."""
from pathlib import Path
import subprocess
import sys
import time
from common import RUN,SEEDS,save


def call(script,*args):
    subprocess.run([sys.executable,str(Path(__file__).with_name(script)),*args],check=True)


def main():
    deadline=time.monotonic()+3000
    while not (RUN/'evaluation/complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Primary evaluation did not finish')
        time.sleep(3)
    call('evaluate_references.py')
    names=[]
    for seed in SEEDS:
        names += [f'complex_{v}_s{seed}_f1.0_n0.0_none_r1' for v in ['G1','G2','G3','G4']]
        names += [f'anyburl_{v}_s{seed}_f1.0_n0.0' for v in ['G1','G2','G3_bridge','G4_bridge']]
        names += [f'simkgc_{v}_s{seed}' for v in ['G1','G2','G3','G4']]
        names += [f'simkgc_G3_s{seed}_{v}' for v in ['continue','anchor','anchor_uniform']]
    for name in names:call('evaluate_frozen.py','--folder',name,'--fold','document_holdout')
    save(RUN/'evaluation/document_holdout_complete.json',dict(models=len(names),targets=50,document='MP022',no_fitting=True))
    call('discover.py')
    save(RUN/'discovery/generation_complete.json',dict(source_packets_ready=True,semantic_AI_review_still_required=True))


if __name__=='__main__':main()
