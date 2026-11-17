"""Isolated raw-graph experiment IO. Never redirect a historical output path."""
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
EXP = Path(os.environ.get('RP1_RAW_RUN_DIR',str(BASE))).resolve()
assert EXP.is_relative_to(BASE.resolve()), 'Replay outputs must stay inside this experiment'
ROOT = BASE.parents[3]
OLD = BASE.parent / 'kg_query_aware_completion_v1'
PILOT = BASE.parent / 'kg_completion_algorithm_pilot'
sys.dont_write_bytecode = True
sys.path.append(str(PILOT / 'code'))
# Pure, already-used identity and quotation functions. No historical main runs.
from prepare import I, UF
from refine_safety import shingles

SEEDS = [16112026, 16112027, 16112028]
def scalar(x):
    import numpy as np
    if isinstance(x, np.generic): return x.item()
    raise TypeError(type(x).__name__)
def canonical(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'),default=scalar)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()
def read(p):
    p = Path(p)
    if not p.exists() and p.with_name(p.name+'.gz').exists():
        import gzip
        text=gzip.decompress(p.with_name(p.name+'.gz').read_bytes()).decode()
    else:text=p.read_text()
    return [json.loads(s) for s in text.splitlines() if s.strip()] if p.suffix == '.jsonl' else json.loads(text)
def save(p, value):
    p = Path(p)
    assert p.resolve().is_relative_to(EXP.resolve()), p
    value = value if isinstance(value, str) else ''.join(canonical(x)+'\n' for x in value) if p.suffix == '.jsonl' else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,default=scalar)+'\n'
    if p.suffix=='.md':value='\n'.join(line.rstrip() for line in value.splitlines()).rstrip()+'\n'
    if p.exists():
        assert p.read_text() == value, 'Refuse overwrite: '+str(p)
    else:
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(value)
def csvsave(p, rows):
    assert rows
    s = io.StringIO(); w = csv.DictWriter(s, fieldnames=list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows); save(p, s.getvalue())
def load_graph(name='train_edges.jsonl'): return read(EXP/'data'/name)
def locked(): return I.load()
def normkey(typ, label): return (typ, I.norm(label))
def device():
    import torch
    return 'cuda' if torch.cuda.is_available() else 'cpu'
def npz(path, **values):
    import numpy as np
    path = Path(path); assert path.resolve().is_relative_to(EXP.resolve())
    if path.exists():
        prior=np.load(path)
        assert set(prior.files)==set(values) and all(np.array_equal(prior[k],v) for k,v in values.items()), path
        return
    path.parent.mkdir(parents=True, exist_ok=True); np.savez_compressed(path, **values)
