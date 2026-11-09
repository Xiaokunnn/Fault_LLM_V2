#!/usr/bin/env python3
"""Four source-backed development examples, authored locally, NOT API outputs."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import BASE, REGISTRY, rows, sha, write
from research_point_1_graph_evidence.stage02_triple_extraction.native_evidence_selection import catalog, compile_selection, digest
from research_point_1_graph_evidence.stage03_schema_validation.layout_direction_context_v1 import locate

OLD=BASE/'extraction_validation'
OUT=BASE/'source_selection_development'


def main():
    source=next(s for s in rows(OLD/'sources.jsonl') if s['page_key']=='MP005:p0108')
    page=source['target'];previous=source['context_pages'];cat=catalog(page,previous)
    by_native={u['native_id']:(k,u) for k,u in cat.items()}
    old=json.loads((OLD/'api/P02.parsed.json').read_text())
    def select(quote,ids):
        hits,_=locate({**page,'tables':[]},quote,ids)
        hits=[h for h in hits if all(w.get('block_id') in ids for w in h['witnesses'])]
        assert len(hits)==1,(quote,len(hits))
        refs=[]
        for w in hits[0]['witnesses']:
            k,u=by_native[w['block_id']]
            start=next(i for i,t in enumerate(u['tokens']) if t['start']==w['start'])
            end=next(i+1 for i,t in enumerate(u['tokens']) if t['end']==w['end'])
            refs.append(dict(unit_id=k,start=start,end=end))
        return refs
    selected=[10,11,12,16];records=[]
    for i in selected:
        a=old['records'][i-1]
        records.append(dict(record_id=f'R{i}',
            # R11 explicitly chooses the occurrence in its own tool-use clause,
            # not the identical noun in the preceding hand-push instruction.
            head=dict(canonical_zh=a['head_canonical_zh'],type=a['head_type'],spans=select(a['head_surface'],
                ['MP005:p0108:b0009'] if i==11 else a['head_evidence_ids'])),
            tail=dict(canonical_zh=a['tail_canonical_zh'],type=a['tail_type'],spans=select(a['tail_surface'],a['tail_evidence_ids'])),
            relation=a['relation'],evidence=[r for q in a['evidence'] for r in select(q['quote'],[q['unit_id']])],
            polarity=a['polarity'],negation_evidence=[],modality=a['modality'],scope='primary',
            condition_ids=['ASSEMBLY']+({11:['TIGHT'],12:['CARBON_UNFIXED'],16:['AFTER_START']}.get(i,[])),
            conditions_complete=True,unresolved_reason=None,table_branch=None))
    conditions=[dict(condition_id='ASSEMBLY',kind='procedure_phase',canonical_zh='泵组装配阶段',
        evidence=select('ASSEMBLING PUMP SET',['MP005:p0108:b0000']),
        applies_to=[dict(record_id=r['record_id'],binding_evidence=r['evidence']) for r in records])]
    for cid,i,text,ids,zh,kind in [
        ('TIGHT',11,'If the rubber bellows is tight',['MP005:p0108:b0008'],'橡胶波纹管过紧时','local_antecedent'),
        ('CARBON_UNFIXED',12,'If the carbon ring is not fixed',['MP005:p0108:b0009'],'碳环未固定时','local_antecedent'),
        ('AFTER_START',16,'After start',['MP005:p0108:b0013'],'启动后','procedure_phase')]:
        record=next(r for r in records if r['record_id']==f'R{i}')
        conditions.append(dict(condition_id=cid,kind=kind,canonical_zh=zh,evidence=select(text,ids),
            applies_to=[dict(record_id=f'R{i}',binding_evidence=record['evidence'])]))
    response=dict(catalog_sha256=digest(cat),conditions=conditions,records=records,
        coverage_note='Four locally authored interface examples; not full-page extraction, new API results or quality evaluation.')
    compiled=compile_selection(response,page,previous,REGISTRY)
    assert len(compiled)==4 and all(r['automatic_pass'] for r in compiled),[(r['record_id'],r['flags']) for r in compiled]
    write(OUT/'local_examples.selection.json',response)
    write(OUT/'local_examples.compiled.jsonl',compiled)
    write(OUT/'local_examples.manifest.json',dict(authored_by='Codex source-reading development examples',
        actual_API_outputs=False,independent_evaluation=False,records=4,automatic_pass=4,
        source_sha256=sha(OLD/'sources.jsonl'),old_response_sha256=sha(OLD/'api/P02.parsed.json'),
        script_sha256=sha(Path(__file__)),compiler_sha256=sha(ROOT/'src/research_point_1_graph_evidence/stage02_triple_extraction/native_evidence_selection.py'),
        semantic_repairs_applied_to_224=False,final_graph_promoted=False))
    print(json.dumps([dict(id=a['record_id'],head=a['head']['surface'],tail=a['tail']['surface'],
        conditions=[c['canonical_zh'] for c in a['conditions']]) for a in compiled],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
