#!/usr/bin/env python3
"""Supplement whole-process memory with /proc readings; preserve original costs.

The original runner's child ru_maxrss values share the parent's high-water floor.
They cannot estimate encoder incremental memory. Fresh execs record current RSS
and /proc HWM, as well as the original API, with no training or timing reruns.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def memory():
    values={}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:','VmHWM:')):
            k,v=line.split(':',1);values[k+'_kib']=int(v.split()[0])
    values['ru_maxrss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return values


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=['C0','H512','E1'],required=True)
    arm=parser.parse_args().arm;os.chdir(ROOT);stages={'python_before_torch':memory()}
    import torch
    from src.research_point_3.artifacts import canonical_json_bytes,_write_immutable,file_sha256
    from src.research_point_3.experiment_io import prepare
    from src.research_point_3.semantic_features import FrozenSemanticEncoder,query_text
    from src.research_point_3.training import load_controller_checkpoint
    from src.research_point_3.features import hash_text
    from scripts.benchmark_rp3_semantic import assemble_inputs
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    stages['libraries_loaded']=memory()
    root=Path('results/experiments/research_point_3/semantic_v1');snap=json.loads((root/'protocol_snapshot.json').read_text());p=snap['protocol']
    target=root/f'memory_{arm}.json'
    if target.exists():raise FileExistsError('preserve memory audit')
    d=root/f"seed_{p['cost']['seed']}/{arm}";data=prepare(d/'config.json',attach_development=False)
    boot=(Path(p['reference_root'])/f"seed_{p['cost']['seed']}/requested_balanced" if arm=='C0' else d)/'bootstrap'
    m=json.loads((boot/'training_manifest.json').read_text());model,_=load_controller_checkpoint(boot/m['checkpoint_file'],expected_input_fingerprint=data.input_fingerprint);model.eval()
    stages['features_and_controller_loaded']=memory()
    encoder=FrozenSemanticEncoder(p['encoder_directory'],snap['encoder_files']) if arm=='E1' else None
    cache={k:torch.tensor(v,dtype=torch.float32) for k,v in data.feature_store.evidence_features.items()}
    stages['encoder_and_evidence_cache_loaded']=memory()
    count=0
    with torch.inference_mode():
        for ds in (data.train_dataset,data.validation_dataset):
            for t in ds.traces:
                if t.perturbation_id!='original':continue
                q=encoder.encode([query_text(t.query)],query=True,batch_size=1)[0] if encoder else hash_text(query_text(t.query),data.feature_store.query_dimension)
                model(**assemble_inputs(q,t.candidate_evidence_ids,t.availability_mask,t.selection_budget,cache));count+=1
    stages['after_40_query_forwards']=memory()
    result={'arm':arm,'pid':os.getpid(),'stages':stages,'queries':count,'checkpoint_sha256':file_sha256(boot/m['checkpoint_file']),
        'scope':'whole Python process including loaded libraries, corpus and feature tables; inference only, CPU FP32 single thread',
        'timing_repeated':False,'training_repeated':False,'old_cost_files_preserved':True,
        'boundary':'proc RSS/HWM supplement; do not interpret equal original child ru_maxrss as equal model memory',
        'development_read':False,'external_read':False,'target_edge_measurement':False}
    _write_immutable(target,canonical_json_bytes(result));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
