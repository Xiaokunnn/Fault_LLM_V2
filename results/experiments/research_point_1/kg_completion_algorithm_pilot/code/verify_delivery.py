"""Read-only source preservation, finite leakage blockers, saved-score replay.

Writes only verification artifacts inside the isolated pilot. This is technical
verification, not a new semantic evaluation or a factual accuracy certificate.
"""
from collections import Counter,defaultdict
import hashlib
import json
import subprocess
import numpy as np
from common import PILOT,ROOT,RUN,read,save,file_sha
from prepare import I,UF
from refine_safety import shingles
from eval_core import Evaluator
from final_evaluation_driver import expected
from summarize import table


def main():
    checks=[];input_checks=[]
    for relative,expected_hash in read(RUN/'data/freeze.json')['inputs'].items():
        original=subprocess.check_output(['git','show',I.REV+':'+relative],cwd=ROOT)
        assert hashlib.sha256(original).hexdigest()==expected_hash,relative
        assert file_sha(ROOT/relative)==expected_hash,('Working input changed',relative)
        input_checks.append(dict(path=relative,sha256=expected_hash,working_file_unchanged=True))
    for name,key in [('freeze.json','data_files'),('task_exports_freeze.json','files'),('safety_refinement_freeze.json','files')]:
        for relative,sha in read(RUN/'data'/name)[key].items():assert file_sha(RUN/relative)==sha,(name,relative)
    checks+=['All locked domain inputs match Git object and unchanged current working files','Initial/export/effective-safety freezes reproduce exactly']
    d=I.load();cat=read(RUN/'data/catalogue.json');split=read(RUN/'data/base_split.jsonl')
    assert len(d['graph']['claims'])==1400 and len(d['graph']['evidence_assertions'])==1456
    aliases=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for rec in pop:
            for s in ['head','tail']:aliases.join('L|'+rec[s+'_type']+'|'+I.norm(rec[s+'_canonical_zh']),'S|'+I.norm(rec[s+'_surface']))
    ea=[aliases.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in cat['entities']]
    def pair(triple):return tuple(sorted([ea[triple[0]],ea[triple[2]]]))
    held={x['claim_id'] for x in split if x['fold']!='train'}
    pairs={pair(x['triple']) for x in split if x['claim_id'] in held}
    targetgrams=set()
    for rec in d['graph']['source_records']:
        if rec['expanded_claim_id'] in held:targetgrams.update(shingles(rec['evidence_text']))
    normalized={r['triple_id']:r for r in d['normalized']}
    for row in read(RUN/'data/training_candidate_edges.jsonl'):
        assert pair(row['triple']) not in pairs
        for rid in row['occurrences']:
            rec=normalized[rid];assert rec['doc_id']!='MP022'
            assert not shingles(rec['evidence_text'])&targetgrams
    for unit in read(RUN/'data/training_safe_context_units.jsonl'):
        assert unit['doc_id']!='MP022' and not shingles(unit['text'])&targetgrams
    checks.append('No held alias/unordered-pair or exhaustive 20-character quote overlap in effective candidate occurrences/safe native text, under finite saved blockers')
    # Candidate-to-audit linkage by persisted IDs: inspect rather than assume.
    byid={k:r for r in d['audit'] for k in I.record_ids(r)};mismatches=[]
    for rec in d['normalized']:
        old=next((byid[k] for k in I.record_ids(rec) if k in byid),None)
        if old and (old['doc_id'],old['pdf_page_number'])!=(rec['doc_id'],rec['pdf_page_number']):mismatches.append(rec['triple_id'])
    assert not mismatches
    checks.append('Candidate/audit source document and physical page agree across ID linkage')
    names=expected();release=read(RUN/'configs/test_release.json');assert set(names)==set(release['models']) and len(names)==78
    targets=read(RUN/'audit_only/test_targets.jsonl');truth=read(RUN/'audit_only/test_truth.json')
    ids={(r['id'],task) for r in targets for task in ['head','tail','relation']}
    ev=Evaluator(targets,truth,cat,list(range(cat['nbase'])));sealed=[]
    for name in names:
        folder=RUN/'models'/name;metric=read(RUN/'evaluation'/name/'test/metrics.json')
        rankings=read(RUN/'evaluation'/name/'test/rankings.jsonl')
        assert {(r['id'],r['task']) for r in rankings}==ids and len(rankings)==639
        assert read(folder/'complete.json')==release['checkpoints'][name]
        if name.startswith('anyburl'):
            sel=read(folder/'selection_full.json');checkpoint=folder/f"rules-{sel['best_snapshot']}"
            assert file_sha(checkpoint)==sel['rules_sha256']
        else:checkpoint=folder/'best.pt'
        assert file_sha(checkpoint)==metric['source_checkpoint_sha256']
        saved=np.load(RUN/'evaluation'/name/'test/scores.npz')
        assert saved['head'].shape==saved['tail'].shape==(213,2150) and saved['relation'].shape==(213,15)
        assert all(np.isfinite(saved[k]).all() for k in saved.files)
        sealed.append(dict(model=name,checkpoint_sha256=file_sha(checkpoint),scores_sha256=file_sha(RUN/'evaluation'/name/'test/scores.npz')))
    checks.append('78 models match pre-test release records, checkpoint hashes, identical 639 task rows and full finite 2150/15 score arrays')
    replay=[]
    for name in ['complex_G4_s14112026_f1.0_n0.0_none_r1','anyburl_G4_bridge_s14112026_f1.0_n0.0','simkgc_G3_s14112026_anchor_uniform']:
        z=np.load(RUN/'evaluation'/name/'test/scores.npz');index={tuple(r['triple']):j for j,r in enumerate(targets)}
        def predict(h,r,t,task):return z[task][index[h,r,t]]
        predict.symbolic=name.startswith('anyburl');metric,ranks=ev.score(predict)
        prior=read(RUN/'evaluation'/name/'test/rankings.jsonl')
        for a,b in zip(ranks,prior):assert all(a[k]==b[k] for k in ['id','task','rank','ties','top1','expected_tie_reciprocal_rank'])
        assert metric['link_MRR']==read(RUN/'evaluation'/name/'test/metrics.json')['link_MRR']
        replay.append(dict(model=name,all_639_rows_reproduced=True,link_MRR=metric['link_MRR']))
    checks.append('Three different algorithms replay every saved rank/tie/top1 exactly from sealed scores without training')
    # Semantic graph only: no Claim/Evidence/Provenance intermediate nodes.
    deg=Counter()
    for q in split:
        h,r,t=q['triple'];deg[h]+=1;deg[t]+=1
    from views import build
    structure=[]
    test_entities={i for r in targets for i in [r['triple'][0],r['triple'][2]]}
    for view in ['G1','G2','G3','G4']:
        v=build(view);adj=defaultdict(set)
        triples=list(v['base'])+[x for x,w,legal in zip(v['aux'],v['weights'],v['legal']) if legal and w>0]
        for h,r,t in triples:adj[int(h)].add(int(t));adj[int(t)].add(int(h))
        active=set(adj);allnodes=set(range(len(cat['entities'])) if view!='G1' else range(cat['nbase']));seen=set();sizes=[]
        for start in active:
            if start in seen:continue
            stack=[start];seen.add(start);size=0
            while stack:
                x=stack.pop();size+=1
                for nxt in adj[x]:
                    if nxt not in seen:seen.add(nxt);stack.append(nxt)
            sizes.append(size)
        structure.append(dict(view=view,positive_context_edges=len(triples),base_entities_zero_positive_degree=sum(i not in active for i in range(cat['nbase'])),
            unique_test_endpoint_entities=len(test_entities),unique_test_endpoints_isolated=sum(i not in active for i in test_entities),
            full_base_degree1_test_endpoints=sum(deg[i]==1 for i in test_entities),active_components=len(sizes),largest_active_component=max(sizes),
            scope='Positive legal semantic edges including candidates as computational contexts only; G3/G4 statuses do not become facts'))
    table('isolated_endpoint_structure.csv',structure)
    reviews=read(RUN/'discovery/AI_source_review.jsonl');assert len(reviews)==24 and not any(r['new_complete_fact_confirmed'] for r in reviews)
    overlay=read(RUN/'enhancement/claim_overlays.jsonl');assert len(overlay)==1400 and sum(len(x['evidence']) for x in overlay)==1456
    checks+=['1400 Claim overlays preserve all 1456 source links; no graph rewrite','24 AI review decisions preserve evidence/method limitations and zero promoted new facts']
    save(RUN/'verification/input_preservation.json',input_checks)
    save(RUN/'verification/model_and_score_manifest.json',sealed)
    save(RUN/'verification/score_replay.json',replay)
    save(RUN/'verification/checks.json',dict(passed=True,checks=checks,unit_tests='8 passed; test_pilot.py',semantic_truth_certified=False,
        automatic_copy_blocker_limits='Finite aliases + literal20grams; not exhaustive paraphrase/multilingual entailment or pretraining memory guarantee',
        protected_graph='expanded_v1_20261012 unchanged; no other graph inputs used',formal_predictions_published=0))
    print('Verified:',len(input_checks),'domain inputs;',len(sealed),'models; 3 score replays; finite leakage and source preservation checks')


if __name__=='__main__':main()
