"""Frozen semantic index with explicit roles, native metadata and missingness."""
from collections import Counter
import time
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer
from io_utils import *


def edge_sources(e, registry):
    out=[]
    for k in e['source_keys']:
        x=registry.get(k,[])
        out.extend(x if isinstance(x,list) else [x])
    return out


def bindings(rows):
    values=[]
    for x in rows[:2]:
        units=x.get('evidence_units') or x.get('expansion_source_witnesses') or []
        layout=[{k:u.get(k) for k in ['cell_id','block_id','row_group_id','column_name','column_role','text'] if u.get(k) is not None} for u in units[:8]]
        values.append(dict(doc=x['doc_id'],pump_type=x.get('pump_type','<missing>'),service=x.get('service','<missing>'),
            scope=x.get('applicability_scope','<missing>'),condition=x.get('conditions_source') or '<missing>',
            modality=x.get('modality') or '<missing>',native_units=x.get('evidence_unit_ids') or '<missing>',layout=layout,
            evidence=x.get('evidence_text','')[:900]))
    return values


def main():
    if (EXP/'index/freeze.json').exists():print('REUSE frozen index');return
    torch.set_num_threads(2); cat=read(EXP/'data/catalogue.json');R=len(cat['relations']);n=cat['nbase']
    rows=[e for e in read(EXP/'data/context_edges.jsonl') if e['legal']]
    sources=read(EXP/'data/training_source_registry.json');types=sorted({e['entity_type'] for e in cat['entities']});ti={t:i for i,t in enumerate(types)}
    views=[];fieldcounts=Counter()
    for j,e in enumerate(rows):
        ss=edge_sources(e,sources); info=bindings(ss)
        text=' '.join(x.get('evidence_text','') for x in ss)
        us=[u for x in ss for u in (x.get('evidence_units') or x.get('expansion_source_witnesses') or [])]
        native_count=sum(bool(x.get('evidence_unit_ids') or x.get('evidence_units') or x.get('expansion_source_witnesses')) for x in ss)
        flags=[float(bool(ss)),float(any(x.get('conditions_source') for x in ss)),float(any(x.get('modality') for x in ss)),float(bool(native_count)),
               float(any(u.get('row_group_id') for u in us)),float(any(u.get('column_role') and u.get('column_role')!='unclassified' for u in us)),
               float(any(x.get('pump_type') for x in ss)),float(any(x.get('native_address',{}).get('exact_contiguous_offset') or x.get('native_address',{}).get('all_provided_cells_match') or x.get('native_address',{}).get('all_native_witnesses_match') for x in ss))]
        for k,v in zip(['evidence','explicit_condition','modality','native_location','row_group','column_role','pump_metadata','native_address_verified'],flags):fieldcounts[k]+=int(v)
        h,r,t=e['triple']
        for direction,(a,b,rel) in enumerate([(h,t,r),(t,h,r+R)]):
            relation=('逆向关系：' if direction else '')+cat['registry'][cat['relations'][r]]['label_zh']
            plain=f"主体：{cat['entities'][a]['label_zh']}。关系：{relation}。客体：{cat['entities'][b]['label_zh']}。"
            full=plain+' 适用和证据绑定：'+canonical(info) if info else plain+' 证据、条件、型号及原生位置：<missing>'
            views.append(dict(view_id=2*j+direction,edge_index=j,anchor=a,neighbor=b,relation=rel,plain=plain,semantic=full,
                metadata_missing=not bool(info),flags=flags))
    path=ROOT/'data/model/BAAI-bge-small-zh-v1.5-r7999e1d'
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True);model=AutoModel.from_pretrained(path,local_files_only=True).cuda().eval()
    start=time.perf_counter();tokens=0
    def encode(texts,length=128):
        nonlocal tokens
        result=[]
        with torch.no_grad():
            for off in range(0,len(texts),128):
                b=tok(texts[off:off+128],padding=True,truncation=True,max_length=length,return_tensors='pt');tokens+=int(b['attention_mask'].sum())
                z=model(**{k:v.cuda() for k,v in b.items()}).last_hidden_state[:,0]
                result.append(torch.nn.functional.normalize(z,dim=-1).cpu())
        return torch.cat(result)
    reltexts=[('逆向关系：' if r>=R else '')+cat['registry'][cat['relations'][r%R]]['label_zh']+'；'+cat['relations'][r%R] for r in range(2*R)]
    vectors=dict(entities=encode([e['label_zh'] for e in cat['entities']]),relations=encode(reltexts),
        plain=encode([v['plain'] for v in views]),semantic=encode([v['semantic'] for v in views],192),
        queries=encode([cat['entities'][h]['label_zh']+' [SEP] '+reltexts[r] for h in range(n) for r in range(2*R)]).reshape(n,2*R,-1))
    out=EXP/'index/vectors.pt';out.parent.mkdir(parents=True,exist_ok=True);torch.save(vectors,out)
    save(EXP/'index/edges.jsonl',rows);save(EXP/'index/oriented_views.jsonl',views)
    save(EXP/'index/feature_inventory.json',dict(edges=len(rows),views=len(views),native_features_present=fieldcounts,
        condition_labels_are_not_gold=True,embedding_truncation_tokens=192,full_provenance_retained=True,
        caution='Distinct native IDs make inputs observable, not semantically proven. Query h,r lacks user operating conditions; no applicability certification.'))
    save(EXP/'index/freeze.json',dict(data_freeze_sha256=file_sha(EXP/'data/freeze.json'),files={str(p.relative_to(EXP)):file_sha(p) for p in (EXP/'index').glob('*') if p.name!='freeze.json'},
        encoder=str(path),seconds=time.perf_counter()-start,actual_tokens=tokens,pretrained_frozen=True,no_test_target_read=True))
    print('INDEX',len(rows),'edges',len(views),'oriented records',dict(fieldcounts),flush=True)


if __name__=='__main__':main()
