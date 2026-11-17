"""Read-only expanded1456 attribution; all writes stay in this experiment."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
from pathlib import Path
from collections import Counter,defaultdict
import csv,hashlib,importlib.util,io,itertools,json,platform,re,subprocess,sys
import networkx as nx
import numpy as np
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[3]
PARENT=OUT.parent
SPEC=importlib.util.spec_from_file_location('locked_root_cause_inputs',PARENT/'kg_enhancement_task_comparison/code/inputs.py')
I=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(I)
SIX={'causes','diagnosed_by','inspected_by','mitigated_by','prevented_by','maintained_by'}
CONDITION=re.compile(r'\b(if|when|unless|otherwise|provided|before|after|only|must not|do not|never)\b|如果|若|否则|除非|仅当|不得|禁止',re.I)
DIAGNOSTIC=re.compile(r'\b(fault|trouble|cause|fail\w*|check\w*|inspect\w*|monitor\w*|repair\w*|replac\w*|clean\w*|maint\w*|damag\w*|leak\w*|cavitat\w*|vibrat\w*)\b|故障|原因|检查|维修|泄漏|汽蚀|振动',re.I)
TOPIC=re.compile(r'\b(pump\w*|bearing\w*|seal\w*|shaft\w*|motor\w*|impeller\w*|piping|suction|lubrica\w*|vibrat\w*)\b|泵|轴承|轴封',re.I)


def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def read(p):
    p=Path(p)
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.suffix=='.jsonl' else json.loads(p.read_text())
def save(p,x):
    p=OUT/p if not Path(p).is_absolute() else Path(p);assert p.resolve().is_relative_to(OUT)
    s=x if isinstance(x,str) else ''.join(canon(r)+'\n' for r in x) if p.suffix=='.jsonl' else json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if p.exists():assert p.read_text()==s,'Preserve output: '+str(p);return
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
def csvsave(name,rows):
    assert rows
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);save(name,f.getvalue())
def dataset():
    d=I.load();E={x['entity_id']:x for x in d['graph']['entities']};C={x['claim_id']:x for x in d['graph']['claims']};S=defaultdict(list)
    for s in d['graph']['source_records']:S[s['expanded_claim_id']].append(s)
    return d,E,C,S
def key(r):return tuple(I.core_tuple(r))
def signature(r):return digest([key(r),r.get('conditions_source'),r.get('modality')])
def source_key(r):return (r['doc_id'],r['pdf_page_number'],I.norm(r['head_surface']),r['relation'],I.norm(r['tail_surface']))
def pointer(r):return I.source_pointer(r)
def legal(r,registry):
    rule=registry.get(r['relation'],{})
    return r['head_type'] in rule.get('domain',[]) and r['tail_type'] in rule.get('range',[])
def identities(r):return set(I.record_ids(r))
def roles(c,E):
    """Diagnostic coverage by directed roles; never invent symptom->cause."""
    h,t,r=c['head_entity_id'],c['tail_entity_id'],c['relation'];out=[]
    if r=='causes' and E[t]['entity_type'] in ['FaultMode','Symptom','FailureMechanism']:out.append((t,'cause'))
    if r in ['diagnosed_by','inspected_by']:out.append((h,'inspection'))
    if r in ['mitigated_by','prevented_by']:out.append((h,'remedy'))
    if r=='maintained_by':out.append((h,'component_maintenance'))
    if r=='occurs_at':out.append((h,'component_location'))
    return out
