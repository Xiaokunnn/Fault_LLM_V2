"""Same proxy probes on the frozen old full; no additional fitting."""
import torch
from role_io import *
from contrast import load_parent
from evaluate import probe
def main():
    torch.set_num_threads(2)
    for seed in SEEDS:
        out=OUT/'reference_probes'/f'parent_s{seed}'
        if (out/'summary.json').exists():continue
        model,data,graph=load_parent(seed);model.eval();summary,rows=probe(model,data,graph,seed)
        save(out/'summary.json',summary);save(out/'rows.jsonl',rows)
        del model,data;torch.cuda.empty_cache()
    print('Old full probe reference saved',DATASET)
if __name__=='__main__':main()
