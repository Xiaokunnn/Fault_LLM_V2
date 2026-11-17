"""Exact edge-labelled node-simple sequence counts; training leave-group-out support."""
import numpy as np
from raw_io import *

def seq_counts(cat,edges):
    R=len(cat['relations']);adj=defaultdict(list);legal=[]
    for i,e in enumerate(edges):
        h,r,t=e['triple'];rule=cat['registry'][cat['relations'][r]]
        good=cat['entities'][h]['entity_type'] in rule['domain'] and cat['entities'][t]['entity_type'] in rule['range'];legal.append(good)
        if h==t:continue
        adj[h].append((t,r,i,good));adj[t].append((h,r+R,i,good))
    def inv(r):return (r+R)%(2*R)
    counters={};neighbors={}
    for u,row in adj.items():
        counters[u]=(Counter(r for v,r,i,g in row),Counter(r for v,r,i,g in row if g))
        byv=defaultdict(list)
        for v,r,i,g in row:byv[v].append((r,g))
        neighbors[u]=byv
    two=[Counter(),Counter()];three=[Counter(),Counter()]
    for u,row in adj.items():
        cc=counters[u]
        for k,c in enumerate(cc):
            for a,ca in c.items():
                for b,cb in c.items():two[k][inv(a),b]+=ca*cb
        for vv in neighbors[u].values():
            for a,ga in vv:
                for b,gb in vv:
                    two[0][inv(a),b]-=1
                    if ga and gb:two[1][inv(a),b]-=1
        for v,m,edge,gm in row:
            for k in [0,1]:
                if k and not gm:continue
                left=counters[u][k].copy();right=counters[v][k].copy()
                for a,g in neighbors[u][v]:
                    if not k or g:left[a]-=1
                for b,g in neighbors[v][u]:
                    if not k or g:right[b]-=1
                for a,ca in left.items():
                    if ca<=0:continue
                    for b,cb in right.items():
                        if cb>0:three[k][inv(a),m,b]+=ca*cb
                for w in neighbors[u].keys()&neighbors[v].keys():
                    if w in [u,v]:continue
                    for a,ga in neighbors[u][w]:
                        for b,gb in neighbors[v][w]:
                            if not k or (ga and gb):three[k][inv(a),m,b]-=1
    def name(r):return ('inverse:' if r>=R else '')+cat['relations'][r%R]
    output=[]
    for L,cc in [(2,two),(3,three)]:
        for key,n in sorted(cc[0].items()):
            if n>0:output.append(dict(length=L,sequence=' > '.join(map(name,key)),all_candidate_paths=n,schema_compatible_paths=cc[1][key],all_arrows_original=all(r<R for r in key)))
    return output

def training_loo(cat,edges):
    R=len(cat['relations']);aliases=read(OLD/'data/entity_alias_closure.json');meta=read(OLD/'data/train_group_context.json')
    bypair=defaultdict(set);bypage=defaultdict(set);bygram=defaultdict(set);bygroup=defaultdict(set)
    adj=defaultdict(list)
    for j,e in enumerate(edges):
        h,r,t=e['triple'];adj[h].append((t,j));adj[t].append((h,j));bypair[tuple(sorted([aliases[h],aliases[t]]))].add(j)
        for s in e['sources']:
            bypage[s['doc_id'],s['pdf_page_number']].add(j)
            for g in shingles(s.get('evidence_text','')):bygram[g].add(j)
    rows=[]
    for x in read(OLD/'data/base_split.jsonl'):
        if x['fold']!='train':continue
        m=meta[x['group_id']];bad=set()
        for pair in m['pairs']:bad|=bypair[tuple(pair)]
        for page in m['pages']:bad|=bypage[tuple(page)]
        for gram in m['quotegrams']:bad|=bygram[gram]
        h,r,t=x['triple']
        def ns(u):return {v for v,j in adj[u] if j not in bad and v!=u}
        hn=ns(h);tn=ns(t);two=len(hn&tn);three=sum(len((ns(u)-{h,t})&(tn-{h,u})) for u in hn if u!=t)
        rows.append(dict(id=x['claim_id'],group=x['group_id'],one_hop=t in hn,two_hop=two,three_hop=three,head_degree=len(hn),tail_degree=len(tn),blocked_edges=len(bad)))
    return rows

def main():
    if (EXP/'analysis/sequence_freeze.json').exists():return
    cat=read(EXP/'data/catalogue.json');summary={}
    for name in ['full','train']:
        rows=seq_counts(cat,load_graph(name+'_edges.jsonl'));csvsave(EXP/f'analysis/{name}_relation_sequences.csv',rows)
        summary[name]={str(L):dict(all_oriented_labelled_paths=sum(x['all_candidate_paths'] for x in rows if x['length']==L),schema_compatible_paths=sum(x['schema_compatible_paths'] for x in rows if x['length']==L),original_direction_only=sum(x['all_candidate_paths'] for x in rows if x['length']==L and x['all_arrows_original'])) for L in [2,3]}
    loo=training_loo(cat,load_graph());save(EXP/'analysis/training_leave_group_out.jsonl',loo)
    summary['training_loo']=dict(targets=len(loo),one_hop=sum(x['one_hop'] for x in loo),two_hop=sum(x['two_hop']>0 for x in loo),three_hop=sum(x['three_hop']>0 for x in loo))
    save(EXP/'analysis/sequence_freeze.json',summary);print(canonical(summary),flush=True)

if __name__=='__main__':main()
