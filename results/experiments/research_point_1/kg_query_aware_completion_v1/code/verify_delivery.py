"""Read-only protected-asset checks, cached-score replay and explicit costs."""
import gc
import time
import platform
import subprocess
import numpy as np
import torch
from io_utils import *
from eval_core import Evaluator
from retrieval import Retriever
from query_model import Context,Residual
from fixed_baselines import Fixed
from build_index import edge_sources


def main():
    torch.set_num_threads(2);checks=[];prior_counts=[]
    for root,name in [(PILOT/'runs/20261114_controlled_v1','delivery_manifest.json'),(PILOT/'runs/20261114_relation_collab_v1','delivery_manifest.json'),(PILOT/'runs/20261116_role_contribution_v1','role_delivery_manifest.json'),(PILOT/'runs/20261116_role_contribution_clean_v2','role_delivery_manifest.json')]:
        rows=read(root/'verification'/name)['files']
        for x in rows:assert file_sha(PILOT/x['path'])==x['sha256'],x['path']
        prior_counts.append(dict(manifest=str((root/'verification'/name).relative_to(ROOT)),files=len(rows)))
    checks.append('Previous four complete delivery manifests byte-identical')
    for name,sha in read(EXP/'data/freeze.json')['inputs'].items():assert file_sha(ROOT/name)==sha,name
    for row in read(PILOT/'runs/20261114_controlled_v1/verification/build_pdf_preservation.json'):assert file_sha(ROOT/row['path'])==row['sha256']
    for name,sha in read(EXP/'data/freeze.json')['files'].items():assert file_sha(EXP/name)==sha,name
    for name,sha in read(EXP/'verification/test_release.json')['code'].items():assert file_sha(EXP/'code'/name)==sha,name
    checks.append('Locked domain inputs, 15 PDFs, data freeze and main pretest code unchanged')
    reg=read(EXP/'data/training_source_registry.json');blocked=set(read(EXP/'audit_only/copy_blockers.json')['quotegrams'])
    def nested(v):
        if isinstance(v,str):yield v
        elif isinstance(v,list):
            for x in v:yield from nested(x)
        elif isinstance(v,dict):
            for k,x in v.items():
                if k in ['text','conditions_source','evidence_units','expansion_source_witnesses']:yield from nested(x)
    for e in read(EXP/'index/edges.jsonl'):
        for x in edge_sources(e,reg):assert all(not shingles(t)&blocked for t in nested(x))
    checks.append('Nested condition/layout evidence has no held quote overlap under declared 20grams')
    cat=read(EXP/'data/catalogue.json');targets=read(EXP/'audit_only/test_targets.jsonl');index={tuple(x['triple']):i for i,x in enumerate(targets)}
    ev=Evaluator(targets,read(EXP/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])));replay=[]
    for method in ['simkgc_G2','collab_full','query_full','fixed_R3','transport_R3','knn_train_log','knn_candidates_log']:
        path=EXP/'evaluation'/f'{method}_s{SEEDS[0]}';z=np.load(path/'scores.npz')
        def p(h,r,t,task):return z[task][index[h,r,t]]
        m,rows=ev.score(p);saved=read(path/'rankings.jsonl');assert [(x['rank'],x['ties']) for x in rows]==[(x['rank'],x['ties']) for x in saved]
        assert m['link_MRR']==read(path/'metrics.json')['link_MRR'];replay.append(dict(method=method,MRR=m['link_MRR'],all_rows_identical=True))
    for method in ['knn_train_log','knn_candidates_log']:
        for seed in SEEDS:
            if read(EXP/'models'/f'{method}_s{seed}'/'complete.json')['alpha']!=0:continue
            a=read(EXP/'evaluation'/f'{method}_s{seed}'/'rankings.jsonl');b=read(EXP/'evaluation'/f'simkgc_G2_s{seed}'/'rankings.jsonl')
            assert [(x['rank'],x['ties']) for x in a]==[(x['rank'],x['ties']) for x in b]
    checks.append('Seven raw-score ranking replays exact; kNN alpha0 exactly recovers G2 ranks')
    # Timing preloaded catalogue queries only. No model/threshold changes.
    retriever=Retriever();keys=sorted([(h,r) for h in range(cat['nbase']) for r in range(len(cat['relations']))],key=lambda k:digest(['latency',k]))[:100];lat=[]
    for strategy in ['R0','R1','R2','R3']:
        values=[]
        for h,r in keys[:3]:retriever.search([h],[r],strategy,k=16)
        for h,r in keys:
            torch.cuda.synchronize();start=time.perf_counter();retriever.search([h],[r],strategy,k=16);torch.cuda.synchronize();values.append(1000*(time.perf_counter()-start))
        lat.append(dict(stage='live_preloaded_retrieval',method=strategy,n=100,mean_ms=float(np.mean(values)),p50_ms=float(np.median(values)),p95_ms=float(np.quantile(values,.95))))
    del retriever;gc.collect();torch.cuda.empty_cache()
    for method in ['fixed_R3','transport_R3','query_full']:
        if method=='query_full':
            ctx=Context(SEEDS[0]);model=Residual().cuda();model.load_state_dict(torch.load(EXP/'models'/f'query_full_s{SEEDS[0]}'/'best.pt',map_location='cuda',weights_only=True));model.eval()
            def forward(k):
                with torch.no_grad():
                    q,x,m,*_=ctx.values([k[0]],[k[1]],'full');return model(q,x,m)@ctx.data['entities'][:cat['nbase']].T
        else:
            cfg=read(EXP/'models'/f'{method}_s{SEEDS[0]}'/'complete.json');model=Fixed(SEEDS[0],method,cfg['alpha']);forward=lambda k:model.score([k])
        for k in keys[:3]:forward(k)
        values=[]
        for k in keys:
            torch.cuda.synchronize();start=time.perf_counter();forward(k);torch.cuda.synchronize();values.append(1000*(time.perf_counter()-start))
        lat.append(dict(stage='cached_retrieval_fusion_and_2150_scoring',method=method,n=100,mean_ms=float(np.mean(values)),p50_ms=float(np.median(values)),p95_ms=float(np.quantile(values,.95))))
        del model
        if method=='query_full':del ctx
        gc.collect();torch.cuda.empty_cache()
    csvsave('analysis/runtime_latency.csv',lat)
    trained=[]
    for p in sorted((EXP/'models').glob('*/best.pt')):
        folder=p.parent;c=read(folder/'complete.json');cfg=read(folder/'config.json')
        assert file_sha(p)==c['checkpoint_sha256']
        trained.append(dict(model=folder.name,fit_seconds=c['seconds'],peak_cuda_bytes=c['peak_cuda_bytes'],best_epoch=c['best_epoch'],executed_epochs=c.get('executed_epochs'),parameters=cfg['parameters']))
    assert len(trained)==39
    csvsave('analysis/training_costs.csv',trained)
    save(EXP/'analysis/cost_summary.json',dict(trained_models=len(trained),summed_fit_worker_seconds=sum(x['fit_seconds'] for x in trained),max_torch_peak_bytes=max(x['peak_cuda_bytes'] for x in trained),new_encoder_training_models=9,new_old_architecture_models=6,new_minimal_adapters=24,output_checkpoints_bytes=sum(p.stat().st_size for p in (EXP/'models').glob('*/best.pt')),index_encoding_seconds=read(EXP/'index/freeze.json')['seconds'],latency_note='Preloaded finite catalogue-query experiment. Retrieval and fusion/scoring are measured separately; not end-to-end new-text latency or edge hardware. No encoder/cache/disk startup cost included in warm query timing. Worker sum is not wall time.'))
    save(EXP/'verification/checks.json',dict(passed=True,checks=checks,old_manifests=prior_counts,score_replays=replay,unit_test_log=file_sha(EXP/'tests.log'),domain_object=I.REV,formal_graph_changes=0,RP2_RP3_changes=0,independent_fact_accuracy_certified=False))
    save(EXP/'verification/runtime.json',dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),repository_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    print('VERIFIED 39 trained models, four prior manifests, inputs, code and score replays.',flush=True)


if __name__=='__main__':main()
