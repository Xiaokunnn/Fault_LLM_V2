"""Isolated second-stage IO, reusing the frozen pilot's genuine implementations."""
import os
import sys
from pathlib import Path
PILOT=Path(__file__).resolve().parents[1]
OLD=PILOT/'runs/20261114_controlled_v1'
STUDY=PILOT/'runs/20261114_relation_collab_v1'
DATASET=os.environ.get('RP1_COLLAB_DATASET','cold')
assert DATASET in ['cold','structured']
os.environ['RP1_KGC_RUN']='20261114_relation_collab_v1/'+DATASET
sys.path.insert(0,str(PILOT/'code'))
from common import RUN,ROOT,SEEDS,read,save,digest,file_sha,seed_all
from prepare import I,UF
from refine_safety import shingles


def dataset_path(name):return STUDY/name
