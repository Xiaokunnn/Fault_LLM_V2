"""Bounded role recovery from native table headers or explicit prose syntax.

No labels, record IDs, graph membership, files or model calls are consulted.
The result is a new, context-qualified assertion, never an upgrade of the old
validator record. Headers and original cell/block characters remain attached.
"""
import copy
import re
from .layout_direction_context_v1 import locate, native_views

def norm(s): return ''.join(str(s).casefold().split())
def flat(s): return ' '.join(str(s).split())

def span(text,value):
    chars=[i for i,c in enumerate(text) if not c.isspace()]
    hay=''.join(text[i].casefold() for i in chars);needle=norm(value)
    if not needle:return None
    pos=hay.find(needle)
    if pos<0 or hay.find(needle,pos+1)>=0:return None
    # The corpus languages used here have one-codepoint case mappings.
    if len(hay)!=len(chars):return None
    return chars[pos],chars[pos+len(needle)-1]+1

def witness(unit):
    key='cell_id' if 'cell_id' in unit else 'block_id'
    return dict(kind='native_cell_subspan' if key=='cell_id' else 'native_block_subspan',
        **{key:unit[key]},start=0,end=len(unit['text']),text=unit['text'],bbox=copy.deepcopy(unit['bbox']))

def header_role(text):
    text=flat(text).strip().lower()
    if re.fullmatch(r'(?:possible |probable )?(?:causes?|reasons?)',text):return 'cause'
    if re.fullmatch(r'(?:faults?|trouble|symptoms?|problem(?: description)?|defect \(failure\))',text):return 'fault'
    if re.fullmatch(r'(?:remed(?:y|ies)|(?:possible )?solutions?|corrections?|what to do)',text):return 'remedy'
    if re.fullmatch(r'(?:check point|checks?|inspection)',text):return 'check'
    return None

def table_roles(table):
    headers=[]
    for row in table['rows'][:3]:
        for c in row['cells']:
            role=header_role(c['text'])
            if role:headers.append((role,c))
    # Real header geometry handles parsers splitting border/padding columns.
    def role_of(cell):
        b=cell['bbox'];center=(b['x0']+b['x1'])/2
        roles={role for role,h in headers if h['bbox']['x0']-2<=center<=h['bbox']['x1']+2 and h['bbox']['bottom']<=b['top']+1}
        return next(iter(roles)) if len(roles)==1 else None
    return headers,role_of

def type_ok(a,schema):
    rule=schema.get(a['relation'],{})
    return a['head_type'] in rule.get('domain',[]) and a['tail_type'] in rule.get('range',[])

def orient(record,swapped,relation):
    result=copy.deepcopy(record)
    if swapped:
        keys={k[5:] for k in record if k.startswith('head_')}|{k[5:] for k in record if k.startswith('tail_')}
        for suffix in keys:
            result['head_'+suffix],result['tail_'+suffix]=record.get('tail_'+suffix),record.get('head_'+suffix)
        result['head'],result['tail']=record.get('tail'),record.get('head')
    result['relation']=relation
    return result

def table_proposals(record,page,schema):
    proposals=[]
    for table in page['tables']:
        headers,role_of=table_roles(table)
        if not {'fault','cause'}<={r for r,_ in headers}:continue
        cells=[c for row in table['rows'] for c in row['cells'] if c['text'].strip()]
        hs=[c for c in cells if span(c['text'],record['head_surface'])]
        ts=[c for c in cells if span(c['text'],record['tail_surface'])]
        for h in hs:
            for t in ts:
                if h['cell_id']==t['cell_id']:continue
                hb,tb=h['bbox'],t['bbox']
                overlap=min(hb['bottom'],tb['bottom'])-max(hb['top'],tb['top'])
                if overlap<.8*min(hb['bottom']-hb['top'],tb['bottom']-tb['top']):continue
                hr,tr=role_of(h),role_of(t);swapped=False;relation=None
                if (hr,tr)==('cause','fault'):relation='causes'
                elif (hr,tr)==('fault','cause'):relation='causes';swapped=True
                elif hr in {'fault','cause'} and tr in {'remedy','check'}:
                    if record['tail_type']=='MaintenanceAction':relation='mitigated_by'
                    elif record['tail_type'] in {'InspectionMethod','InspectionAction'}:relation='diagnosed_by'
                elif tr in {'fault','cause'} and hr in {'remedy','check'}:
                    swapped=True
                    if record['head_type']=='MaintenanceAction':relation='mitigated_by'
                    elif record['head_type'] in {'InspectionMethod','InspectionAction'}:relation='diagnosed_by'
                if not relation:continue
                result=orient(record,swapped,relation)
                if not type_ok(result,schema):continue
                # Do not turn lists of parts/periods or operating start-up into
                # repair actions merely because they occupy a remedy column.
                if relation=='mitigated_by' and not re.search(r'\b(replace|repair|clean|adjust|tighten|remove|correct|renew|check)\b|更换|清理|修理|调整',result['tail_surface'],re.I):continue
                # Preserve every fault/cause/remedy/check cell at the actual
                # row intersection, including merged fault cells and conditions.
                y0=max(hb['top'],tb['top']);y1=min(hb['bottom'],tb['bottom'])
                context=[c for c in cells if role_of(c) and min(c['bbox']['bottom'],y1)>max(c['bbox']['top'],y0)]
                proof=[witness(c) for c in [h,t]]+[witness(c) for _,c in headers]
                proposals.append(dict(payload=result,mechanism='native_table_role_binding',swapped=swapped,
                    source_witnesses=proof,conditions_source=[dict(role=role_of(c),cell_id=c['cell_id'],text=c['text']) for c in context],
                    modality='possible' if relation=='causes' else 'recommended',
                    support_explanation='source header roles and overlapping original cell geometry',
                    header_units=[c['cell_id'] for _,c in headers]))
    # Multiple geometric interpretations stay unresolved.
    unique={str((p['payload']['head_surface'],p['payload']['relation'],p['payload']['tail_surface'],p['conditions_source'])):p for p in proposals}
    return list(unique.values())

ACTIVE=re.compile(r'^\s*[,;:]?\s*(?:(?:may|can|could|will|would)\s+)?(?:cause[sd]?|causing|leads? to|results? in|produces?)\s+(?:(?:a|an|the)\s+)?$',re.I)
PASSIVE=re.compile(r'^\s*(?:(?:is|are|was|were|may be|can be)\s+)?(?:caused by|due to|because of)\s+(?:(?:a|an|the)\s+)?$',re.I)

def prose_proposal(record,page,schema):
    quote=record.get('evidence_text','');hits,_=locate(page,quote,record.get('evidence_unit_ids',[]))
    if len(hits)!=1 or len(quote)>1800:return None
    q=flat(quote);h=span(q,record['head_surface']);t=span(q,record['tail_surface'])
    if not h or not t:return None
    # No negated causal relation, title, cross-reference, or bare parameter.
    if re.search(r'\b(?:not caused|does not cause|do not cause|no maintenance|maintenance.free|see (?:page|section|chapter))\b',q,re.I):return None
    relation=record['relation'];swapped=False
    if relation=='causes':
        if h[1]<=t[0] and ACTIVE.fullmatch(q[h[1]:t[0]]):pass
        elif t[1]<=h[0] and PASSIVE.fullmatch(q[t[1]:h[0]]):pass
        elif t[1]<=h[0] and ACTIVE.fullmatch(q[t[1]:h[0]]):swapped=True
        elif h[1]<=t[0] and PASSIVE.fullmatch(q[h[1]:t[0]]):swapped=True
        else:return None
    elif relation in {'maintained_by','inspected_by','diagnosed_by'}:
        action=flat(record['tail_surface'])
        if relation=='maintained_by':verb=r'(?:clean|replace|repair|lubricate|relubricate|renew|tighten|adjust|remove|install)'
        else:verb=r'(?:check|inspect|examine|measure|monitor|test)'
        # The action must explicitly contain its target; generic headings and
        # co-occurrence elsewhere in the paragraph cannot establish a role.
        if norm(record['head_surface']) not in norm(action):return None
        if not re.match(r'^(?:\d+[.)]\s*)?'+verb+r'\b',action,re.I):return None
        if relation=='maintained_by' and re.search(r'\b(?:do not|never|before starting|initial startup)\b',q,re.I):return None
    else:return None
    result=orient(record,swapped,relation)
    if not type_ok(result,schema):return None
    hit=hits[0]
    # Conditions are retained verbatim as a context-qualified proposition,
    # not dropped or replaced by a made-up unconditional graph edge.
    conditions=[dict(role='local_source_context',text=u['text'],unit_id=u.get('block_id',u.get('cell_id'))) for u in hit['context_units']]
    modality='possible' if re.search(r'\b(may|can|could|might)\b',q,re.I) else 'required' if re.search(r'\b(must|shall)\b',q,re.I) else 'recommended' if re.search(r'\bshould\b',q,re.I) else 'asserted'
    return dict(payload=result,mechanism='explicit_prose_role_binding',swapped=swapped,
        source_witnesses=hit['witnesses'],conditions_source=conditions,modality=modality,
        support_explanation='unique native quotation with explicitly ordered causal syntax or action target')

def repair(record,page,schema):
    if record['doc_id']!=page['doc_id'] or record['pdf_page_number']!=page['pdf_page_number'] or record['page_text_sha256']!=page['page_text_sha256'] or record['document_sha256']!=page['document_sha256']:raise ValueError('Source identity mismatch')
    if 'dual_qwen_relation_not_entailed' in record.get('rejection_reasons',[]):return None,'prior_model_contradiction'
    # General reliability texts and generic motor texts require a separate
    # applicability intervention; this batch adds only pump-manual knowledge.
    if record['doc_id'] not in {'MP004','MP005','MP006','MP007','MP015','MP016','MP017','MP018','MP020','MP021','MP022'}:return None,'scope_not_extended'
    proposals=table_proposals(record,page,schema)
    if len(proposals)>1:return None,'ambiguous_table_binding'
    if proposals:return proposals[0],None
    proposal=prose_proposal(record,page,schema)
    return (proposal,None) if proposal else (None,'no_unique_explicit_role_proof')
