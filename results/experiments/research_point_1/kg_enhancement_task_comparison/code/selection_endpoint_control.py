"""A stronger simple matching control: preserve predicate argument identity.

No learning objective, model proposal, or threshold tuning. Scores remain
suggestions; no automatic merging is performed.
"""
from collections import defaultdict
import json
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from inputs import load,save
from selection_screen import OUT,OLD,read


def main():
    sys.stdout.reconfigure(encoding='utf-8');d=load();graph=d['graph']['source_records']
    candidates=[m for m in read(OLD/'mapping/raw_occurrence_mapping.jsonl') if not m['current_lineage_assertion_ids']]
    allrows=graph+[m['normalized_source'] for m in candidates]
    vectors=[]
    for side in ['head','tail']:
        texts=[' | '.join(str(r.get(k,'')) for k in [side+'_canonical_zh',side+'_surface']) for r in allrows]
        vec=TfidfVectorizer(analyzer='char',ngram_range=(2,4),sublinear_tf=True)
        vectors.append(vec.fit_transform(texts))
    bins=defaultdict(list)
    for i,r in enumerate(graph):bins[r['head_type'],r['relation'],r['tail_type']].append(i)
    results=[]
    for i,m in enumerate(candidates):
        r=m['normalized_source'];ids=bins[r['head_type'],r['relation'],r['tail_type']]
        hs=(vectors[0][len(graph)+i]@vectors[0][ids].T).toarray().ravel()
        ts=(vectors[1][len(graph)+i]@vectors[1][ids].T).toarray().ravel()
        score=np.minimum(hs,ts)
        best=np.argsort(-score,kind='stable')[:3]
        results.append({'raw_occurrence_id':m['raw_occurrence_id'],'top_matches':[{
            'assertion_id':graph[ids[k]]['expanded_assertion_id'],'head':graph[ids[k]]['head_canonical_zh'],
            'tail':graph[ids[k]]['tail_canonical_zh'],'head_cosine':float(hs[k]),'tail_cosine':float(ts[k]),
            'score_min_head_tail':float(score[k])} for k in best],
            'conditions_or_equivalence_certified':False,'automatic_merge_allowed':False})
    save(OUT/'matching/endpoint_separated_top3.jsonl',results)
    lookup={r['raw_occurrence_id']:r for r in results}
    old={r['raw_occurrence_id']:r for r in read(OUT/'matching/candidate_to_base_top3.jsonl')}
    probes=[]
    for oid in ['RAW-03430','RAW-03441','RAW-03440']:
        probes.append({'raw_occurrence_id':oid,'whole_record_top1':old[oid]['top_matches'][0],
                       'endpoint_separated_top1':lookup[oid]['top_matches'][0],
                       'interpretation':'Removes merged-evidence domination using a simple control, not an algorithmic contribution.'})
    save(OUT/'evaluation/endpoint_control_hard_negative_comparison.jsonl',probes)
    summary={'executed_unpublished_queries':len(results),'same_base_assertions':len(graph),
        'method':'separate_head_tail_character_TFIDF+min_cosine+exact_relation_type_constraint',
        'three_reviewed_nonduplicate_probes':probes,'no_calibrated_merge_threshold':True,
        'no_independent_precision_or_recall_claim':True}
    save(OUT/'evaluation/endpoint_control_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
