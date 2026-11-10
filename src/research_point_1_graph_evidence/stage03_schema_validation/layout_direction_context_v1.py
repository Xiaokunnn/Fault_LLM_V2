"""Pure bounded refinement on native geometry. No labels, files, or API calls.

Original text and candidate quotes are immutable. A layout match yields a list
of actual block/cell subspans, never a synthetic contiguous page offset.
"""
import copy
import re
if __package__:
    from .native_evidence_binding_v2 import screen_with_native_binding
else:  # Historical experiment scripts also load this pure module by file path.
    from research_point_1_graph_evidence.stage03_schema_validation.native_evidence_binding_v2 import screen_with_native_binding


def flat(s):
    return ' '.join(s.split())


def norm(s):
    return re.sub(r'[^\w]+', ' ', s.lower()).strip()


def contained(small, large):
    a, b = norm(small), norm(large)
    return bool(a) and (' '+a+' ') in (' '+b+' ')


def valid(a, schema):
    r = schema.get(a.get('relation'), {})
    return a.get('head_type') in r.get('domain', []) and a.get('tail_type') in r.get('range', [])


def native_views(page):
    """Split genuine long-text columns, without sorting source text in place."""
    cells = [c for t in page.get('tables', []) for r in t['rows'] for c in r['cells']]
    views = [dict(kind='cell', units=[c], text=c['text']) for c in cells if c['text'].strip()]
    boxes = [t.get('bbox') for t in page.get('tables', []) if t.get('bbox')]
    def inside(b, box):
        return b['x0'] >= box['x0']-1 and b['x1'] <= box['x1']+1 and b['top'] >= box['top']-1 and b['bottom'] <= box['bottom']+1
    blocks = [b for b in page.get('text_blocks', []) if b.get('bbox') and b['text'].strip()
              and not any(inside(b['bbox'], box) for box in boxes)]
    width = page.get('page_width', 0)
    long = [b for b in blocks if len(b['text'].split()) >= 5]
    candidates = []
    for fraction in [.40, .45, .50, .55, .60]:
        cut = width*fraction
        left = [b for b in long if b['bbox']['x1'] < cut-3]
        right = [b for b in long if b['bbox']['x0'] > cut+3]
        cross = len(long)-len(left)-len(right)
        overlap = sum(any(abs(l['bbox']['top']-r['bbox']['top']) < 15 for r in right) for l in left)
        if min(len(left), len(right)) >= 3 and overlap >= 3 and cross <= .20*max(1,len(long)):
            candidates.append((overlap-cross, -abs(fraction-.5), cut))
    cut = max(candidates)[2] if candidates else None
    if cut is None:
        groups = [blocks]
    else:
        # Spanning headers/footers are separate; never join end of left column
        # with top of right column or attach a wide warning to both implicitly.
        groups = [[b for b in blocks if b['bbox']['x1'] < cut-3],
                  [b for b in blocks if b['bbox']['x0'] > cut+3]]
        groups += [[b] for b in blocks if b['bbox']['x1'] >= cut-3 and b['bbox']['x0'] <= cut+3]
    for group in groups:
        ordered = sorted(group, key=lambda b:(b['bbox']['top'],b['bbox']['x0']))
        if ordered:
            views.append(dict(kind='blocks', units=ordered, text='\n'.join(b['text'] for b in ordered)))
    return views, dict(two_columns=cut is not None, split_x=cut, text_units=len(blocks), native_cells=len(cells))


def locate(page, quote, declared=()):
    views, geometry = native_views(page)
    needle = ''.join(quote.split())
    if not needle:
        return [], geometry
    hits = []
    for view in views:
        chars, addresses = [], []
        for ui, unit in enumerate(view['units']):
            if ui and view['kind']=='blocks':
                previous=view['units'][ui-1]['bbox']; current=unit['bbox']
                if current['top']-previous['bottom'] > max(30,3*(previous['bottom']-previous['top'])):
                    chars.append('\x00');addresses.append((-1,-1))
            for ci, ch in enumerate(unit['text']):
                if not ch.isspace():
                    chars.append(ch); addresses.append((ui,ci))
        text = ''.join(chars); offset = 0
        while True:
            at = text.find(needle,offset)
            if at < 0: break
            selected = addresses[at:at+len(needle)]; witnesses=[]
            for ui in sorted({p[0] for p in selected}):
                u=view['units'][ui];positions=[p[1] for p in selected if p[0]==ui]
                start,end=min(positions),max(positions)+1
                kind='native_cell_subspan' if view['kind']=='cell' else 'native_block_subspan'
                key='cell_id' if view['kind']=='cell' else 'block_id'
                witnesses.append(dict(kind=kind, **{key:u[key]}, start=start,end=end,
                    text=u['text'][start:end],bbox=copy.deepcopy(u.get('bbox'))))
            # Bounds into a derived view are explicitly not source-page offsets.
            first=selected[0][0];last=selected[-1][0]
            hits.append(dict(witnesses=witnesses,unit_start=first,unit_end=last,
                context_units=copy.deepcopy(view['units'][max(0,first-3):last+4]),
                context_kind=view['kind']))
            offset=at+len(needle)
    if declared:
        anchored=[h for h in hits if any(w.get('cell_id') in declared for w in h['witnesses'])]
        if anchored:hits=anchored
    # A duplicate table/prose representation of the same exact quotation is
    # addressed by the explicitly declared cell; otherwise ambiguity remains.
    return hits,geometry


def unique_flip(a, quote, schema):
    if valid(a,schema) or a.get('polarity') != 'positive': return None
    b=copy.deepcopy(a)
    for suffix in ['surface','type']:
        b['head_'+suffix],b['tail_'+suffix]=a['tail_'+suffix],a['head_'+suffix]
    if not valid(b,schema):return None
    if not all(contained(b[k],quote) for k in ['head_surface','tail_surface']):return None
    rel=b['relation'];q=norm(quote)
    if rel=='inspected_by':
        if not re.search(r'\b(check|inspect|examine|measure|verify)\b',norm(b['tail_surface'])):return None
    elif rel=='maintained_by':
        if not re.search(r'\b(clean|replace|repair|lubricate|adjust|tighten|remove)\b',norm(b['tail_surface'])):return None
        if re.search(r'\b(do not|no maintenance|never)\b',q):return None
    elif rel=='increases_risk_of':
        if not re.search(r'\b(risk|may|avoid|could|danger)\b',q):return None
        b['modality']='possible'
    else:
        return None
    return b


def refine(raw,page,parent,schema,screen,stage='C'):
    if stage not in ['L','D','C']:raise ValueError(stage)
    result=copy.deepcopy(parent);before=copy.deepcopy(result['payload']);a=result['payload']
    hits,geometry=locate(page,a['evidence_text'],a.get('evidence_unit_ids',[]))
    events=[];proof=[];barriers=list(result.get('barriers',[]))
    def emit(rule,reason,**changes):
        delta={k:dict(before=copy.deepcopy(a.get(k)),after=copy.deepcopy(v)) for k,v in changes.items() if a.get(k)!=v}
        if delta:
            a.update(copy.deepcopy(changes));events.append(dict(rule=rule,reason=reason,changes=delta))
    if len(hits)==1:
        proof=hits[0]['witnesses']
        barriers=[b for b in barriers if b!='unbound_source_quote']
    elif geometry['two_columns'] and not hits:
        barriers.append('no_same_column_or_native_cell_binding')
    # Existing unambiguous page-span/table binding may be retained on ordinary
    # layouts. It is never used to invent a new semantic repair when native
    # evidence positions are ambiguous or absent.
    if len(hits)==1 and stage in ['D','C'] and not barriers:
        proposal=unique_flip(a,a['evidence_text'],schema)
        if proposal:
            emit('DIRECTION','unique type-valid inverse plus local lexical roles',**proposal)
    if len(hits)==1 and stage=='C' and not barriers and not a.get('record_kind'):
        q=flat(a['evidence_text'])
        context=' '.join(u['text'] for u in hits[0]['context_units'])
        # Recover the containing sentence only when quote occurs uniquely in
        # the small local context, preserving a complete antecedent as text.
        joined=flat(context)
        if joined.count(q)==1:
            start=joined.index(q);previous=max(joined.rfind('. ',0,start),joined.rfind('! ',0,start))
            stop=joined.find('. ',start+len(q));stop=len(joined) if stop<0 else stop+1
            sentence=joined[previous+2 if previous>=0 else 0:stop]
            antecedent=re.match(r'\s*((?:If|When|Before|After|In case of|During)\b[^,!?]{3,300}),',sentence,re.I)
            if antecedent and not re.search(r'check\s+(?:if|whether)|or not',antecedent.group(),re.I):
                cond=antecedent.group(1).strip()
                if not any(norm(cond)==norm(c) for c in a['conditions']):
                    ws,_=locate(page,cond,a.get('evidence_unit_ids',[]))
                    if len(ws)==1:
                        emit('LOCAL_ANTECEDENT','antecedent of the same source sentence',conditions=a['conditions']+[cond])
                        proof.extend(ws[0]['witnesses'])
        if a['relation'] in {'maintained_by','mitigated_by','prevented_by'} and re.search(r'\balternatively\b',q,re.I):
            if not re.search(r'\balternatively\b',flat(a['tail_surface']+' '+' '.join(a['conditions'])),re.I):
                barriers.append('alternative_action_not_preserved')
        if a['relation'] in {'causes','increases_risk_of','manifests_as'} and a['modality']=='asserted' and re.search(r'\bmay\b',q,re.I):
            emit('LOCAL_MODALITY','source possibility must not become certainty',modality='possible')
    binding=None if a.get('record_kind') else screen_with_native_binding(a,page,screen)
    flags=[] if binding is None else binding['screen_flags']
    result.update(payload=a,barriers=sorted(set(barriers)),screen_flags=flags,
        included=not barriers and not flags,
        layout_binding=dict(geometry=geometry,unique_native_path=len(hits)==1,candidate_paths=len(hits),
                            original_quote_preserved=a['evidence_text']==before['evidence_text']),
        new_rules=events,refinement_stage=stage)
    result['rules']=result.get('rules',[])+events
    if binding is not None:
        result['evidence_binding_contract']=binding
    result['source_witnesses']=result.get('source_witnesses',[])+[w for w in proof if w not in result.get('source_witnesses',[])]
    result['refinement_delta']={k:dict(before=before.get(k),after=a.get(k)) for k in sorted(set(before)|set(a)) if before.get(k)!=a.get(k)}
    return result
