"""Independent diagnostic of observability, not another KGC gate objective."""
from collections import Counter,defaultdict
import copy
import time
import numpy as np
import torch
from transformers import AutoModel,AutoTokenizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from io_utils import *
from build_index import bindings,edge_sources


def main():
    if (EXP/'feature_analysis/complete.json').exists():return
    torch.set_num_threads(2);cat=read(EXP/'data/catalogue.json');R=len(cat['relations'])
    edges=read(EXP/'index/edges.jsonl');views=read(EXP/'index/oriented_views.jsonl');reg=read(EXP/'data/training_source_registry.json')
    groups=defaultdict(list)
    for j,e in enumerate(edges):
        ss=edge_sources(e,reg)
        if ss and (e['is_base'] or e['conservative']):groups[ss[0]['doc_id']].append((j,ss))
    pairs=[];counts=Counter();known={tuple(e['triple']) for e in edges}
    for doc,examples in sorted(groups.items()):
        for j,ss in examples:
            e=edges[j];h,r,t=e['triple']
            if h>=cat['nbase']:continue
            original=views[2*j];pos=original['semantic'];variants=[]
            donors=[(k,rr) for k,rr in examples if k!=j and edges[k]['triple'][2]!=t and cat['entities'][edges[k]['triple'][2]]['entity_type']==cat['entities'][t]['entity_type']]
            if donors:
                k,rr=sorted(donors,key=lambda p:digest(['role-donor',e['edge_id'],edges[p[0]]['edge_id']]))[0]
                tt=edges[k]['triple'][2]
                if (h,r,tt) not in known:
                    plain=original['plain'].replace('客体：'+cat['entities'][t]['label_zh']+'。','客体：'+cat['entities'][tt]['label_zh']+'。')
                    variants.append(('object',plain+' 适用和证据绑定：'+canonical(bindings(ss)),tt,r,edges[k]['edge_id']))
            condition_donors=[(k,rr) for k,rr in examples if rr[0].get('conditions_source') and rr[0].get('conditions_source')!=ss[0].get('conditions_source')]
            if ss[0].get('conditions_source') and condition_donors:
                k,rr=condition_donors[0];bad=copy.deepcopy(ss);bad[0]['conditions_source']=rr[0]['conditions_source']
                variants.append(('condition_owner',original['plain']+' 适用和证据绑定：'+canonical(bindings(bad)),t,r,edges[k]['edge_id']))
            rowdonors=[(k,rr) for k,rr in examples if rr[0].get('evidence_unit_ids') and rr[0].get('evidence_unit_ids')!=ss[0].get('evidence_unit_ids')]
            if ss[0].get('evidence_unit_ids') and rowdonors:
                k,rr=rowdonors[0];bad=copy.deepcopy(ss);bad[0]['evidence_unit_ids']=rr[0]['evidence_unit_ids']
                variants.append(('native_owner',original['plain']+' 适用和证据绑定：'+canonical(bindings(bad)),t,r,edges[k]['edge_id']))
            rule=cat['registry'][cat['relations'][r]]
            if cat['entities'][t]['entity_type'] in rule['domain'] and cat['entities'][h]['entity_type'] in rule['range'] and (t,r,h) not in known:
                variants.append(('direction',views[2*j+1]['semantic'],h,r+R,None))
            for kind,neg,nt,nr,donor in variants:
                if counts[kind]>=80:continue
                counts[kind]+=1
                pairs.append(dict(pair_id='FP-'+digest([e['edge_id'],kind,donor])[:20],doc=doc,kind=kind,edge_id=e['edge_id'],donor=donor,
                    positive=pos,proxy_negative=neg,source=ss[:1],h=h,r=r,t=t,nt=nt,nr=nr,proxy_not_verified_false=True,
                    split='probe' if int(digest(['feature-probe-doc',doc])[:8],16)%4==0 else 'fit'))
    path=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d';tok=AutoTokenizer.from_pretrained(path,local_files_only=True);model=AutoModel.from_pretrained(path,local_files_only=True).cuda().eval()
    texts=[v for p in pairs for v in [p['positive'],p['proxy_negative']]];vectors=[];tokens=[]
    with torch.no_grad():
        for off in range(0,len(texts),64):
            b=tok(texts[off:off+64],padding='max_length',truncation=True,max_length=192,return_tensors='pt');tokens+=b['input_ids'].tolist()
            z=model(**{k:v.cuda() for k,v in b.items()}).last_hidden_state[:,0];vectors.append(torch.nn.functional.normalize(z,dim=-1).cpu().numpy())
    z=np.concatenate(vectors);oldvec=torch.load(EXP/'index/vectors.pt',map_location='cpu',weights_only=True);old=[]
    for p in pairs:
        quality=edges[next(i for i,e in enumerate(edges) if e['edge_id']==p['edge_id'])]['features']
        for t,r in [(p['t'],p['r']),(p['nt'],p['nr'])]:
            old.append(quality+[float(oldvec['queries'][p['h'],p['r']]@oldvec['entities'][t]),float(oldvec['relations'][p['r']]@oldvec['relations'][r]),.5])
    old=np.array(old);y=np.tile([1,0],len(pairs));fit=np.repeat([p['split']=='fit' for p in pairs],2);results=[]
    for seed in SEEDS:
        for name,x in [('old_scalar',old),('new_binding_text',z)]:
            scaler=StandardScaler();a=scaler.fit_transform(x[fit]);b=scaler.transform(x[~fit]);clf=LogisticRegression(C=1.,max_iter=1000,random_state=seed).fit(a,y[fit]);pred=clf.predict_proba(b)[:,1]
            results.append(dict(seed=seed,representation=name,fit_records=int(fit.sum()),probe_records=int((~fit).sum()),AUC=roc_auc_score(y[~fit],pred),balanced_accuracy=balanced_accuracy_score(y[~fit],pred>=.5),probe_docs=sorted({p['doc'] for p in pairs if p['split']=='probe'})))
    for i,p in enumerate(pairs):
        p['old_inputs_equal']=bool(np.array_equal(old[2*i],old[2*i+1]));p['new_token_inputs_equal']=tokens[2*i]==tokens[2*i+1]
        p['new_embedding_cosine']=float(z[2*i]@z[2*i+1]);p['observability_class']='still_identical_after_truncation' if p['new_token_inputs_equal'] else 'newly_observable_not_semantically_verified' if p['old_inputs_equal'] else 'already_observable_object_or_direction'
    save(EXP/'feature_analysis/pairs.jsonl',pairs);csvsave('feature_analysis/classifier_results.csv',results)
    inventory=read(EXP/'index/feature_inventory.json');classes=Counter(p['observability_class'] for p in pairs)
    save(EXP/'feature_analysis/complete.json',dict(pairs=len(pairs),kinds=counts,observability=classes,results=results,classifier_not_KGC_supervision=True))
    lines=['# 最小关系语义表示与可辨识性实测\n',f'字段盘点：{canonical(inventory)}。','\n| 类别 | 对照对数 |','| --- | --- |']
    lines += [f'| {k} | {v} |' for k,v in classes.items()]
    lines += ['\n| seed | 表示 | 留出源文档AUC | balanced accuracy |','| --- | --- | --- | --- |']+[f"| {x['seed']} | {x['representation']} | {x['AUC']:.4f} | {x['balanced_accuracy']:.4f} |" for x in results]
    lines += ['\n诊断分类器是独立的小线性读出器，不参与KGC训练，不构成新的门损失。来源按文档固定留出；同一固定特征/划分下三次确定性读出可能完全相同，不能视为三份独立泛化证据。',
        'condition_owner/native_owner只改变条件或地址拥有者，旧15维门输入必然相同。新字段/词元不同表示可观察，不等于模型已正确理解。192词元截断后仍同输入者如实单列。',
        '正例为现有自动证据合同支持的原候选，负例为保持类型合法的代理扰动；其他行的动作可能同样有效。原生行组字段不代表列角色可靠，当前明确列角色均缺失。不得将AUC当真实候选正确率。',
        '输入不同但监督不足：没有对这些代理进行独立事实标注，尤其条件/型号语义可能未由当前查询h,r提供。原始证据/字段缺失者只记录缺失，不编造条件；全部缺失率见index/feature_inventory.json。',
        '所有关系与对象替换仅作诊断，不写入候选索引/训练事实/正式图谱；训练仍只有KGC交叉熵。']
    save(EXP/'FEATURE_ANALYSIS.md','\n'.join(lines)+'\n');print('FEATURE',len(pairs),dict(classes),results,flush=True)


if __name__=='__main__':main()
