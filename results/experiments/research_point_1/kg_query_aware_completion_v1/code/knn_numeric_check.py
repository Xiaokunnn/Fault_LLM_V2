"""Correct probability-scale tie artifacts, retaining original evaluations.

Only a monotone output representation changes; no KGC fitting/hyperparameter
grid changes. Lambda is selected again on validation in the corrected scale.
"""
import gc
import numpy as np
import torch
from io_utils import *
from fixed_baselines import Fixed,evaluate_valid
from eval_core import Evaluator


class FixedLog(Fixed):
    @torch.no_grad()
    def score(self,keys):
        result=[]
        for off in range(0,len(keys),128):
            kk=keys[off:off+128];h=torch.tensor([k[0] for k in kk],device='cuda');r=torch.tensor([k[1] for k in kk],device='cuda')
            q=self.ctx.data['queries'][h,r];raw=q@self.ctx.data['entities'][:self.n].T
            if self.alpha==0:score=raw
            else:
                base=torch.softmax(20*raw,-1);v,ix=(q@self.memory.T).topk(min(16,len(self.memory)),dim=-1)
                memory=torch.zeros_like(base);memory.scatter_add_(1,self.targets[ix],torch.softmax(v/.05,-1))
                score=torch.log(((1-self.alpha)*base+self.alpha*memory).clamp_min(1e-30))
            result.append(score.cpu().numpy())
        return np.concatenate(result)


def main():
    torch.set_num_threads(2);cat=read(EXP/'data/catalogue.json');ev=Evaluator.validation(cat);models=[]
    for seed in SEEDS:
        for method in ['knn_train','knn_candidates']:
            folder=EXP/'models'/f'{method}_log_s{seed}';m=FixedLog(seed,method,0.);history=[]
            for alpha in [0.,.05,.1,.2]:
                m.alpha=alpha;history.append(dict(alpha=alpha,validation_link_MRR=evaluate_valid(m,ev)))
            best=max(history,key=lambda x:x['validation_link_MRR']);save(folder/'history.jsonl',history)
            save(folder/'complete.json',dict(**best,method=method+'_log',seed=seed,no_test_selection=True,implementation='Same kNN probability interpolation; log score for numerical ties, alpha0 exact raw cosine fallback',trained_parameters=0))
            models.append((method,seed));del m;gc.collect();torch.cuda.empty_cache()
    save(EXP/'verification/knn_numeric_release.json',dict(configs={f'{m}_log_s{s}':file_sha(EXP/'models'/f'{m}_log_s{s}'/'complete.json') for m,s in models},
        code=file_sha(Path(__file__)),reason='Probability output compresses small scores below fixed absolute tie tolerance; preserve old results and correct score representation only',no_main_model_changes=True))
    targets=read(EXP/'audit_only/test_targets.jsonl');R=len(cat['relations']);ev=Evaluator(targets,read(EXP/'audit_only/test_truth.json'),cat,list(range(cat['nbase'])))
    keys=sorted({k for x in targets for k in [(x['triple'][2],x['triple'][1]+R)]+[(x['triple'][0],r) for r in range(R)]});idx={k:i for i,k in enumerate(keys)}
    for method,seed in models:
        out=EXP/'evaluation'/f'{method}_log_s{seed}';cfg=read(EXP/'models'/f'{method}_log_s{seed}'/'complete.json');matrix=FixedLog(seed,method,cfg['alpha']).score(keys)
        def predict(h,r,t,task):return np.array([matrix[idx[h,j],t] for j in range(R)]) if task=='relation' else matrix[idx[(h,r) if task=='tail' else (t,r+R)]]
        matrices={task:np.stack([predict(*x['triple'],task) for x in targets]) for task in ['head','tail','relation']}
        metrics,rows=ev.score(predict);save(out/'metrics.json',dict(metrics,method=method+'_log',seed=seed,proxy_only=True));save(out/'rankings.jsonl',rows)
        out.mkdir(exist_ok=True,parents=True);np.savez_compressed(out/'scores.npz',**matrices)
        save(out/'complete.json',dict(supplemental_numeric_correction=True,raw_probability_results_preserved=True,no_test_selection=True))
        print(method+'_log',seed,cfg['alpha'],metrics['link_MRR'],flush=True);gc.collect();torch.cuda.empty_cache()
    save(EXP/'verification/knn_numeric_notes.md','''# kNN数值检查

初始57项评分全部保留。kNN直接返回概率，在绝对1e-8并列容差下可能将小概率错误合并，甚至lambda=0时排名偏离原G2。补充实现返回log混合概率；lambda=0直接返回原余弦分数，确保退回G2的身份一致。只在相同验证集和原四项lambda网格重新选择，未改训练、检索或主模型；补充配置封存后才评分。

主强基线采用knn_*_log，概率版本作为数值诊断附带结果。两者不能当两次独立算法试验。所有候选答案仍2150，模型得分和log概率都不是事实可信概率。
''')


if __name__=='__main__':main()
