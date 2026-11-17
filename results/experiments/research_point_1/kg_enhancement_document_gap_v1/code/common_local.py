"""CPU-only additive study; existing graph, caches and results are read-only."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('MKL_NUM_THREADS','2')
from collections import Counter,defaultdict
import csv
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import re
import sys
import numpy as np
import torch
torch.set_num_threads(2)
sys.dont_write_bytecode=True

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[3]
STUDY=OUT.parent/'kg_query_aware_completion_v1'
AUDIT=OUT.parent/'kg_structure_cross_document_audit_v1'
spec=importlib.util.spec_from_file_location('locked_gap_inputs',OUT.parent/'kg_enhancement_task_comparison/code/inputs.py')
I=importlib.util.module_from_spec(spec);spec.loader.exec_module(I)
SEEDS=[16112026,16112027,16112028]


def read(p):
    p=Path(p)
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.suffix=='.jsonl' else json.loads(p.read_text())


def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def save(p,x):
    p=Path(p);assert p.resolve().is_relative_to(OUT.resolve())
    s=x if isinstance(x,str) else ''.join(canonical(v)+'\n' for v in x) if p.suffix=='.jsonl' else json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if p.exists():assert p.read_text()==s,'Keep previous output: '+str(p);return
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)


def csvsave(name,rows):
    assert rows,name
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);save(OUT/name,f.getvalue())


def sources(edge,registry):
    out=[]
    for k in edge['source_keys']:
        r=registry.get(k,[]);out.extend(r if isinstance(r,list) else [r])
    return out


class UF:
    def __init__(self):self.p={}
    def find(self,x):
        self.p.setdefault(x,x)
        if self.p[x]!=x:self.p[x]=self.find(self.p[x])
        return self.p[x]
    def join(self,*xs):
        rr=sorted({self.find(x) for x in xs})
        for x in rr[1:]:self.p[x]=rr[0]


def load_domain():
    d=I.load();cat=read(STUDY/'data/catalogue.json');entities=cat['entities'][:2150];ei={e['entity_id']:j for j,e in enumerate(entities)};claims={x['claim_id']:x for x in d['graph']['claims']};src=defaultdict(list)
    for x in d['graph']['source_records']:src[x['expanded_claim_id']].append(x)
    uf=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for x in pop:
            for side in ['head','tail']:uf.join('L|'+x[side+'_type']+'|'+I.norm(x[side+'_canonical_zh']),'S|'+I.norm(x[side+'_surface']))
    return d,cat,entities,ei,claims,src,uf


def explicit_stage(s):
    text=I.norm(s);found=set()
    events={'启动':['starting','start-up','startup'],'运行':['operation','operating'],'拆卸':['dismantling','disassembly'],'安装':['installation','assembly'],'停机':['stopping','shutdown']}
    for event,english in events.items():
        for state in ['前','后']:
            if event+state in text:found.add((event,state))
            word='before' if state=='前' else 'after'
            if any(re.search(r'\b'+word+r'\s+(?:the\s+)?'+re.escape(w)+r'\b',text) for w in english):found.add((event,state))
    return found


def explicit_models(s):
    # Restrict to literal alphanumeric model IDs, never broad pump_type tags.
    return set(re.findall(r'(?<![a-z0-9])[a-z]{2,}[- ]?\d+[a-z0-9-]*(?![a-z0-9])',I.norm(s)))


def conflict(query_label,candidate_label,condition_text=''):
    q=explicit_models(query_label);c=explicit_models(candidate_label)
    if q and c and q.isdisjoint(c):
        stem=lambda z:re.sub(r'[a-z]{2,}[- ]?\d+[a-z0-9-]*','',I.norm(z))
        if stem(query_label)==stem(candidate_label):return 'different_explicit_model_ids_for_same_named_object'
    qs=explicit_stage(query_label);cs=explicit_stage(condition_text)
    if any(e==f and a!=b for e,a in qs for f,b in cs):return 'opposite_explicit_before_after_stage'
    return None
