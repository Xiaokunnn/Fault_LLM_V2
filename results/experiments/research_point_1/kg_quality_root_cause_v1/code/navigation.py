"""Diagnostic traversal can use incoming edges, without adding inverse facts."""
from common import *

PATTERNS={('causes^-1',r) for r in ['diagnosed_by','inspected_by','mitigated_by','prevented_by']}|{('occurs_at^-1',r) for r in ['diagnosed_by','inspected_by','mitigated_by','prevented_by']}|{('causes',r) for r in ['diagnosed_by','inspected_by','mitigated_by','prevented_by']}|{('contains',r) for r in ['inspected_by','maintained_by']}


def main():
    if (OUT/'navigation/complete.json').exists():print('REUSE role-oriented navigation');return
    d,E,C,S=dataset();ledger=[];metrics=[];counts={}
    for view in ['G0','GA','GB','GAB','GC']:
        vc=read(OUT/'counterfactual'/f'{view}_business_claims.jsonl');vs=S
        if view in ['GA','GAB','GC']:
            vs=defaultdict(list)
            for x in read(OUT/'counterfactual'/f"{'GA' if view=='GAB' else view}_business_sources.jsonl"):vs[x['claim_id']].append(x['source'])
        adj=defaultdict(list)
        for c in vc:
            h,t,r=c['head_entity_id'],c['tail_entity_id'],c['relation'];adj[h].append((t,r,c['claim_id']));adj[t].append((h,r+'^-1',c['claim_id']))
        n=local=0;patterncounts=Counter()
        for start,arcs in adj.items():
            for mid,r1,c1 in arcs:
                for end,r2,c2 in adj[mid]:
                    if start==end or c1==c2 or (r1,r2) not in PATTERNS:continue
                    pages={(x['doc_id'],x['pdf_page_number']) for x in vs[c1]}&{(x['doc_id'],x['pdf_page_number']) for x in vs[c2]};n+=1;local+=bool(pages);patterncounts[r1+' -> '+r2]+=1
                    ledger.append(dict(view=view,nodes=[start,mid,end],traversal_pattern=[r1,r2],claim_ids=[c1,c2],same_source_page=bool(pages),conditions_jointly_verified=False,inverse_labels_are_traversal_only=True,new_business_fact=False))
        counts[view]=dict(two_hop_diagnostic_traversals=n,same_source_page_traversals=local,patterns=patterncounts)
        for name,value in [('role_oriented_two_hop_diagnostic_traversals',n),('role_oriented_two_hop_same_source_page',local)]:metrics.append(dict(view=view,projection='semantic_business_navigation',metric=name,value=value,denominator='',unit='claim_pair_traversals',evidence_level='exact_navigation_count',interpretation_limit='Inverse is traversal direction, not a new relation/fact; same page does not prove joint conditions'))
    save('navigation/paths.jsonl',ledger);save('navigation/counts.json',counts)
    f=OUT/'QUALITY_METRICS.csv';rr=list(csv.DictReader(f.open()));assert not any(r['projection']=='semantic_business_navigation' for r in rr);rr+=metrics
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr);f.write_text(s.getvalue())
    save('navigation/complete.json',dict(metric_rows_added=len(metrics),business_inverse_facts_added=0,counts=counts,total_quality_metrics_after_stage=len(rr)))
    print(read(OUT/'navigation/complete.json'),flush=True)


if __name__=='__main__':main()
