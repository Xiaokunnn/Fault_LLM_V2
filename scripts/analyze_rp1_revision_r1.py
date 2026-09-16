"""Reproduce reviewer-requested RP1 analyses from frozen records, without API calls.

All outputs are revision-only analyses. No upstream decisions or graph files are
modified. The basic baseline deliberately ignores full-gate results when selecting
records. Audit metrics describe source recoverability, not factual accuracy.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from run_evidence_contract_validation_experiments import (
    audit_record, load_pages, normalized, PROVENANCE_FIELDS, read_jsonl,
    sha256_file, load_provenance_schema,
)
from research_point_1_graph_evidence.stage05_evaluation.rp1_b0_ours import (
    relation_schema_gate, evidence_grounding_gate, relation_entailment_gate,
    provenance_and_split_gate,
)

OUT = ROOT / "results/experiments/research_point_1/revision_r1_20260905"
CORPUS = ROOT / "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl"
TERMS = ROOT / "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full"
CMP = ROOT / "results/experiments/research_point_1/api_prompt_comparison_v1"
BUILD = frozenset([f"MP{i:03}" for i in range(1, 8)] + [f"MP{i:03}" for i in range(15, 23)])


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def table(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def primary_failure(record):
    reasons = set(record.get("rejection_reasons", []))
    for group, codes in [
        ("schema_type", {"schema_invalid", "relation_type_invalid"}),
        ("evidence", {"evidence_invalid"}),
        ("relation_support", {"relation_not_entailed", "dual_qwen_relation_not_entailed"}),
        ("below_candidate_0.60", {"below_candidate_confidence"}),
    ]:
        if reasons & codes:
            return group
    raise ValueError(f"Unmapped rejection reasons: {reasons}")


def hard_pass(record):
    return (relation_schema_gate(record) and evidence_grounding_gate(record)
            and relation_entailment_gate(record)
            and provenance_and_split_gate(record, build_doc_ids=BUILD))


def basic_filter(records, pages):
    """Complete native fields + page co-occurrence + within-page deduplication.

    No relation-type mapping, full-gate labels, scores, quotations, table alignment,
    or semantic validation enter selection. Cross-page support stays distinct.
    """
    kept, seen = [], set()
    for r in records:
        h, t = [normalized(r.get(s + "_surface", r.get(s))) for s in ("head", "tail")]
        rel = normalized(r.get("relation"))
        key = (r["doc_id"], r["pdf_page_number"], h, rel, t)
        if not all((h, t, rel, r.get("head_type"), r.get("tail_type"))) or h == t:
            continue
        text = normalized(pages[key[:2]]["page_text"])
        if h not in text or t not in text or key in seen:
            continue
        seen.add(key)
        kept.append(r)
    return kept


def baseline_rows(pages, schema):
    # Cache records already have normalized surfaces and parser metadata.
    shared = read_jsonl(CMP / "Ours/strict/candidate_triples.strict_v2.jsonl")
    assert len(shared) == 367 and len({(r['doc_id'], r['pdf_page_number']) for r in shared}) == 20
    direct = []
    for i, proposal in enumerate(read_jsonl(CMP / "B0/rejected_model_proposals.jsonl")):
        doc, page = proposal["page_key"].split(":p")
        p = pages[(doc, int(page))]
        r = dict(proposal["proposal"])
        # Supply the same parser-side provenance to both extraction configurations.
        for field in PROVENANCE_FIELDS:
            r[field] = p.get(field)
        r.update(triple_id=f"B0-native-{i:03}", evidence_level=str(r.get("evidence_mode", ""))[:2])
        direct.append(r)
    assert len(direct) == 162
    full = [r for r in shared if r.get("decision") == "silver_candidate"]
    assert len(full) == 148
    basic_ids = {r['triple_id'] for r in basic_filter(shared, pages)}
    lost = [r for r in full if r['triple_id'] not in basic_ids]
    dump('basic_missed_qualified.json', dict(records=len(lost), evidence_levels=dict(Counter(r['evidence_level'] for r in lost)),
        triple_ids=[r['triple_id'] for r in lost]))
    selections = [
        ("Direct LLM", "open", direct),
        ("Direct LLM + basic", "open", basic_filter(direct, pages)),
        ("Shared extraction: no gate", "shared", shared),
        ("Shared extraction: basic", "shared", basic_filter(shared, pages)),
        ("Shared extraction: full", "shared", full),
    ]
    rows, record_rows = [], []
    for name, group, selected in selections:
        counts = Counter()
        for r in selected:
            r = dict(r)
            r.setdefault("evidence_level", str(r.get("evidence_mode", ""))[:2])
            audited = audit_record(r, pages, schema=schema)
            c = audited["checks"]
            counts["evidence"] += c["evidence_located"]
            # Both endpoints must be inside the actual located evidence.
            counts["endpoints"] += c["evidence_located"] and c["endpoints_located_in_evidence"]
            counts["provenance"] += all(c[k] for k in (
                "provenance_fields_complete", "source_metadata_match", "page_payload_hash_valid"))
            record_rows.append(dict(method=name, triple_id=r['triple_id'], doc_id=r['doc_id'],
                                    page=r['pdf_page_number'], **c))
        rows.append(dict(method=name, extraction=group, records=len(selected),
                         evidence_count=counts['evidence'], evidence_pct=round(100*counts['evidence']/len(selected),2),
                         endpoints_count=counts['endpoints'], endpoints_pct=round(100*counts['endpoints']/len(selected),2),
                         provenance_pct=round(100*counts['provenance']/len(selected),2),
                         evidence_qualified=sum(r.get('decision') == 'silver_candidate' for r in selected) if group == 'shared' else None))
    table("baseline.csv", rows)
    dump("baseline_audit_records.json", record_rows)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = [CORPUS, TERMS / 'candidate_triples.zh_local_full.jsonl', TERMS / 'terminology_unresolved.json',
              CMP / 'Ours/strict/candidate_triples.strict_v2.jsonl', CMP / 'B0/rejected_model_proposals.jsonl',
              ROOT / 'configs/document_split_marine_pump_v4.json',
              ROOT / 'data/kg/marine_pump/schema/provenance_schema_v3.json',
              ROOT / 'results/experiments/research_point_1/evidence_contract_validation_v1/all_candidate_audit_records.jsonl']
    pages, duplicates, page_files = load_pages(ROOT / 'data/interim/parsed_pages/corpus_v2')
    assert not duplicates
    inputs += page_files
    before = {str(p.relative_to(ROOT)): sha256_file(p) for p in inputs}
    records = read_jsonl(CORPUS)
    assert Counter(r['decision'] for r in records) == {'silver_candidate':1698, 'rejected':5424, 'candidate_needs_review':881}
    audit = {r['triple_id']:r for r in read_jsonl(inputs[7])}
    primary, overlapping, recovered = Counter(), Counter(), Counter()
    failures = []
    for r in records:
        if r['decision'] != 'rejected':
            continue
        key = primary_failure(r)
        primary[key] += 1
        overlapping.update(set(r['rejection_reasons']))
        if audit[r['triple_id']]['locator_contract_pass']:
            recovered[key] += 1
        failures.append(dict(triple_id=r['triple_id'], doc_id=r['doc_id'], primary_failure=key,
                             all_reasons=';'.join(r['rejection_reasons'])))
    assert sum(primary.values()) == 5424 and sum(recovered.values()) == 1707
    rejection = dict(primary=dict(primary), overlapping=dict(overlapping),
                     primary_among_1707_reaudit_passed=dict(recovered),
                     attribution_order=['schema_type','evidence','relation_support','below_candidate_0.60'])
    dump('rejections.json', rejection)
    table('rejection_records.csv', failures)
    residual = [r for r in records if r['decision']=='rejected' and
                audit[r['triple_id']]['locator_contract_pass'] and primary_failure(r)=='evidence']
    dump('rejections_reaudit_residual.json', dict(records=len(residual),
        evidence_levels=dict(Counter(r['evidence_level'] for r in residual)),
        overlapping_failure_flags=dict(Counter(x for r in residual for x in r['evidence_validation'].get('hard_veto_reasons',[])))))

    base = [r for r in records if hard_pass(r)]
    assert len(base) == 1704
    def retained(e2, rs, threshold):
        return {r['triple_id'] for r in base
                if round(float(r['model_confidence']) * (e2 if r['evidence_level']=='E2' else 1.0) * rs,6) >= threshold}
    original = retained(.95,1,.8)
    assert len(original)==1698
    assert original == {r['triple_id'] for r in records if r['decision']=='silver_candidate'}, 'Original setting must reproduce exact frozen membership'
    sweep = []
    for e2 in [.85,.90,.95,1.0]:
        for rs in [.90,.95,1.0]:
            for threshold in [.75,.80,.85,.90,.925,.95,.975]:
                keep = retained(e2,rs,threshold)
                sweep.append(dict(e2_weight=e2, supported_weight=rs, threshold=threshold, records=len(keep),
                                  e2_records=sum(r['triple_id'] in keep and r['evidence_level']=='E2' for r in base),
                                  gained=len(keep-original),lost=len(original-keep),
                                  jaccard=round(len(keep&original)/len(keep|original),6)))
    table('weight_threshold_sensitivity.csv',sweep)
    # E3/undetermined changes cannot relax the unchanged hard conditions.
    assert all(r['evidence_level'] in {'E1','E2'} and r['relation_entailment_validation']['status']=='entailed' for r in base)
    dump('nonadmissible_weight_sensitivity.json',dict(e3_weights=[.5,.75,1],undetermined_weights=[.5,.75,1],
        combinations=9,admission_counts=[1698]*9,explanation='E3 and undetermined relations fail mandatory hard conditions at every weight.'))

    zh = [r for r in read_jsonl(TERMS/'candidate_triples.zh_local_full.jsonl') if r['decision']=='silver_candidate']
    excluded = [r for r in zh if not r['eligible_for_chinese_graph']]
    assert len(zh)==1698 and len(excluded)==372
    patterns={}
    for field in ['doc_id','relation','head_type','tail_type']:
        total=Counter(r[field] for r in zh)
        no=Counter(r[field] for r in excluded)
        patterns[field]=[dict(group=k,total=v,excluded=no[k],excluded_pct=round(100*no[k]/v,2)) for k,v in total.most_common()]
        table('terminology_'+field+'.csv',patterns[field])
    unresolved=json.loads((TERMS/'terminology_unresolved.json').read_text(encoding='utf-8'))
    reasons=Counter(r['decision_reason'] for r in unresolved)
    assert len(unresolved)==286
    def term_key(entity_type, surface):
        return entity_type, ' '.join(unicodedata.normalize('NFKC',str(surface)).casefold().split())
    pending={term_key(x['entity_type'],s):x for x in unresolved for s in x['source_forms']}
    term_sweep=[]
    for threshold in [.85,.88,.90]:
        retained_count=0
        for r in zh:
            passes=[]
            for side in ('head','tail'):
                if r['chinese_canonicalization'][side]['graph_ready']:
                    passes.append(True)
                else:
                    k=term_key(r[side+'_type'],r.get(side+'_surface',r.get(side)))
                    candidate=pending.get(k)
                    passes.append(bool(candidate and candidate['decision_reason'] in {
                        'singleton_below_confidence','repeated_candidate_below_confidence'} and
                        candidate['minimum_translation_confidence']>=threshold))
            retained_count+=all(passes)
        term_sweep.append(dict(threshold=threshold,records=retained_count))
    assert term_sweep[-1]['records']==1326
    table('terminology_threshold_relaxation.csv',term_sweep)
    lengths={}
    for label,rows in [('included',[r for r in zh if r['eligible_for_chinese_graph']]),('excluded',excluded)]:
        lengths[label]=dict(records=len(rows), median_max_endpoint_words=statistics.median(
            max(len(str(r.get(s+'_surface',r.get(s,''))).split()) for s in ('head','tail')) for r in rows))
    dump('terminology.json',dict(excluded_records=372,unresolved_endpoint_groups=286,
                               endpoint_reasons=dict(reasons),patterns=patterns,lengths=lengths))
    schema=load_provenance_schema(project_root=ROOT)
    baseline=baseline_rows(pages,schema)
    after={str(p.relative_to(ROOT)):sha256_file(p) for p in inputs}
    assert before==after, 'Frozen inputs changed during analysis'
    dump('manifest.json',dict(version='revision_r1_20260905',model_api_called=False,human_labels_used=False,
        frozen_inputs_unchanged=True,inputs=before,script_sha256=sha256_file(Path(__file__)),
        split_scope='Build records only; original 20 build pages for baseline; no held-out tuning',
        sensitivity_scope='Post-submission descriptive perturbations; no parameter reselection'))
    dump('summary.json',dict(baseline=baseline,rejections=rejection,hard_gate_pool=len(base),
                            terminology_endpoint_reasons=dict(reasons),lengths=lengths,
                            sensitivity_at_threshold_080=[r for r in sweep if r['threshold']==.8]))
    print(json.dumps(json.loads((OUT/'summary.json').read_text(encoding='utf-8')),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
