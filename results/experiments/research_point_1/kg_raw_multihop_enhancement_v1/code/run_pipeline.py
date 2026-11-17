"""Fresh, uniquely named replay with actual stdout/stderr saved per stage."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True,help='Unused child name below replays/')
    args=ap.parse_args();base=Path(__file__).resolve().parents[1];out=(base/'replays'/args.run).resolve()
    assert out.is_relative_to((base/'replays').resolve()) and not out.exists(), 'Use a new replay name'
    (out/'logs').mkdir(parents=True);env=dict(os.environ,RP1_RAW_RUN_DIR=str(out),OPENBLAS_NUM_THREADS='4')
    scripts=['build_graph','vector_bridges','path_search','sequence_audit','run_completion','matched_random_control','controlled_relation_ablation','diagnose','prediction_traces','verify','write_reports','package']
    for stage in scripts:
        print('START',stage,flush=True)
        with (out/'logs'/f'{stage}.txt').open('w') as f:
            subprocess.run([sys.executable,'-B',str(base/'code'/f'{stage}.py')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        print('COMPLETE',stage,flush=True)

if __name__=='__main__':main()
