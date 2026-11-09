"""Finite source-grammar transducer; pure runtime, no datasets, labels or file IO.

Rules are development hypotheses. A passed screen is not semantic certification.
Source IDs are opaque addresses only; document/page/candidate identifiers are not
used to choose an operation. English grammar coverage is deliberately bounded.
"""
import copy
import re


def flat(text):
    return ' '.join(text.split())


def norm(text):
    return re.sub(r'[^\w]+', ' ', flat(text).lower()).strip()


def spans(text, quote):
    if not quote.strip(): return []
    pos=[i for i,c in enumerate(text) if not c.isspace()]
    whole=''.join(text[i] for i in pos);needle=''.join(quote.split())
    result=[];offset=0
    while True:
        k=whole.find(needle,offset)
        if k<0:break
        start,end=pos[k],pos[k+len(needle)-1]+1
        result.append({'kind':'page_span','start':start,'end':end,'text':text[start:end]})
        offset=k+len(needle)
    return result


def cells(page):
    return [c for t in page.get('tables',[]) for row in t['rows'] for c in row['cells']]


def cell_witness(c):
    return {'kind':'native_cell_subspan','cell_id':c['cell_id'],'row_id':c['row_id'],
            'column_index':c['column_index'],'start':0,'end':len(c['text']),
            'text':c['text'],'bbox':copy.deepcopy(c.get('bbox'))}


def bindings(page,quote):
    result=spans(page['page_text'],quote)
    for c in cells(page):
        for w in spans(c['text'],quote):
            result.append({**w,'kind':'native_cell_subspan','cell_id':c['cell_id'],
                           'row_id':c['row_id'],'column_index':c['column_index'],'bbox':copy.deepcopy(c.get('bbox'))})
    return result


def source_sentence(text, start):
    """A sentence boundary outside parentheses; internal abbreviation dots survive."""
    depth=0
    for i in range(start,len(text)):
        if text[i]=='(':depth+=1
        elif text[i]==')':depth=max(0,depth-1)
        elif text[i] in '.!?' and depth==0 and (i+1==len(text) or text[i+1].isspace()):
            return text[start:i+1]
    return text[start:]


def numbered_steps(text):
    hs=list(re.finditer(r'(?m)^\s*(\d+(?:\.\d+)+)\s+((?:Assembly|Disassembly)\b[^\n]*)',text))
    items=[]
    for i,h in enumerate(hs):
        end=hs[i+1].start() if i+1<len(hs) else len(text)
        chunk=text[h.end():end]
        # Only explicit numbered imperative paragraphs are supported.
        ms=list(re.finditer(r'(?m)^\s*(\d{1,2})\s+(?=(?:Place|For|Push|Put|Remove|Bearing|Disassemble|Pull|Slide|Degrease|Tap|Loosen|Clean|Fit|Tighten)\b)',chunk))
        for j,m in enumerate(ms):
            start=h.end()+m.end();stop=h.end()+(ms[j+1].start() if j+1<len(ms) else len(chunk))
            body=text[start:stop]
            # Page footer begins after a blank line, a common bounded manual layout.
            tail=re.search(r'\n\s*\n',body)
            if tail:stop=start+tail.start();body=body[:tail.start()]
            body=body.strip()
            # Source may not have a blank line before a publisher/page footer.
            footer=re.search(r'\n\s*[A-Z]{2,}/[A-Z]{2,}\s*\(',body)
            if footer:body=body[:footer.start()].strip();stop=start+footer.start()
            items.append({'section':h.group(1),'heading':flat(h.group()),'heading_start':h.start(),
                          'section_end':end,'ordinal':int(m.group(1)),'start':start,'end':stop,'body':body})
    return items


def part_name_conflict(page,assertion):
    # A finite incompatible-noun family, not a general entity identity resolver.
    names={}
    for noun,number in re.findall(r'\b(?:impeller\s+)?(nut|key)\s*\((\d+)\)',flat(page['page_text']),re.I):
        names.setdefault(number,set()).add(noun.lower())
    used=set(re.findall(r'\((\d+)\)',assertion['head_surface']+' '+assertion['tail_surface']))
    return sorted(n for n in used if names.get(n)=={'nut','key'})


def transform(assertion,page,schema,screen,mode='roles'):
    if mode not in {'context','roles'}:raise ValueError(mode)
    allowed=('head_surface','head_type','relation','tail_surface','tail_type','conditions','modality','polarity','scope','applicability','evidence_text','evidence_unit_ids')
    raw={k:copy.deepcopy(assertion[k]) for k in allowed}
    a=copy.deepcopy(raw);events=[];witnesses=[];barriers=[]
    def proof(quote):
        found=bindings(page,quote)
        if not found:return False
        w=found[0]
        if w not in witnesses:witnesses.append(w)
        return True
    def emit(rule,reason,**changes):
        delta={k:{'before':copy.deepcopy(a.get(k)),'after':copy.deepcopy(v)} for k,v in changes.items() if a.get(k)!=v}
        a.update(copy.deepcopy(changes));events.append({'rule':rule,'reason':reason,'changes':delta})
    def conditions(*values):
        out=list(a['conditions'])
        for v in values:
            if v and v not in out:out.append(v)
        return out
    def sidecar(kind,**fields):
        emit('SIDE','source requirement/function is preserved outside positive diagnostic edges',record_kind=kind,statement_source=raw['evidence_text'],**fields)
    quote=flat(a['evidence_text']);q=norm(quote);h=norm(a['head_surface']);t=norm(a['tail_surface'])
    initial=bindings(page,a['evidence_text'])
    if not initial and mode=='roles' and a['relation']=='inspected_by':
        # Recover only an exact, unique literal check clause already present in the candidate.
        clause=re.sub(r'^check that\s+','',flat(a['tail_surface']),flags=re.I)
        hits=spans(page['page_text'],clause)
        if len(hits)==1 and len(clause.split())>=5:
            initial=hits
            emit('QUOTE_CHECK','unique declarative check clause bound separately; no disjoint quote concatenation',evidence_text=hits[0]['text'])
    if not initial:barriers.append('unbound_source_quote')
    else:witnesses.append(initial[0])
    native={c['cell_id']:c for c in cells(page)}
    if any(cid not in native for cid in a['evidence_unit_ids']):barriers.append('unknown_native_unit')
    if part_name_conflict(page,a):barriers.append('incompatible_source_part_names')
    text=page['page_text'];source=flat(text)
    position=next((w['start'] for w in initial if w['kind']=='page_span'),None)

    # Hierarchical source context for explicit maintenance programs.
    programs=numbered_steps(text)
    source_sections={s['section'] for w in initial if w['kind']=='page_span' for s in programs if s['start']<=w['start']<s['end']}
    if len(source_sections)>1:barriers.append('nonunique_source_section')
    matched=[s for s in programs if position is not None and s['start']<=position<s['end']]
    if len(matched)==1 and not barriers:
        s=matched[0]
        if proof(s['body']) and proof(s['heading']):
            cs=conditions(s['heading'],f"source procedure step {s['ordinal']}; retain previous applicable steps and order; not a complete procedure")
            pre=text[s['heading_start']:s['start']]
            for m in re.finditer(r'After\s+[^.]+\.',flat(pre)):
                if proof(m.group()):cs.append(m.group())
            emit('PROGRAM_CONTEXT','numbered source step supplies action and its bounded section/sequence',
                 relation='maintained_by',tail_type='MaintenanceAction',tail_surface=flat(s['body']),conditions=cs,
                 applicability=page.get('applicability_scope','')+'; '+page.get('title','')+'; '+s['heading'],
                 procedure_step={'section':s['section'],'ordinal':s['ordinal'],'complete_procedure':False})

    # Native table row and header semantics; never infer columns from flattened row order.
    for table in page.get('tables',[]):
        if not table['rows']:continue
        header=table['rows'][0]['cells'];by_col={c['column_index']:norm(c['text']) for c in header}
        if not any('defect' in v or 'failure' in v for v in by_col.values()):continue
        if not any('appearance' in v for v in by_col.values()) or not any('cause' in v for v in by_col.values()):continue
        refcells=[native[c] for c in a['evidence_unit_ids'] if c in native and native[c].get('row_index',0)>0]
        rowids={c['row_id'] for c in refcells}
        global_rule=a['relation']=='mitigated_by' and 'defect' in h and re.search(r'replace.*found',q)
        if len(rowids)>1:barriers.append('multiple_native_data_rows');continue
        if rowids and not any(spans(c['text'],a['evidence_text']) for c in refcells):
            barriers.append('quote_not_bound_to_declared_native_row');continue
        if not rowids and not global_rule:continue
        if re.search(r'\bpump\b',page.get('title',''),re.I) and 'pump' in page.get('pump_type','').lower():
            for c in header:
                if cell_witness(c) not in witnesses:witnesses.append(cell_witness(c))
            emit('TABLE_SCOPE','pump-document metadata plus native fault-table context; no ship-specific factual claim',
                 scope='primary',applicability='; '.join(page.get(k,'') for k in ['title','pump_type','service','applicability_scope']))
        if a['relation']=='manifests_as' and any('appearance' in by_col.get(c['column_index'],'') for c in refcells):
            emit('TABLE_MODAL','cause-column probability does not qualify appearance-column descriptions',modality='descriptive')
        if a['relation']=='causes' and any('probable cause' in by_col.get(c['column_index'],'') for c in refcells):
            emit('TABLE_MODAL','cause edge retains probability from its own column header',modality='probable')
        exceptions=[]
        for row in table['rows'][1:]:
            for c in row['cells']:
                if re.search(r'not a reason for (?:discard|replacement)',flat(c['text']),re.I):
                    sentences=re.findall(r'\([^)]*not a reason for (?:discard|replacement)[^)]*\)',flat(c['text']),re.I)
                    for e in sentences:
                        proof(e);exceptions.append(e)
        if global_rule and exceptions:
            emit('TABLE_EXCEPTION','global replacement rule retains native-table negative exceptions; no row fan-out',conditions=conditions('bearing defect found',*exceptions))
        break

    # Source-defined requirement channels. No new positive KG relation is introduced.
    if a['relation']=='maintained_by' and re.search(r'\brequires? no maintenance\b',quote,re.I):
        sidecar('maintenance_requirement',requirement='not_required',action='maintenance',modality='not_required')
    elif a['relation']=='maintained_by' and 'lubricat' in q and re.search(r'by the liquid|by liquid',quote,re.I):
        sidecar('operating_mechanism')
    elif a['relation']=='maintained_by' and re.search(r'see paragraph',a['tail_surface'],re.I) and not re.search(r'\b(?:remove|fit|mount|tighten|loosen)\b',a['tail_surface'],re.I):
        sidecar('cross_reference')
    elif a['relation']=='maintained_by' and re.search(r'(?:opened|open).*after.*(?:start|started)',quote,re.I):
        sidecar('operating_procedure')
    elif a['relation']=='maintained_by' and re.search(r'earthing|provided with.*protector',quote,re.I):
        sidecar('electrical_requirement')

    # Paragraph-local maintenance safety scope and explicit conditional subject bindings.
    maintenance=list(re.finditer(r'(?m)^\s*\d+(?:\.\d+)*\.?\s+MAINTENANCE\s*$',text))
    in_maintenance=bool(maintenance and position is not None and position>maintenance[-1].end())
    if in_maintenance and a['relation'] in {'maintained_by','prevented_by','mitigated_by'} and not a.get('record_kind'):
        shut=re.search(r'Before maintenance,\s*confirm that [^.]+\.',source,re.I)
        if shut and proof(shut.group()):emit('MAINTENANCE_PRECONDITION','maintenance chapter safety prerequisite',conditions=conditions(shut.group()))
        if re.search(r'\blubricat',a['tail_surface'],re.I):
            motor=re.search(r'The motor with a nozzle\s*\([^)]*\)',source,re.I)
            if motor and proof(motor.group()):emit('LOCAL_COMPONENT_SCOPE','lubrication paragraph specifies the nozzle-equipped motor',conditions=conditions(motor.group()))
    # Repeated condition already in the subject can be made explicit without importing other clauses.
    for m in re.finditer(r'\b(If|In case of)\s+([^,]+),',quote,re.I):
        cond=m.group(2)
        if 'or not' in norm(cond) or re.search(r'check\s*$',quote[:m.start()],re.I):continue
        cn=re.sub(r'\b(?:the|is|are)\b','',norm(cond));cn=flat(cn)
        hn=re.sub(r'\b(?:the|is|are)\b','',norm(raw['head_surface']));hn=flat(hn)
        if (len(cn.split())>=2 and (cn in hn or hn in cn)) and proof(m.group()):
            emit('LOCAL_CONDITION','source antecedent matches current subject; unrelated following warnings are not inherited',conditions=conditions(m.group().rstrip(',')))

    if mode=='roles' and not barriers and not a.get('record_kind'):
        qtext=flat(a['evidence_text'])
        # Bounded inspection grammar. Methods with ambiguous control/current binding remain unresolved.
        if a['relation'] in {'inspected_by','diagnosed_by'}:
            if re.search(r'current.*via the pressure switch',qtext,re.I):
                barriers.append('ambiguous_control_measurement_binding')
            else:
                options=[]
                markers=[r'check working pressure',r'shaft rotates freely without jarring sounds',r'pump casing is filled with liquid',r'check the direction of rotation']
                if sum(bool(re.search(x,qtext,re.I)) for x in markers)>1:barriers.append('nonunique_inspection_object')
                def option(head,ht,tail,relation,condition_quotes=()):
                    if all(proof(x) for x in condition_quotes):options.append((head,ht,tail,relation,condition_quotes))
                if re.search(r'check working pressure if a pressure meter is installed',qtext,re.I):
                    option('working pressure','SignalFeature','check working pressure using an installed pressure meter','diagnosed_by',('if a pressure meter is installed',))
                elif re.search(r'shaft rotates freely without jarring sounds',qtext,re.I):
                    option('shaft','Component','check that the shaft rotates freely without jarring sounds','inspected_by')
                elif re.search(r'pump casing is filled with liquid',qtext,re.I):
                    option('pump casing','Component','check that the pump casing is filled with liquid','inspected_by')
                elif re.search(r'check the direction of rotation',qtext,re.I):
                    mc=re.search(r'If the direction is correct',source,re.I)
                    if mc:option('pump','Equipment','start briefly to check the direction of rotation','inspected_by',(source_sentence(source,mc.start()),))
                else:
                    m=re.search(r'(?:Check if|If)\s+(?:the )?(.+?)\s+(?:are|is)\s+(.+?)(?:\.|$)',qtext,re.I)
                    if m:
                        target,state=m.groups();target=target.strip();state=state.strip()
                        if norm(target)=='rotating direction' and re.search(r'CHECK BEFORE PUMP STARTUP',source,re.I):target='pump'
                        # Explicit object types only; do not treat a measured quantity as a component.
                        if re.search(r'bolt|valve|pipes?|pump',target,re.I):
                            ht='Equipment' if target.lower()=='pump' else 'Component'
                            option(target,ht,'check '+m.group().rstrip('.'),'inspected_by')
                if len(options)==1:
                    oh,ht,ot,rel,cs=options[0]
                    extras=list(cs)
                    if re.search(r'CHECK BEFORE PUMP STARTUP',source,re.I):
                        hh=re.search(r'\d+(?:\.\d+)*\s+CHECK BEFORE PUMP STARTUP',source,re.I)
                        if hh and proof(hh.group()):extras.append(hh.group())
                    elif 'Before starting the pump check that' in source:
                        proof('Before starting the pump check that');extras.append('Before starting the pump check that')
                    emit('INSPECTION_ROLE','source grammar identifies inspected object, not instrument/action label',head_surface=oh,head_type=ht,tail_surface=ot,tail_type='InspectionAction',relation=rel,conditions=conditions(*extras))
                elif len(options)>1:barriers.append('nonunique_inspection_object')
        # Purpose of a source procedure is not an adverse event to be prevented.
        if a['relation']=='prevented_by':
            m=re.search(r'(?:When it is necessary to replace|If you want to install) the ([^,]+),\s*(.+)',qtext,re.I)
            if m:
                obj,action=m.groups()
                emit('PROCEDURE_ROLE','source replacement/installation purpose becomes maintained object, ordered action retained',
                     head_surface=obj,head_type='Component',relation='maintained_by',tail_surface=action,tail_type='MaintenanceAction',
                     conditions=conditions(qtext.split(',',1)[0]),procedure_sequence_preserved=True)
            elif re.search(r'When using .* once again',qtext,re.I):
                sidecar('operating_procedure')
        if a['relation']=='mitigated_by' and a['head_type'] in {'Equipment','OperatingCondition'} and re.search(r'you should drain the liquid',qtext,re.I):
            m=re.search(r'If (.+?), you should (drain[^.]+)\.',qtext,re.I)
            if m:
                emit('DRAIN_ROLE','conditional draining is an equipment maintenance action',head_surface='pump',head_type='Equipment',relation='maintained_by',tail_surface=m.group(2),tail_type='MaintenanceAction',conditions=conditions('If '+m.group(1)))
        if a['relation']=='inspected_by' and re.search(r'liquid.*drained via',qtext,re.I) and not re.search(r'\bcheck|\binspect',qtext,re.I):
            sidecar('maintenance_procedure_location')

    if a.get('record_kind'):
        flags=[]
    else:flags=list(screen(a,page))
    accepted=not barriers and not flags
    return {'payload':a,'included':accepted,'rules':events,'source_witnesses':witnesses,
            'barriers':barriers,'screen_flags':flags,
            'changes':{k:{'before':raw.get(k),'after':a.get(k)} for k in set(raw)|set(a) if raw.get(k)!=a.get(k)},
            'semantic_certification':False}
