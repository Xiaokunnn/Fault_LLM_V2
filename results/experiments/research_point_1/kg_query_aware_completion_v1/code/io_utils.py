"""Isolated new experiment; reuse author models/helpers, never old fit weights."""
from collections import defaultdict
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[3]
PILOT = EXP.parent / 'kg_completion_algorithm_pilot'
RUN = STUDY = EXP
DATASET = 'internal_query_aware_v1'
SEEDS = [16112026, 16112027, 16112028]
sys.path.insert(0, str(PILOT / 'code'))
import common
from common import canonical, digest, file_sha, read, seed_all, rank, rank_summary


def save(path, value, replace=False):
    p = Path(path)
    assert p.resolve().is_relative_to(EXP.resolve()), p
    text = value if isinstance(value, str) else ''.join(canonical(x)+'\n' for x in value) if p.suffix == '.jsonl' else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n'
    if p.exists() and not replace:
        assert p.read_text() == text, 'Preserve differing output: '+str(p)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def csvsave(name, rows):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader(); w.writerows(rows); save(EXP / name, out.getvalue())


# The original helpers import common.RUN/save at import time. Redirect them to
# this separate experiment, preserving the author's source unchanged.
common.RUN = RUN
common.save = save
common.SEEDS = SEEDS
from prepare import I, UF
from refine_safety import shingles
sys.path.insert(0, str(PILOT / 'code_collab_v1'))
sys.modules['collab_io'] = sys.modules[__name__]


def frozen(path):
    save(path, dict(files={str(p.relative_to(EXP)): file_sha(p) for p in sorted((EXP/'data').glob('*')) if p != path}))
