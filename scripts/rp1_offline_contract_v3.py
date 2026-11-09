#!/usr/bin/env python3
"""Offline contract utilities. Filter never consumes adjudication/reference labels."""
import copy
import hashlib
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/experiments/research_point_1'
OUT = BASE / 'offline_contract_v3'
SOURCE = BASE / 'adjudication_targeted_v2_1'
REVIEW = BASE / 'targeted_api_review_v2_1'
REGISTRY = json.loads((ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json').read_text())['relation_registry']

def rows(path): return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def object_sha(obj): return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
def write(path, value):
    content = ''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in value) if path.suffix == '.jsonl' else json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if path.exists():
        if path.read_text() != content: raise ValueError(f'Refuse overwrite {path}')
    else:
        with path.open('x') as f: f.write(content)
def flat(s): return ' '.join(s.split())
def span(text, quote):
    if not quote.strip(): return None
    indexes = [i for i,c in enumerate(text) if not c.isspace()]
    s = ''.join(text[i] for i in indexes); q = ''.join(quote.split()); offset = s.find(q)
    if offset < 0: return None
    start, end = indexes[offset], indexes[offset+len(q)-1]+1
    return {'kind':'page_span', 'start':start, 'end':end, 'text':text[start:end]}
def bind(page, quote):
    w = span(page['page_text'], quote)
    if w: return w
    for t in page['tables']:
        for row in t['rows']:
            for c in row['cells']:
                w = span(c['text'], quote)
                if w:
                    return {**w, 'kind':'native_cell_subspan', 'cell_id':c['cell_id'], 'bbox':c.get('bbox'), 'offset_basis':'original_native_cell'}
    return None

def type_valid(a):
    rel = REGISTRY.get(a['relation'])
    return bool(rel and a['head_type'] in rel['domain'] and a['tail_type'] in rel['range'])
def core(a): return REGISTRY.get(a.get('relation'),{}).get('core_diagnostic_relation',False)
def channel(a):
    if a.get('scope') == 'background': return 'background'
    if a.get('record_kind'): return 'auxiliary'
    return 'core' if core(a) else 'noncore'

def filter_flags(a, page):
    """Prespecified intentionally limited automatic screening, no label/ID access."""
    flags=[]
    if not type_valid(a): flags.append('schema_type_direction')
    if bind(page,a['evidence_text']) is None: flags.append('unbound_quote')
    units={c['cell_id'] for t in page['tables'] for row in t['rows'] for c in row['cells']}
    if any(x not in units for x in a['evidence_unit_ids']): flags.append('unknown_native_unit')
    h,t=flat(a['head_surface']).lower(),flat(a['tail_surface']).lower()
    e=flat(a['evidence_text']).lower()
    if a['relation']=='maintained_by':
        if a['polarity']=='negative' or re.search(r'\bno maintenance\b',t): flags.append('negative_requirement_not_action')
        if re.search(r'\bsee paragraph\b',t): flags.append('cross_reference_not_concrete_action')
        if 'liquid conveyed' in t and 'lubricat' in t: flags.append('operating_mechanism_not_maintenance_action')
        if 'outlet valve' in h and 'opened' in t: flags.append('startup_operation_not_maintenance')
    if a['relation']=='prevented_by' and re.search(r'using .* once again|replace the|install the|age exploration tasks',h):
        flags.append('procedure_goal_not_adverse_event')
    if a['relation']=='inspected_by' and 'pressure meter'==h and 'working pressure' in t:
        flags.append('instrument_not_inspection_target')
    # Conditional word warning is deliberately conservative; checklist whether is not antecedent.
    conditional = bool(re.search(r'\b(?:unless|when|except|only if)\b',e) or re.search(r'\bif\b',e) and ' or not' not in e and not re.search(r'check if',e))
    asserted_fields=flat(' '.join([a['head_surface'],a['tail_surface'],a['applicability'],*a['conditions']])).lower()
    explicit_marker=bool(re.search(r'\bif\b|\bwhen\b|\bbefore\b|\bafter\b|\bunless\b|\bexcept\b',asserted_fields))
    if conditional and not a['conditions'] and not explicit_marker: flags.append('conditional_context_not_explicit')
    if re.search(r'\bmay\b',e) and a['relation'] in {'causes','evolves_to','manifests_as'} and a['modality']=='asserted':
        flags.append('possible_to_asserted')
    return flags

def exact_key(a):
    # Exact textual dedup only, no claim of complete semantic dedup.
    keys=('head_surface','head_type','relation','tail_surface','tail_type','conditions','modality','polarity','scope','applicability','record_kind','requirement')
    return object_sha({k:a.get(k) for k in keys})

def maximum_matching(edges):
    """One candidate can account for at most one full reference per page/arm."""
    owner={}
    def augment(ref,visited):
        for cid in sorted(edges[ref]):
            if cid in visited: continue
            visited.add(cid)
            if cid not in owner or augment(owner[cid],visited):
                owner[cid]=ref; return True
        return False
    for ref in sorted(edges): augment(ref,set())
    return {ref:cid for cid,ref in owner.items()}
