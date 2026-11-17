"""All available source-document folds, after tiny fixed probe proved weak."""
from collections import Counter
import numpy as np
import torch
from transformers import AutoTokenizer,AutoModel
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from io_utils import *


def main():
    pairs=read(EXP/'feature_analysis/pairs.jsonl');edges={x['edge_id']:x for x in read(EXP/'index/edges.jsonl')}
    base=torch.load(EXP/'index/vectors.pt',map_location='cpu',weights_only=True);old=[]
    for p in pairs:
        for t,r in [(p['t'],p['r']),(p['nt'],p['nr'])]:old.append(edges[p['edge_id']]['features']+[float(base['queries'][p['h'],p['r']]@base['entities'][t]),float(base['relations'][p['r']]@base['relations'][r]),.5])
    folder=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d';tok=AutoTokenizer.from_pretrained(folder,local_files_only=True);m=AutoModel.from_pretrained(folder,local_files_only=True).cuda().eval();torch.set_num_threads(2)
    texts=[s for p in pairs for s in [p['positive'],p['proxy_negative']]];zz=[]
    with torch.no_grad():
        for off in range(0,len(texts),64):
            b=tok(texts[off:off+64],padding='max_length',truncation=True,max_length=192,return_tensors='pt');z=m(**{k:v.cuda() for k,v in b.items()}).last_hidden_state[:,0];zz.append(torch.nn.functional.normalize(z,dim=-1).cpu().numpy())
    new=np.concatenate(zz);old=np.array(old);y=np.tile([1,0],len(pairs));docs=np.repeat([p['doc'] for p in pairs],2);results=[];predictions={}
    for name,x in [('old_scalar',old),('new_binding_text',new)]:
        for seed in SEEDS:
            allp=np.zeros(len(y))
            for doc in sorted(set(docs)):
                fit=docs!=doc;probe=~fit;s=StandardScaler();a=s.fit_transform(x[fit]);b=s.transform(x[probe]);clf=LogisticRegression(C=1.,max_iter=1000,random_state=seed).fit(a,y[fit]);pr=clf.predict_proba(b)[:,1];allp[probe]=pr
                results.append(dict(representation=name,seed=seed,held_document=doc,n=int(probe.sum()),AUC=roc_auc_score(y[probe],pr),balanced_accuracy=balanced_accuracy_score(y[probe],pr>=.5)))
            predictions[name,str(seed)]=allp
            results.append(dict(representation=name,seed=seed,held_document='ALL_OUT_OF_FOLD',n=len(y),AUC=roc_auc_score(y,allp),balanced_accuracy=balanced_accuracy_score(y,allp>=.5)))
    csvsave('feature_analysis/leave_one_document_out.csv',results)
    save(EXP/'feature_analysis/lodo_notes.md','''# 完整文档留出诊断

最初固定hash probe仅MP018两对、四条记录，不能判断稳定性。随后对全部已构造训练来源文档逐一留出，固定同一线性分类器和C=1，不调超参数、不反馈KGC；每一对都得到一次未见其来源文档的读出预测。全部折与负结果见leave_one_document_out.csv。原固定probe完整保留，未替换或择优报告。

这个扩展仍只是自动来源正例与合成扰动的代理辨识，不是独立专家评价。相同数据和确定性求解器的三个seed不是三份独立证据。某些地址/条件拥有者差异被192词元截断抹除，文本表示也可能只辨别位置字符串而非条件逻辑；分类器表现不能替代KGC指标。
''')
    print([r for r in results if r['held_document']=='ALL_OUT_OF_FOLD'],flush=True)


if __name__=='__main__':main()
