#!/usr/bin/env python3
"""Fixed three-seed G1 experiment; existing C0 and W1 are read-only controls."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes,canonical_jsonl_bytes,file_sha256,stable_sha256,_write_immutable
from src.research_point_3.ablations import seed_statistics
from src.research_point_3.experiment_io import prepare
from src.research_point_3.diagnostics import mean
from scripts.run_rp3_joint_contract import diagnose
from scripts.audit_rp3_support_separability import score_metrics


def control(directory,seed):
    config=json.loads((directory/'config.json').read_text());mp=directory/'bootstrap/training_manifest.json';m=json.loads(mp.read_text())
    assert config['training']==m['training_config'] and config['training']['seed']==seed
    assert not any(k.startswith('development') for k in config) and not m['development_set']['attached']
    assert stable_sha256({k:v for k,v in m.items() if k!='logical_sha256'})==m['logical_sha256']
    names=[directory/'config.json',mp,directory/'task_metrics.json',directory/'predictions.jsonl']
    for key in ('checkpoint','history'):
        path=directory/'bootstrap'/m[key+'_file'];assert file_sha256(path)==m[key+'_sha256'];names.append(path)
    r=json.loads((directory/'task_metrics.json').read_text())
    assert file_sha256(directory/'predictions.jsonl')==r['predictions_sha256']
    return config,m,{str(f):file_sha256(f) for f in names}


def new_config(config,p,seed):
    value=copy.deepcopy(config);value['experiment_id']=f'rp3_positive_guard_v1_seed_{seed}'
    value['training'].update(p['treatment'])
    a,b=copy.deepcopy(config),copy.deepcopy(value)
    a.pop('experiment_id');b.pop('experiment_id')
    for key in p['treatment']:b['training'].pop(key)
    assert a==b,'undeclared config change'
    assert value['training']['hard_negative_support_weight']==.25 and value['training']['joint_contract_weight']==0
    return value


def support_summary(rows):
    result={}
    for split in ('train','validation'):
        for kind in ('original','derived','all'):
            subset=[r for r in rows if r['split']==split and (kind=='all' or (r['perturbation_id']=='original')==(kind=='original'))]
            candidates=[{'label':y,'probability':p} for r in subset for y,p in zip(r['support_labels'],r['support_probabilities'])]
            value=score_metrics(candidates)
            value['by_scenario']={s:score_metrics([{'label':y,'probability':p} for r in subset if r['scenario_id']==s
                                        for y,p in zip(r['support_labels'],r['support_probabilities'])]) for s in sorted({r['scenario_id'] for r in subset})}
            value['scenario_macro_recall']=mean(m['recall'] for m in value['by_scenario'].values() if m['positive_count'])
            result[split+'_'+kind]=value
    return result


def comparison(reports,old,new,seeds):
    quality={}
    for arm in (old,new):
        ms=[reports[f'{arm}/{s}']['metrics']['validation_original']['scenario_macro'] for s in seeds]
        quality[arm]={'pointer_f1':mean(m['pointer_f1'] for m in ms),
            'decoded_empty':mean(m['nonempty_target_decoded_empty']['mean'] for m in ms),
            'decoded_cardinality_accuracy':mean(m['requested_decoded_cardinality_accuracy'] for m in ms),
            'support_recall':mean(reports[f'{arm}/{s}']['support']['validation_original']['scenario_macro_recall'] for s in seeds)}
    a,b=quality[old],quality[new];safeguards=[]
    for seed in seeds:
        x,y=[reports[f'{arm}/{seed}']['metrics']['validation_all'] for arm in (old,new)]
        safeguards.append({'seed':seed,'teacher_empty_no_increase':y['teacher_empty_false_fill']['rate']<=x['teacher_empty_false_fill']['rate'],
            'no_candidate_false_fill_zero':y['no_available_false_fill']['numerator']==0,'output_contract_passed':y['proposal_contract_violations']==0})
    checks={'pointer_f1_strictly_improved':b['pointer_f1']>a['pointer_f1'],
            'support_recall_not_lower':b['support_recall']>=a['support_recall'],
            'decoded_empty_not_higher':b['decoded_empty']<=a['decoded_empty'],
            'decoded_cardinality_not_lower':b['decoded_cardinality_accuracy']>=a['decoded_cardinality_accuracy'],
            'all_seed_false_fill_safeguards':all(all(v for k,v in s.items() if k!='seed') for s in safeguards)}
    return {'improved_under_prespecified_rule':all(checks.values()),'checks':checks,'quality_means':quality,'safeguards':safeguards}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',default='configs/research_point_3/positive_guard_v1.json')
    args=p.parse_args();os.chdir(ROOT);protocol_path=Path(args.protocol);p=json.loads(protocol_path.read_text())
    assert p['schema']=='rp3_positive_guard_protocol_v1' and p['seeds']==[7042027,7042028,7042029]
    assert p['treatment']=={'positive_step_guard':True,'positive_guard_margin':.1,'positive_guard_backtracks':8,'positive_guard_tolerance':1e-7}
    assert not any(p[k] for k in ('development_attached','external_evaluation_allowed','deployment_allowed'))
    root=Path(p['output_root'])
    if root.exists():raise FileExistsError('preserve experiment; do not rerun')
    directories={};controls={}
    for seed in p['seeds']:
        for arm in ('C0','W1'):
            d=(Path(p['reference_root'])/f'seed_{seed}/requested_balanced' if arm=='C0' else Path(p['weighted_control_root'])/f'seed_{seed}/W1')
            directories[(arm,seed)]=d;controls[(arm,seed)]=control(d,seed)
    import torch
    assert all(m['runtime']['torch']==torch.__version__ for _,m,_ in controls.values())
    data=prepare(directories[('W1',p['seeds'][0])]/'config.json',attach_development=False)
    # Saved support arrays have no role IDs; this guard makes their metric scope explicit.
    for ds in (data.train_dataset,data.validation_dataset):
        assert all(not (ds[i]['availability_mask']&~ds[i]['requested_candidate_mask']).any() for i in range(len(ds)))
    root.mkdir(parents=True)
    for seed in p['seeds']:
        for arm in ('C0','W1'):
            config,m,bindings=controls[(arm,seed)]
            _write_immutable(root/f'seed_{seed}/{arm}/config.json',canonical_json_bytes(config))
            _write_immutable(root/f'seed_{seed}/{arm}/control_reference.json',canonical_json_bytes({'reused_without_training':True,'files':bindings}))
        _write_immutable(root/f'seed_{seed}/G1/config.json',canonical_json_bytes(new_config(controls[('W1',seed)][0],p,seed)))
    sources=[protocol_path,Path(p['diagnostic_protocol']),Path('docs/RP3_POSITIVE_GUARD_V1_PROTOCOL.md'),Path(p['audit_root'])/'audit.json',
        Path(__file__),Path('scripts/audit_rp3_support_separability.py'),Path('scripts/run_rp3_joint_contract.py'),Path('scripts/train_rp3_lec.py'),
        *Path('src/research_point_3').glob('*.py'),Path('tests/unit/test_research_point_3_positive_guard.py'),*root.glob('seed_*/*/config.json')]
    snapshot={'protocol':p,'files':{str(f):file_sha256(f) for f in sources},
        'control_files':{f'{arm}/{seed}':v[2] for (arm,seed),v in controls.items()},
        'environment':{'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','torch':torch.__version__},'reference_split':'train_only'}
    _write_immutable(root/'protocol_snapshot.json',canonical_json_bytes(snapshot))
    with zipfile.ZipFile(root/'source_snapshot.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for f in sources:archive.write(f,f.resolve().relative_to(ROOT))
    reports={};env={**os.environ,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    diagnostic=json.loads(Path(p['diagnostic_protocol']).read_text())
    for seed in p['seeds']:
        reference_identity=None
        for arm in ('C0','W1','G1'):
            d=root/f'seed_{seed}/{arm}';model_dir=d/'bootstrap' if arm=='G1' else directories[(arm,seed)]/'bootstrap'
            if arm=='G1':
                print(f'[positive guard] seed={seed} G1; reuse C0/W1',flush=True)
                command=[sys.executable,'-u','scripts/train_rp3_lec.py','--config',str(d/'config.json'),'--output-dir',str(model_dir)]
                with (d/'execution.log').open('x') as log:
                    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
                if result.returncode:
                    _write_immutable(d/'failure.json',canonical_json_bytes({'command':command,'exit_code':result.returncode}))
                    raise RuntimeError(f'failed run preserved: {d}')
                m=json.loads((model_dir/'training_manifest.json').read_text());c=controls[('W1',seed)][1]
                assert m['model_config']==c['model_config'] and m['runtime']==c['runtime'] and not m['development_set']['attached']
            rows,report=diagnose(d/'config.json',model_dir,diagnostic)
            identity={r['trace_id']:(r['split'],r['scenario_id'],r['teacher_selected_ids'],r['available_ids'],r['target_cardinalities']) for r in rows}
            if reference_identity is None:reference_identity=identity
            else:assert identity==reference_identity
            assert report['input_fingerprint']==controls[('W1',seed)][1]['input_fingerprint']
            if arm!='G1':
                previous={r['trace_id']:r['selected_ids'] for r in map(json.loads,(directories[(arm,seed)]/'predictions.jsonl').read_text().splitlines())}
                assert previous=={r['trace_id']:r['selected_ids'] for r in rows}
            _write_immutable(d/'predictions.jsonl',canonical_jsonl_bytes(rows))
            report.update(arm=arm,seed=seed,support=support_summary(rows),predictions_sha256=file_sha256(d/'predictions.jsonl'),
                          development_read=False,external_read=False,deployment_allowed=False,reused_control=arm!='G1')
            _write_immutable(d/'task_metrics.json',canonical_json_bytes(report));reports[f'{arm}/{seed}']=report
    for _,_,bindings in controls.values():
        for name,digest in bindings.items():assert file_sha256(name)==digest
    comparisons={f'G1_vs_{old}':comparison(reports,old,'G1',p['seeds']) for old in ('W1','C0')}
    aggregate=[]
    for arm in ('C0','W1','G1'):
        for subset in next(iter(reports.values()))['metrics']:
            ms=[reports[f'{arm}/{seed}']['metrics'][subset]['scenario_macro'] for seed in p['seeds']]
            aggregate.append({'arm':arm,'subset':subset,'quality':{k:seed_statistics([m[k] for m in ms]) for k in ('pointer_f1','pointer_precision','pointer_recall','requested_raw_cardinality_accuracy','requested_decoded_cardinality_accuracy')},
                'nonempty_raw_zero':seed_statistics([m['nonempty_target_raw_zero']['mean'] for m in ms]),
                'nonempty_decoded_empty':seed_statistics([m['nonempty_target_decoded_empty']['mean'] for m in ms]),
                'positive_support_recall':seed_statistics([reports[f'{arm}/{seed}']['support'][subset]['scenario_macro_recall'] for seed in p['seeds']])})
    _write_immutable(root/'summary.json',canonical_json_bytes({'protocol':p,'reports':reports,'aggregate':aggregate,'comparisons':comparisons,'deployment_allowed':False}))
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['arm','seed','best_epoch','subset','raw_zero_n','nonempty_n','decoded_empty_n','raw_cardinality_accuracy','decoded_cardinality_accuracy','pointer_f1','support_positive_recall','support_auc','teacher_empty_false_n','teacher_empty_n','hard_empty_false_n','hard_empty_n'])
    lines=['# 正支持更新保护三种子结果','','仅构建集内部诊断；C0/W1未重训。', '',
           '| 臂 | seed | 最佳epoch | 原始val Pointer F1 | 非空目标最终为空 | 正支持召回@0.5 | 完整val教师空集误填 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in reports.values():
        for subset,m in r['metrics'].items():
            z=m['nonempty_target_raw_zero'];e=m['teacher_empty_false_fill'];h=r['joint_metrics'][subset]['hard_empty_false_fill'];s=r['support'][subset]
            writer.writerow([r['arm'],r['seed'],r['best_epoch'],subset,z['numerator'],z['denominator'],m['nonempty_target_decoded_empty']['numerator'],m['requested_raw_cardinality_accuracy'],m['requested_decoded_cardinality_accuracy'],m['pointer_f1'],s['recall'],s['roc_auc'],e['numerator'],e['denominator'],h['numerator'],h['denominator']])
        m=r['metrics']['validation_original'];z=m['nonempty_target_decoded_empty'];e=r['metrics']['validation_all']['teacher_empty_false_fill'];s=r['support']['validation_original']
        lines.append(f"| {r['arm']} | {r['seed']} | {r['best_epoch']} | {m['pointer_f1']:.4f} | {z['numerator']}/{z['denominator']} | {s['recall']:.4f} | {e['numerator']}/{e['denominator']} |")
    for name,c in comparisons.items():lines+=['',f"{name}: 预声明整体改善={c['improved_under_prespecified_rule']}；条件={c['checks']}。"]
    lines+=['','分母按每种子计，不把多种子或派生轨迹合并为独立病例；原始validation只有2个场景。']
    _write_immutable(root/'summary.csv',stream.getvalue().encode());_write_immutable(root/'summary.md',('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines),flush=True)


if __name__=='__main__':main()
