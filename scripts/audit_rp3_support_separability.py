#!/usr/bin/env python3
"""Build-only score, input-aliasing and full-training-gradient audit. No updates."""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, _write_immutable
from src.research_point_3.dataset import collate_teacher_batch
from src.research_point_3.diagnostics import binary_summary
from src.research_point_3.experiment_io import prepare
from src.research_point_3.joint_contract import hard_empty_rows, hard_negative_support_loss
from src.research_point_3.losses import LossWeights, compute_evidence_controller_loss
from src.research_point_3.training import load_controller_checkpoint, _targets_on_device


def score_metrics(rows):
    import numpy as np
    positives=np.array([r['probability'] for r in rows if r['label']==1])
    negatives=np.array([r['probability'] for r in rows if r['label']==0])
    auc=float(((positives[:,None]>negatives[None,:]).sum()+.5*(positives[:,None]==negatives[None,:]).sum())/(len(positives)*len(negatives))) if len(positives) and len(negatives) else None
    result=binary_summary([r['probability'] for r in rows],[r['label'] for r in rows])
    result.update(roc_auc=auc,positive_quantiles=(np.quantile(positives,[0,.25,.5,.75,1]).tolist() if len(positives) else None),
                  negative_quantiles=(np.quantile(negatives,[0,.25,.5,.75,1]).tolist() if len(negatives) else None))
    return result


def alias_statistics(rows,key):
    groups=defaultdict(list)
    for row in rows:groups[row[key]].append(row)
    conflicts=[];minimum_errors=0;minimum_ce=0.
    for identity,items in groups.items():
        ones=sum(r['label'] for r in items);zeros=len(items)-ones
        minimum_errors+=min(ones,zeros)
        if ones and zeros:
            p=ones/len(items)
            minimum_ce+=-ones*math.log(p)-zeros*math.log1p(-p)
            conflicts.append({'input_sha256':identity,'positive_count':ones,'negative_count':zeros,
                              'occurrences':[{k:r[k] for k in ('trace_id','evidence_id','label','hard_empty')} for r in items]})
    return {'occurrences':len(rows),'unique_inputs':len(groups),'conflicting_inputs':len(conflicts),
            'empirical_minimum_01_errors':minimum_errors,'empirical_minimum_01_error_rate':minimum_errors/len(rows),
            'empirical_minimum_unweighted_bce':minimum_ce/len(rows),'conflicts':conflicts}


def gradient_audit(model,batch):
    import torch
    import torch.nn.functional as F
    model.eval()
    output=model(batch['query_features'],batch['candidate_features'],batch['availability_mask'],batch['selection_budget'])
    eligible=batch['availability_mask']&batch['requested_candidate_mask']
    labels=batch['support_labels'];positive=eligible&(labels==1);negative=eligible&(labels==0)
    counts=batch['cardinality_labels'][batch['requested_field_mask']]
    terms={'positive':F.softplus(-output.support_logits[positive]).mean(),
           'negative':F.softplus(output.support_logits[negative]).mean(),
           'hard_empty':hard_negative_support_loss(output.support_logits,labels,eligible,counts,5/129),
           'base':compute_evidence_controller_loss(output,_targets_on_device(batch,torch.device('cpu')),
               weights=LossWeights(ranking=1,support=1,field_state=.6,cardinality=.6,route=0,intervention=0,calibration=0),
               field_loss_normalization='requested_balanced').total}
    named=list(model.named_parameters());parameters=[p for _,p in named]
    gradients={}
    for key,loss in terms.items():
        gradients[key]=torch.autograd.grad(loss,parameters,retain_graph=True,allow_unused=True)
    result={}
    for scope in ('all','shared','support_head'):
        indexes=[i for i,(name,_) in enumerate(named) if scope=='all' or
                 (scope=='support_head' and name.startswith('support_head.')) or
                 (scope=='shared' and name.startswith(('query_encoder.','evidence_encoder.','candidate_fusion.')))]
        vectors={key:torch.cat([(grad[i] if grad[i] is not None else torch.zeros_like(parameters[i])).detach().flatten().double()
                               for i in indexes]) for key,grad in gradients.items()}
        norms={k:float(v.norm()) for k,v in vectors.items()}
        pairs={}
        for a,b in [('positive','hard_empty'),('positive','negative'),('base','hard_empty')]:
            dot=float(torch.dot(vectors[a],vectors[b]));den=norms[a]*norms[b]
            pairs[a+'_vs_'+b]={'dot':dot,'cosine':dot/den if den else None}
        result[scope]={'norms':norms,'pairs':pairs,
            'weighted_hard_to_base_norm_ratio':.25*norms['hard_empty']/norms['base'] if norms['base'] else None,
            'positive_directional_derivative_for_negative_base_step':-float(torch.dot(vectors['positive'],vectors['base'])),
            'positive_directional_derivative_for_negative_w1_step':-float(torch.dot(vectors['positive'],vectors['base']+.25*vectors['hard_empty']))}
    return {'losses':{k:float(v.detach()) for k,v in terms.items()},'geometry':result,
            'scope':'CPU eval-mode full train batch at saved checkpoint; no parameter update; not historical minibatch/AdamW trajectory'}


def main():
    import torch
    torch.set_num_threads(1)
    out=ROOT/'results/experiments/research_point_3/support_separability_v1'
    if out.exists():raise FileExistsError('preserve prior audit')
    base=ROOT/'results/experiments/research_point_3'
    prepared=prepare(base/'field_normalization_v1/seed_7042027/requested_balanced/config.json',attach_development=False)
    batches={};identities={};label_rows=[]
    for ds in (prepared.train_dataset,prepared.validation_dataset):
        split=ds.traces[0].split.value;batch=collate_teacher_batch([ds[i] for i in range(len(ds))]);batches[split]=batch
        eligible=batch['availability_mask']&batch['requested_candidate_mask']
        hard=hard_empty_rows(batch['support_labels'],eligible,batch['cardinality_labels'][batch['requested_field_mask']])
        items=[]
        for i,t in enumerate(ds.traces):
            q=batch['query_features'][i].numpy().tobytes()
            context=hashlib.sha256(q+batch['candidate_features'][i].numpy().tobytes()+batch['availability_mask'][i].numpy().tobytes()+batch['selection_budget'][i].numpy().tobytes()).hexdigest()
            for j,eid in enumerate(t.candidate_evidence_ids):
                if not eligible[i,j] or batch['support_labels'][i,j]==-100:continue
                item={'trace_id':t.trace_id,'scenario_id':t.query.scenario_id,'split':split,'perturbation_id':t.perturbation_id,
                      'evidence_id':eid,'label':int(batch['support_labels'][i,j]),'hard_empty':bool(hard[i]),
                      'row_index':i,'candidate_index':j,'pointwise_key':hashlib.sha256(q+batch['candidate_features'][i,j].numpy().tobytes()).hexdigest(),
                      'full_context_key':context+'/'+str(j)}
                items.append(item);label_rows.append(item)
        identities[split]=items
    aliases={split:{key:alias_statistics(items,key) for key in ('pointwise_key','full_context_key')} for split,items in identities.items()}
    reports={};all_rows=[];bindings={}
    for seed in (7042027,7042028,7042029):
        for arm in ('C0','W1','J1'):
            directory=base/(f'field_normalization_v1/seed_{seed}/requested_balanced' if arm=='C0' else f'joint_contract_v1/seed_{seed}/{arm}')
            mp=directory/'bootstrap/training_manifest.json';m=json.loads(mp.read_text());checkpoint=directory/'bootstrap'/m['checkpoint_file']
            assert file_sha256(checkpoint)==m['checkpoint_sha256']
            bindings[str(checkpoint.relative_to(ROOT))]=file_sha256(checkpoint);bindings[str(mp.relative_to(ROOT))]=file_sha256(mp)
            model,_=load_controller_checkpoint(checkpoint,expected_input_fingerprint=prepared.input_fingerprint);model.eval()
            metrics={};invariance={}
            for split,batch in batches.items():
                with torch.no_grad():
                    output=model(batch['query_features'],batch['candidate_features'],batch['availability_mask'],batch['selection_budget'])
                rows=[]
                for item in identities[split]:
                    logit=float(output.support_logits[item['row_index'],item['candidate_index']]);prob=float(torch.sigmoid(torch.tensor(logit)))
                    r={**item,'seed':seed,'arm':arm,'logit':logit,'probability':prob};rows.append(r);all_rows.append(r)
                for kind in ('all','original','derived'):
                    selected=[r for r in rows if kind=='all' or (r['perturbation_id']=='original')==(kind=='original')]
                    metrics[split+'_'+kind]=score_metrics(selected)
                    metrics[split+'_'+kind]['by_scenario']={s:score_metrics([r for r in selected if r['scenario_id']==s]) for s in sorted({r['scenario_id'] for r in selected})}
                buckets=defaultdict(list)
                for r in rows:buckets[r['pointwise_key']].append(r['logit'])
                invariance[split]={'max_logit_spread_for_identical_pointwise_input':max(max(v)-min(v) for v in buckets.values())}
            reports[f'{arm}/{seed}']={'metrics':metrics,'pointwise_invariance':invariance,'gradients':gradient_audit(model,batches['train'])}
            print(f'[support audit] {arm}/{seed}',flush=True)
    result={'schema':'rp3_support_separability_audit_v1','aliases':aliases,'reports':reports,'input_fingerprint':prepared.input_fingerprint,
            'bindings':bindings,'development_read':False,'external_read':False,'updates_performed':False,
            'label_boundary':'frozen replay variability may be context dependence or verifier variability; context differences do not establish causal correctness'}
    _write_immutable(out/'audit.json',canonical_json_bytes(result));_write_immutable(out/'candidate_rows.jsonl',canonical_jsonl_bytes(all_rows))
    lines=['# 支持可分性、观测别名与梯度审计','','只读已有checkpoint，仅构建集。', '',
           '| split | 同输入定义 | 出现项 | 唯一输入 | 标签冲突组 | 最少错误项 | BCE经验下界 |','|---|---|---:|---:|---:|---:|---:|']
    for split,keys in aliases.items():
        for key,m in keys.items():lines.append(f"| {split} | {key} | {m['occurrences']} | {m['unique_inputs']} | {m['conflicting_inputs']} | {m['empirical_minimum_01_errors']} | {m['empirical_minimum_unweighted_bce']:.6f} |")
    lines+=['','| 臂/seed | 原始val支持AUC | AP | 正支持召回@0.5 | cos(g+,gH)全参数 | .25gH/gBase范数 |','|---|---:|---:|---:|---:|---:|']
    for key,r in reports.items():
        m=r['metrics']['validation_original'];g=r['gradients']['geometry']['all']
        lines.append(f"| {key} | {m['roc_auc']:.4f} | {m['auprc_average_precision']:.4f} | {m['recall']:.4f} | {g['pairs']['positive_vs_hard_empty']['cosine']:.4f} | {g['weighted_hard_to_base_norm_ratio']:.4f} |")
    lines+=['','梯度为已选checkpoint上的全train eval-mode局部诊断，不是历史训练轨迹或因果证明。',
            '同输入标签冲突下界仅适用于这些经验出现项上的确定性点式分类器；不等于外部风险下界。完整上下文能区分这些输入，不保证新模型能正确学习，也不证明教师变化全由上下文引起。']
    _write_immutable(out/'audit.md',('\n'.join(lines)+'\n').encode());print('\n'.join(lines))


if __name__=='__main__':main()
