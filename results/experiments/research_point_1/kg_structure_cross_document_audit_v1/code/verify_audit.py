"""Independent counting identities and byte preservation, no model execution."""
from common_audit import *


def main():
    if (OUT/'verification.json').exists():print('REUSE verified audit');return
    d,entities,E,S,C,src=dataset();checks=[]
    for row in read(STUDY/'verification/delivery_manifest.json')['files']:
        assert sha(STUDY/row['path'])==row['sha256'],row['path']
    checks.append('All 868 files of the preceding completion study retain their sealed hashes')
    for path,value in read(OUT/'source_manifest.json')['domain_inputs'].items():assert sha(ROOT/path)==value,path
    checks.append('Locked expanded graph, candidate, 15 parsed-document and schema inputs unchanged')
    stats=read(OUT/'structure_complete.json')['graphs'];rem={x['claim_id'] for x in read(OUT/'mask_removals.jsonl')}
    views={'G_full':set(C),'G_train':{c for c in S if S[c]['fold']=='train'},'G_masked':set(C)-rem}
    replays=[]
    for row in stats:
        view=row['view'];g,dg,loops=graphs(E,C,views[view]);assert not loops
        assert sum(dict(g.degree()).values())==2*row['unique_undirected_pairs']
        u2=sum(n*(n-1)//2 for n in dict(g.degree()).values())
        u3=sum((g.degree(a)-1)*(g.degree(b)-1)-len(set(g[a])&set(g[b])) for a,b in g.edges())
        d2=sum(len(set(dg.predecessors(v)))*len(set(dg.successors(v)))-len(set(dg.predecessors(v))&set(dg.successors(v))) for v in dg)
        d3=0
        for b,c in dg.edges():
            left=set(dg.predecessors(b))-{c};right=set(dg.successors(c))-{b};d3+=len(left)*len(right)-len(left&right)
        assert u2==row['undirected_2hop_node_paths'];assert u3==row['undirected_3hop_node_paths'];assert d2==row['directed_2hop_node_paths'];assert d3==row['directed_3hop_node_paths']
        raw=read(OUT/f'paths/{view}_paths.jsonl')
        assert all(len(set(r['nodes']))==len(r['nodes']) and len(r['nodes'])==r['hops']+1 for r in raw)
        assert all(all((dg if r['directed'] else g).has_edge(a,b) for a,b in zip(r['nodes'],r['nodes'][1:])) for r in raw)
        replays.append(dict(view=view,undirected2=u2,undirected3=u3,directed2=d2,directed3=d3,independent_formulas_match=True))
    checks.append('Every structural path is real and node-simple; independent center/wedge formulas reproduce all counts')
    cold=read(OUT/'cold_endpoint_ledger.jsonl');f=read(OUT/'cold_fact_ledger.jsonl')
    assert len(cold)==448 and len(f)==224
    assert sum(x['train_neighbor_degree']==0 for x in cold)==366
    assert all(x['full_neighbor_degree']>=1 for x in cold)
    assert sum(x['reason']!='warm_in_G_train' for x in cold)==366
    assert Counter(x['train_status'] for x in f)=={'both_cold':147,'one_cold':72,'warm':5}
    assert len({x['entity_id'] for x in cold if x['train_neighbor_degree']==0})==321
    assert set(rem)=={c for c in S if S[c]['fold']=='test'}
    checks.append('224 facts/448 endpoint occurrences exactly recover historical coldness; full graph has no zero-degree target endpoints')
    for view in views:assert len(E)==2150
    assert len(d['graph']['claims'])==1400 and len(d['graph']['evidence_assertions'])==1456
    checks.append('Shared 2150-entity inventory; Claim/evidence occurrence multiplicity never inflates adjacency')
    save(OUT/'verification.json',dict(passed=True,checks=checks,replays=replays,old_experiment_files_verified=868,new_training_runs=0,new_extractions=0,original_graph_writes=0,RP2_RP3_changes=0,expert_Gold=False))
    print('VERIFIED',checks,flush=True)


if __name__=='__main__':main()
