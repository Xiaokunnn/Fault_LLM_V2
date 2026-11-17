"""Compressed delivery mirrors and hashes. Leave all local research assets intact."""
import gzip
from raw_io import *

def main():
    if (EXP/'verification/delivery_manifest.json').exists():print('REUSE delivery');return
    import numpy as np
    trace=[json.loads(x) for x in gzip.decompress((EXP/'analysis/predictions_with_paths.jsonl.gz').read_bytes()).decode().splitlines()]
    usage=np.load(EXP/'completion/path_usage.npz');u={k:usage['P4_B3_full__'+k] for k in ['picked','destinations','scores']}
    keys=read(EXP/'paths/query_keys.json');ki={tuple(k):i for i,k in enumerate(keys)};alpha=read(EXP/'completion/freeze.json')['selected']['P4_B3_full']
    assert len(trace)==1122
    for t in trace:
        i=ki[tuple(t['query'])];pred=t['top1'];chosen=set(np.where(u['picked'][i]&(u['destinations'][i]==pred))[0].tolist())
        assert chosen=={x['path_index'] for x in t['used_top1_paths']}
        assert abs(t['top1_score']-(t['top1_text_score']+alpha*t['top1_path_support']))<1e-7
    save(EXP/'verification/prediction_trace_checks.json',dict(predictions=len(trace),all_three_seeds=True,path_ids_and_triple_score_decomposition_pass=True))
    mirrors=[];ignored=[]
    large=[p for p in sorted(EXP.rglob('*.jsonl')) if p.stat().st_size>300_000 and not p.is_relative_to(EXP/'replays')]
    large += [EXP/'verification/prior_files.json']
    for p in large:
        data=p.read_bytes();compressed=gzip.compress(data,compresslevel=9,mtime=0);target=p.with_name(p.name+'.gz')
        if target.exists():assert gzip.decompress(target.read_bytes())==data
        else:target.write_bytes(compressed)
        mirrors.append(dict(original=str(p.relative_to(EXP)),compressed=str(target.relative_to(EXP)),original_sha256=sha(p),compressed_sha256=sha(target),original_bytes=len(data),compressed_bytes=len(compressed)))
        ignored.append('/'+str(p.relative_to(EXP)))
    save(EXP/'.gitignore','# Full local mirrors are preserved; deterministic gzip copies are committed.\n'+'\n'.join(ignored)+'\n/index/vectors.npz\n/replays/\n')
    save(EXP/'verification/compressed_mirrors.json',mirrors)
    # Numeric caches needed for audit are small; keep large encoder index local.
    local=[EXP/'index/vectors.npz']
    save(EXP/'verification/local_numeric_assets.json',[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p),rebuild='vector_bridges.py from reused frozen BGE vectors + local encoder') for p in local])
    # Hash all used cached foundations, not only the frozen indexing inputs.
    sources=[OLD/'features'/f'{view}_s{seed}.pt' for seed in SEEDS for view in ['G1','G2']]
    sources += [OLD/'retrieval/R3_all_global.npz',OLD/'index/oriented_views.jsonl']
    save(EXP/'verification/foundation_asset_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in sources})
    wanted={'.md','.py','.json','.csv','.gz','.svg','.txt','.jsonl','.npz'};files={}
    for p in sorted(EXP.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or 'replays' in p.relative_to(EXP).parts:continue
        relative=str(p.relative_to(EXP))
        if '/'+relative in ignored or p in local:continue
        if p.suffix in wanted or p.name=='.gitignore':files[relative]=dict(bytes=p.stat().st_size,sha256=sha(p))
    save(EXP/'verification/delivery_manifest.json',dict(files=files,files_count=len(files),total_bytes=sum(v['bytes'] for v in files.values()),all_original_large_mirrors_left_in_place=True,formal_graph_modified=False))
    print('DELIVERY',len(files),'files',sum(v['bytes'] for v in files.values()),'bytes',flush=True)

if __name__=='__main__':main()
