"""Wait for frozen training jobs, reselect rules on validation, then release test."""
from pathlib import Path
import subprocess
import sys
import time
from common import RUN,SEEDS,read,save,file_sha


def expected():
    names=[]
    for seed in SEEDS:
        names += [f'complex_{v}_s{seed}_f1.0_n0.0_none_r1' for v in ['G1','G2','G3','G3_flat','G3_uniform','G3_labels','G4','G3_flat_filtered']]
        names += [f'complex_G3_s{seed}_f{f}_n0.0_none_r1' for f in [.25,.5]]
        names += [f'complex_G3_s{seed}_f1.0_n{n}_none_r1' for n in [.25,.5]]
        names += [f'anyburl_{v}_s{seed}_f1.0_n0.0' for v in ['G1','G2','G3','G3_flat','G4','G3_bridge','G4_bridge']]
        names += [f'simkgc_{v}_s{seed}' for v in ['G1','G2','G3','G4']]
        names += [f'simkgc_G3_s{seed}_{p}' for p in ['continue','anchor','anchor_uniform']]
    return names


def main():
    names=expected();deadline=time.monotonic()+2400;last=None
    while True:
        missing=[n for n in names if not (RUN/'models'/n/'complete.json').exists()]
        if len(missing)!=last:print('Waiting training:',len(names)-len(missing),'/',len(names),'completed',flush=True);last=len(missing)
        if not missing:break
        if time.monotonic()>deadline:raise TimeoutError(str(missing))
        time.sleep(3)
    subprocess.run([sys.executable,str(Path(__file__).with_name('reselect_anyburl.py'))],check=True)
    save(RUN/'configs/test_release.json',dict(models=names,selection='All models and prototype controls fixed from validation before test was scored',
         checkpoints={n:read(RUN/'models'/n/'complete.json') for n in names},
         prototype_decision_sha256=file_sha(RUN/'configs/prototype_pretest_decision.json'),
         safety_freeze_sha256=file_sha(RUN/'data/safety_refinement_freeze.json'),
         note='No further hyperparameter or model decisions may use these test scores'))
    for name in names:
        subprocess.run([sys.executable,str(Path(__file__).with_name('evaluate_frozen.py')),'--folder',name],check=True)
    save(RUN/'evaluation/complete.json',dict(models=len(names),all_test_evaluations_completed=True,no_training_after_release=True))
    print('ALL TEST EVALUATIONS COMPLETE',flush=True)


if __name__=='__main__':main()
