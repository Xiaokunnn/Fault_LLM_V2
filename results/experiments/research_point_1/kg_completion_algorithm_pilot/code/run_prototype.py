"""Matched continuation vs frozen-base KL, frozen before any test evaluation."""
from pathlib import Path
import subprocess
import sys
import time
from common import RUN,SEEDS,save,read,file_sha


def main():
    observed=[]
    for view in ['G1','G2','G3']:
        folder=RUN/'models'/f'simkgc_{view}_s{SEEDS[0]}'
        if (folder/'complete.json').exists():observed.append(dict(view=view,seed=SEEDS[0],validation=read(folder/'complete.json')))
    save(RUN/'configs/prototype_pretest_decision.json',dict(observed_validation_only=observed,
         problem='Strong text KGC baseline degrades with uncertain extra candidates on validation; preserve trusted training response geometry while learning candidate context',
         mechanism='L = CE_base + .3 * weighted_CE_candidate + lambda * KL(p_frozen_base || p_student), evaluated only on train-base query/tail minibatches',
         rows=[dict(seed=s,prototype=p,epochs=5,lr=2e-5,lambda_anchor=0 if p=='continue' else 1.) for s in SEEDS for p in ['continue','anchor','anchor_uniform']],
         controls='All start from identical seed-matched G1 best checkpoint; same base and aux samples, reference forward and optimizer-step budget. anchor_uniform only removes candidate confidence weights.',
         novelty_limit='Distillation/anti-forgetting and uncertainty weighting are established; this is a bounded application prototype, not a novelty claim',
         no_test_access_before_decision=True))
    statuses=[]
    for seed in SEEDS:
        ref=RUN/'models'/f'simkgc_G1_s{seed}'/'complete.json';deadline=time.monotonic()+1200
        while not ref.exists():
            if time.monotonic()>deadline:raise TimeoutError('Anchor not completed')
            time.sleep(2)
        for prototype in ['continue','anchor','anchor_uniform']:
            log=RUN/'logs/prototype'/f'{seed}_{prototype}.log';log.parent.mkdir(parents=True,exist_ok=True)
            command=[sys.executable,str(Path(__file__).with_name('train_simkgc.py')),'--view','G3','--seed',str(seed),'--epochs','5','--prototype',prototype]
            start=time.perf_counter()
            with log.open('x') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
            statuses.append(dict(seed=seed,prototype=prototype,returncode=result.returncode,seconds=time.perf_counter()-start))
            print('prototype',seed,prototype,'returncode',result.returncode,flush=True)
            if result.returncode:raise RuntimeError(log)
    save(RUN/'configs/prototype_execution.json',statuses)


if __name__=='__main__':main()
