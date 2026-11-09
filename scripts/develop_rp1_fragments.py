#!/usr/bin/env python3
"""Use all ten cached pages to develop complete-fragment menus, with no API."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from rp1_offline_contract_v3 import BASE,REGISTRY,rows,sha,write
from research_point_1_graph_evidence.stage02_triple_extraction.native_evidence_selection import normalize_legacy
from research_point_1_graph_evidence.stage02_triple_extraction.source_fragment_extraction import (
    prepare_catalog,model_input,source_endpoint_dictionary,compile_records)

OLD=BASE/'extraction_validation'
OUT=BASE/'fragment_extraction'


def compact(text):return ''.join(text.casefold().split())


def main():
    directory=OUT/'development';directory.mkdir(parents=True,exist_ok=True)
    for child in ['catalogs','model_inputs']:(directory/child).mkdir(exist_ok=True)
    requests=rows(OLD/'requests.jsonl');sources={s['page_key']:s for s in rows(OLD/'sources.jsonl')}
    responses={r['request_id']:json.load(open(OLD/'api'/f'{r["request_id"]}.parsed.json')) for r in requests}
    dictionary=source_endpoint_dictionary(list(responses.values()))
    write(directory/'endpoint_dictionary.json',dictionary)
    audit=[];catalogs={};summaries=[];roundtrips=0
    for req in requests:
        s=sources[req['page_key']];cat=prepare_catalog(s['target'],s['context_pages'],dictionary);catalogs[s['page_key']]=cat
        assert cat['coverage']['source_character_coverage']==1 and not cat['coverage']['missing']
        write(directory/'catalogs'/f'{req["request_id"]}.json',cat)
        write(directory/'model_inputs'/f'{req["request_id"]}.json',model_input(cat))
        native={}
        for p in [s['target'],*s['context_pages']]:
            native.update({b['block_id']:b for b in p['text_blocks']})
            native.update({c['cell_id']:c for t in p['tables'] for r in t['rows'] for c in r['cells']})
        for part in [*cat['paragraphs'].values(),*cat['candidates'].values()]:
            for w in part['source_spans']:
                assert native[w['unit_id']]['text'][w['start']:w['end']]==w['text']
                assert native[w['unit_id']]['bbox']==w['bbox'];roundtrips+=1
        clean=normalize_legacy(responses[req['request_id']])
        for i,r in enumerate(clean['records'],1):
            matches={}
            for side in ['head','tail']:
                surface=r.get(side+'_surface') if isinstance(r,dict) else None
                ids=r.get(side+'_evidence_ids',[]) if isinstance(r,dict) else []
                types=r.get(side+'_type') if isinstance(r,dict) else None
                allowed='A' if types in ['MaintenanceAction','InspectionAction','InspectionMethod'] else 'E'
                matches[side]=[c['id'] for c in cat['candidates'].values() if c['id'].startswith(allowed) and
                    isinstance(surface,str) and surface.strip() and compact(surface) in compact(c['text']) and
                    isinstance(ids,list) and set(ids)&{w['unit_id'] for w in c['source_spans']}]
            audit.append(dict(candidate_id=f'{req["request_id"]}:{i:03d}',page_key=s['page_key'],
                choices=matches,both_endpoints_representable=bool(matches['head']) and bool(matches['tail']),
                cached_semantics_modified=False,quality_gain_established=False,
                meaning='Exact whitespace/case-insensitive cached surface containment at declared source units; menu representability, NOT correctness'))
        summaries.append(dict(page_key=s['page_key'],paragraphs=len(cat['paragraphs']),choices=len(cat['candidates']),
            table_rows=len(cat['branches']),primary_source_characters=cat['coverage']['total_nonwhitespace_characters'],
            covered_source_characters=cat['coverage']['covered_nonwhitespace_characters'],
            duplicate_native_units=cat['coverage']['duplicate_units'],source_character_coverage=1))
    write(directory/'cache_menu_audit.jsonl',audit)
    # These proposals exercise the new interface, not a new extraction result.
    examples=[]
    def example(page_key,action_text,head_text,head_zh,tail_zh,condition_names=None):
        cat=catalogs[page_key]
        acts=[c for cid,c in cat['candidates'].items() if cid.startswith('A') and action_text in c['text']]
        a=min(acts,key=lambda c:len(c['text']))
        heads=[c for cid,c in cat['candidates'].items() if cid.startswith('E') and c['kind']=='nominal_candidate' and head_text in c['text']]
        # Prefer the noun in the selected action, not a different occurrence.
        e=min(heads,key=lambda c:(not bool(set(c['parents'])&set(a['parents'])),len(c['text'])))
        shared=[sid for sid in a['scope_ids'] if cat['candidates'][sid].get('scope_kind') in ['phase','branch','applicability']]
        used=a['local_condition_ids']+shared
        names={cid:(condition_names or {}).get(cat['candidates'][cid]['text']) for cid in used}
        for cid in a['local_condition_ids']:
            text=cat['candidates'][cid]['text']
            if names[cid] is not None:continue
            if 'free of dirt' in text:names[cid]='确认转子轴及密封腔孔无污物、砂砾和划痕'
            elif 'after seal is installed' in text:names[cid]='密封安装到轴上后'
            elif 'Some seals are equipped' in text:names[cid]='仅适用于配有压缩密封弹簧保持夹片的密封'
            else:raise ValueError(('Untranslated local demo condition',text))
        for cid in shared:
            text=cat['candidates'][cid]['text']
            names[cid]='泵组装配阶段' if 'ASSEMBLING' in text else '部件式机械密封安装阶段' if 'INSTALLATION' in text else 'O形圈型机械密封座安装' if 'O-RING' in text else '源文章节适用阶段'
        record=dict(head=[e['id'],'Component',head_zh],relation='maintained_by',tail=[a['id'],'MaintenanceAction',tail_zh],
            local=a['local_condition_ids'],shared=shared,evidence=list(dict.fromkeys(e['parents']+a['parents'])),mode='required',polarity='positive',unresolved=None)
        response=dict(catalog_sha256=cat['catalog_sha256'],records=[record],condition_names=names)
        dec=compile_records(response,cat,REGISTRY)[0];assert dec['automatic_pass'],dec['flags']
        examples.append(dict(page_key=page_key,authorship='Codex local interface proposal, not API output or quality evaluation',response=response,decision=dec))
    example('MP005:p0108','Push the slide ring','slide ring','动环','用手将动环推过轴')
    example('MP005:p0108','use a\nfitting tool','slide ring','动环','波纹管过紧时使用装配工具并避免损坏动环',{'If the rubber bellows is tight':'橡胶波纹管过紧时'})
    example('MP005:p0108','important to check','carbon ring','碳环','检查碳环安装正确，倒角/研磨面朝静环座',{'If the carbon ring is not fixed':'碳环未固定时'})
    example('MP005:p0108','check by viewing','leak hole','泄漏孔','目视泄漏孔确认没有泄漏',{'After start':'启动后'})
    example('MP021:p0006','Clean rotor shaft','rotor shaft','转子轴','清洁转子轴并确认无污物、砂砾及划痕')
    example('MP021:p0006','Remove holding\nclips','holding\nclips','保持夹片','密封安装到轴上后移除保持夹片以释放弹簧')
    example('MP021:p0006','Lubricate outer diameter','O-Ring seal gasket','O形圈密封垫片','用P-80或等效品润滑O形圈密封垫片外径')
    write(directory/'local_examples.jsonl',examples)
    result=dict(status='offline_interface_development_complete_not_model_quality',API_calls=0,
        cached_pages=len(summaries),all_cached_outputs_retained=len(audit),
        both_cached_endpoints_have_menu_choices=sum(a['both_endpoints_representable'] for a in audit),
        primary_source_characters=sum(p['primary_source_characters'] for p in summaries),
        covered_source_characters=sum(p['covered_source_characters'] for p in summaries),
        source_character_coverage=1,native_source_roundtrips=roundtrips,local_examples=len(examples),
        pages=summaries,source_semantic_recall_or_accuracy=None,graph_promoted=False)
    write(directory/'summary.json',result)
    write(directory/'input_manifest.json',dict(source_sha256=sha(OLD/'sources.jsonl'),
        response_sha256={str((OLD/'api'/f'{r["request_id"]}.parsed.json').relative_to(ROOT)):sha(OLD/'api'/f'{r["request_id"]}.parsed.json') for r in requests},
        dictionary_used_source_surfaces_only=True,AI_quality_labels_used=False))
    print(json.dumps({k:v for k,v in result.items() if k!='pages'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
