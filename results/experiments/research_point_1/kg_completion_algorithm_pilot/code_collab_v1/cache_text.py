"""Encode all catalogue queries, never test targets, with frozen G2 encoder."""
import fcntl
import time
import torch
from collab_io import *
from baselines import foundation
from train_simkgc import setup,query_text


def main():
    while not (RUN/'data/collab_freeze.json').exists():time.sleep(2)
    cat=read(RUN/'data/catalogue.json');n=cat['nbase'];R=len(cat['relations'])
    for seed in SEEDS:
        out=RUN/'features'/f'seed{seed}.pt'
        if out.exists():continue
        path=foundation(seed)
        while not (path/'complete.json').exists():time.sleep(2)
        with (STUDY/'gpu.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);torch.set_num_threads(2)
            start=time.perf_counter();model,tok,descriptions,_=setup('G2',cat);model=model.cuda().eval()
            model.load_state_dict(torch.load(path/'best.pt',map_location='cuda',weights_only=True))
            def encode(texts,encoder):
                result=[]
                with torch.no_grad():
                    for off in range(0,len(texts),128):
                        batch=tok(texts[off:off+128],padding='max_length',truncation=True,max_length=96,return_tensors='pt')
                        ids=batch['input_ids'].cuda();mask=batch['attention_mask'].cuda();typ=batch.get('token_type_ids',torch.zeros_like(batch['input_ids'])).cuda()
                        result.append(model._encode(encoder,ids,mask,typ).cpu())
                return torch.cat(result)
            entities=encode(descriptions,model.tail_bert)
            queries=encode([query_text(h,r,descriptions,cat) for h in range(n) for r in range(2*R)],model.hr_bert).reshape(n,2*R,-1)
            out.parent.mkdir(parents=True,exist_ok=True)
            torch.save(dict(entities=entities,queries=queries),out)
            save(out.with_suffix('.json'),dict(seed=seed,base_checkpoint=str(path.relative_to(PILOT)),checkpoint_sha256=file_sha(path/'best.pt'),
                cache_sha256=file_sha(out),entities=len(entities),query_shape=list(queries.shape),seconds=time.perf_counter()-start,
                no_target_file_read=True,known_catalogue_names_only=True,encoder_frozen=True))
            print('CACHED',DATASET,seed,list(queries.shape),flush=True)
            del model;torch.cuda.empty_cache()


if __name__=='__main__':main()
