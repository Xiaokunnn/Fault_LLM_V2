"""Sentence/step-local selection and source-bound conditions.

The compiler establishes address, ontology and condition-owner consistency;
it does not establish semantic entailment. Frozen old extraction stays intact.
"""
import copy
import re

from .contextual_extraction import units_of
from .source_fragment_extraction import (
    BUILD_DOCS, ACTION, NOMINAL_RE, SECTION_RE, grammatical_nominals,
    joined, witnesses, sentence_ranges, object_hash, real_table,
)
from research_point_1_graph_evidence.stage03_schema_validation.layout_direction_context_v1 import native_views

STEP = re.compile(r'^\s*(?:\d{1,2}[A-Z]?[.)]?|[a-z][.)])\s+(?=[A-Za-z])')
PHASE = re.compile(r'\b(assembly|assembling|disassembly|disassembling|installation|removal|maintenance|fitting|lubrication)\b', re.I)
ACTION_TYPES = {'MaintenanceAction', 'InspectionAction', 'InspectionMethod'}
PHYSICAL = {'Component', 'Equipment', 'Standard'}
STEP_ACTION = ACTION + r'|fill|rotate|provide|insulate|point|disassemble|requir(?:e|es)|adjustment|inspection|replacement'


def display(text):
    return re.sub(r'(?<=[A-Za-z])-\s*\n\s*(?=[A-Za-z])', '', text)


def header_kind(text, unfinished=False):
    """Inline model lines inside unfinished steps are NOT shared headings."""
    s = text.strip()
    if SECTION_RE.match(s):
        return 'phase' if PHASE.search(s) else 'section'
    if unfinished:
        return None
    if re.match(r'^(?:FOR\b|In\s+\S+\s+combination\s*:)', s, re.I):
        return 'model'
    if re.match(r'^[Øø]\s*\d', s):
        return 'model'
    letters = re.sub('[^A-Za-z]', '', s)
    if len(s) < 160 and letters and letters.isupper() and not s.endswith(('.', ',', ';')):
        return 'phase' if PHASE.search(s) else 'topic'
    return None


def structural_table(table):
    if real_table(table):return True
    names=' '.join(table.get('column_names',[]))
    return len(table.get('column_names',[]))>=3 and bool(re.search(r'Inspect\s*\(I\).*Maintain\s*\(M\)',names,re.I)) and bool(re.search(r'Daily|Weekly|Monthly|running\s+hours',names,re.I))


def prepare_local_catalog(target, context_pages=(), endpoint_dictionary=()):
    if target['doc_id'] not in BUILD_DOCS:
        raise ValueError('not_build_document')
    pages = [*sorted(context_pages, key=lambda p: p['pdf_page_number']), target]
    if any(p['doc_id'] != target['doc_id'] for p in pages):
        raise ValueError('cross_document_context')
    native = units_of(pages)
    units = []; headings = []; represented = set(); geometry = []; duplicates={}

    def emit(run, path, scope, step=False, row=None, target_unit=True):
        if not run:
            return
        text, addresses = joined(run)
        ranges = [(0, len(text))] if step or row else list(sentence_ranges(text))
        for a, b in ranges:
            while a < b and text[a].isspace(): a += 1
            while b > a and text[b-1].isspace(): b -= 1
            if a == b: continue
            ws = witnesses(text, addresses, a, b, native)
            units.append(dict(id=f'u{len(units)+1}', text=text[a:b], source_spans=ws,
                path=path, step=step, row=row, target=target_unit,
                shared_ids=list(scope), choices={}, conditions={}))
            represented.update((w['unit_id'], i) for w in ws for i in range(w['start'], w['end']) if not native[w['unit_id']]['text'][i].isspace())

    prior_scope = []
    for page in pages:
        tables = [t for t in page.get('tables', []) if structural_table(t)]
        views, geo = native_views({**page, 'tables': tables})
        geometry.append(dict(page=page['pdf_page_number'], **geo))
        for vi, view in enumerate(v for v in views if v['kind'] == 'blocks'):
            path = f'{page["pdf_page_number"]}:column:{vi}'
            scope = list(prior_scope) if len([v for v in views if v['kind']=='blocks']) == 1 else []
            run = []; is_step = False
            for block in view['units']:
                u = native[block['block_id']]; s = u['text'].strip()
                unfinished = bool(run and not run[-1]['text'].rstrip().endswith(('.', '!', '?', ':')))
                hk = header_kind(s, unfinished)
                if hk:
                    emit(run, path, scope, is_step, target_unit=page is target); run=[]; is_step=False
                    sid=f's{len(headings)+1}'
                    text, addr=joined([u]); ws=witnesses(text,addr,0,len(text),native)
                    headings.append(dict(id=sid,text=text,kind=hk,source_spans=ws))
                    represented.update((u['native_id'],i) for i,ch in enumerate(text) if not ch.isspace())
                    if hk in ('phase','section'):
                        scope=[sid] if hk=='phase' else []
                    elif hk=='model':
                        scope=[old for old in scope if next(h for h in headings if h['id']==old)['kind']=='phase']+[sid]
                    continue
                newstep=bool(STEP.match(s) and not SECTION_RE.match(s))
                if newstep:
                    emit(run,path,scope,is_step,target_unit=page is target);run=[];is_step=True
                if not is_step and run and run[-1]['text'].rstrip().endswith(('.', '!', '?')):
                    emit(run,path,scope,False,target_unit=page is target);run=[]
                # Footer remains visible but cannot swallow an unfinished step.
                if run and re.search(r'(?:www\.|E-mail:|Tagholm\s+1|FRE/EN\s*\()',s):
                    emit(run,path,scope,is_step,target_unit=page is target);run=[];is_step=False
                run.append(u)
            emit(run,path,scope,is_step,target_unit=page is target)
            if len([v for v in views if v['kind']=='blocks'])==1: prior_scope=list(scope)
        for table in tables:
            header_cells={c.get('column_index',i):c for i,c in enumerate(table['rows'][0]['cells'])} if table['rows'] else {}
            for row in table['rows']:
                cells=[native[c['cell_id']] for c in row['cells'] if c['text'].strip()]
                before=len(units)
                emit(cells,f'{page["pdf_page_number"]}:table:{table["table_id"]}',[],
                    row=f'{table["table_id"]}:{row["row_id"]}',target_unit=page is target)
                for item in units[before:]:
                    item['table_columns']=copy.deepcopy(table.get('column_names',[]))
                    item['table_cells']=[dict(column=c.get('column_index'),text=c['text']) for c in row['cells']]
                    item['interval_headers']=[]
                    for i,c in enumerate(row['cells']):
                        h=header_cells.get(c.get('column_index',i))
                        if h and re.fullmatch('[IM]',c['text'].strip()) and re.search(r'Daily|Weekly|Monthly|hours|months',h['text'],re.I):
                            hn=native[h['cell_id']];ht,ha=joined([hn])
                            item['interval_headers'].append(dict(text=ht,source_spans=witnesses(ht,ha,0,len(ht),native)))
    # All unmatched native characters remain visible; duplicate representations
    # are exposed as source-only units, not silently labelled semantic knowledge.
    for uid, u in native.items():
        missing=[i for i,ch in enumerate(u['text']) if not ch.isspace() and (uid,i) not in represented]
        if missing:
            key=''.join(u['text'].split());box=u.get('bbox')
            same=[]
            for item in units:
                if item.get('source_only') or not key or key not in ''.join(item['text'].split()):continue
                if any(w['pdf_page_number']==u['page'] and box and w['bbox'] and
                    max(box['x0'],w['bbox']['x0'])<min(box['x1'],w['bbox']['x1']) and
                    max(box['top'],w['bbox']['top'])<min(box['bottom'],w['bbox']['bottom']) for w in item['source_spans']):same.append(item['id'])
            if same:
                duplicates[uid]=dict(original_text=u['text'],bbox=copy.deepcopy(box),primary_unit_ids=same,
                    proof='exact nonwhitespace containment plus same-page overlapping native geometry')
                represented.update((uid,i) for i,ch in enumerate(u['text']) if not ch.isspace())
                continue
            before=len(units)
            emit([u],f'{u["page"]}:source-only:{uid}',[],target_unit=u['page']==target['pdf_page_number'])
            for item in units[before:]:item['source_only']=True
    heading_map={h['id']:h for h in headings}
    previous={}
    for unit in units:
        text=unit['text'];ws=unit['source_spans'];joined_text='';addr=[]
        for w in ws:
            if joined_text: joined_text+='\n';addr.append(None)
            joined_text+=w['text'];addr += [(w['unit_id'],i) for i in range(w['start'],w['end'])]
        # Spans refer to actual native substrings, never derived page coordinates.
        text=joined_text
        def choice(a,b,kind,context=False,spans=None):
            cid=str(len(unit['choices'])+1)
            unit['choices'][cid]=dict(id=cid,text=text[a:b] if spans is None else spans['text'],
                kind=kind,context=context,source_spans=witnesses(text,addr,a,b,native) if spans is None else copy.deepcopy(spans['source_spans']),required=[])
            return cid
        matches={(m.start(),m.end()) for m in NOMINAL_RE.finditer(text)}|grammatical_nominals(text)
        for word in endpoint_dictionary:
            pat=r'\s+'.join(re.escape(x) for x in word.split())
            matches|={(m.start(),m.end()) for m in re.finditer(pat,text,re.I)}
        matches={s for s in matches if not any(t!=s and t[0]<=s[0] and s[1]<=t[1] for t in matches)}
        for a,b in sorted(matches):
            if not re.match(r'^(?:'+ACTION+r')\b',text[a:b],re.I): choice(a,b,'entity')
        full=choice(0,len(text),'statement')
        # Full steps stay addressable even with an interleaved note or no known verb.
        actions=[]
        if unit['step'] or unit.get('interval_headers') or re.search(r'\b(?:'+STEP_ACTION+r')(?:s|ed|ing)?\b|\bnot recommended\b|\bno maintenance',text,re.I):
            actions.append(choice(0,len(text),'action'))
        if unit['step']:
            for a,b in sentence_ranges(text):
                if a==0 and b==len(text):continue
                if re.search(r'\b(?:'+STEP_ACTION+r')(?:s|ed|ing)?\b',text[a:b],re.I):actions.append(choice(a,b,'action'))
        def condition(a,b,owners,kind):
            cid=choice(a,b,'condition')
            unit['conditions'][cid]=dict(id=cid,owners=list(owners),kind=kind)
            for eid in owners:unit['choices'][eid]['required'].append(cid)
            return cid
        for h in unit.get('interval_headers',[]):
            cid=choice(0,0,'condition',True,h)
            unit['conditions'][cid]=dict(id=cid,owners=list(actions),kind='table_interval')
            for aid in actions:unit['choices'][aid]['required'].append(cid)
        # Only the matching source sentence owns an if/variant/order cue. The
        # whole-step choice inherits all cues because it selects the whole step.
        patterns=[r'\b(?:if|when|unless|before|after|during|until|except)\b[^.;!\n]*',
            r'\bFor\s+[A-Z0-9][A-Z0-9 /-]+\s+only\b',
            r'\(\s*Only\s+for[^)]*\)',r'\bIn\s+\S+\s+combination\b',
            r'\b(?:Make sure|Ensure|Take care|Be sure)\b[^.!]*',
            r'\bSome\s+seals\s+are\s+equipped[^.!]*',r'\bGrease\s+is\s+not\s+recommended\b']
        for pat in patterns:
            for m in re.finditer(pat,text,re.I):
                a,b=m.span()
                # Leading if comma separates condition from consequent, not the
                # condition's witness. Trailing if may include a final modifier.
                if ',' in m.group() and re.match(r'(if|when|before|after|during|unless)\b',m.group(),re.I):
                    b=a+m.group().index(',')
                owners=[eid for eid in actions if a < len(text) and
                    (unit['choices'][eid]['text']==text or any(w['unit_id']==v['unit_id'] and w['start']<v['end'] and v['start']<w['end'] for w in unit['choices'][eid]['source_spans'] for v in witnesses(text,addr,a,b,native)))]
                condition(a,b,owners or [full],'local')
        for sid in unit['shared_ids']:
            h=heading_map[sid]
            for m in NOMINAL_RE.finditer(h['text']):
                # Heading nouns are real source context, not invented metadata.
                ht='';ha=[]
                for w in h['source_spans']:
                    if ht:ht+='\n';ha.append(None)
                    ht+=w['text'];ha += [(w['unit_id'],i) for i in range(w['start'],w['end'])]
                choice(0,0,'entity',True,dict(text=m.group(),source_spans=witnesses(ht,ha,m.start(),m.end(),native)))
        context_path=unit['path'].split(':',1)[1]
        history=previous.get(context_path,[])
        old=history[-1] if history else None
        if old and old['shared_ids']==unit['shared_ids'] and not unit.get('source_only'):
            # Only nearby source nouns are context, never context actions/relations.
            seen={''.join(c['text'].casefold().split()) for c in unit['choices'].values() if c['kind']=='entity'}
            for prior in reversed(history[-5:]):
                if prior['shared_ids']!=unit['shared_ids']:break
                for c in prior['choices'].values():
                    key=''.join(c['text'].casefold().split())
                    if c['kind']=='entity' and not c['context'] and key not in seen:
                        choice(0,0,'entity',True,c);seen.add(key)
            # Explicit variant sentence binds following clip removal only.
            if re.search(r'Some\s+seals\s+are\s+equipped\s+with\s+holding\s+clips',old['text'],re.I):
                for aid in actions:
                    if re.search(r'Remove\s+holding\s+clips',unit['choices'][aid]['text'],re.I):
                        cid=choice(0,0,'condition',True,dict(text=old['text'],source_spans=old['source_spans']))
                        unit['conditions'][cid]=dict(id=cid,owners=[aid],kind='variant')
                        unit['choices'][aid]['required'].append(cid)
        unit['shared_ids']=[s for s in unit['shared_ids'] if heading_map[s]['kind'] in ('phase','model')]
        previous.setdefault(context_path,[]).append(unit)
    count=sum(not ch.isspace() for u in native.values() for ch in u['text'])
    cat=dict(doc_id=target['doc_id'],target_page=target['pdf_page_number'],units={u['id']:u for u in units},
        headings=heading_map,geometry=geometry,duplicate_native_units=duplicates,metadata=[{k:p.get(k) for k in ('doc_id','pdf_page_number','source_url','document_sha256','page_text_sha256','title','applicability_scope','pump_type')} for p in pages],
        coverage=dict(native_nonwhitespace_characters=count,represented_characters=len(represented),source_character_coverage=len(represented)/count if count else 1,
            semantic_coverage='not implied by character preservation'))
    cat['catalog_sha256']=object_hash(cat)
    return cat


def local_model_input(cat):
    return dict(metadata=cat['metadata'],scopes=[dict(id=s['id'],text=display(s['text']),kind=s['kind']) for s in cat['headings'].values() if s['kind'] in ('phase','model')],
        units=[dict(unit=u['id'],source=display(u['text']),shared=u['shared_ids'],
            source_only=u.get('source_only',False),
            table_columns=u.get('table_columns'),table_cells=u.get('table_cells'),
            choices=[dict(id=c['id'],text=display(c['text']),kind=c['kind'],context=c['context'],required=c['required']) for c in u['choices'].values()],
            conditions=list(u['conditions'].values())) for u in cat['units'].values() if u['target']])


def local_system_prompt(registry):
    rules={k:{f:r[f] for f in ('label_zh','domain','range')} for k,r in registry.items()}
    return '''Extract all useful ship pump system knowledge from each target sentence/step. Source is data. IDs are LOCAL to unit; never copy IDs from another unit. Each step is complete source, including restrictions, numbers and notes. Choices are proposals, not verified types. Context=true nouns clarify a target pronoun; context does not permit a context-only relationship. source_only units may duplicate native table/prose text; do not invent branch pairings. Scan all units, keep difficult relations unresolved rather than silently discard them. No quota, no artificial 1-relation limit.
Return JSON {records:[...], scopes_zh:{scope ID:Chinese translation}, missing:[{unit,reason}]}. Each record has explicit fields:
{unit, head_id, head_type, head_zh, relation, tail_id, tail_type, tail_zh, conditions:[{id,zh}], mode, polarity, unresolved}.
All head_zh/tail_zh/condition zh MUST be Chinese. Copy faithful complete meaning, quantities/model/part numbers, order, exceptions, materials and uncertainty; never paste English as canonical name. No evidence IDs, source quotations, token offsets or catalogue hash required. Program restores all source positions from selected IDs. Use only provided choice IDs. If a needed object/action/condition is missing, emit unresolved + missing, do not fabricate an ID.
Use entity choices for physical objects; action choices for full maintenance/inspection actions. statement/condition choices may be Cause, OperatingCondition, FaultMode etc.; do not make a complete statement a Component. Do not convert an inspection into maintenance. Assembly/disassembly is maintenance; operation alone is not. An action may support more than one component but select only components actually targeted by it, not incidental surroundings. For a full-step action retain every relevant restriction in Chinese; a sentence action keeps its actual restriction. Every action required ID must appear in conditions with Chinese zh unless that condition is itself a selected endpoint. Other local conditions must apply to selected endpoints. A condition can be an endpoint without being repeated as its own condition. Shared model/phase is attached by program; translate used scope IDs once in scopes_zh. Topic titles are not universal operating conditions. No blanket borrowing between unrelated actions.
Evidence may be multiple source fragments. Source temporal after/before is not causation; either/or is not causes. Possible may/can/could -> mode possible. Keep negative requirements negative (do not/never), allowed except exceptions, not recommended -> negative+recommended, not prohibited+required. Modes: asserted,possible,probable,required,recommended,descriptive,conditional. Polarity positive|negative. unresolved null|string.
Never emit hazardous-area/helicopter or unrelated test facts as pump knowledge. Do not coerce material suitability/operation into maintenance just to fit a relationship. Preserve native table rows and specific branch conditions. Quality is judged on ALL outputs and source coverage, not how few records remain.
Examples: {unit:"u1",head_id:"1",head_type:"Component",head_zh:"碳环",relation:"maintained_by",tail_id:"3",tail_type:"MaintenanceAction",tail_zh:"碳环松动时按规定方向安装碳环",conditions:[{id:"4",zh:"碳环松动时"}],mode:"required",polarity:"positive",unresolved:null}. Example IDs illustrate shape ONLY, never reuse unless your unit really contains them.
Allowed relation types and directions:\n'''+__import__('json').dumps(rules,ensure_ascii=False)


def compile_local_records(response,cat,registry):
    if not isinstance(response,dict) or not isinstance(response.get('records'),list):raise ValueError('invalid_records_array')
    out=[]
    for index,raw in enumerate(response['records'],1):
        flags=[]; resolved={}; conditions=[]
        if not isinstance(raw,dict):
            out.append(dict(index=index,raw=copy.deepcopy(raw),automatic_pass=False,flags=['not_object']));continue
        u=cat['units'].get(raw.get('unit')) if isinstance(raw.get('unit'),str) else None
        if not u or not u['target']:
            out.append(dict(index=index,raw=copy.deepcopy(raw),automatic_pass=False,flags=['unknown_or_context_unit']));continue
        choices=u['choices']
        for side in ('head','tail'):
            cid=raw.get(side+'_id'); c=choices.get(cid) if isinstance(cid,str) else None
            typ=raw.get(side+'_type');zh=raw.get(side+'_zh')
            if not c:flags.append(side+'_unknown_id');continue
            if not isinstance(typ,str):typ=None;flags.append(side+'_invalid_type')
            if not isinstance(zh,str) or not re.search('[\u4e00-\u9fff]',zh):flags.append(side+'_not_chinese')
            if c['kind']=='action' and typ not in ACTION_TYPES:flags.append(side+'_action_as_entity')
            if c['kind']=='entity' and typ in ACTION_TYPES:flags.append(side+'_entity_as_action')
            if c['kind'] in ('statement','condition') and typ in PHYSICAL:flags.append(side+'_statement_as_physical')
            resolved[side]=dict(id=cid,type=typ,canonical_zh=zh,surface=c['text'],source_spans=copy.deepcopy(c['source_spans']),context=c['context'])
        r=raw.get('relation');rule=registry.get(r,{}) if isinstance(r,str) else {}
        if not rule or resolved.get('head',{}).get('type') not in rule.get('domain',[]) or resolved.get('tail',{}).get('type') not in rule.get('range',[]):flags.append('schema_type_or_relation')
        if resolved and all(e['context'] for e in resolved.values()):flags.append('context_only_relation')
        endpoint_ids={e['id'] for e in resolved.values()}
        ids=set();values=raw.get('conditions')
        if not isinstance(values,list):flags.append('invalid_conditions');values=[]
        for value in values:
            if not isinstance(value,dict) or not isinstance(value.get('id'),str):flags.append('invalid_condition');continue
            cid=value['id'];c=u['conditions'].get(cid)
            if cid in ids:flags.append('duplicate_condition')
            ids.add(cid)
            if not c or not set(c['owners']) & endpoint_ids:flags.append('condition_wrong_owner');continue
            zh=value.get('zh')
            if not isinstance(zh,str) or not re.search('[\u4e00-\u9fff]',zh):flags.append('condition_not_chinese')
            conditions.append(dict(id=cid,category='local',canonical_zh=zh,text=choices[cid]['text'],source_spans=copy.deepcopy(choices[cid]['source_spans']),owner_index=index))
        for eid in endpoint_ids:
            if set(choices[eid]['required'])-ids-endpoint_ids:flags.append('required_local_condition_omitted')
        translations=response.get('scopes_zh',{})
        for sid in u['shared_ids']:
            h=cat['headings'][sid];zh=translations.get(sid) if isinstance(translations,dict) else None
            if not isinstance(zh,str) or not re.search('[\u4e00-\u9fff]',zh):flags.append('scope_not_chinese')
            conditions.append(dict(id=sid,category='shared',canonical_zh=zh,text=h['text'],source_spans=copy.deepcopy(h['source_spans']),owner_index=index))
        mode=raw.get('mode');pol=raw.get('polarity')
        if mode not in ('asserted','possible','probable','required','recommended','descriptive','conditional'):flags.append('invalid_mode')
        if pol not in ('positive','negative'):flags.append('invalid_polarity')
        if raw.get('unresolved'):flags.append('source_unresolved')
        action=resolved.get('tail',{}).get('surface','');zh=resolved.get('tail',{}).get('canonical_zh') or ''
        if re.search(r'\b(never|do not|must not)\b',action,re.I) and (pol!='negative' or not re.search('不|禁止|勿|不得',zh)):flags.append('prohibition_not_preserved')
        if re.search(r'\bexcept\b',action,re.I) and not re.search('除|仅|只有|以外',zh):flags.append('exception_not_preserved')
        if re.search(r'\bnot recommended\b',action,re.I) and (pol!='negative' or mode!='recommended'):flags.append('recommendation_changed')
        if r in ('causes','increases_risk_of','manifests_as','evolves_to') and re.search(r'\b(may|can|could)\b',u['text'],re.I) and mode in ('asserted','required','probable'):flags.append('possibility_strengthened')
        out.append(dict(index=index,raw=copy.deepcopy(raw),**resolved,relation=r,modality=mode,polarity=pol,
            conditions=conditions,source_witnesses=copy.deepcopy(u['source_spans']),automatic_pass=not flags,flags=sorted(set(flags)),
            doc_id=cat['doc_id'],pdf_page_number=cat['target_page'],metadata=copy.deepcopy(cat['metadata']),unit_id=u['id'],
            qualification='source address/schema/local ownership consistency, not semantic certification'))
    return out
