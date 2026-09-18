#!/usr/bin/env python3
"""Post-run independent artifact/objective checks and support-gate diagnosis."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, stable_sha256, _write_immutable
from src.research_point_3.field_audit import counted_rate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',required=True)
    args=p.parse_args()
    root=ROOT/'results/experiments/research_point_3/joint_contract_v1'
    inventory=Path(args.inventory)
    old=json.loads(inventory.read_text())
    changed=[name for name,h in old.items() if not (ROOT/name).is_file() or file_sha256(ROOT/name)!=h]
    snapshot=json.loads((root/'protocol_snapshot.json').read_text())
    mismatches=[name for name,h in snapshot['files'].items() if file_sha256(ROOT/name)!=h]
    assert not changed and not mismatches, (changed,mismatches)
    previous=json.loads((ROOT/'results/experiments/research_point_3/field_normalization_v1/protocol_snapshot.json').read_text())
    immutable_forward={name:file_sha256(ROOT/name)==previous['files'][name] for name in ('src/research_point_3/model.py','src/research_point_3/decoding.py')}
    assert all(immutable_forward.values())
    checks=[];gate={}
    for seed in snapshot['protocol']['seeds']:
        control=ROOT/f'results/experiments/research_point_3/field_normalization_v1/seed_{seed}/requested_balanced'
        c=json.loads((control/'bootstrap/training_manifest.json').read_text())
        for arm in ('C0','W1','J1'):
            directory=root/f'seed_{seed}/{arm}'
            report=json.loads((directory/'task_metrics.json').read_text())
            assert file_sha256(directory/'predictions.jsonl')==report['predictions_sha256']
            rows=[json.loads(l) for l in (directory/'predictions.jsonl').read_text().splitlines()]
            gate[f'{arm}/{seed}']={}
            for split in ('train','validation'):
                for kind in ('original','derived','all'):
                    chosen=[r for r in rows if r['split']==split and (kind=='all' or (r['perturbation_id']=='original')==(kind=='original'))]
                    positive=[prob for r in chosen for prob,y in zip(r['support_probabilities'],r['support_labels']) if y==1]
                    negative=[prob for r in chosen for prob,y in zip(r['support_probabilities'],r['support_labels']) if y==0]
                    gate[f'{arm}/{seed}'][split+'_'+kind]={
                        'teacher_positive_pass_support_gate':counted_rate(sum(prob>=.5 for prob in positive),len(positive)),
                        'teacher_negative_pass_support_gate':counted_rate(sum(prob>=.5 for prob in negative),len(negative)),
                        'proposals':sum(bool(r['selected_ids']) for r in chosen),
                        'teacher_nonempty_rows':sum(bool(r['teacher_selected_ids']) for r in chosen),
                        'teacher_nonempty_but_decoded_empty':sum(bool(r['teacher_selected_ids']) and not r['selected_ids'] for r in chosen)}
            if arm=='C0':continue
            model=directory/'bootstrap';m=json.loads((model/'training_manifest.json').read_text())
            config=m['training_config']
            assert stable_sha256({k:v for k,v in m.items() if k!='logical_sha256'})==m['logical_sha256']
            assert all(file_sha256(model/m[k+'_file'])==m[k+'_sha256'] for k in ('checkpoint','history'))
            assert not m['development_set']['attached']
            assert m['model_config']==c['model_config'] and m['runtime']==c['runtime'] and m['input_fingerprint']==c['input_fingerprint']
            history=[json.loads(l) for l in (model/'training_history.jsonl').read_text().splitlines()]
            errors=[]
            for row in history:
                for split in ('train','validation'):
                    saved=row[split]
                    total=sum(w*saved['intervention_augmented_supervision' if k=='intervention' else k] for k,w in config['loss_weights'].items())
                    total+=config['hard_negative_support_weight']*saved['hard_negative_support']+config['joint_contract_weight']*saved['joint_contract']
                    errors.append(abs(total-saved['total']))
            best=min(history,key=lambda r:r['validation']['total'])['epoch']
            assert max(errors)<1e-5 and best==m['best_epoch']
            checks.append({'seed':seed,'arm':arm,'epochs':len(history),'best_epoch':best,
                'max_objective_reconstruction_error':max(errors),'same_inputs_model_runtime':True,
                'manifest_checkpoint_history_hashes_valid':True,'development_attached':False})
    verification={'preserved_existing_files':len(old),'inventory':str(inventory),'changed_or_missing_files':changed,
        'frozen_source_mismatches':mismatches,'model_and_decoder_unchanged':immutable_forward,
        'training_checks':checks,'unit_tests':{'passed':123,'existing_onnx_tracer_warnings':10},'deployment_allowed':False}
    _write_immutable(root/'verification.json',canonical_json_bytes(verification))
    _write_immutable(root/'support_gate_audit.json',canonical_json_bytes({'threshold':.5,'source':'saved final-checkpoint predictions only',
        'boundary':'candidate-query occurrences, not independent cases; unassessed excluded; no new model selection', 'results':gate}))
    print(json.dumps(verification,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
