"""Post-unblinding AI review, kept separate from sealed source-first reference.

Judgments below were entered after reading all 210 triples against source pages.
String equality only proposes unambiguous matches on two manually read tables;
it never supplies factual truth labels. Partial representations are NOT omissions.
"""
import json
import re
import unicodedata
from pathlib import Path

P=Path(__file__).resolve().parent
read=lambda name: [json.loads(x) for x in (P/name).open()]
refs=read('page_reference_annotations.jsonl')
original=sorted(read('page_candidate_comparison_packets.jsonl'),key=lambda r:(r['doc_id'],r['pdf_page_number'],r['triple_id']))
cands={f'C{i:03d}':r for i,r in enumerate(original,1)}
unsupported={
3:'ISO4406 cleanliness comparison is not an operating condition.',
5:'Trained operator is not a method diagnosing the particle counter.',
28:'Insulated bearings and bearing currents are reversed as mitigation target/action.',
29:'DESMI Automation is the measuring provider, not the item inspected.',
30:'Common Mode filters and Interference are reversed as mitigation target/action.',
36:'Screening prevents incidental contact; does not prevent exhaust gases themselves.',
44:'Adjacent closed-valve warning does not explicitly entail impeller-damage risk without an extra mechanism assumption.',
51:'Tightening supports does not prevent alignment; target should involve misalignment.',
53:'Trouble-free operation does not cause misalignment; actual source names transit/handling.',
54:'Tightening foundation bolts does not prevent alignment; wrong target polarity.',
104:'Connecting thermal sensors is not an inspection of those sensors.',
105:'Negative desired state cannot be the prevented event; circular/mis-polarized relation.',
183:'Tilting head prevents idler falling, not the idler component.',
185:'Safety prohibition does not prevent the relief-valve body component.',
191:'Prevented target is a component instead of mixing/damage event.',
192:'Marking ensures reassembly; it does not prevent pump disassembly.',
197:'Do not spin during cleaning prevents damage, not bearing components themselves.',
}
uncertain={i:'Numeric/specification record lacks unit, material, variable or clear Standard identity; do not declare a fully valid parameter claim.' for i in range(18,28)}
uncertain.update({32:'Bearing currents mentioned in supplier consultancy context; explicit causal statement may require preceding page.',33:'Motor power/start-stop specification assigned to Electric pump; target/granularity needs adjudication.',34:'Motor power/start-stop specification assigned to Electric pump; target/granularity needs adjudication.',55:'Bleed line leads back to sump; located_in may overstate its entire location.'})
uncertain.update({i:'Finnish page held for independent bilingual technical review; not scored as false or empty.' for i in range(108,114)})

quality=[]
for i,(cid,r) in enumerate(cands.items(),1):
    status='unsupported' if i in unsupported else 'unresolved' if i in uncertain else 'supported'
    note=unsupported.get(i,uncertain.get(i,'AI compared against the corresponding source paragraph/table row; source-relative support, subject to document/branch conditions; not expert truth or schema correctness.'))
    if 114<=i<=173 and r['relation']!='causes':
        note+=' Troubleshooting remedy is conditional on its cause branch; symptom-to-action representation does not explicitly encode that branch.'
    if i in [59,64,67,69,75,78,179,184,187,189,200]:
        note+=' Valid source content outside or more granular than the sealed reference inventory; reference is demonstrably not exhaustive.'
    quality.append(dict(candidate_id=cid,triple_id=r['triple_id'],semantic_support=status,review_note=note,reviewer='Codex assistant',human_expert_reviewed=False))
with (P/'page_candidate_semantic_annotations.jsonl').open('x',encoding='utf-8') as f:
    for r in quality:f.write(json.dumps(r,ensure_ascii=False)+'\n')

# Same-relation semantic matches versus related/partial representations. Explicit
# mappings are annotation decisions, not a tuned retrieval/evaluation algorithm.
M={}
def put(page, ai, candidates, kind='matched', note='Source-relative semantic correspondence; keep page conditions.'):
    M[f'{page}:A{ai:03d}']=dict(candidate_ids=[f'C{x:03d}' for x in candidates],match_status=kind,match_note=note)
def mapping(page, matches, partials=None):
    for ai, ids in matches.items():put(page,ai,ids if isinstance(ids,list) else [ids])
    for ai, ids in (partials or {}).items():put(page,ai,ids if isinstance(ids,list) else [ids],'partial_or_related','Grouped endpoints, changed relation/target, incomplete action, or condition loss; do not call this completely unextracted knowledge.')

mapping('MP001:p0081',{4:1,5:2},{1:4,2:4,3:4})
mapping('MP005:p0013',{1:17,2:13,3:15,4:12,5:10,6:11,7:16},{8:14})
mapping('MP006:p0011',{}, {1:31,2:31,3:29})
mapping('MP015:p0025',{}, {1:36,2:39,3:40})
mapping('MP016:p0027',{1:41,2:46,6:43,7:47},{3:50,4:42,5:48,10:49,11:45})
mapping('MP017:p0013',{}, {1:53,2:56,3:52})
mapping('MP018:p0013',{3:71,4:65,5:70,6:63,8:66,13:76,14:73,15:61},{1:74,2:77,7:[60,72],9:66,11:[68,75],12:[58,64]})
mapping('MP019:p0009',{2:106,6:103},{1:105,3:107,4:107})
mapping('MP021:p0007',{4:181,5:195,6:194,7:180,9:188,23:190,24:182,25:198},
        {2:183,3:192,8:193,10:[188,197],12:186,13:186,14:186,15:186,16:186,17:186,18:186,19:186,20:196,21:196,22:197,26:198})
mapping('MP021:p0002',{9:174,10:176,11:178},{16:177,17:175})
mapping('MP022:p0023',{1:201,2:202})
mapping('MP022:p0029',{2:208,3:204,4:205,5:206,7:209},{1:210,6:207})

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())

for ref in refs:
    page=ref['page_key']
    if page not in ['MP018:p0026','MP020:p0026']:continue
    for a in ref['atoms']:
        ai=int(a['atom_id'].split(':A')[-1])
        exact=[]
        related=[]
        for cid,c in cands.items():
            if f"{c['doc_id']}:p{c['pdf_page_number']:04d}"!=page:continue
            if a['relation']==c['relation'] and norm(a['head'])==norm(c['head_surface']) and norm(a['tail'])==norm(c['tail_surface']):
                exact.append(int(cid[1:]))
            # Cornell corrective columns use symptom rather than branch cause.
            # Same action with a different head is partial, never exact recall.
            elif page=='MP020:p0026' and a['relation'] in ['mitigated_by','diagnosed_by'] and c['relation'] in ['mitigated_by','diagnosed_by']:
                action=norm(c['tail_surface'])
                if action in [norm(a['tail'])] or (a['tail']=='Align all rotating parts' and action in ['align','aligncorrectly','alignallrotatingparts']):
                    related.append(int(cid[1:]))
        if exact:put(page,ai,exact)
        elif related:put(page,ai,related,'partial_or_related','Same corrective action appears for symptom, but branch cause is not encoded; some identical generic actions have several branches, so this is only an ambiguity flag.')

# Manually inspected bearing table paraphrases/grouped source cells.
for ref in refs:
    if ref['page_key']!='MP018:p0026':continue
    for a in ref['atoms']:
        ai=int(a['atom_id'].split(':A')[-1])
        if a['relation']=='manifests_as' and a['head']=='Flaking and cracking':put(ref['page_key'],ai,[95])
        if a['relation']=='causes' and a['head']=='Lubricant breaks down into acid (Wrong lubricant)':put(ref['page_key'],ai,[80])
        if a['head']=='misalignment':put(ref['page_key'],ai,[92],'partial_or_related','Cause nested in a composite endpoint, no separate causal edge.')
        if a['relation']=='evolves_to':put(ref['page_key'],ai,[95],'partial_or_related','Progression remains inside appearance text, not a separate evolves_to relation.')

flat=[]
for ref in refs:
    for a in ref['atoms']:
        m=M.get(a['atom_id'],dict(candidate_ids=[],match_status='not_found_in_audited_candidates',match_note='No semantic/related representation identified in saved audited records on this page; raw lineage check still required.'))
        assert all(f"{cands[c]['doc_id']}:p{cands[c]['pdf_page_number']:04d}"==ref['page_key'] for c in m['candidate_ids'])
        flat.append(dict(page_key=ref['page_key'],**a,**m))
assert len(flat)==245
with (P/'page_reference_matches.jsonl').open('x',encoding='utf-8') as f:
    for r in flat:f.write(json.dumps(r,ensure_ascii=False)+'\n')
print('Post-opening semantic judgments',len(quality),'reference comparisons',len(flat))
