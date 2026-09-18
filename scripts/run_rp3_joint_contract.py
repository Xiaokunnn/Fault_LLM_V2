#!/usr/bin/env python3
"""Run frozen W1/J1 three-seed controls; reuse C0, preserve all existing artifacts."""
import argparse
import copy
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, canonical_jsonl_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.ablations import ablation_row, seed_statistics
from src.research_point_3.experiment_io import prepare, onnx_feed
from src.research_point_3.field_audit import grouped_field_metrics
from src.research_point_3.joint_diagnostics import augment_joint_row, grouped_joint_metrics
from src.research_point_3.joint_contract import hard_empty_rows
from src.research_point_3.training import load_controller_checkpoint
from src.research_point_3.model import CardFieldStateIndex as State


def checked_control(directory, seed):
    config = json.loads((directory/'config.json').read_text())
    manifest_path = directory/'bootstrap/training_manifest.json'
    m = json.loads(manifest_path.read_text())
    assert m['training_config']==config['training'] and m['training_config']['seed']==seed
    assert stable_sha256({k:v for k,v in m.items() if k!='logical_sha256'})==m['logical_sha256']
    assert not m['development_set']['attached'] and not any(k.startswith('development') for k in config)
    for name in ('checkpoint','history'):
        assert file_sha256(directory/'bootstrap'/m[name+'_file'])==m[name+'_sha256']
    metrics=json.loads((directory/'task_metrics.json').read_text())
    assert file_sha256(directory/'predictions.jsonl')==metrics['predictions_sha256']
    assert metrics['diagnostics']['checkpoint_sha256']==m['checkpoint_sha256']
    assert metrics['diagnostics']['config_sha256']==file_sha256(directory/'config.json')
    names=[directory/'config.json',manifest_path,directory/'task_metrics.json',directory/'predictions.jsonl',
           directory/'bootstrap'/m['checkpoint_file'],directory/'bootstrap'/m['history_file']]
    return config,m,{str(p):file_sha256(p) for p in names}


def materialize_config(control, protocol, arm, seed):
    assert control['training']['field_loss_normalization']=='requested_balanced'
    assert control['training']['loss_weights']=={'ranking':1.,'support':1.,'field_state':.6,'cardinality':.6,'route':0.,'intervention':0.,'calibration':0.}
    value=copy.deepcopy(control)
    value['experiment_id']=f'rp3_joint_contract_v1_{arm}_seed_{seed}'
    value['training'].update(protocol['arms'][arm])
    value['training']['hard_negative_reference_rate']=protocol['hard_negative_reference_count']/protocol['training_rows']
    old,new=copy.deepcopy(control),copy.deepcopy(value)
    old.pop('experiment_id');new.pop('experiment_id')
    for k in ('hard_negative_support_weight','joint_contract_weight','hard_negative_reference_rate'):
        new['training'].pop(k)
    assert old==new, 'undeclared training change'
    return value


def diagnose(config_path, model_dir, protocol):
    import torch
    torch.set_num_threads(1)
    prepared=prepare(config_path,attach_development=False)
    m=json.loads((model_dir/'training_manifest.json').read_text())
    checkpoint=model_dir/m['checkpoint_file']
    assert file_sha256(checkpoint)==m['checkpoint_sha256']
    assert stable_sha256({k:v for k,v in m.items() if k!='logical_sha256'})==m['logical_sha256']
    model,_=load_controller_checkpoint(checkpoint,expected_input_fingerprint=prepared.input_fingerprint)
    model.eval();rows=[]
    for ds in (prepared.train_dataset,prepared.validation_dataset):
        for i,t in enumerate(ds.traces):
            batch_row=ds[i]
            with torch.no_grad():
                output=model(**{k:torch.from_numpy(v) for k,v in onnx_feed(ds,i).items()})
            logits=[getattr(output,k).numpy() for k in ('rank_logits','support_logits','field_state_logits','cardinality_logits','route_logits')]
            row=ablation_row(t,ds.records,logits,protocol,'full_local')
            rows.append(augment_joint_row(row,output,batch_row))
    return rows, {'best_epoch':m['best_epoch'],'checkpoint_sha256':m['checkpoint_sha256'],
        'input_fingerprint':prepared.input_fingerprint,'metrics':grouped_field_metrics(rows),'joint_metrics':grouped_joint_metrics(rows)}


def compare(reports, old_arm, new_arm, seeds):
    quality={}
    for arm in (old_arm,new_arm):
        ms=[reports[f'{arm}/{s}']['metrics']['validation_original']['scenario_macro'] for s in seeds]
        quality[arm]={k:sum(m[k] for m in ms)/len(ms) for k in ('pointer_f1','requested_raw_cardinality_accuracy','requested_decoded_cardinality_accuracy')}
        quality[arm]['nonempty_target_raw_zero']=sum(m['nonempty_target_raw_zero']['mean'] for m in ms)/len(ms)
    a,b=quality[old_arm],quality[new_arm]
    safeguards=[];empty_rates={old_arm:[],new_arm:[]}
    for seed in seeds:
        x,y=[reports[f'{arm}/{seed}']['metrics']['validation_all'] for arm in (old_arm,new_arm)]
        for arm,m in ((old_arm,x),(new_arm,y)):empty_rates[arm].append(m['teacher_empty_false_fill']['rate'])
        safeguards.append({'seed':seed,'teacher_empty_no_increase':y['teacher_empty_false_fill']['rate']<=x['teacher_empty_false_fill']['rate'],
                           'no_candidate_false_fill_zero':y['no_available_false_fill']['numerator']==0,
                           'output_contract_passed':y['proposal_contract_violations']==0})
    checks={'pointer_f1_not_lower':b['pointer_f1']>=a['pointer_f1'],
            'raw_zero_not_higher':b['nonempty_target_raw_zero']<=a['nonempty_target_raw_zero'],
            'raw_cardinality_not_lower':b['requested_raw_cardinality_accuracy']>=a['requested_raw_cardinality_accuracy'],
            'all_seed_safeguards':all(all(v for k,v in s.items() if k!='seed') for s in safeguards),
            'some_strict_improvement':(b['pointer_f1']>a['pointer_f1'] or b['nonempty_target_raw_zero']<a['nonempty_target_raw_zero']
                or b['requested_raw_cardinality_accuracy']>a['requested_raw_cardinality_accuracy'] or sum(empty_rates[new_arm])<sum(empty_rates[old_arm]))}
    masses={arm:sum(reports[f'{arm}/{s}']['joint_metrics']['validation_all']['mean_violation_mass'] for s in seeds)/len(seeds)
            for arm in (old_arm,new_arm)}
    return {'quality_means':quality,'checks':checks,'safeguards':safeguards,
            'pareto_improvement':all(checks.values()),'mean_violation_mass':masses,
            'contract_mass_improved':masses[new_arm]<masses[old_arm],
            'joint_algorithm_increment_supported':all(checks.values()) and masses[new_arm]<masses[old_arm]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',default='configs/research_point_3/joint_contract_v1.json')
    args=parser.parse_args();os.chdir(ROOT)
    protocol_path=Path(args.protocol);p=json.loads(protocol_path.read_text())
    assert p['schema']=='rp3_joint_contract_protocol_v1' and p['seeds']==[7042027,7042028,7042029]
    assert p['arms']=={'W1':{'hard_negative_support_weight':.25,'joint_contract_weight':0.},'J1':{'hard_negative_support_weight':.25,'joint_contract_weight':.1}}
    assert not any(p[k] for k in ('development_attached','external_evaluation_allowed','deployment_allowed'))
    root=Path(p['output_root'])
    if root.exists():raise FileExistsError('experiment exists; preserve it, do not rerun')
    controls={s:checked_control(Path(p['control_root'])/f'seed_{s}'/p['control_arm'],s) for s in p['seeds']}
    import torch
    assert all(m['runtime']['torch']==torch.__version__ for _,m,_ in controls.values())
    prepared=prepare(Path(p['control_root'])/f"seed_{p['seeds'][0]}"/p['control_arm']/'config.json',attach_development=False)
    hard_count=0
    for ds in (prepared.train_dataset,prepared.validation_dataset):
        for i in range(len(ds)):
            row=ds[i];requested=row['requested_field_mask'];eligible=row['requested_candidate_mask']&row['availability_mask']
            n=int(row['cardinality_labels'][requested][0]);f=int(row['field_state_labels'][requested][0])
            assert n<=int(((row['support_labels']==1)&eligible).sum())
            assert ((n==0 and f in (State.INSUFFICIENT,State.NOT_APPLICABLE)) or (n>=1 and f==State.SUPPORTED) or (n>=2 and f==State.CONFLICT))
            if ds is prepared.train_dataset:
                hard_count+=int(hard_empty_rows(row['support_labels'][None],eligible[None],row['cardinality_labels'][requested])[0])
    assert hard_count==p['hard_negative_reference_count'] and len(prepared.train_dataset)==p['training_rows']
    root.mkdir(parents=True)
    for seed,(config,m,bindings) in controls.items():
        _write_immutable(root/f'seed_{seed}/C0/control_reference.json',canonical_json_bytes({'reused_without_training':True,'files':bindings}))
        _write_immutable(root/f'seed_{seed}/C0/config.json',canonical_json_bytes(config))
        for arm in p['arms']:
            _write_immutable(root/f'seed_{seed}/{arm}/config.json',canonical_json_bytes(materialize_config(config,p,arm,seed)))
    sources=[protocol_path,Path(p['diagnostic_protocol']),Path('docs/RP3_JOINT_CONTRACT_V1_PROTOCOL.md'),
             Path(p['audit_root'])/'audit.json',Path('scripts/audit_rp3_joint_gating.py'),Path(__file__),Path('scripts/train_rp3_lec.py'),
             *Path('src/research_point_3').glob('*.py'),*Path('tests/unit').glob('test_research_point_3_joint_contract.py'),*root.glob('seed_*/*/config.json')]
    snapshot={'protocol':p,'files':{str(f):file_sha256(f) for f in sources},
              'controls':{str(s):b for s,(_,_,b) in controls.items()},'validated_train_hard_count':hard_count,
              'environment':{'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','torch':torch.__version__}}
    _write_immutable(root/'protocol_snapshot.json',canonical_json_bytes(snapshot))
    with zipfile.ZipFile(root/'source_snapshot.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for f in sources:archive.write(f,f.resolve().relative_to(ROOT))
    reports={};diagnostic_protocol=json.loads(Path(p['diagnostic_protocol']).read_text())
    env={**os.environ,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    for seed,(control,manifest,bindings) in controls.items():
        reference_rows=None
        for arm in ('C0','W1','J1'):
            directory=root/f'seed_{seed}/{arm}';config=directory/'config.json'
            if arm=='C0':
                model_dir=Path(p['control_root'])/f'seed_{seed}'/p['control_arm']/'bootstrap'
            else:
                model_dir=directory/'bootstrap'
                print(f'[joint contract] seed={seed} arm={arm}',flush=True)
                command=[sys.executable,'-u','scripts/train_rp3_lec.py','--config',str(config),'--output-dir',str(model_dir)]
                with (directory/'execution.log').open('x') as log:
                    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
                if result.returncode:
                    _write_immutable(directory/'failure.json',canonical_json_bytes({'command':command,'exit_code':result.returncode}))
                    raise RuntimeError(f'preserved failed training: {directory}')
                new_manifest=json.loads((model_dir/'training_manifest.json').read_text())
                assert new_manifest['model_config']==manifest['model_config'] and new_manifest['runtime']==manifest['runtime']
                assert not new_manifest['development_set']['attached']
            rows,report=diagnose(config,model_dir,diagnostic_protocol)
            assert report['input_fingerprint']==manifest['input_fingerprint']
            identities={r['trace_id']:(r['split'],r['scenario_id'],r['target_cardinalities'],r['teacher_selected_ids'],r['available_ids']) for r in rows}
            if arm=='C0':
                reference_rows=identities
                previous={r['trace_id']:r['selected_ids'] for r in map(json.loads,(Path(p['control_root'])/f'seed_{seed}'/p['control_arm']/'predictions.jsonl').read_text().splitlines())}
                assert previous=={r['trace_id']:r['selected_ids'] for r in rows},'default decoding changed'
            else:assert identities==reference_rows
            _write_immutable(directory/'predictions.jsonl',canonical_jsonl_bytes(rows))
            report.update(arm=arm,seed=seed,predictions_sha256=file_sha256(directory/'predictions.jsonl'),
                          development_read=False,external_read=False,deployment_allowed=False,reused_control=arm=='C0')
            _write_immutable(directory/'task_metrics.json',canonical_json_bytes(report));reports[f'{arm}/{seed}']=report
            for name,digest in bindings.items():assert file_sha256(name)==digest
    comparisons={f'{b}_vs_{a}':compare(reports,a,b,p['seeds']) for a,b in [('C0','W1'),('W1','J1'),('C0','J1')]}
    aggregate=[]
    for arm in ('C0','W1','J1'):
        for subset in next(iter(reports.values()))['metrics']:
            ms=[reports[f'{arm}/{s}']['metrics'][subset]['scenario_macro'] for s in p['seeds']]
            aggregate.append({'arm':arm,'subset':subset,'quality':{k:seed_statistics([m[k] for m in ms]) for k in
                ('pointer_f1','pointer_precision','pointer_recall','requested_raw_cardinality_accuracy','requested_decoded_cardinality_accuracy')},
                'nonempty_raw_zero':seed_statistics([m['nonempty_target_raw_zero']['mean'] for m in ms]),
                'joint_violation_mass':seed_statistics([reports[f'{arm}/{s}']['joint_metrics'][subset]['scenario_macro_violation_mass'] for s in p['seeds']])})
    _write_immutable(root/'summary.json',canonical_json_bytes({'protocol':p,'reports':reports,'aggregate':aggregate,'comparisons':comparisons,'deployment_allowed':False}))
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['arm','seed','best_epoch','subset','rows','raw_zero_n','nonempty_n','raw_cardinality_accuracy','decoded_cardinality_accuracy','pointer_f1','empty_false_n','empty_n','hard_false_n','hard_n','unavailable_false_n','unavailable_n','raw_contract_violation_rate','violation_mass'])
    lines=['# 联合契约三种子实验', '', '均为构建集内部诊断，不能部署。C0复用旧模型；W1困难负例加权；J1额外加入契约正则。', '',
           '| 臂 | seed | 最佳epoch | 原始validation raw零预测 | 请求raw基数准确率 | Pointer F1 | 完整validation空集误填 | 困难空集误填 | 模型违约质量 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for report in reports.values():
        for subset,m in report['metrics'].items():
            j=report['joint_metrics'][subset];z=m['nonempty_target_raw_zero'];e=m['teacher_empty_false_fill'];h=j['hard_empty_false_fill'];n=m['no_available_false_fill']
            writer.writerow([report['arm'],report['seed'],report['best_epoch'],subset,m['rows'],z['numerator'],z['denominator'],m['requested_raw_cardinality_accuracy'],m['requested_decoded_cardinality_accuracy'],m['pointer_f1'],e['numerator'],e['denominator'],h['numerator'],h['denominator'],n['numerator'],n['denominator'],j['raw_joint_violation']['rate'],j['mean_violation_mass']])
        m=report['metrics']['validation_original'];z=m['nonempty_target_raw_zero'];e=report['metrics']['validation_all']['teacher_empty_false_fill'];j=report['joint_metrics']['validation_all'];h=j['hard_empty_false_fill']
        lines.append(f"| {report['arm']} | {report['seed']} | {report['best_epoch']} | {z['numerator']}/{z['denominator']} | {m['requested_raw_cardinality_accuracy']:.4f} | {m['pointer_f1']:.4f} | {e['numerator']}/{e['denominator']} | {h['numerator']}/{h['denominator']} | {j['mean_violation_mass']:.4f} |")
    for name,c in comparisons.items():
        lines+=['',f"{name}: Pareto改善={c['pareto_improvement']}; 违约质量下降={c['contract_mass_improved']}; 两者同时满足={c['joint_algorithm_increment_supported']}。"]
    lines+=['','0/0为NA。派生样本不增加独立场景；原始validation仅2个场景。完整逐场景/种子统计和失败检查见JSON，非空和误填分母见CSV。']
    _write_immutable(root/'summary.csv',stream.getvalue().encode())
    _write_immutable(root/'summary.md',('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines),flush=True)


if __name__=='__main__':main()
