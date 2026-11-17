"""Bounded, answer-independent paths on the already masked graph."""
import time
import numpy as np
from raw_io import *

def relation_feature(rs, rv):
    rr=[r for r in rs if r>=0]
    if not rr:return np.zeros(rv.shape[1],np.float32)
    # Position weights preserve order; inverse traversals have separate vectors.
    x=(rv[rr]*np.arange(1,len(rr)+1,dtype=np.float32)[:,None]).sum(0)
    return x/max(1e-12,np.linalg.norm(x))

class Paths:
    def __init__(self):
        self.cat=read(EXP/'data/catalogue.json'); self.R=len(self.cat['relations']); self.edges=load_graph()
        v=np.load(EXP/'index/vectors.npz'); self.ev=v['entities']; self.rv=v['relations']; self.qv=v['queries']
        self.views=read(EXP/'index/oriented_views.jsonl'); self.n=len(self.cat['entities']);self.cfg=read(EXP/'config.json')
        self.real=[[] for _ in range(self.n)]
        for v in self.views:self.real[v['anchor']].append((v['neighbor'],v['relation'],v['view_id']))
        self.struct=np.load(EXP/'data/structure.npz'); self.components=self.struct['components']; self.degree=self.struct['degree']
    def bridge_adj(self,kind):
        adj=[[] for _ in range(self.n)]
        if kind=='B0':return adj
        rows=read(EXP/f'bridges/{kind}.jsonl'); pairs={}
        for j,z in enumerate(rows):
            key=tuple(sorted([z['a'],z['b']]))
            if key not in pairs or z['score']>pairs[key][1]['score']:pairs[key]=(j,z)
        for (a,b),(j,z) in pairs.items():
            adj[a].append((b,-1,-j-1));adj[b].append((a,-1,-j-1))
        return adj
    def search(self,h,r,badj,max_hops=3):
        q=self.qv[h,r]; e=self.ev; relcos=self.rv@self.rv[r]
        # No hidden answer argument is accepted by this function.
        front=[([h],[],[],0.)]; complete=[]; expanded=0; truncated=0
        cache={}
        for depth in range(max_hops):
            proposals=[]
            for nodes,rs,es,_ in front:
                u=nodes[-1]; nv=sum(x<0 for x in rs)
                if u not in cache:
                    opts=self.real[u]+badj[u]
                    cache[u]=sorted(opts,key=lambda z:(-(.6*float(e[z[0]]@q)+.4*float(relcos[z[1]] if z[1]>=0 else e[u]@e[z[0]])),z[0],z[1]))
                opts=[z for z in cache[u] if z[0] not in nodes and not (z[1]<0 and (nv>=self.cfg['max_virtual'] or (rs and rs[-1]<0)))]
                truncated+=max(0,len(opts)-self.cfg['branch_limit'])
                for b,rel,edge in opts[:self.cfg['branch_limit']]:
                    nn=nodes+[b]; rr=rs+[rel]; ee=es+[edge]; real=[x for x in rr if x>=0]
                    ns=.5*float(e[h]@e[nn[1]])+.5*float(np.mean(e[nn[1:]]@q))
                    rf=relation_feature(rr,self.rv); rc=float(rf@self.rv[r]) if real else 0.
                    score=.5*ns+.5*rc-.05*sum(x<0 for x in rr)
                    proposals.append((nn,rr,ee,score));expanded+=1
            # One exact node/relation/edge path appears only once, regardless of record multiplicity.
            proposals.sort(key=lambda z:(-z[3],z[0],z[1],z[2]))
            seen=set(); unique=[]
            for z in proposals:
                key=(tuple(z[0]),tuple(z[1]),tuple(z[2]))
                if key not in seen:seen.add(key);unique.append(z)
            retain=[z for z in unique if any(x>=0 for x in z[1])]
            quota=self.cfg['max_paths_per_query']//max_hops
            complete+=retain[:quota]
            front=unique[:self.cfg['beam_width']]
            if not front:break
        return complete,dict(expanded=expanded,branch_truncations=truncated)

def exact_real_support(paths,targets):
    adj=[{v for v,r,idx in row if v!=u} for u,row in enumerate(paths.real)]
    rows=[]
    for x in targets:
        h,r,t=x['triple']; n2=len(adj[h]&adj[t]); n3=sum(len((adj[u]-{h,t})&(adj[t]-{h,u})) for u in adj[h] if u!=t)
        rows.append(dict(id=x['id'],triple=x['triple'],one_hop=t in adj[h],simple_two_hop_paths=n2,simple_three_hop_paths=n3,
            head_degree=len(adj[h]),tail_degree=len(adj[t]),same_component=bool(paths.components[h]==paths.components[t]),
            masked_endpoint_status='both_cold' if not adj[h] and not adj[t] else 'one_cold' if not adj[h] or not adj[t] else 'warm'))
    return rows

def sequences(paths):
    # Complete 2-edge oriented sequence distribution, excluding return to start.
    hist=Counter(); legalhist=Counter(); co=Counter(); R=paths.R
    legal=[]
    for e in paths.edges:
        h,r,t=e['triple'];rule=paths.cat['registry'][paths.cat['relations'][r]]
        legal.append(paths.cat['entities'][h]['entity_type'] in rule['domain'] and paths.cat['entities'][t]['entity_type'] in rule['range'])
    for u,arr in enumerate(paths.real):
        cc=Counter(r for v,r,i in arr); lc=Counter(r for v,r,i in arr if legal[i//2])
        byv=defaultdict(list)
        for v,r,i in arr:byv[v].append((r,legal[i//2]))
        for a,ca in cc.items():
            ra=(a+R)%(2*R)
            for b,cb in cc.items():hist[ra,b]+=ca*cb
        for a,ca in lc.items():
            ra=(a+R)%(2*R)
            for b,cb in lc.items():legalhist[ra,b]+=ca*cb
        for vv in byv.values():
            for a,la in vv:
                for b,lb in vv:
                    hist[(a+R)%(2*R),b]-=1
                    if la and lb:legalhist[(a+R)%(2*R),b]-=1
        present={r%R for r in cc}
        for a in present:
            for b in present:
                if a<=b:co[a,b]+=1
    def name(r):return ('inverse:' if r>=R else '')+paths.cat['relations'][r%R]
    rows=[dict(r1=name(a),r2=name(b),all_candidate_sequences=int(n),schema_compatible_sequences=int(legalhist[a,b]),counting='edge-labelled node-simple length2 with inverse traversal; not entailed composition') for (a,b),n in sorted(hist.items()) if n>0]
    csvsave(EXP/'analysis/relation_sequences_2.csv',rows)
    csvsave(EXP/'analysis/diagnostic_role_cooccurrence.csv',[dict(r1=name(a),r2=name(b),shared_nodes=n) for (a,b),n in sorted(co.items())])

def main():
    if (EXP/'paths/freeze.json').exists(): print('REUSE path pool'); return
    p=Paths(); targets=read(EXP/'data/validation_targets.jsonl')
    keys=sorted({(a,r) for x in targets for a,r in [(x['triple'][0],x['triple'][1]),(x['triple'][2],x['triple'][1]+p.R)]})
    save(EXP/'paths/query_keys.json',keys)
    exact=exact_real_support(p,targets);save(EXP/'analysis/real_target_support.jsonl',exact);sequences(p)
    summaries={}
    for kind in ['B0','B1','B2','B3','random']:
        start=time.perf_counter();badj=p.bridge_adj(kind);M=p.cfg['max_paths_per_query'];H=3
        nodes=np.full((len(keys),M,H+1),-1,np.int32);rels=np.full((len(keys),M,H),-2,np.int16);edgeids=np.full((len(keys),M,H),-1,np.int32);length=np.zeros((len(keys),M),np.int8);ns=np.zeros_like(length,dtype=np.float32);rc=np.zeros_like(ns);counter=Counter();featureseq=Counter()
        for i,(h,r) in enumerate(keys):
            found,meta=p.search(h,r,badj,H);counter.update(meta)
            for j,(nn,rr,ee,score) in enumerate(found[:M]):
                L=len(rr);nodes[i,j,:L+1]=nn;rels[i,j,:L]=rr;edgeids[i,j,:L]=ee;length[i,j]=L
                ns[i,j]=.5*float(p.ev[h]@p.ev[nn[1]])+.5*float(np.mean(p.ev[nn[1:]]@p.qv[h,r]))
                rc[i,j]=relation_feature(rr,p.rv)@p.rv[r]; featureseq[tuple(rr)]+=1
        npz(EXP/f'paths/{kind}.npz',nodes=nodes,relations=rels,edge_ids=edgeids,length=length,node_score=ns,relation_score=rc)
        realcounts=(rels>=0).sum(-1);virtualcounts=(rels==-1).sum(-1)
        valid=length>0
        summaries[kind]=dict(query_keys=len(keys),queries_with_any_path=int(valid.any(-1).sum()),queries_with_real_multihop=int(((realcounts>=2)&valid).any(-1).sum()),queries_with_virtual_multihop=int(((realcounts>=2)&(virtualcounts>0)&valid).any(-1).sum()),paths=int(valid.sum()),real_multiedge_paths=int(((realcounts>=2)&valid).sum()),one_real_edge_virtual_paths=int(((realcounts==1)&(virtualcounts>0)&valid).sum()),length_distribution=dict(Counter(str(x) for x in length[valid])),wall_seconds=time.perf_counter()-start,**counter)
        save(EXP/f'analysis/{kind}_path_sequences.jsonl',[dict(sequence=list(k),paths=v) for k,v in featureseq.most_common()])
        print(kind,canonical(summaries[kind]),flush=True)
    # No automatic model expansion: four-hop is a separately identified diagnostic.
    if summaries['B3']['one_real_edge_virtual_paths']>summaries['B3']['real_multiedge_paths']:
        start=time.perf_counter();out=[];badj=p.bridge_adj('B3')
        for h,r in keys:
            found,meta=p.search(h,r,badj,4)
            out.append(dict(head=h,relation=r,total=len(found),four_hop_at_least_two_real=sum(len(rr)==4 and sum(z>=0 for z in rr)>=2 for nn,rr,ee,s in found)))
        save(EXP/'analysis/four_hop_diagnostic.jsonl',out)
        summaries['four_hop_diagnostic']=dict(wall_seconds=time.perf_counter()-start,query_keys_with_real2_virtual2=sum(x['four_hop_at_least_two_real']>0 for x in out),policy='diagnostic only, no validation-selected extra model arm')
    save(EXP/'paths/freeze.json',dict(summaries=summaries,answer_independent_search=True,no_test_scoring=True,exact_real_support=dict(targets=len(exact),one_hop=sum(x['one_hop'] for x in exact),two_hop=sum(x['simple_two_hop_paths']>0 for x in exact),three_hop=sum(x['simple_three_hop_paths']>0 for x in exact),endpoint_status=dict(Counter(x['masked_endpoint_status'] for x in exact)))))

if __name__=='__main__':main()
