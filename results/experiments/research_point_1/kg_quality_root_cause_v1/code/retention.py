"""Check retained TEXT channels without equating fields with semantic binding."""
from common import *


def main():
    if (OUT/'details/retention_complete.json').exists():print('REUSE text retention');return
    d,E,C,S=dataset();units=read(OUT/'SOURCE_UNIT_AUDIT.jsonl');rows=[]
    def clean(x):return I.norm(re.sub(r'(?<=\w)-\s+(?=\w)','',x))
    def contains(r,frags):
        text=' '.join(str(r.get(k,'')) for k in ['head_surface','tail_surface','head_canonical_zh','tail_canonical_zh','evidence_text','conditions_source','modality','applicability_scope'])
        return all(clean(f) in clean(text) for f in frags)
    for u in units:
        if not u['complex_semantics']:continue
        frags=u['complex_semantics']['required'];nn=[r for r in d['normalized'] if r['doc_id']==u['doc_id'] and r['pdf_page_number']==u['pdf_page_number']];ss=[r for r in d['graph']['source_records'] if r['doc_id']==u['doc_id'] and r['pdf_page_number']==u['pdf_page_number']]
        n=[r['triple_id'] for r in nn if contains(r,frags)];s=[r['expanded_claim_id'] for r in ss if contains(r,frags)]
        rows.append(dict(sample_id=u['sample_id'],doc_id=u['doc_id'],physical_page=u['pdf_page_number'],semantic_kind=u['complex_semantics']['kind'],required_fragments=frags,export_records_with_all_literal_fragments=n,published_sources_with_all_literal_fragments=s,old_typed_candidate_may_still_be_wrong=True,missing_literal_match_not_proof_of_semantic_loss=True,structured_binding_correctness_unmeasured=True))
    save('details/complex_retention_channels.jsonl',rows)
    save('details/retention_complete.json',dict(complex_source_units=len(rows),export_records_literal_context_present_units=sum(bool(r['export_records_with_all_literal_fragments']) for r in rows),published_literal_context_present_units=sum(bool(r['published_sources_with_all_literal_fragments']) for r in rows),not_semantic_binding_accuracy=True))
    print(read(OUT/'details/retention_complete.json'),flush=True)


if __name__=='__main__':main()
