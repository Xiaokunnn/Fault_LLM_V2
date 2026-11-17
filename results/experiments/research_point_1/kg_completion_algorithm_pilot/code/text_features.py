"""Actual frozen BGE encoder features from sanitized native evidence, not TF-IDF."""
import time
import torch
from transformers import AutoModel,AutoTokenizer
from common import RUN,ROOT,read,save,file_sha


def main():
    folder=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d'
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2)
    tokenizer=AutoTokenizer.from_pretrained(folder,local_files_only=True)
    model=AutoModel.from_pretrained(folder,local_files_only=True).to(device).eval()
    data=read(RUN/'data/training_entity_text.jsonl')
    for mode in ['labels','evidence']:
        output=RUN/'data'/('text_labels.pt' if mode=='labels' else 'text_features.pt')
        if output.exists():continue
        vectors=[];tokens=0;start=time.perf_counter()
        with torch.no_grad():
            for off in range(0,len(data),64):
                texts=[r['label'] if mode=='labels' else r['text'] for r in data[off:off+64]]
                batch=tokenizer(texts,padding=True,truncation=True,max_length=128,return_tensors='pt');tokens+=int(batch['attention_mask'].sum())
                result=model(**{k:v.to(device) for k,v in batch.items()}).last_hidden_state[:,0]
                vectors.append(torch.nn.functional.normalize(result,dim=-1).cpu())
        torch.save(dict(features=torch.cat(vectors),model_path=str(folder),mode=mode),output)
        save(output.with_suffix('.metadata.json'),dict(mode=mode,entities=len(data),encoder=str(folder),
             pooling='normalized CLS',fine_tuned=False,max_length=128,actual_tokens=tokens,seconds=time.perf_counter()-start,
             input_sha256=file_sha(RUN/'data/training_entity_text.jsonl'),output_sha256=file_sha(output),
             checkpoint_files={p.name:file_sha(p) for p in folder.iterdir() if p.suffix in ['.json','.safetensors','.bin']},
             source_claim='pretrained encoder + sanitized allowed native evidence; not SimKGC'))
        print('Encoded',mode,len(data),time.perf_counter()-start,flush=True)


if __name__=='__main__':main()
