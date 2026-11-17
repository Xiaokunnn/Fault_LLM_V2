"""Finish complete result tables, frozen interventions and proposed-model inference."""
import subprocess
import sys
import time
from collab_io import *


def main():
    deadline=time.monotonic()+7200
    while not all((STUDY/d/'evaluation/complete.json').exists() for d in ['cold','structured']):
        if time.monotonic()>deadline:raise TimeoutError('Preserve pending results')
        time.sleep(3)
    code=PILOT/'code_collab_v1'
    subprocess.run([sys.executable,str(code/'summarize_collab.py')],check=True)
    for dataset in ['cold','structured']:
        env=dict(os.environ,RP1_COLLAB_DATASET=dataset)
        subprocess.run([sys.executable,str(code/'intervene.py')],env=env,check=True)
    subprocess.run([sys.executable,str(code/'predict_relations.py')],check=True)
    save(STUDY/'postprocess_complete.json',dict(metrics=True,interventions=True,proposals=True,source_AI_reading_pending=True))


if __name__=='__main__':main()
