"""New outputs only; reuse the complete immutable 20261114 collaboration study."""
import sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'code_collab_v1'))
from collab_io import *
PARENT=STUDY
NEW=P/'runs'/os.environ.get('RP1_ROLE_VERSION','20261116_role_contribution_v1')
assert NEW.resolve().is_relative_to((P/'runs').resolve())
OUT=NEW/DATASET


def checkpoint(seed):return RUN/'models'/f'collab_full_s{seed}'/'best.pt'
