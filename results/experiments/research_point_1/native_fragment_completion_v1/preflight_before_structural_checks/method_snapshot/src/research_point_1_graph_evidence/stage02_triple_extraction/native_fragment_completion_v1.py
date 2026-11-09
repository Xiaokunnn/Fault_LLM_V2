"""Experimental source-only fragment completion. No IO, models or labels.

Display normalization never changes native strings or manufactures positions.
Types and structural proposals are hypotheses, not semantic certification.
Opaque native IDs are used only as addresses, never to select a repair rule.
"""
import copy
import hashlib
import json
import re

from .contextual_extraction import units_of
from .source_fragment_extraction import (
    ACTION, BUILD_DOCS, NOMINAL_RE, grammatical_nominals, joined,
    sentence_ranges, witnesses,
)
from ..stage03_schema_validation.batch_evidence_repair_v1 import header_role
from ..stage03_schema_validation.layout_direction_context_v1 import native_views

VERSION = 'native_fragment_completion_v1'
PHYSICAL = r'pumps?|motors?|shafts?|seals?|bearings?|glands?|bushings?|valves?|impellers?|chambers?|casings?|housings?|pipes?|strainers?|filters?|rings?|sleeves?'
EVENT = r'rotation|running|wear|failure|damage|overheating|leakage|cavitation|blockage|corrosion|misalignment|vibration|explosion|fatigue|looseness|rubs?|microwelding|contact|lubrication|pressure|temperature|flow'
STOP = r'the|a|an|is|are|was|were|will|may|can|must|should|would|could|to|from|by|for|with|without|at|in|on|of|and|or|as|if|when|until|that|which|be|been|being|causes?|causing|result|results|recommended|not|never'
IMPERATIVE = r'(?:'+ACTION+r'|allow|increase|decrease|replace|renew|refill|drain|monitor|test|make sure|be sure)'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def normalized_view(text):
    """Return display chars and their real character positions in input text."""
    chars=[];positions=[];i=0
    while i<len(text):
        # Detect using the complete string so lookbehind remains meaningful.
        if text[i]=='-' and i and text[i-1].isalpha():
            m=re.match(r'-[ \t]*\n\s*(?=[A-Za-z])',text[i:])
            if m:i+=m.end();continue
        if text[i].isspace():
            if chars and chars[-1]!=' ':chars.append(' ');positions.append(i)
            i+=1;continue
        word=re.match(r'[A-Za-z0-9]+',text[i:])
        if word:
            token=word.group();runs=list(re.finditer(r'(.)\1*',token))
            factor=next((n for n in (3,2) if len(token)>=6 and len(runs)>=2 and all(len(r.group())%n==0 for r in runs)),1)
            for r in runs:
                for offset in range(0,len(r.group()),factor):
                    chars.append(r.group()[offset]);positions.append(i+r.start()+offset)
            i+=len(token);continue
        chars.append(text[i]);positions.append(i);i+=1
    return ''.join(chars),positions


def display(text):return normalized_view(text)[0].strip()


def phrase_ranges(text):
    """Bounded syntactic proposals; no list of known answers is supplied."""
    spans=set(grammatical_nominals(text)) | {m.span() for m in NOMINAL_RE.finditer(text)}
    # Compound nouns and event heads are taken from the actual sentence. The
    # modifiers are open vocabulary; e.g. any adjective before a motion noun.
    pattern=r'\b(?:(?!(?:'+STOP+r')\b)[A-Za-z][A-Za-z0-9/-]*\s+){0,4}(?:'+PHYSICAL+'|'+EVENT+r')\b'
    spans.update(m.span() for m in re.finditer(pattern,text,re.I))
    # Preserve coordinated targets as separate source fragments, not as one
    # phantom concatenation. Keep shorter head nouns as alternatives too.
    spans.update(m.span() for m in re.finditer(r'\b(?:'+PHYSICAL+'|'+EVENT+r')\b',text,re.I))
    for m in re.finditer(r'\b(?:will|can|may|does|do)\s+not\s+([a-z]+(?:\s+[a-z]+){0,2})(?=\s+(?:if|when|unless)|[,.]|$)',text,re.I):
        spans.add(m.span())
    return sorted((a,b) for a,b in spans if 2<=b-a<=180)


def type_hints(text,kind):
    if kind=='method':return ['InspectionMethod']
    if kind=='action':
        return ['InspectionAction'] if re.search(r'\b(check|inspect|examine|measure|verify|monitor|test)\b',text,re.I) else ['MaintenanceAction']
    out=[]
    if re.search(r'\b'+PHYSICAL+r'\b',text,re.I):
        out.append('Equipment' if re.fullmatch(r'(?:the\s+)?(?:[\w-]+\s+){0,2}pump(?:s| set)?',text,re.I) else 'Component')
    if re.search(r'\b(?:rotation|running|wear|failure|damage|overheating|leakage|cavitation|blockage|corrosion|misalignment|explosion|fatigue|looseness|microwelding)\b',text,re.I):out.append('FaultMode')
    if re.search(r'\b(?:pressure|temperature|flow|speed|head)\b',text,re.I):out.append('OperatingCondition')
    if re.search(r'\b(?:ISO|IEC|ASME|JIS|NEMA)\b',text):out.append('Standard')
    return out


def classify_table(table):
    """Infer table family only from existing headers/cells; unknown abstains."""
    rows=table.get('rows',[])
    for ri,row in enumerate(rows[:4]):
        cells=[(c,display(c['text'])) for c in row['cells'] if c['text'].strip()]
        roles={c.get('column_index',i):header_role(s) for i,(c,s) in enumerate(cells)}
        if {'fault','cause'}<={v for v in roles.values() if v}:
            return 'fault',ri,roles,{c.get('column_index',i):c for i,(c,_) in enumerate(cells)}
        method=[c for c,s in cells if re.search(r'monitoring\s+techniques?|inspection\s+methods?',s,re.I)]
        targets=[c for c,s in cells if re.search(r'conditions?\s+monitored|faults?\s+detected',s,re.I)]
        if len(method)==len(targets)==1:
            roles={c.get('column_index',i):('method' if c is method[0] else 'target' if c is targets[0] else 'qualifier') for i,(c,_) in enumerate(cells)}
            return 'monitoring',ri,roles,{c.get('column_index',i):c for i,(c,_) in enumerate(cells)}
        components=[(c,s) for c,s in cells if len(s.split())<=6 and re.search(r'\b'+PHYSICAL+r'\b',s,re.I) and not re.match(r'^(?:clean|replace|remove|inspect|check|lubricate|tighten|install|fit)\b',s,re.I)]
        if len(components)>=2 and min(c.get('column_index',0) for c,_ in components)>0:
            roles={c.get('column_index',i):'component' for i,(c,_) in enumerate(components)}
            return 'maintenance_matrix',ri,roles,{c.get('column_index',i):c for i,(c,_) in enumerate(components)}
    return None,None,{},{}


def complete_fragments(page,context_pages=()):
    if page['doc_id'] not in BUILD_DOCS:raise ValueError('not_build_document')
    if any(p['doc_id']!=page['doc_id'] for p in context_pages):raise ValueError('cross_document_context')
    pages=[*context_pages,page];native=units_of(pages)
    units=[];fragments=[];issues=[];headings=[];known={}

    def emit(run,kind,path,qualifiers=(),role=None,row=None):
        text,addr=joined(run);view,mapping=normalized_view(text)
        uid='U'+digest([path,[(u['native_id'],u['text']) for u in run]])[:18]
        unit=dict(id=uid,kind=kind,path=path,text=text,display_text=view,source_spans=witnesses(text,addr,0,len(text),native),qualifiers=copy.deepcopy(list(qualifiers)),role=role,row=row,fragment_ids=[])
        units.append(unit)

        def add(a,b,fkind,forced_hints=None):
            while a<b and view[a].isspace():a+=1
            while b>a and view[b-1].isspace():b-=1
            if a==b:return
            start=mapping[a];end=mapping[b] if b<len(mapping) else len(text)
            ws=witnesses(text,addr,start,end,native)
            value=view[a:b]
            key=(uid,a,b,fkind)
            if key in known:return
            fid='F'+digest([uid,a,b,fkind])[:18];known[key]=fid
            fragments.append(dict(id=fid,unit_id=uid,kind=fkind,text=text[start:end],display_text=value,source_spans=ws,type_hints=forced_hints if forced_hints is not None else type_hints(value,fkind),role=role,qualifiers=copy.deepcopy(list(qualifiers))))
            unit['fragment_ids'].append(fid)

        if kind=='table_method':add(0,len(view),'method',['InspectionMethod'])
        if kind=='table_component':add(0,len(view),'entity')
        for a,b in phrase_ranges(view):add(a,b,'entity')
        # Complete local sentences remain evidence units, not physical nodes.
        for a,b in sentence_ranges(view):
            sentence=view[a:b]
            if re.search(r'\b'+IMPERATIVE+r'\b',sentence,re.I):
                add(a,b,'action')
            # Explicit antecedents remain their own addressable fragments.
            for m in re.finditer(r'\b(?:if|when|unless|before|after|until|during|in case of)\b[^,;.!?]{2,240}',sentence,re.I):
                add(a+m.start(),a+m.end(),'condition',[])
        # Entire table-cell actions include their own temporal qualifier even
        # where OCR has no terminal punctuation.
        if kind=='table_action' and re.search(r'\b'+IMPERATIVE+r'\b',view,re.I):add(0,len(view),'action')
        return unit

    tables=[]
    for table in page.get('tables',[]):
        family,hi,roles,headers=classify_table(table)
        if not family:
            for row in table.get('rows',[]):
                for c in row['cells']:
                    if c['text'].strip():
                        emit([native[c['cell_id']]],'unresolved_table_cell',c['cell_id'],role='unresolved',row=row.get('row_id'))
            issues.append(dict(kind='table_family_unresolved',table_id=table['table_id']))
            continue
        tables.append(table)
        # Header fragments have actual native addresses, never invented boxes.
        for col,c in headers.items():
            if roles.get(col)=='component':
                emit([native[c['cell_id']]],'table_component',table['table_id']+':header:'+str(col),role='component')
        for row in table['rows'][hi+1:]:
            cells=[c for c in row['cells'] if c['text'].strip()]
            if not cells:continue
            # A source cell covering more than one header column has already
            # lost internal geometry. Retain it, do not pretend to unmerge it.
            def wide(c):
                box=c.get('bbox')
                if not box:return False
                return sum(1 for h in headers.values() if h.get('bbox') and min(box['x1'],h['bbox']['x1'])-max(box['x0'],h['bbox']['x0'])>.5*(h['bbox']['x1']-h['bbox']['x0']))>1
            bad=[c for c in cells if wide(c)]
            context=[dict(role='row_context',source_spans=[dict(unit_id=c['cell_id'],start=0,end=len(c['text']),text=c['text'],bbox=copy.deepcopy(c.get('bbox')),doc_id=page['doc_id'],pdf_page_number=page['pdf_page_number'])],text=c['text']) for c in cells]
            for c in bad:
                issues.append(dict(kind='merged_columns_unresolved',table_id=table['table_id'],row_id=row.get('row_id'),cell_id=c['cell_id']))
                emit([native[c['cell_id']]],'unresolved_table_cell',c['cell_id'],context,role='unresolved',row=row.get('row_id'))
            for c in cells:
                if c in bad:continue
                col=c.get('column_index');role=roles.get(col)
                q=copy.deepcopy(context)
                if family=='maintenance_matrix':
                    if col not in headers:continue
                    for item,cell in zip(q,cells):
                        if cell.get('column_index')==0:item['role']='row_condition'
                    h=headers[col]
                    q.append(dict(role='component_header',text=h['text'],source_spans=[dict(unit_id=h['cell_id'],start=0,end=len(h['text']),text=h['text'],bbox=copy.deepcopy(h.get('bbox')),doc_id=page['doc_id'],pdf_page_number=page['pdf_page_number'])]))
                    emit([native[c['cell_id']]],'table_action',c['cell_id'],q,role='maintenance',row=row.get('row_id'))
                else:
                    for item,cell in zip(q,cells):
                        h=headers.get(cell.get('column_index'),{})
                        if re.search(r'disadvantages?|limitations?|restrictions?',display(h.get('text','')),re.I):item['role']='source_limitation'
                    emit([native[c['cell_id']]],'table_method' if role=='method' else 'table_cell',c['cell_id'],q,role=role,row=row.get('row_id'))
    # Body: recognized tables are excluded so their row text is not rejoined
    # into a competing whole-page action. Unknown tables remain diagnosable.
    views,_=native_views({**page,'tables':tables})
    for vi,view in enumerate(v for v in views if v['kind']=='blocks'):
        run=[];scope=[]
        def flush():
            if not run:return
            text,addr=joined(run);vv,mp=normalized_view(text)
            for a,b in sentence_ranges(vv):
                if a==b:continue
                ws=witnesses(text,addr,mp[a],mp[b] if b<len(mp) else len(text),native)
                segment=[]
                for w in ws:
                    # Subspan origin is preserved via the full unit plus a
                    # real native slice; emit's addresses are remapped below.
                    segment.append(w)
                # Emit on the original run, then restrict using real offsets
                # via a native view sliced with source offset metadata.
                sliced=[]
                for w in segment:
                    u=copy.deepcopy(native[w['unit_id']]);u['_slice_start']=w['start'];u['text']=w['text'];sliced.append(u)
                before=len(fragments);ui=len(units)
                emit(sliced,'prose',f'column:{vi}:sentence:{len(units)}',scope)
                starts={u['native_id']:u['_slice_start'] for u in sliced}
                for obj in [*units[ui:],*fragments[before:]]:
                    for w in obj['source_spans']:w['start']+=starts[w['unit_id']];w['end']+=starts[w['unit_id']]
                    # witnesses initially read unsliced native text; replace
                    # by its actual addressed source for an exact round trip.
                    for w in obj['source_spans']:w['text']=native[w['unit_id']]['text'][w['start']:w['end']]
            run.clear()
        for block in view['units']:
            s=display(block['text'])
            if re.match(r'^\s*\d+(?:\.\d+)*\s+[A-Z][A-Za-z /-]{2,80}$',s) or (s.isupper() and 2<len(s)<100):
                flush()
                w=dict(unit_id=block['block_id'],start=0,end=len(block['text']),text=block['text'],bbox=copy.deepcopy(block.get('bbox')),doc_id=page['doc_id'],pdf_page_number=page['pdf_page_number'])
                scope=[dict(role='source_heading',text=block['text'],source_spans=[w])];headings+=scope
                continue
            if run and block['bbox']['top']-run[-1]['bbox']['bottom']>35:flush()
            if re.match(r'^\s*(?:\d{1,2}[.)]|[a-z][.)])\s+',s):flush()
            run.append(native[block['block_id']])
            if s.rstrip().endswith(('.', '!', '?')):flush()
        flush()
    # Repair all fragment surface strings to the exact witnessed bytes. The
    # display form is explicitly separate and can dehyphenate/reduce overprint.
    for f in fragments:
        f['text']='\n'.join(w['text'] for w in f['source_spans'])
    result=dict(version=VERSION,doc_id=page['doc_id'],page=page['pdf_page_number'],page_text_sha256=page['page_text_sha256'],units=units,fragments=fragments,issues=issues,headings=headings,claim='source-addressed fragment hypotheses, not complete or correct entities')
    result['pool_sha256']=digest(result)
    return result
