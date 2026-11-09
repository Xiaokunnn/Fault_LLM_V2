#!/usr/bin/env python3
"""Seal developed code, then select new pages by metadata and fixed hash order."""
import datetime
import hashlib
import json
from pathlib import Path
from rp1_offline_contract_v3 import ROOT,BASE,rows,sha,write

OUT=BASE/'layout_direction_context_v1'


def collect_keys(obj):
    if isinstance(obj,dict):
        found={obj['page_key']} if isinstance(obj.get('page_key'),str) else set()
        for value in obj.values():found |= collect_keys(value)
        return found
    if isinstance(obj,list):
        return set().union(*(collect_keys(v) for v in obj)) if obj else set()
    return set()


def main():
    target=OUT/'new_pages';target.mkdir(exist_ok=False)
    dependencies=[Path(__file__),ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py',
        ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/automatic_contract_v4_1.py',
        ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/clause_binding_v1.py',
        ROOT/'scripts/rp1_offline_contract_v3.py',ROOT/'scripts/postprocess_rp1_holdout_v1.py',
        ROOT/'tests/unit/test_rp1_layout_direction_context_v1.py',OUT/'development/summary.json',OUT/'development/outputs.jsonl',
        ROOT/'docs/research/RP1_LAYOUT_DIRECTION_CONTEXT_V1_PROTOCOL_20261004.md',
        BASE/'independent_review_v1/extraction_template.json']
    # All method choices are fixed BEFORE opening candidate new page contents.
    write(OUT/'method_freeze.json',dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        sha256={str(p.relative_to(ROOT)):sha(p) for p in dependencies},new_pages_opened=False,
        sampling=dict(document_order=['MP015','MP016','MP018','MP021','MP007','MP004'],documents_needed=4,
            strata=['has_table','no_table'],minimum_text_characters=800,source_language='en',
            seed='RP1-LDC-20261004-new-pages-v1',fallback='next document in fixed list only if either stratum empty',
            exclusion='all page keys from old page/record review packets and six/29 page inventories'),
        no_new_API_calls=True,reviewer_basis='AI source support; not document-disjoint external evaluation'))
    exclusions=[BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl',BASE/'ai_review_v1/heldout_sources/source_only.jsonl',
        BASE/'scope_repair_v2/development_pages.jsonl',BASE/'loss_page_audit_v1/record_review_packets.jsonl',
        BASE/'loss_page_audit_v1/page_raw_comparison_packets.jsonl']
    used=set()
    for p in exclusions:
        if p.exists():used |= collect_keys(rows(p))
    selected=[];inventory=[];attempts=[]
    for doc in ['MP015','MP016','MP018','MP021','MP007','MP004']:
        path=ROOT/f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl'
        candidates=[]
        for p in rows(path):
            key=f'{doc}:p{p["pdf_page_number"]:04d}'
            if key in used or p.get('source_language')!='en' or len(p['page_text'].strip())<800:continue
            assert doc in ['MP015','MP016','MP018','MP021','MP007','MP004']
            p['page_key']=key;candidates.append(p)
        bins={flag:[p for p in candidates if bool(p['tables'])==flag] for flag in [True,False]}
        attempts.append(dict(doc_id=doc,with_table=len(bins[True]),without_table=len(bins[False])))
        if not all(bins.values()):continue
        for flag in [True,False]:
            p=min(bins[flag],key=lambda p:hashlib.sha256(('RP1-LDC-20261004-new-pages-v1|'+p['page_key']).encode()).hexdigest())
            selected.append(p);inventory.append(dict(page_key=p['page_key'],doc_id=doc,has_table=flag,
                source_language=p['source_language'],source_page_sha256=p['page_text_sha256'],
                local_file=p['local_file'],physical_page=p['pdf_page_number']))
        if len(selected)==8:break
    if len(selected)!=8:raise ValueError('Prespecified metadata frame has fewer than four eligible documents')
    write(target/'source_only.jsonl',selected);write(target/'inventory.jsonl',inventory)
    write(target/'selection.json',dict(excluded_page_keys=sorted(used),attempts=attempts,
        method_freeze_sha256=sha(OUT/'method_freeze.json'),source_sha256=sha(target/'source_only.jsonl'),
        historical_candidates_used=False,postselection_replacement=False))
    print(json.dumps(dict(selected=inventory,excluded_pages=len(used),attempts=attempts),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
