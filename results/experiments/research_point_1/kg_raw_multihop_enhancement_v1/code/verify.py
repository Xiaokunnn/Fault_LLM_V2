"""Meaningful integrity/leakage/counting/fallback checks; no model/API calls."""
import gzip
import itertools
import unittest
import numpy as np
from raw_io import *
from build_graph import stats
from sequence_audit import seq_counts
from path_search import relation_feature

class Invariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat=read(EXP/'data/catalogue.json');cls.records=read(EXP/'data/record_graph.jsonl');cls.edges=load_graph();cls.views=read(EXP/'index/oriented_views.jsonl');cls.R=len(cls.cat['relations'])
    def test_full_record_identity_and_dedup(self):
        self.assertEqual(len(self.records),8003);self.assertEqual(len({x['record_id'] for x in self.records}),8003)
        mapped=[r for e in load_graph('full_edges.jsonl') for r in e['records']]
        self.assertEqual(sorted(mapped),sorted(x['record_id'] for x in self.records))
        self.assertEqual(len({tuple(e['triple']) for e in self.edges}),len(self.edges))
    def test_no_status_or_schema_graph_filter(self):
        visible=[x for x in self.records if not x['exclusions']];used={rid for e in self.edges for rid in e['records']}
        self.assertEqual(used,{x['record_id'] for x in visible});self.assertGreater(sum(not x['schema_compatible'] for x in visible),900)
        self.assertEqual(set(x['audit_status'] for x in visible),{'silver_candidate','candidate_needs_review','rejected'})
    def test_held_source_quote_native_unit_and_alias_pair_absent(self):
        bb=read(OLD/'audit_only/copy_blockers.json');pages=set(map(tuple,bb['pages']));units=set(bb['units']);grams=set(bb['quotegrams']);pairs=set(map(tuple,bb['pairs']));alias=read(OLD/'data/entity_alias_closure.json')
        for e in self.edges:
            h,r,t=e['triple'];self.assertNotIn(tuple(sorted([alias[h],alias[t]])),pairs)
            for s in e['sources']:
                self.assertIn(s['doc_id'],I.BUILD);self.assertNotIn((s['doc_id'],s['pdf_page_number']),pages)
                self.assertFalse(shingles(s.get('evidence_text',''))&grams)
                native=set(s.get('evidence_unit_ids') or [])|{w.get('cell_id') or w.get('block_id') for w in s.get('expansion_source_witnesses',[]) or []}
                self.assertFalse(native&units)
    def test_path_actual_direction_bridge_membership_and_simple_nodes(self):
        keys=read(EXP/'paths/query_keys.json')
        for kind in ['B0','B1','B2','B3','random','random_degree_matched']:
            z=dict(np.load(EXP/f'paths/{kind}.npz'));bridges=[] if kind=='B0' else read(EXP/f'bridges/{kind}.jsonl')
            for i,j in zip(*np.where(z['length']>0)):
                L=int(z['length'][i,j]);nn=z['nodes'][i,j,:L+1].tolist();rr=z['relations'][i,j,:L];ee=z['edge_ids'][i,j,:L]
                self.assertEqual(nn[0],keys[i][0]);self.assertEqual(len(nn),len(set(nn)));self.assertLessEqual(sum(r<0 for r in rr),2)
                self.assertFalse(any(a<0 and b<0 for a,b in zip(rr,rr[1:])))
                for k,(r,e) in enumerate(zip(rr,ee)):
                    if r>=0:
                        v=self.views[int(e)];self.assertEqual((v['anchor'],v['neighbor'],v['relation']),(nn[k],nn[k+1],int(r)))
                    else:
                        b=bridges[-int(e)-1];self.assertEqual({b['a'],b['b']},{nn[k],nn[k+1]});self.assertNotEqual(b['component_a'],b['component_b'])
    def test_counts_against_independent_enumeration_with_cycles_parallel_edges_and_loop(self):
        triples=[[0,0,1],[0,1,1],[1,0,2],[2,0,0],[2,1,3],[0,0,0]];es=[dict(triple=t) for t in triples]
        st,_,_=stats(4,es,4);adj=defaultdict(set);out=defaultdict(set);arcs=defaultdict(list)
        for h,r,t in triples:
            if h==t:continue
            adj[h].add(t);adj[t].add(h);out[h].add(t);arcs[h].append((t,r));arcs[t].append((h,r+2))
        for L in [2,3]:
            un=di=0
            for nodes in itertools.permutations(range(4),L+1):
                un+=all(b in adj[a] for a,b in zip(nodes,nodes[1:]));di+=all(b in out[a] for a,b in zip(nodes,nodes[1:]))
            self.assertEqual(st[f'undirected_simple_node_paths_{L}'],un//2);self.assertEqual(st[f'directed_simple_node_paths_{L}'],di)
        cat=dict(relations=['r0','r1'],entities=[dict(entity_type='X') for _ in range(4)],registry={k:dict(domain=['X'],range=['X']) for k in ['r0','r1']})
        seq=seq_counts(cat,es)
        def count(h,visited,L):
            if L==0:return 1
            return sum(count(v,visited|{v},L-1) for v,r in arcs[h] if v not in visited)
        for L in [2,3]:
            self.assertEqual(sum(x['all_candidate_paths'] for x in seq if x['length']==L),sum(count(h,{h},L) for h in range(4)))
    def test_role_order_is_not_commutative(self):
        rv=np.eye(3,dtype=np.float32);a=relation_feature([0,1],rv);b=relation_feature([1,0],rv)
        self.assertFalse(np.allclose(a,b));self.assertGreater(a[1],b[1])
    def test_no_path_fallback_and_historical_replay(self):
        rows=[json.loads(x) for x in gzip.decompress((EXP/'completion/query_ranks.jsonl.gz').read_bytes()).decode().splitlines()];lu={(x['method'],x['seed'],x['id'],x['task']):x for x in rows}
        support=np.load(EXP/'completion/P4_B3_full_support.npz')['support'];fallback=0
        for x in rows:
            if x['method']=='P4_B3_full' and not support[x['key_index']].any():
                self.assertEqual(x['rank'],lu['SimKGC_G2',x['seed'],x['id'],x['task']]['rank']);fallback+=1
        self.assertGreater(fallback,0)
        results=read(EXP/'completion/freeze.json')['summary'];mean=next(x['MRR_mean'] for x in results if x['method']=='transport_R3_historical')
        old=np.mean([read(OLD/f'models/transport_R3_s{s}/complete.json')['validation_link_MRR'] for s in SEEDS]);self.assertAlmostEqual(mean,float(old),places=12)
    def test_random_control_effective_count_degree_types(self):
        def stats_(rows):
            pairs={tuple(sorted([x['a'],x['b']])) for x in rows};typ=[x['entity_type'] for x in self.cat['entities']]
            return len(pairs),Counter(v for x in pairs for v in x),Counter(tuple(sorted([typ[a],typ[b]])) for a,b in pairs)
        self.assertEqual(stats_(read(EXP/'bridges/B3.jsonl')),stats_(read(EXP/'bridges/random_degree_matched.jsonl')))
    def test_all_seeds_and_test_remains_unscored(self):
        f=read(EXP/'completion/freeze.json');self.assertFalse(f['test_evaluated']);self.assertEqual(f['directions'],374)
        rr=list(csv.DictReader((EXP/'completion/seed_results.csv').open()))
        for method in {x['method'] for x in rr}:self.assertEqual({int(x['seed']) for x in rr if x['method']==method},set(SEEDS))
        self.assertFalse((EXP/'data/test_targets.jsonl').exists())

def preservation():
    prior=read(EXP/'verification/prior_files.json');missing=[];changed=[]
    for x in prior:
        p=ROOT/x['path']
        if not p.exists():missing.append(x['path']);continue
        s=p.stat()
        if s.st_size!=x['bytes'] or s.st_mtime_ns!=x['mtime_ns']:changed.append(x['path'])
    reused=read(EXP/'verification/reused_input_hashes.json')
    for path,value in reused.items():assert sha(ROOT/path)==value,path
    domain=read(EXP/'verification/domain_inputs.json');current={path:sha(ROOT/path) for path in domain['hashes']}
    # Both checkout files and pinned domain Git blobs must agree with the recorded inputs.
    assert current==domain['hashes']
    assert not missing and not changed,(missing,changed)
    return dict(prior_files_checked=len(prior),missing=missing,metadata_changes=changed,reused_cache_sha256_checks=len(reused),domain_sha256_checks=len(current),note='all prior file sizes/mtime unchanged, used caches and domain inputs additionally SHA256 checked; not a byte hash of every unrelated checkpoint')

def main():
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Invariants))
    assert result.wasSuccessful()
    save(EXP/'verification/checks.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=True,preservation=preservation()))

if __name__=='__main__':main()
