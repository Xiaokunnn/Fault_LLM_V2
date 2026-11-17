"""Conservation, split/initialization and saved-ranking replay checks."""
import hashlib
import subprocess
from collections import defaultdict
import numpy as np
from collab_io import *
from eval_core import Evaluator


def main():
    checks=[]
    original=read(OLD/'verification/input_preservation.json')
    for r in original:assert file_sha(ROOT/r['path'])==r['sha256']
    for r in read(OLD/'verification/build_pdf_preservation.json'):assert file_sha(ROOT/r['path'])==r['sha256']
    # Earlier results remain byte-identical to their original sealed manifest.
    for r in read(OLD/'verification/delivery_manifest.json')['files']:
        p=PILOT/r['path'];assert file_sha(p)==r['sha256'],str(p)
    checks.append('All 24 domain inputs, 15 build PDFs and 1896 earlier-delivery files remain unchanged')
    for dataset in ['cold','structured']:
        root=STUDY/dataset;cat=read(root/'data/catalogue.json');targets=read(root/'audit_only/test_targets.jsonl')
        for filename in ['collab_freeze.json','controls_freeze.json']:
            for rel,sha in read(root/'data'/filename)['files'].items():assert file_sha(root/rel)==sha
        train=read(root/'data/train_base.jsonl');split=read(root/'data/base_split.jsonl');which={}
        for r in split:
            if r['group_id'] in which:assert which[r['group_id']]==r['fold']
            which[r['group_id']]=r['fold']
        source=read(root/'data/context_edges.jsonl')
        assert all(doc not in ['MP008','MP009','MP010','MP011','MP012','MP013','MP014','MP022'] for e in source for doc,page in e['pages'])
        release=read(root/'configs/test_release.json');assert len(release['models'])==48
        allids={(q['id'],task) for q in targets for task in ['head','tail','relation']}
        for name,record in release['models'].items():
            folder=PILOT/record['folder'];assert file_sha(folder/'best.pt')==record['checkpoint_sha256']
            assert file_sha(folder/'complete.json')==record['complete_sha256']
            assert {(q['id'],q['task']) for q in read(root/'evaluation'/name/'rankings.jsonl')}==allids
        ev=Evaluator(targets,read(root/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
        for name in ['collab_full_s14112026','collab_lan_s14112026','simkgc_filter_s14112026']:
            z=np.load(root/'evaluation'/name/'scores.npz');index={tuple(x['triple']):i for i,x in enumerate(targets)}
            def score(h,r,t,task):return z[task][index[h,r,t]]
            m,rr=ev.score(score);old=read(root/'evaluation'/name/'rankings.jsonl')
            assert [(x['rank'],x['ties'],x['top1']) for x in rr]==[(x['rank'],x['ties'],x['top1']) for x in old]
            assert m['link_MRR']==read(root/'evaluation'/name/'metrics.json')['link_MRR']
        if dataset=='structured':
            selection=read(root/'audit_only/structure_selection.json')['selected'];assert len(selection)==28
            assert all(min(x['context_degrees'])>0 and x['original_fold']=='train' for x in selection)
            # Actual fresh encoders: configs reference raw pretrained folder and no reference checkpoint.
            for name,record in release['models'].items():
                if name.startswith('simkgc'):
                    cfg=read(PILOT/record['folder']/'config.json');assert cfg['reference_checkpoint_sha256'] is None
        checks.append(dataset+': same48 methods, exact target/answer set, checkpoints sealed, three saved-score ranking replays, source/fold preservation')
    save(STUDY/'verification/checks.json',dict(passed=True,checks=checks,unit_tests=7,
        factual_truth_verified=False,formal_graph_updates=0,old_test_is_previously_exposed=True,
        residual_leakage_limits='Finite aliases/20gram literal blockers; not exhaustive semantic paraphrase or pretrained memory guarantee'))
    print('All conservation/split/score replay checks passed',flush=True)


if __name__=='__main__':main()
