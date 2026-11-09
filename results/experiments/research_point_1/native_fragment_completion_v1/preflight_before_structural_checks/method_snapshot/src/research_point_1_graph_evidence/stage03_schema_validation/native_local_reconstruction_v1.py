"""Finite experimental reconstruction over an immutable common candidate pool.

No labels, reference answers, candidate/document-ID branching, IO or model use.
The local proof is an executable hypothesis, never semantic certification.
"""
import copy
import re

from . import automatic_contract_v4_1 as context
from . import clause_binding_v1 as clause
from . import layout_direction_context_v1 as layout
from .batch_evidence_repair_v1 import repair as batch_repair
from .relation_type_validator import normalize_relation_direction
from ..stage02_triple_extraction.native_fragment_completion_v1 import display,digest,type_hints,PHYSICAL


FIELDS=('head_surface','head_type','relation','tail_surface','tail_type','conditions','modality','polarity','scope','applicability','evidence_text','evidence_unit_ids')


def legal(a,registry):
    r=registry.get(a.get('relation'),{})
    return a.get('head_type') in r.get('domain',[]) and a.get('tail_type') in r.get('range',[])


def normalize(a):
    a=copy.deepcopy(a)
    n=normalize_relation_direction(head=a['head_surface'],head_type=a['head_type'],relation=a['relation'],tail=a['tail_surface'],tail_type=a['tail_type'])
    if n.head==a['tail_surface'] and n.tail==a['head_surface'] and n.head!=n.tail:
        for suffix in ['canonical_zh']:
            a['head_'+suffix],a['tail_'+suffix]=a.get('tail_'+suffix),a.get('head_'+suffix)
    a.update(head_surface=n.head,head_type=n.head_type,relation=n.relation,tail_surface=n.tail,tail_type=n.tail_type)
    return a,list(n.actions)


def legacy_rules(assertion,page,registry,screen):
    """The same complete declared chain in all arms; no old outputs replaced."""
    a,events=normalize(assertion)
    ctx=context.transform(a,page,registry,screen,'roles')
    result=clause.refine(a,page,ctx,screen,'repair')
    result=layout.refine(a,page,result,registry,screen,'C')
    payload=result['payload']
    metadata={k:page[k] for k in ['doc_id','pdf_page_number','page_text_sha256','document_sha256']}
    proposal,reason=batch_repair({**payload,**metadata,'rejection_reasons':assertion.get('rejection_reasons',[])},page,registry)
    # Preserve every field selected by the legacy rule and its native context.
    if proposal:
        payload={k:proposal['payload'][k] for k in FIELDS}
        flags=screen(payload,page)
        result.update(payload=payload,screen_flags=flags,included=not flags and not result.get('barriers'))
        result['batch_native_proof']=proposal
    result['normalizer_actions']=events;result['batch_reason']=reason
    return result


def semantic_key(a):
    return digest({k:a.get(k) for k in FIELDS if k not in {'evidence_text','evidence_unit_ids'}})


def make_pool(originals,catalog,page,registry):
    """B1 and B2 receive byte-identical outputs of this function.

    Candidate generation has no access to grades, references, arms or selectors.
    Source structural proposal and acceptance are deliberately separate.
    """
    fs={f['id']:f for f in catalog['fragments']};units={u['id']:u for u in catalog['units']}
    pool=[];seen=set()
    def add(a,origin,proof=None,parent_ids=()):
        # Repeated model outputs remain separate occurrences in the raw
        # denominator. Only identical source-generated hypotheses deduplicate.
        key=digest([a,origin,proof,list(parent_ids)])
        if key in seen:return
        seen.add(key)
        pool.append(dict(id='C'+key[:22],payload=copy.deepcopy(a),origin=origin,proof=copy.deepcopy(proof),parent_ids=list(parent_ids)))
    for r in originals:add(r['payload'],'cached',parent_ids=[r['candidate_id']])

    def qualifiers(u):
        q=[x['text'] for x in u['qualifiers'] if x.get('role') in {'source_heading','row_condition','source_limitation'}]
        for fid in u['fragment_ids']:
            if fs[fid]['kind']=='condition':q.append(fs[fid]['text'])
        return list(dict.fromkeys(q))

    def propose(h,ht,rel,t,tt,u,kind,extra=()):
        ws=[*h['source_spans'],*t['source_spans'],*u['source_spans']]
        evidence='\n'.join(w['text'] for w in u['source_spans'])
        negative=bool(re.search(r'\b(never|do not|must not)\b',display(t['text']),re.I))
        mode='possible' if rel=='causes' and re.search(r'\b(may|can|could|might)\b',u['display_text'],re.I) else 'required' if re.search(r'\b(must|shall)\b',u['display_text'],re.I) else 'recommended' if re.search(r'\b(should|recommended)\b',u['display_text'],re.I) else 'asserted'
        a=dict(head_surface=h['text'],head_type=ht,relation=rel,tail_surface=t['text'],tail_type=tt,conditions=list(dict.fromkeys([*qualifiers(u),*extra])),modality=mode,polarity='negative' if negative else 'positive',scope='primary',applicability=page.get('applicability_scope') or page.get('title') or '',evidence_text=evidence,evidence_unit_ids=[w['unit_id'] for w in u['source_spans'] if ':t' in w['unit_id']])
        if not legal(a,registry):return
        proof=dict(kind=kind,unit_id=u['id'],head_id=h['id'],tail_id=t['id'],source_spans=ws,qualifiers=copy.deepcopy(u['qualifiers']),semantic_support_unverified=True)
        add(a,'native_structural_proposal',proof)

    # Maintenance matrices: preserve the exact header and full row qualifiers.
    for u in units.values():
        if u['kind']!='table_action':continue
        headers=[q for q in u['qualifiers'] if q['role']=='component_header']
        if len(headers)!=1:continue
        hq=headers[0];heads=[f for f in fs.values() if f['role']=='component' and f['kind']=='entity' and f['source_spans']==hq['source_spans']]
        heads=[h for h in heads if display(h['text'])==display(hq['text'])]
        for h in heads:
            for fid in u['fragment_ids']:
                t=fs[fid]
                if t['kind']!='action':continue
                tt=t['type_hints'][0]
                ht='Equipment' if 'Equipment' in h['type_hints'] else 'Component'
                propose(h,ht,'inspected_by' if tt=='InspectionAction' else 'maintained_by',t,tt,u,'maintenance_column')

    # Monitoring methods stay within their native row, with ALL other columns
    # available as qualifiers (including limitations); no pump transfer implied.
    for u in units.values():
        if u['kind']!='table_method':continue
        method=[fs[f] for f in u['fragment_ids'] if fs[f]['kind']=='method']
        if len(method)!=1:continue
        for target_u in units.values():
            if target_u['row']!=u['row'] or target_u['role']!='target':continue
            targets=[fs[f] for f in target_u['fragment_ids'] if fs[f]['kind']=='entity' and 'FaultMode' in fs[f]['type_hints']]
            # Prefer a complete longer phrase over its own contained noun.
            targets=[f for f in targets if not any(f is not g and display(f['text']).lower() in display(g['text']).lower() for g in targets)]
            for h in targets:propose(h,'FaultMode','diagnosed_by',method[0],'InspectionMethod',target_u,'monitoring_row',extra=[q['text'] for q in u['qualifiers'] if q['role']=='source_limitation'])

    for u in units.values():
        if u['kind']!='prose':continue
        text=u['display_text'];entities=[fs[f] for f in u['fragment_ids'] if fs[f]['kind']=='entity']
        for fid in u['fragment_ids']:
            action=fs[fid]
            if action['kind']!='action':continue
            ad=display(action['text'])
            # The explicit direct object after a bounded verb is required.
            m=re.search(r'\b(check|inspect|examine|measure|verify|clean|replace|renew|lubricate|tighten|remove|fit|install|allow)\b\s+(?:that\s+)?(?:the\s+|a\s+|an\s+)?(.+?)(?=\s+(?:is|are|with|using|to|for|from|in|on|at|until|if|when|and|or)\b|[,.;]|$)',ad,re.I)
            if not m:continue
            obj=m.group(2).strip();choices=[f for f in entities if re.fullmatch(r'\b'+re.escape(display(f['text']))+r'\b',obj,re.I) and any(t in {'Equipment','Component'} for t in f['type_hints'])]
            if len(choices)!=1:continue
            h=choices[0];ht='Equipment' if 'Equipment' in h['type_hints'] else 'Component'
            tt=action['type_hints'][0];rel='inspected_by' if tt=='InspectionAction' else 'maintained_by'
            # Startup/install alone is not automatically a maintenance action.
            if m.group(1).lower() in {'install','fit','remove'} and not any(re.search(r'maintenance|repair|assembly|disassembly',display(q['text']),re.I) for q in u['qualifiers']):continue
            propose(h,ht,rel,action,tt,u,'explicit_action_object')
        # Atomic explicit causation only; multiple cues are left unresolved to
        # avoid collapsing a chain. The complete sentence remains attached.
        cues=list(re.finditer(r'\b(?:causes?|causing|results? in|leads? to)\b',text,re.I))
        if len(cues)!=1 or re.search(r'\b(?:not|never|no)\b',text[:cues[0].end()],re.I):continue
        cue=cues[0];left=text[:cue.start()].lower();right=text[cue.end():].lower()
        hs=[f for f in entities if display(f['text']).lower() in left and any(t in {'FaultMode','OperatingCondition'} for t in f['type_hints'])]
        ts=[f for f in entities if display(f['text']).lower() in right and 'FaultMode' in f['type_hints']]
        hs=[f for f in hs if not any(f is not g and display(f['text']).lower() in display(g['text']).lower() for g in hs)]
        ts=[f for f in ts if not any(f is not g and display(f['text']).lower() in display(g['text']).lower() for g in ts)]
        if len(hs)==len(ts)==1:
            ht='OperatingCondition' if 'OperatingCondition' in hs[0]['type_hints'] else 'FaultMode'
            propose(hs[0],ht,'causes',ts[0],'FaultMode',u,'explicit_single_cause')
    return pool


def local_select(candidate,legacy,registry):
    """No learned scores: require one structurally addressed local proof.

    Cached candidates keep the identical legacy decision. New candidates with
    ambiguous structure are never rescued. The new rule only rescues a native
    path rejected because a contiguous quotation could not be bound.
    """
    if candidate['origin']=='cached':return bool(legacy['included']),'same_legacy_decision'
    proof=candidate.get('proof');a=candidate['payload']
    if not proof or not legal(a,registry):return False,'no_unique_local_proof'
    if a['polarity']=='negative':return False,'negative_requirement_not_resolved'
    if any(q.get('role')=='unresolved' for q in proof['qualifiers']):return False,'ambiguous_structure'
    if legacy['included']:return True,'legacy_plus_local_proof'
    flags=set(legacy.get('screen_flags',[]))|set(legacy.get('barriers',[]))
    if flags and flags<={'unbound_quote','unbound_source_quote','no_same_column_or_native_cell_binding'}:
        return True,'native_multi_span_binding_rescued'
    return False,'legacy_barriers_preserved'
