"""Same proxy pairs/LODO probe, correcting actual native role serialization."""
import json
from collections import Counter
import numpy as np
import torch
from torch.nn import functional as F
from transformers import AutoModel,AutoTokenizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from io_utils import *
from native_role_correction import COR


def main():
    if (COR/'probe_complete.json').exists():return
    pairs=read(EXP/'feature_analysis/pairs.jsonl');roles=read(COR/'cell_roles.json');texts=[]
    def corrected(text):
        if ' 适用和证据绑定：' not in text:return text
        head,body=text.split(' 适用和证据绑定：',1);info=json.loads(body)
        for x in info:
            for u in x['layout']:
                role=roles.get(u.get('cell_id'))
                if role is not None:u['role']=role
        return head+' 适用和证据绑定：'+canonical(info)
    for p in pairs:texts += [corrected(p['positive']),corrected(p['proxy_negative'])]
    folder=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d';tok=AutoTokenizer.from_pretrained(folder,local_files_only=True);m=AutoModel.from_pretrained(folder,local_files_only=True).cuda().eval();torch.set_num_threads(2);zz=[];ids=[]
    with torch.no_grad():
        for off in range(0,len(texts),64):
            b=tok(texts[off:off+64],padding='max_length',truncation=True,max_length=192,return_tensors='pt');ids+=b['input_ids'].tolist();z=m(**{k:v.cuda() for k,v in b.items()}).last_hidden_state[:,0];zz.append(F.normalize(z,dim=-1).cpu().numpy())
    z=np.concatenate(zz);y=np.tile([1,0],len(pairs));docs=np.repeat([p['doc'] for p in pairs],2);results=[];observability=Counter()
    for i,p in enumerate(pairs):
        key='still_identical_after_truncation' if ids[2*i]==ids[2*i+1] else 'newly_observable_not_semantically_verified' if p['old_inputs_equal'] else 'already_observable_object_or_direction'
        observability[key]+=1
    for seed in SEEDS:
        pred=np.zeros(len(y))
        for doc in sorted(set(docs)):
            fit=docs!=doc;probe=~fit;s=StandardScaler();a=s.fit_transform(z[fit]);b=s.transform(z[probe]);clf=LogisticRegression(C=1.,max_iter=1000,random_state=seed).fit(a,y[fit]);pr=clf.predict_proba(b)[:,1];pred[probe]=pr
            results.append(dict(seed=seed,held_document=doc,n=int(probe.sum()),AUC=roc_auc_score(y[probe],pr),balanced_accuracy=balanced_accuracy_score(y[probe],pr>=.5)))
        results.append(dict(seed=seed,held_document='ALL_OUT_OF_FOLD',n=len(y),AUC=roc_auc_score(y,pred),balanced_accuracy=balanced_accuracy_score(y,pred>=.5)))
    csvsave('native_role_correction/proxy_lodo_results.csv',results);save(COR/'probe_complete.json',dict(pairs=len(pairs),observability=observability,pooled=[r for r in results if r['held_document']=='ALL_OUT_OF_FOLD'],no_hyperparameter_change=True,proxy_only=True))
    print(read(COR/'probe_complete.json'),flush=True)


if __name__=='__main__':main()
