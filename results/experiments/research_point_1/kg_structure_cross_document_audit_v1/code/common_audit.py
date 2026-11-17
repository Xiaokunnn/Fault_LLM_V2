"""Expanded-only read audit; all writes confined to a new diagnostic folder."""
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
import networkx as nx
import numpy as np

sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[3]
STUDY=OUT.parent/'kg_query_aware_completion_v1'
spec=importlib.util.spec_from_file_location('expanded_locked_inputs',OUT.parent/'kg_enhancement_task_comparison/code/inputs.py')
I=importlib.util.module_from_spec(spec);spec.loader.exec_module(I)


def read(p):
    p=Path(p)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.suffix=='.jsonl' else json.loads(p.read_text())


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()


def save(p,x):
    p=Path(p);assert p.resolve().is_relative_to(OUT.resolve())
    s=x if isinstance(x,str) else ''.join(canonical(r)+'\n' for r in x) if p.suffix=='.jsonl' else json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if p.exists():assert p.read_text()==s,'Preserve existing output: '+str(p);return
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)


def csvsave(p,rows):
    assert rows,p
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);save(OUT/p,s.getvalue())


def dataset():
    d=I.load();entities=sorted(d['graph']['entities'],key=lambda x:x['entity_id']);E={x['entity_id']:x for x in entities}
    cat=read(STUDY/'data/catalogue.json');assert [x['entity_id'] for x in entities]==[x['entity_id'] for x in cat['entities'][:cat['nbase']]]
    split=read(STUDY/'data/base_split.jsonl');S={x['claim_id']:x for x in split};claims={x['claim_id']:x for x in d['graph']['claims']}
    assert set(claims)==set(S)
    for cid,c in claims.items():
        h,r,t=S[cid]['triple'];assert entities[h]['entity_id']==c['head_entity_id'] and entities[t]['entity_id']==c['tail_entity_id'] and cat['relations'][r]==c['relation']
    src=defaultdict(list)
    for x in d['graph']['source_records']:src[x['expanded_claim_id']].append(x)
    return d,entities,E,S,claims,src


def graphs(E,claims,cids):
    u=nx.Graph();v=nx.DiGraph();u.add_nodes_from(E);v.add_nodes_from(E)
    loops=[]
    for cid in sorted(cids):
        c=claims[cid];a,b=c['head_entity_id'],c['tail_entity_id']
        assert a in E and b in E
        if a==b:loops.append(cid);continue
        if not u.has_edge(a,b):u.add_edge(a,b,claims=[],relations=set())
        u[a][b]['claims'].append(cid);u[a][b]['relations'].add(c['relation'])
        if not v.has_edge(a,b):v.add_edge(a,b,claims=[],relations=set())
        v[a][b]['claims'].append(cid);v[a][b]['relations'].add(c['relation'])
    return u,v,loops


def all_simple_paths(g,k,directed):
    for start in sorted(g):
        def visit(path):
            if len(path)==k+1:
                if directed or path[0]<path[-1]:yield tuple(path)
                return
            for v in sorted(g[path[-1]]):
                if v not in path:yield from visit(path+[v])
        yield from visit([start])


def metric(E,claims,cids,assertions,view,paths=False):
    g,dg,loops=graphs(E,claims,cids);components=sorted(nx.connected_components(g),key=lambda z:(-len(z),min(z)))
    degree=dict(g.degree());hist=Counter(degree.values());onepair=[x for x in components if len(x)==2 and g.subgraph(x).number_of_edges()==1]
    strict=[x for x in onepair if len(g[next(iter(x))][next(v for v in x if v!=next(iter(x)))]['claims'])==1]
    row=dict(view=view,inventory_entities=len(E),active_entities=sum(x>0 for x in degree.values()),claims=len(cids),assertion_records=sum(x['claim_id'] in cids for x in assertions),unique_directed_relations=len({(claims[c]['head_entity_id'],claims[c]['relation'],claims[c]['tail_entity_id']) for c in cids}),unique_directed_pairs=dg.number_of_edges(),unique_undirected_pairs=g.number_of_edges(),self_loop_claims=len(loops),zero_degree=hist[0],degree1=hist[1],degree2=hist[2],degree_ge3=sum(n for k,n in hist.items() if k>=3),components_including_zero=len(components),components_active_only=len(components)-hist[0],two_node_one_pair_components=len(onepair),two_node_exactly_one_claim_components=len(strict),entities_in_strict_single_claim_components=2*len(strict),largest_component_entities=len(components[0]),largest_component_fraction=len(components[0])/len(E),mean_neighbor_degree=float(np.mean(list(degree.values()))),undirected_density=nx.density(g),directed_pair_density=nx.density(dg),directed_2hop_node_paths=0,directed_3hop_node_paths=0,undirected_2hop_node_paths=0,undirected_3hop_node_paths=0,directed_2hop_relation_paths=0,directed_3hop_relation_paths=0)
    patterns=Counter();ledger=[]
    for k in [2,3]:
        for directed,graph in [(True,dg),(False,g)]:
            count=0;typed=0
            for path in all_simple_paths(graph,k,directed):
                count+=1
                if directed:
                    rr=[sorted(dg[a][b]['relations']) for a,b in zip(path,path[1:])]
                    for pattern in itertools.product(*rr):patterns[k,pattern]+=1;typed+=1
                if paths:ledger.append(dict(view=view,directed=directed,hops=k,nodes=list(path),claim_choices=[list(graph[a][b]['claims']) for a,b in zip(path,path[1:])]))
            row[('directed' if directed else 'undirected')+f'_{k}hop_node_paths']=count
            if directed:row[f'directed_{k}hop_relation_paths']=typed
    if paths:save(OUT/f'paths/{view}_paths.jsonl',ledger)
    return row,g,dg,components,degree,patterns
