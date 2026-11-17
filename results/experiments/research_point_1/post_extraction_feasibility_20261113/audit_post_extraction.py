#!/usr/bin/env python3
"""Read-only post-extraction feasibility audit. Retrieval hypotheses are NOT labels.

Only this independent output directory is writable. No inference or graph export.
"""
import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import run_evidence_contract_validation_experiments as locator
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

BUILD = [f'MP{i:03d}' for i in [*range(1, 8), *range(15, 23)]]
BASE = 'results/experiments/research_point_1/'
PATHS = {
    'raw_cache': 'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl',
    'audit': 'data/kg/marine_pump/triples/KG_v1_raw/source_records.jsonl',
    'expansion_input': 'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl',
    'strict208': 'data/kg/marine_pump/triples/KG_v1_validated',
    'standard1326': 'data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/standard_graph/triples/KG_v1_validated',
    'expanded1456': 'data/kg/marine_pump/versions/expanded_v1_20261012',
}
PATTERNS = {
    'condition': r'\b(if|when|whenever|unless|otherwise|provided that|in case|only when|only if)\b|如果|若|否则|仅当|除非',
    'time_order': r'\b(after|before|then|prior to|subsequently|until)\b|之后|之前|然后|先.{0,12}再',
    'negation': r'\b(do not|must not|shall not|never|not permitted|prohibited|cannot|may not)\b|不得|禁止|切勿|不能',
    'alternative_joint': r'\b(alternatively|either|or else|and then)\b|或者|或是|二选一|同时必须',
    'numeric_limit': r'\d\s*(?:°\s*[CF]|mm\s*/\s*s|hours?\b|minutes?\b|months?\b|rpm\b)|不超过|至少|最多',
}
RX = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
SOURCES = {}
METRICS = []


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def source(name):
    p = ROOT / name
    SOURCES[name] = {'sha256': sha(p), 'bytes': p.stat().st_size}
    return p


def read(name):
    p = source(name)
    with p.open(encoding='utf-8-sig') as f:
        return [json.loads(x) for x in f if x.strip()] if p.suffix == '.jsonl' else json.load(f)


def save(name, value):
    p = HERE / name
    assert p.resolve().is_relative_to(HERE)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in value) if p.suffix == '.jsonl' else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    p.write_text(text)


def csvout(name, rows):
    if not rows:
        save(name, '')
        return
    s = io.StringIO(newline='')
    w = csv.DictWriter(s, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader(); w.writerows(rows); save(name, s.getvalue())


def metric(category, name, count, denominator, unit, population, auto=True, limit='Deterministic count; not a semantic truth label'):
    derived={'qualified1698':PATHS['audit']+' [saved qualified decisions]',
             'locator_pool':PATHS['audit']+' + candidate_locator_audit.jsonl [locator_contract_pass]',
             'build1934':'data/interim/parsed_pages/corpus_v2/{15 BUILD IDs}.pages.v2.jsonl'}
    METRICS.append(dict(category=category, problem_type=name, count=count, denominator=denominator,
                        proportion=round(count / denominator, 6) if denominator else '',
                        unit=unit, population=population, source=derived.get(population,PATHS.get(population, population)),
                        automatic_candidate=auto, confidence_limit=limit))


def norm(s):
    return ' '.join(unicodedata.normalize('NFKC', str(s or '')).casefold().split())


def compact(s):
    return re.sub(r'[^\w\u4e00-\u9fff]', '', norm(s))


def key(r):
    return tuple(norm(r.get(k)) for k in ['head_type', 'head_canonical_zh', 'relation', 'tail_type', 'tail_canonical_zh'])


def src_key(r):
    return tuple(r.get(k) for k in ['doc_id', 'pdf_page_number', 'relation', 'head_surface', 'tail_surface', 'evidence_text'])


def rid(r):
    return r['triple_id']


def packet(r):
    fields = ['triple_id', 'doc_id', 'pdf_page_number', 'source_family_id', 'source_language',
              'head_surface', 'head_canonical_zh', 'head_type', 'relation', 'tail_surface',
              'tail_canonical_zh', 'tail_type', 'evidence_text', 'evidence_mode', 'evidence_level',
              'evidence_start', 'evidence_end', 'evidence_unit_ids', 'evidence_units',
              'applicability_scope', 'pump_type', 'conditions_source', 'modality', 'decision',
              'rejection_reasons', 'review_reasons', 'expanded_claim_id', 'expanded_assertion_id',
              'expansion_layer', 'expansion_source_witnesses', 'document_sha256', 'page_text_sha256']
    return {k: r.get(k) for k in fields}


def tags(text):
    return [name for name, regex in RX.items() if regex.search(str(text or ''))]


def group_audit(name, records):
    by = defaultdict(list)
    for r in records:
        by[key(r)].append(r)
    groups = []
    for k, rr in sorted(by.items()):
        if len(rr) < 2:
            continue
        docs = sorted({r['doc_id'] for r in rr})
        families = sorted({r.get('source_family_id') for r in rr if r.get('source_family_id')})
        groups.append(dict(cluster_id='K-' + hashlib.sha256(json.dumps([name, k], ensure_ascii=False).encode()).hexdigest()[:16],
                           population=name, typed_canonical_key=k, records=len(rr), documents=docs,
                           family_proxies=families, independent_sources_confirmed=None,
                           same_document_only=len(docs) == 1, across_documents=len(docs) > 1,
                           multiple_family_proxies=len(families) > 1,
                           distinct_scopes=len({norm(r.get('applicability_scope')) for r in rr}),
                           distinct_explicit_conditions=len({json.dumps(r.get('conditions_source'), ensure_ascii=False, sort_keys=True) for r in rr}),
                           distinct_source_surface_pairs=len({(norm(r.get('head_surface')), norm(r.get('tail_surface'))) for r in rr}),
                           evidence=[packet(r) for r in rr],
                           interpretation='Exact typed canonical claim family only; factual/condition equivalence unassessed'))
    summary = dict(records=len(records), canonical_claim_families=len(by), repeated_clusters=len(groups),
                   records_in_repeated_clusters=sum(g['records'] for g in groups),
                   same_document_only_clusters=sum(g['same_document_only'] for g in groups),
                   across_document_clusters=sum(g['across_documents'] for g in groups),
                   across_family_proxy_clusters=sum(g['multiple_family_proxies'] for g in groups),
                   variant_surface_clusters=sum(g['distinct_source_surface_pairs'] > 1 for g in groups))
    stored = defaultdict(list)
    for r in records:
        stored[r.get('expanded_claim_id') or r['claim_id']].append(r)
    summary.update(actual_stored_claim_ids=len(stored),
                   stored_claims_with_multiple_records=sum(len(v)>1 for v in stored.values()),
                   canonical_keys_with_multiple_stored_claim_ids=sum(len({r.get('expanded_claim_id') or r['claim_id'] for r in rr})>1 for rr in by.values()))
    save(f'clusters/{name}_exact.jsonl', groups)
    metric('fusion', 'repeated_canonical_claim_clusters', len(groups), len(by), 'claim_family', name)
    metric('fusion', 'across_document_exact_clusters', summary['across_document_clusters'], len(by), 'claim_family', name)
    metric('fusion', 'across_family_proxy_exact_clusters', summary['across_family_proxy_clusters'], len(by), 'claim_family', name,
           limit='Source-family labels are dependency proxies; not confirmed independence or condition-equivalent facts')
    return summary, groups


def near_pairs(name, records):
    by = defaultdict(list)
    for r in records:
        by[key(r)].append(r)
    keys = sorted(by)
    labels = [' '.join([k[0], k[1], k[2], k[3], k[4]]) for k in keys]
    x = TfidfVectorizer(analyzer='char', ngram_range=(2, 4), lowercase=False).fit_transform(labels)
    nn = NearestNeighbors(n_neighbors=min(11, len(keys)), metric='cosine', algorithm='brute', n_jobs=1).fit(x)
    distances, indices = nn.kneighbors(x)
    pairs = {}
    for i, (ds, js) in enumerate(zip(distances, indices)):
        for distance, j in zip(ds, js):
            j = int(j)
            if i == j:
                continue
            a, b = keys[i], keys[j]
            if (a[0], a[2], a[3]) != (b[0], b[2], b[3]):
                continue
            sim = 1 - float(distance)
            hs = SequenceMatcher(None, compact(a[1]), compact(b[1])).ratio()
            ts = SequenceMatcher(None, compact(a[4]), compact(b[4])).ratio()
            if sim < .68 or min(hs, ts) < .6 or max(hs, ts) < .85:
                continue
            ij = tuple(sorted([i, j]))
            left, right = by[keys[ij[0]]], by[keys[ij[1]]]
            cross_doc = any(r['doc_id'] != s['doc_id'] for r in left for s in right)
            cross_family = any(r.get('source_family_id') != s.get('source_family_id') for r in left for s in right)
            pairs[ij] = dict(pair_id=f'{name}:P{ij[0]}-{ij[1]}', population=name,
                             left_key=keys[ij[0]], right_key=keys[ij[1]], cosine=round(sim, 6),
                             head_similarity=round(hs, 6), tail_similarity=round(ts, 6),
                             cross_document=cross_doc, cross_family_proxy=cross_family,
                             semantic_equivalence=None, evidence_left=[packet(r) for r in left],
                             evidence_right=[packet(r) for r in right])
    rows = sorted(pairs.values(), key=lambda p: (-p['cosine'], p['pair_id']))
    save(f'clusters/{name}_similarity_pairs.jsonl', rows)
    summary = dict(pairs=len(rows), across_document_pairs=sum(p['cross_document'] for p in rows),
                   across_family_proxy_pairs=sum(p['cross_family_proxy'] for p in rows),
                   method='Character TF-IDF 2-4 grams; top10 nonself neighbors each; cosine>=.68; both endpoint SequenceMatcher>=.6, one>=.85; same relation and types. No embeddings/LLM; not exhaustive.')
    metric('fusion', 'lexical_near_pairs', len(rows), None, 'retrieved_pair', name,
           limit=summary['method'] + ' Equivalence/condition compatibility UNASSESSED; pairs not facts or independent samples.')
    return summary


def semantic_graph(name, entities, claims, records):
    graph = nx.MultiDiGraph()
    graph.add_nodes_from((e['entity_id'], e) for e in entities)
    graph.add_edges_from((c['head_entity_id'], c['tail_entity_id'], {'relation': c['relation'], 'claim_id': c['claim_id']}) for c in claims)
    simple = nx.Graph(graph)
    comps = sorted(nx.connected_components(simple), key=lambda c: (-len(c), sorted(c)))
    degree = Counter(dict(simple.degree()).values())
    cid = {c['claim_id']: c for c in claims}
    by = defaultdict(list)
    for r in records:
        by[r.get('expanded_claim_id') if name == 'expanded1456' else r['claim_id']].append(r)
    support = []
    for claim in claims:
        rr = by[claim['claim_id']]
        support.append(dict(claim_id=claim['claim_id'], assertions=len(rr), documents=len({r['doc_id'] for r in rr}),
                            family_proxies=len({r['source_family_id'] for r in rr}),
                            independent_family_count=None,
                            records=[rid(r) for r in rr]))
    save(f'graph/{name}_claim_evidence.jsonl', support)
    paths = defaultdict(list)
    for c in claims:
        if c['relation'] != 'causes':
            continue
        for _, end, edge in graph.out_edges(c['tail_entity_id'], data=True):
            if edge['relation'] in {'diagnosed_by', 'mitigated_by', 'prevented_by'}:
                paths['causes->' + edge['relation']].append([c['claim_id'], edge['claim_id']])
    save(f'graph/{name}_typed_paths.json', paths)
    summary = dict(entities=len(entities), claims=len(claims), weak_components=len(comps),
                   largest_component_entities=len(comps[0]) if comps else 0,
                   largest_component_claims=sum(c['head_entity_id'] in comps[0] for c in claims) if comps else 0,
                   isolated_entities=len(list(nx.isolates(graph))), degree_histogram=dict(sorted(degree.items())),
                   degree_one_entities=degree[1], two_node_components=sum(len(c) == 2 for c in comps),
                   component_size_histogram=dict(sorted(Counter(map(len, comps)).items())),
                   max_unique_neighbor_degree=max(dict(simple.degree()).values(), default=0),
                   typed_path_counts={k: len(v) for k, v in paths.items()},
                   claim_assertion_histogram=dict(sorted(Counter(r['assertions'] for r in support).items())),
                   claim_family_proxy_histogram=dict(sorted(Counter(r['family_proxies'] for r in support).items())),
                   claims_without_assertions=sum(r['assertions'] == 0 for r in support),
                   entity_types=dict(Counter(e['entity_type'] for e in entities)),
                   claim_relations=dict(Counter(c['relation'] for c in claims)))
    save(f'graph/{name}_summary.json', summary)
    metric('structure', 'weak_components', len(comps), None, 'component', name)
    metric('structure', 'degree_one_entities', degree[1], len(entities), 'entity', name)
    metric('evidence','claims_with_assertions',sum(r['assertions']>0 for r in support),len(claims),'claim',name,limit='Evidence occurrence exists; not factual correctness or conditional equivalence')
    metric('evidence','claims_with_multiple_assertions',sum(r['assertions']>1 for r in support),len(claims),'claim',name)
    metric('evidence','claims_with_multiple_family_proxies',sum(r['family_proxies']>1 for r in support),len(claims),'claim',name,limit='Family proxies are not proved independent sources')
    return summary


def run():
    schema = locator.load_provenance_schema(source('data/kg/marine_pump/schema/provenance_schema_v3.json'), project_root=ROOT)
    raw = read(PATHS['raw_cache']); audit = read(PATHS['audit']); expansion_input = read(PATHS['expansion_input'])
    rejected = read('data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/rejected_model_proposals.jsonl')
    generation = read('data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/extraction_run_summary.json')
    terms = read('data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/entity_terminology_zh_marine_pump_v5_local_full.json')
    pages = {}
    for doc in BUILD:
        for page in read(f'data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl'):
            pages[(doc, page['pdf_page_number'])] = page
    assert len(pages) == 1934
    pdfs = {}
    for page in pages.values():
        name = page['local_file']
        if name not in pdfs:
            path = ROOT / name
            pdfs[name] = dict(exists=path.is_file(), document_hash_matches=path.is_file() and sha(source(name)).casefold() == page['document_sha256'].casefold())
    source('data/source_docs/marine_pump/source_manifest.csv')
    versions = {}; layers = {}
    for name in ['strict208', 'standard1326', 'expanded1456']:
        versions[name] = read(PATHS[name] + '/source_records.jsonl')
        layers[name] = {k: read(PATHS[name] + '/' + k + '.jsonl') for k in ['entities', 'claims', 'evidence_assertions']}
    raw_lineage=[]; audit_legacy=defaultdict(list); expanded_legacy=defaultdict(list)
    raw_ids={rid(r) for r in raw}
    for a in audit:audit_legacy[a.get('legacy_triple_id')].append(a)
    for e in versions['expanded1456']:expanded_legacy[e.get('legacy_triple_id')].append(e)
    for r in raw:
        aa=audit_legacy.get(rid(r),[])
        ee=expanded_legacy.get(rid(r),[])
        raw_lineage.append(dict(raw_cache_id=rid(r),audit_ids=[rid(a) for a in aa],
             expanded_ids=[rid(e) for e in ee],mapping='explicit legacy_triple_id only; unresolved is not proof of loss'))
    save('raw_candidate_lineage.jsonl',raw_lineage)
    raw_lineage_summary=dict(cache_records=len(raw),cache_records_with_explicit_audit_link=sum(bool(r['audit_ids']) for r in raw_lineage),
        cache_records_without_explicit_audit_link=sum(not r['audit_ids'] for r in raw_lineage),
        audit_records_legacy_in_cache=sum(r.get('legacy_triple_id') in raw_ids for r in audit),
        published_records_legacy_in_cache=sum(r.get('legacy_triple_id') in raw_ids for r in versions['expanded1456']))
    qualified = [r for r in audit if r['decision'] in locator.QUALIFIED_DECISIONS]
    checks = [locator.audit_record(r, pages, schema=schema) for r in audit]
    save('candidate_locator_audit.jsonl', checks)
    eligible = [r for r, a in zip(audit, checks) if a['locator_contract_pass']]
    summaries = {}; cls = {}
    for name, population in [('audit', audit), ('locator_pool', eligible), ('qualified1698', qualified), *versions.items()]:
        summaries[name], cls[name] = group_audit(name, population)
    counts = {name: len(rr) for name, rr in [('raw_cache', raw), ('audit', audit), ('qualified1698', qualified), ('locator_pool', eligible), *versions.items()]}
    reasons = Counter(); primary = Counter(); record_eligibility = []
    for r, a in zip(audit, checks):
        for reason in set(r.get('rejection_reasons', []) + r.get('review_reasons', [])):
            reasons[reason] += 1
        if not a['checks']['relation_schema_valid']: main = 'schema'
        elif not a['locator_contract_pass']: main = 'locator_or_provenance_or_E3'
        elif r['decision'] not in locator.QUALIFIED_DECISIONS: main = 'remaining_support_score_or_veto'
        elif not r.get('eligible_for_chinese_graph'): main = 'historical_strict_terminology'
        else: main = 'historical_strict_published'
        primary[main] += 1
        record_eligibility.append(dict(triple_id=rid(r), primary_pipeline_category=main,
                                       locator_contract_pass=a['locator_contract_pass'],
                                       decision=r['decision'], claim_id=r['claim_id'],
                                       head_entity_id=r['head_entity_id'], tail_entity_id=r['tail_entity_id']))
    save('candidate_flow_ledger.jsonl', record_eligibility)
    eligible_decisions = dict(Counter(r['decision'] for r in eligible))
    metric('lineage', 'raw_API_proposals', generation['raw_proposals'], None, 'proposal', 'raw_cache')
    metric('lineage', 'interface_normalization_rejects', len(rejected), generation['raw_proposals'], 'proposal', 'raw_cache', limit='Not PDF parse failure and not a semantic false label')
    for name, count in primary.items(): metric('pipeline_primary', name, count, len(audit), 'record', 'audit')
    for name, count in reasons.items(): metric('pipeline_overlapping', name, count, len(audit), 'record', 'audit', limit='Stored program reason; overlapping, not factual error class')
    for name in ['page_resolved', 'evidence_located', 'endpoints_located_in_evidence', 'relation_schema_valid']:
        metric('evidence', name, sum(a['checks'][name] for a in checks), len(audit), 'record', 'audit')
    metric('evidence', 'locator_contract_pass', len(eligible), len(audit), 'record', 'audit', limit='Structural/locator eligibility only, not complete source support or factual correctness')
    # Fields present and actual contents are reported separately.
    field_counts = {}
    for name, rr in [('raw_cache', raw), ('audit', audit), *versions.items()]:
        fc = {k: dict(present=sum(k in r for r in rr), nonempty=sum(r.get(k) not in (None, '', [], {}) for r in rr))
              for k in ['head_surface', 'head_type', 'relation', 'tail_surface', 'tail_type', 'evidence_text', 'conditions_source', 'conditions', 'modality', 'polarity', 'applicability_scope', 'source_family_id', 'model_confidence', 'rejection_reasons']}
        field_counts[name] = fc
    # Expanded new witnesses use a different contract from the baseline.
    exp = versions['expanded1456']; expanded_location = []
    for r in exp:
        page = pages[(r['doc_id'], r['pdf_page_number'])]
        if r['expansion_layer'] == 'baseline_reused':
            a = locator.audit_record(r, pages, schema=schema)
            valid = a['locator_contract_pass']; details = a['failed_checks']
        else:
            units = {b['block_id']: b['text'] for b in page.get('text_blocks', [])}
            units.update({c['cell_id']: c['text'] for c in locator.parser_cells(page).values()})
            witnesses = r.get('expansion_source_witnesses', [])
            valid = bool(witnesses)
            details = []
            for w in witnesses:
                unit = units.get(w.get('cell_id', w.get('block_id')))
                ok = unit is not None and unit[w['start']:w['end']] == w['text']
                if not ok: details.append(w)
                valid = valid and ok
        expanded_location.append(dict(triple_id=rid(r), claim_id=r['expanded_claim_id'],
                                      contract=r['expansion_layer'], locator_valid=valid, details=details))
    save('expanded_location_checks.jsonl', expanded_location)
    metric('evidence', 'published_record_address_contract_pass', sum(r['locator_valid'] for r in expanded_location), len(exp), 'record', 'expanded1456', limit='Baseline reuses locator contract; added130 checks native witness addresses, not a repeated semantic evaluation')
    # Keyword triage is only a broad, multilingual-incomplete retrieval frame.
    page_hits = []; quote_hits = []
    for (doc, number), page in sorted(pages.items()):
        hits = tags(page['page_text'])
        if hits:
            examples = []
            for kind in hits:
                m = RX[kind].search(page['page_text'])
                examples.append(dict(kind=kind, start=m.start(), end=m.end(), context=page['page_text'][max(0, m.start()-100):m.end()+200]))
            page_hits.append(dict(doc_id=doc, pdf_page_number=number, tags=hits, examples=examples))
    for name, rr in [('audit', audit), ('raw_cache', raw), ('expanded1456', exp)]:
        for r in rr:
            hits = tags(r.get('evidence_text'))
            if hits:
                quote_hits.append(dict(population=name, tags=hits,
                                       endpoints_tags=tags(str(r.get('head_surface'))+' '+str(r.get('tail_surface'))),
                                       explicit_conditions=bool(r.get('conditions_source') or r.get('conditions')),
                                       record=packet(r)))
        for tag in RX:
            metric('condition_keyword', tag, sum(tag in tags(r.get('evidence_text')) for r in rr), len(rr), 'record', name, limit='Suspected cue only; includes non-diagnostic prose, incomplete multi-language coverage, not a binding error or scoped knowledge count')
    for tag in RX:
        metric('source_keyword', tag, sum(tag in r['tags'] for r in page_hits), len(pages), 'page', 'build1934', limit='Suspected source cue; not a semantic diagnostic example or prevalence estimate')
    save('condition_page_candidates.jsonl', page_hits); save('condition_record_candidates.jsonl', quote_hits)
    # Exact source-surface aliases and dictionary contradictions are hypotheses.
    er = defaultdict(list)
    for r in exp:
        for side in ['head', 'tail']:
            er[r['expanded_'+side+'_entity_id']].append(dict(record_id=rid(r), side=side,
                label_zh=r[side+'_canonical_zh'], entity_type=r[side+'_type'], surface=r[side+'_surface'],
                doc_id=r['doc_id'], page=r['pdf_page_number'], family=r['source_family_id'],
                relation=r['relation'], neighbor=r['expanded_'+('tail' if side=='head' else 'head')+'_entity_id'],
                scope=r.get('applicability_scope'), evidence_text=r['evidence_text']))
    source_to_entities = defaultdict(set)
    for eid, occ in er.items():
        for o in occ: source_to_entities[(o['entity_type'], norm(o['surface']))].add(eid)
    ambiguous_source = []
    for k, ids in sorted(source_to_entities.items()):
        if len(ids) > 1:
            ambiguous_source.append(dict(entity_type=k[0], normalized_surface=k[1], entity_ids=sorted(ids),
                                         labels=sorted({er[i][0]['label_zh'] for i in ids}),
                                         occurrences=[o for i in sorted(ids) for o in er[i] if norm(o['surface'])==k[1]],
                                         same_entity_confirmed=None))
    save('entities/same_surface_multiple_entities.jsonl', ambiguous_source)
    dictionary = defaultdict(set)
    for term in terms['terms']:
        for form in term.get('source_forms', []):
            dictionary[(term['entity_type'], norm(form['surface']))].add(norm(term['canonical_label_zh']))
        dictionary[(term['entity_type'], norm(term['canonical_label_zh']))].add(norm(term['canonical_label_zh']))
    raw_surface=defaultdict(list); raw_dictionary=defaultdict(list)
    for r in eligible:
        for side in ['head','tail']:
            o=dict(record_id=rid(r),side=side,entity_id=r[side+'_entity_id'],
                   label=norm(r[side+'_canonical_zh']),surface=r[side+'_surface'],
                   entity_type=r[side+'_type'],doc_id=r['doc_id'],page=r['pdf_page_number'],family=r['source_family_id'])
            sk=(o['entity_type'],norm(o['surface']));raw_surface[sk].append(o)
            dh=dictionary.get(sk,set())
            if len(dh)==1:raw_dictionary[(o['entity_type'],next(iter(dh)))].append(o)
    raw_alias=[]
    for method,groups in [('same_source_surface',raw_surface),('single_dictionary_canonical',raw_dictionary)]:
        for k,oo in sorted(groups.items()):
            if len({o['label'] for o in oo})>1:
                raw_alias.append(dict(method=method,key=k,labels=sorted({o['label'] for o in oo}),occurrences=oo,
                                      cross_document=len({o['doc_id'] for o in oo})>1,
                                      cross_family_proxy=len({o['family'] for o in oo})>1,
                                      semantic_equivalence=None))
    save('entities/locator_pool_alias_hypotheses.jsonl',raw_alias)
    raw_alias_summary={method:dict(clusters=sum(r['method']==method for r in raw_alias),
         cross_document_clusters=sum(r['method']==method and r['cross_document'] for r in raw_alias),
         cross_family_proxy_clusters=sum(r['method']==method and r['cross_family_proxy'] for r in raw_alias))
         for method in ['same_source_surface','single_dictionary_canonical']}
    for method,stats in raw_alias_summary.items():
        metric('entity_alignment','locator_pool_'+method+'_multiple_labels',stats['clusters'],None,'retrieval_cluster','locator_pool',limit='Old candidate label variation; no synonym/error truth; clusters from the two methods may overlap and include cases already solved by publication governance')
    dc = []; dictionary_group = defaultdict(set)
    for eid, occ in er.items():
        for o in occ:
            hits = dictionary.get((o['entity_type'], norm(o['surface'])), set())
            if len(hits) == 1:
                canonical = next(iter(hits)); dictionary_group[(o['entity_type'], canonical)].add(eid)
                if canonical != norm(o['label_zh']):
                    dc.append(dict(entity_id=eid, occurrence=o, dictionary_canonical=canonical))
    dictionary_alias = [dict(entity_type=k[0], dictionary_canonical=k[1], entity_ids=sorted(ids),
                            occurrences=[o for eid in sorted(ids) for o in er[eid]], same_entity_confirmed=None)
                        for k, ids in sorted(dictionary_group.items()) if len(ids)>1]
    save('entities/dictionary_candidate_clusters.jsonl', dictionary_alias)
    save('entities/dictionary_mismatch_occurrences.jsonl', dc)
    save('entities/entity_occurrences.jsonl', [dict(entity_id=eid, occurrences=o) for eid,o in sorted(er.items())])
    nodes = sorted(er)
    alias_pairs = []
    for i, eid in enumerate(nodes):
        a = er[eid][0]
        for fid in nodes[i+1:]:
            b = er[fid][0]
            if a['entity_type'] != b['entity_type']: continue
            if min(len(compact(a['label_zh'])),len(compact(b['label_zh']))) < 2:continue
            similarity=SequenceMatcher(None, compact(a['label_zh']), compact(b['label_zh'])).ratio()
            if similarity < .8:continue
            aa={(o['relation'],o['neighbor']) for o in er[eid]}; bb={(o['relation'],o['neighbor']) for o in er[fid]}
            alias_pairs.append(dict(left=eid,right=fid,left_label=a['label_zh'],right_label=b['label_zh'],type=a['entity_type'],
                                    name_similarity=round(similarity,6),shared_relation_neighbor_count=len(aa&bb),
                                    cross_document=any(o['doc_id']!=q['doc_id'] for o in er[eid] for q in er[fid]),
                                    cross_family_proxy=any(o['family']!=q['family'] for o in er[eid] for q in er[fid]),
                                    same_entity_confirmed=None))
    alias_pairs.sort(key=lambda p:(-p['name_similarity'],p['left'],p['right']))
    save('entities/name_similarity_pairs.jsonl',alias_pairs)
    alias_graph=nx.Graph()
    alias_graph.add_edges_from((p['left'],p['right']) for p in alias_pairs)
    alias_components=sorted(nx.connected_components(alias_graph),key=lambda c:(-len(c),sorted(c)))
    save('entities/name_candidate_clusters.jsonl',[dict(cluster_id=f'EH-{i:03d}',entity_ids=sorted(c),
         labels=[er[e][0]['label_zh'] for e in sorted(c)],
         pair_count=alias_graph.subgraph(c).number_of_edges(),
         interpretation='Retrieval connected component, NOT a transitive synonym class; no merges executed') for i,c in enumerate(alias_components,1)])
    entity_summary=dict(entities=len(er), source_surface_multiple_entity_clusters=len(ambiguous_source),
                        dictionary_candidate_clusters=len(dictionary_alias), dictionary_mismatch_occurrences=len(dc),
                        fuzzy_name_pairs=len(alias_pairs),fuzzy_candidate_components=len(alias_components),fuzzy_cluster_entities=alias_graph.number_of_nodes(), fuzzy_cross_document_pairs=sum(p['cross_document'] for p in alias_pairs),
                        fuzzy_pairs_with_shared_relation_neighbor=sum(p['shared_relation_neighbor_count']>0 for p in alias_pairs),
                        entities_with_multiple_source_forms=sum(len({norm(o['surface']) for o in oo})>1 for oo in er.values()),
                        entities_across_document=sum(len({o['doc_id'] for o in oo})>1 for oo in er.values()),
                        entities_across_family_proxy=sum(len({o['family'] for o in oo})>1 for oo in er.values()))
    save('entities/summary.json',entity_summary)
    for field in ['source_surface_multiple_entity_clusters','dictionary_candidate_clusters','fuzzy_name_pairs','fuzzy_candidate_components','fuzzy_pairs_with_shared_relation_neighbor']:
        metric('entity_alignment',field,entity_summary[field],None,'retrieval_group_or_pair','expanded1456',limit='Potential alias/ambiguity only; not confirmed synonymy, merge error, or a nontrivial joint decision')
    near={name:near_pairs(name,rr) for name,rr in [('locator_pool',eligible),('expanded1456',exp)]}
    graphs={name:semantic_graph(name,layers[name]['entities'],layers[name]['claims'],rr) for name,rr in versions.items()}
    # Candidate polarity competition within identical typed keys: NOT true conflicts.
    competition=[]
    for g in cls['expanded1456']:
        rr=g['evidence']
        flags=[bool(RX['negation'].search(r['evidence_text'])) for r in rr]
        if any(flags) and not all(flags):
            competition.append(dict(cluster_id=g['cluster_id'], evidence=rr,
                                    classification='Mixed quote-level prohibition cues; semantic conflict NOT determined',
                                    matched_equipment_condition_stage=False))
    save('conflict_candidates.jsonl',competition)
    metric('conflict','mixed_quote_polarity_clusters',len(competition),len(cls['expanded1456']),'cluster','expanded1456',limit='No established same equipment+condition+stage contradiction; cue can refer to another clause')
    # Reuse original fixed source audit. It is development AI review, not Gold.
    freq=BASE+'six_checks_final_v1_20261110/frequency/'
    targets=read(freq+'representation_targets.jsonl'); judg=read(freq+'representation_judgments.json')
    freq_summary=read(freq+'semantic_frequency_summary.json'); read(freq+'page_reviews.jsonl')
    traces=read(BASE+'complex_binding_controlled_20261110/formal/pipeline_aligned/trace/target_ledger.jsonl')
    target_ledger=[]
    for target in targets:
        target_ledger.append(dict(target=target,old_AI_judgment=next(j for j in judg['judgments'] if j['target_id']==target['target_id']),
                                  existing_full_chain_trace=next(t for t in traces if t['target_id']==target['target_id']),
                                  published_page_records=[packet(r) for r in exp if f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}'==target['page_key']]))
    save('existing17_full_chain.jsonl',target_ledger)
    target_summary = dict(all_fixed_targets=len(target_ledger),
        scope_counts=dict(Counter(t['existing_full_chain_trace']['scope'] for t in target_ledger)),
        core_preservation=dict(Counter(t['old_AI_judgment']['raw_preservation'] for t in target_ledger if t['existing_full_chain_trace']['scope']!='auxiliary_only')))
    for status,count in target_summary['core_preservation'].items():
        metric('existing_AI_review','core_target_'+status,count,14,'fixed_development_target',freq+'representation_judgments.json',True,'Existing AI analysis, 3 auxiliary targets excluded, 1 remaining target has a type caveat; not independent evaluation or recoverable amount')
    quality = read(BASE+'graph_expansion_v1_20261012/quality_review.jsonl')
    quality_summary = dict(samples=len(quality), context_grades=dict(Counter(r['context_qualified_usable'] for r in quality)),
        source_supported_context_E=sum(r['source_support']=='S' and r['context_qualified_usable']=='E' for r in quality),
        warning='Existing unblinded single-AI labels, heterogeneous reasons; context E is NOT a pure condition-binding error')
    save('existing_expansion_quality.jsonl', quality)
    metric('existing_AI_review','source_supported_but_context_E',quality_summary['source_supported_context_E'],len(quality),'record',BASE+'graph_expansion_v1_20261012/quality_review.jsonl',True,quality_summary['warning'])
    metric('existing_AI_review','scope_complex_pages',freq_summary['any_complex_page_count'],freq_summary['sample_pages'],'page',freq+'page_reviews.jsonl',True,'Existing scoped AI reading, 2 pages/document; unequal sample weights; no corpus prevalence or human Gold')
    # Trace existing IDs to original candidates, rather than borrowing publication IDs.
    cross = list(csv.DictReader(source('docs/thesis/rp1_finalization_20261111/tables/version_record_id_crosswalk.csv').open()))
    save('version_parent_crosswalk.jsonl', cross)
    schema_notes = dict(page_warning_pages=sum(bool(p.get('warnings')) for p in pages.values()),
        page_warning_types=dict(Counter(str(v) for p in pages.values() for v in p.get('warnings',[]))),
        interface_rejection_reasons=dict(Counter(r['reason'] for r in rejected)),
        evidence_level_counts=dict(Counter(r.get('evidence_level') or 'missing' for r in audit)),
        eligible_stored_support_status=dict(Counter(r.get('relation_entailment_validation',{}).get('status') or 'missing' for r in eligible)),
        explicit_condition_role_counts=dict(Counter(c.get('role','missing') for r in exp for c in r.get('conditions_source',[]) or [] if isinstance(c,dict))))
    crosswalk=read('docs/thesis/rp1_finalization_20261111/tables/version_lineage.json')
    for f in ['scripts/build_rp1_graph_expansion_v1.py','scripts/build_versioned_knowledge_graph.py','scripts/run_evidence_contract_validation_experiments.py',
              'src/research_point_1_graph_evidence/stage03_schema_validation/deduplicator.py','src/research_point_1_graph_evidence/stage03_schema_validation/chinese_canonicalizer.py',
              'src/research_point_1_graph_evidence/stage03_schema_validation/evidence_span_validator.py','src/research_point_1_graph_evidence/stage03_schema_validation/relation_type_validator.py',
              BASE+'source_family_replication_pressure_v1/replication_pressure.csv',BASE+'source_family_support_v1/source_family_support_summary.json',
              'src/research_point_1_graph_evidence/stage04_graph_build/source_family_support.py']:
        source(f)
    for p in SOURCES:
        assert sha(ROOT/p)==SOURCES[p]['sha256'],p
    save('summary.json',dict(date='2026-11-13',counts=counts,raw_proposals=generation['raw_proposals'],normalization_rejects=len(rejected),
        decisions=dict(Counter(r['decision'] for r in audit)),raw_lineage=raw_lineage_summary,locator_pool_decisions=eligible_decisions,primary_pipeline_categories=dict(primary),stored_overlapping_reasons=dict(reasons),
        field_counts=field_counts,pdf_status=pdfs,pages=len(pages),exact_groups=summaries,near_pairs=near,entities=entity_summary,locator_pool_aliases=raw_alias_summary,graphs=graphs,
        published_address_pass=sum(a['locator_valid'] for a in expanded_location),expanded_lineage=crosswalk,
        source_keyword_page_counts={k:sum(k in r['tags'] for r in page_hits) for k in RX},
        fixed30_AI_source_summary=freq_summary,fixed17_scope_summary=target_summary,existing80_quality=quality_summary,additional_schema_notes=schema_notes,mixed_polarity_candidate_clusters=len(competition),
        hypothesis_counts_not_factual_truth=True,new_model_calls=0,new_graph_writes=0))
    csvout('rp1_problem_statistics.csv',sorted(METRICS,key=lambda r:(r['category'],r['population'],r['problem_type'],r['unit'])))
    save('audit_config.json',dict(date='2026-11-13',build_documents=BUILD,patterns=PATTERNS,
         retrieval=dict(name_similarity=.8,near_cosine=.68,head_tail_min=.6,one_endpoint_min=.85,neighbors=10),
         counts_are_hypotheses_not_truth=True,readonly=True,models_called=False,graph_modified=False))
    save('source_manifest.json',dict(checkout_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         script_sha256=sha(Path(__file__)),inputs=SOURCES,all_source_hashes_unchanged=True))
    print(json.dumps(dict(counts=counts,exact_groups=summaries,near_pairs=near,entities=entity_summary,published_address_pass=sum(a['locator_valid'] for a in expanded_location)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:
        manifest=json.loads((HERE/'source_manifest.json').read_text())
        for name,meta in manifest['inputs'].items():assert sha(ROOT/name)==meta['sha256'],name
        assert sha(Path(__file__))==manifest['script_sha256']
        print('PASS: source files and audit script hashes preserved; no model or graph write.')
    else:run()
