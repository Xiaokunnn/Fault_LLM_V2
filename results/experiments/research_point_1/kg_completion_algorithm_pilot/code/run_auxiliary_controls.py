"""Reproducible equivalents of the two actually executed auxiliary control loops."""
from pathlib import Path
import subprocess
import sys
from common import RUN,SEEDS


def main():
    for seed in SEEDS:
        for script,view in [('run_anyburl.py','G3_bridge'),('run_anyburl.py','G4_bridge'),('train_complex.py','G3_flat_filtered')]:
            log=RUN/'logs/auxiliary_replay'/f'{view}_{seed}.log';log.parent.mkdir(parents=True,exist_ok=True)
            with log.open('x') as f:subprocess.run([sys.executable,str(Path(__file__).with_name(script)),'--view',view,'--seed',str(seed)],stdout=f,stderr=subprocess.STDOUT,check=True)


if __name__=='__main__':main()
