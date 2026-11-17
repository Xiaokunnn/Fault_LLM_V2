"""Export actual path use and full-prototype triple scores for all three seeds."""
import gzip
import numpy as np
import torch
from raw_io import *
from run_completion import path_support

def main():
    if (EXP/'completion/path_usage.npz').exists():return
    torch.set_num_threads(4);methods=read(EXP/'completion/methods.json');usage={};pools={};full=None
    for name,(kind,mode) in methods.items():
        if kind not in ['B0','B1','B2','B3','random']:continue
        if kind not in pools:pools[kind]=dict(np.load(EXP/f'paths/{kind}.npz'))
        for seed in SEEDS if mode=='shuffle_endpoint' else [SEEDS[0]]:
            s,n,u=path_support(pools[kind],mode,seed,return_usage=True)
            suffix=name+(f'_s{seed}' if mode=='shuffle_endpoint' else '')
            usage.update({suffix+'__'+k:v for k,v in u.items()})
            if name=='P4_B3_full':full=(s,u)
    npz(EXP/'completion/path_usage.npz',**usage)
    rows=[json.loads(x) for x in gzip.decompress((EXP/'completion/query_ranks.jsonl.gz').read_bytes()).decode().splitlines() if json.loads(x)['method']=='P4_B3_full'];alpha=read(EXP/'completion/freeze.json')['selected']['P4_B3_full'];keys=read(EXP/'paths/query_keys.json');support,u=full;output=[]
    for seed in SEEDS:
        f=torch.load(OLD/'features'/f'G2_s{seed}.pt',map_location='cpu',weights_only=True);q=f['queries'][[x[0] for x in keys],[x[1] for x in keys]];base=(q@f['entities'][:2150].T).numpy()
        for row in rows:
            if row['seed']!=seed:continue
            i=row['key_index'];t=row['top1'];target=row['target']
            def paths_for(entity):return [dict(path_index=int(j),score=float(u['scores'][i,j])) for j in np.where(u['picked'][i]&(u['destinations'][i]==entity))[0]]
            output.append(dict(seed=seed,claim_id=row['id'],task=row['task'],query=keys[i],top1=t,top1_score=float(base[i,t]+alpha*support[i,t]),top1_text_score=float(base[i,t]),top1_path_support=float(support[i,t]),used_top1_paths=paths_for(t),reference_target=target,reference_score=float(base[i,target]+alpha*support[i,target]),reference_paths_posthoc=paths_for(target),all_reranking_paths_reference='completion/path_usage.npz, P4_B3_full__picked',score_is_probability=False))
    out=EXP/'analysis/predictions_with_paths.jsonl.gz'
    out.write_bytes(gzip.compress((''.join(canonical(x)+'\n' for x in output)).encode(),mtime=0))
    save(EXP/'PREDICTION_TRACES.md','# 逐预测路径与分数\n\n`analysis/predictions_with_paths.jsonl.gz`保存完整B3原型全部374方向×3种子的过滤后top1、三元组分数、文本分数、路径支持和实际TopM路径索引/分数。reference字段仅作事后评价，不进入路径生成。\n\n`completion/path_usage.npz`对每个原始路径方法保存实际采用的picked掩码、端点及评分；终点打乱对照逐种子分开保存。与`paths/{B0,B1,B2,B3,random}.npz`联接后恢复每条路径的节点、原向/逆向关系及来源边。匹配随机和固定标度无关系补充控制各自有独立代码、支持矩阵及冻结摘要。\n\nR3和普通kNN的实际检索ID/分数保存在`completion/{R3,R3_soft,knn}_retrieval.npz`。全方法排名保存在`completion/query_ranks.jsonl.gz`，补充随机控制的排名位于其独立目录。无路径查询严格回退文本基线已通过测试。\n')
    print('EXPORTED',len(output),'scored predictions and path masks for',len(usage)//3,'method/seed views',flush=True)

if __name__=='__main__':main()
