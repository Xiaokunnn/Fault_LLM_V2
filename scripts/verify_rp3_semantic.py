#!/usr/bin/env python3
"""Read-only verification of the frozen E1 experiment and prior inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.experiment_io import prepare
from src.research_point_3.dataset import collate_teacher_batch
from src.research_point_3.semantic_features import model_bindings
from src.research_point_3.training import load_controller_checkpoint


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inventory',required=True)
    args=parser.parse_args()
    import torch
    torch.set_num_threads(1)
    root=ROOT/'results/experiments/research_point_3/semantic_v1'
    snapshot=json.loads((root/'protocol_snapshot.json').read_text());p=snapshot['protocol']
    inventory=json.loads(Path(args.inventory).read_text())
    assert all((ROOT/name).is_file() and file_sha256(ROOT/name)==h for name,h in inventory.items())
    assert all(file_sha256(ROOT/name)==h for name,h in snapshot['files'].items())
    assert model_bindings(ROOT/p['encoder_directory'])==snapshot['encoder_files']
    with zipfile.ZipFile(root/'source_snapshot.zip') as archive:
        for name,h in snapshot['files'].items():
            assert hashlib.sha256(archive.read(str((ROOT/name).resolve().relative_to(ROOT)))).hexdigest()==h
    for bindings in snapshot['control_files'].values():
        assert all(file_sha256(ROOT/name)==h for name,h in bindings.items())
    data={arm:prepare(root/f'seed_7042027/{arm}/config.json',attach_development=False) for arm in ('C0','H512','E1')}
    for arm in ('H512','E1'):
        assert data[arm].trace_manifest==data['C0'].trace_manifest and data[arm].memory_manifest==data['C0'].memory_manifest
        assert data[arm].development_dataset is None
        for a,b in zip((data['C0'].train_dataset,data['C0'].validation_dataset),(data[arm].train_dataset,data[arm].validation_dataset)):
            assert len(a)==len(b)
            for i in range(len(a)):
                old,new=a[i],b[i]
                for k,v in old.items():
                    if k in ('query_features','candidate_features'):continue
                    assert torch.equal(v,new[k]) if isinstance(v,torch.Tensor) else v==new[k]
                assert torch.equal(old['candidate_features'][:,256:],new['candidate_features'][:,512:])
        for vector in data[arm].feature_store.query_features.values():
            assert abs(sum(v*v for v in vector)-1.)<1e-5
    checks=[]
    names=('query_features','candidate_features','availability_mask','selection_budget')
    for seed in p['seeds']:
        old=ROOT/p['reference_root']/f'seed_{seed}/requested_balanced/bootstrap'
        reference=json.loads((old/'training_manifest.json').read_text())
        for arm in ('C0','H512','E1'):
            directory=root/f'seed_{seed}/{arm}';bootstrap=old if arm=='C0' else directory/'bootstrap'
            manifest=json.loads((bootstrap/'training_manifest.json').read_text())
            assert stable_sha256({k:v for k,v in manifest.items() if k!='logical_sha256'})==manifest['logical_sha256']
            assert all(file_sha256(bootstrap/manifest[k+'_file'])==manifest[k+'_sha256'] for k in ('checkpoint','history'))
            assert not manifest['development_set']['attached'] and manifest['runtime']==reference['runtime']
            assert all(manifest['training_config'][k]==v for k,v in reference['training_config'].items())
            if arm!='C0':
                m=dict(manifest['model_config']);m.update(query_dim=256,evidence_dim=288)
                old_model=dict(reference['model_config']);old_model.setdefault('support_context','pointwise')
                assert m==old_model
                assert not manifest['training_config']['positive_step_guard']
                assert manifest['training_config']['hard_negative_support_weight']==manifest['training_config']['joint_contract_weight']==0
            history=list(map(json.loads,(bootstrap/manifest['history_file']).read_text().splitlines()));errors=[]
            for epoch in history:
                for split in ('train','validation'):
                    metric=epoch[split]
                    total=sum(w*metric['intervention_augmented_supervision' if k=='intervention' else k] for k,w in manifest['training_config']['loss_weights'].items())
                    errors.append(abs(total-metric['total']))
            assert max(errors)<1e-5
            assert min(history,key=lambda r:r['validation']['total'])['epoch']==manifest['best_epoch']
            report=json.loads((directory/'task_metrics.json').read_text())
            assert report['predictions_sha256']==file_sha256(directory/'predictions.jsonl')
            model,_=load_controller_checkpoint(bootstrap/manifest['checkpoint_file'],expected_input_fingerprint=data[arm].input_fingerprint)
            model.eval();ds=data[arm].validation_dataset
            batch=collate_teacher_batch([ds[i] for i in range(len(ds))]);feed={k:batch[k] for k in names}
            with torch.no_grad():
                before=model(**feed)
                modified=feed['candidate_features'].clone();modified[~feed['availability_mask']]=1000.
                after=model(feed['query_features'],modified,feed['availability_mask'],feed['selection_budget'])
            assert all(torch.equal(getattr(before,k),getattr(after,k)) for k in ('rank_logits','support_logits','field_state_logits','cardinality_logits','route_logits'))
            best=next(r for r in history if r['epoch']==manifest['best_epoch'])
            last=history[-1]
            changes={k:last['validation'][k]-best['validation'][k] for k in ('total','ranking','support','field_state','cardinality')}
            checks.append({'arm':arm,'seed':seed,'best_epoch':manifest['best_epoch'],'epochs':len(history),
                'controller_parameters':model.parameter_count(),'max_objective_reconstruction_error':max(errors),
                'last_minus_best_validation_losses':changes,'unavailable_inputs_have_no_effect_all_heads':True})
    output={'source_and_encoder_hashes_valid':True,'source_archive_valid':True,'control_hashes_valid':True,
        'preserved_existing_files':len(inventory),'inventory':args.inventory,'labels_masks_splits_and_metadata_identical':True,
        'training_checks':checks,'development_read':False,'external_read':False,'deployment_allowed':False}
    _write_immutable(root/'verification.json',canonical_json_bytes(output))
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
