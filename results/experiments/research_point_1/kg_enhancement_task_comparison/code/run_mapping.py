"""Build occurrence/fact/Assertion/Claim/source correspondence for one base KG."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from inputs import TASK, ROOT, REV, GRAPH, RAW, AUDIT, NORMALIZED, IdLinks, load, save, identifier, norm, record_ids, core_tuple, source_identity, source_pointer, address_check, digest

OUT = TASK / "runs/20261113_v1"


def main():
    d = load()
    links = IdLinks()
    stages = ["raw", "audit", "normalized"]
    rows_by_stage = {key: d[key] for key in stages}
    rows_by_stage["current_graph"] = d["graph"]["source_records"]
    source_ids = defaultdict(set)
    for rows in rows_by_stage.values():
        for row in rows:
            ids = record_ids(row)
            links.add(ids)
            source_ids[source_identity(row)].update(ids)
    for ids in source_ids.values():
        links.add(sorted(ids))
    by_stage = {key: defaultdict(list) for key in rows_by_stage}
    all_ids = defaultdict(set)
    for key in list(links.parents):
        all_ids[links.find(key)].add(key)
    for stage, rows in rows_by_stage.items():
        for i, row in enumerate(rows):
            root = links.find(record_ids(row)[0])
            by_stage[stage][root].append((i, row))

    graph_sources = d["graph"]["source_records"]
    graph_by_core = defaultdict(list)
    graph_surface_concepts = defaultdict(set)
    for row in graph_sources:
        graph_by_core[core_tuple(row)].append(row)
        for side in ["head", "tail"]:
            graph_surface_concepts[row[side + "_type"], norm(row[side + "_surface"])].add(norm(row[side + "_canonical_zh"]))
    claims = {row["claim_id"]: row for row in d["graph"]["claims"]}
    assertions = {row["assertion_id"]: row for row in d["graph"]["evidence_assertions"]}
    assert len(claims) == 1400 and len(assertions) == len(graph_sources) == 1456
    assert {r["expanded_assertion_id"] for r in graph_sources} == set(assertions)

    occurrence_rows, normalized_groups, graph_rows = [], {}, []
    for index, original in enumerate(d["raw"]):
        root = links.find(record_ids(original)[0])
        preferred_stage = next(stage for stage in reversed(stages) if by_stage[stage].get(root))
        preferred = [row for _, row in by_stage[preferred_stage][root]]
        core_variants = {core_tuple(row) for row in preferred}
        representative = preferred[0]
        lineage_graph = [row for _, row in by_stage["current_graph"].get(root, [])]
        exact_core_graph = [row for key in core_variants for row in graph_by_core.get(key, [])]
        alias_graph = []
        for row in preferred:
            h = graph_surface_concepts.get((row["head_type"], norm(row["head_surface"])), set())
            t = graph_surface_concepts.get((row["tail_type"], norm(row["tail_surface"])), set())
            for hc in h:
                for tc in t:
                    alias_graph.extend(graph_by_core.get((row["head_type"], hc, row["relation"], row["tail_type"], tc), []))
        if lineage_graph:
            category = "current_graph_lineage_present"
        elif exact_core_graph:
            category = "same_normalized_core_tuple_no_lineage"
        elif alias_graph:
            category = "source_alias_core_match_needs_semantic_review"
        elif len(core_variants) > 1:
            category = "ambiguous_normalization_unpublished"
        else:
            category = "unpublished_no_detected_core_match"
        normalized_id = "NCF-" + identifier(sorted(core_variants))
        occurrence_id = f"RAW-{index + 1:05d}"
        audits = [row for _, row in by_stage["audit"].get(root, [])]
        audit_statuses = sorted({row.get("decision", "unknown") for row in audits})
        reasons = sorted({reason for row in audits for reason in row.get("rejection_reasons", []) + row.get("review_reasons", [])})
        src = d["pages"][original["doc_id"], original["pdf_page_number"]]
        current = {row["expanded_assertion_id"]: row for row in lineage_graph + exact_core_graph + alias_graph}
        mapped = dict(raw_occurrence_id=occurrence_id, raw_triple_id=original["triple_id"],
            normalization_lineage_id="LIN-" + identifier(sorted(all_ids[root])),
            all_linked_record_ids=sorted(all_ids[root]),
            normalized_candidate_fact_id=normalized_id, normalized_core_variants=sorted(core_variants),
            normalization_representation=preferred_stage, normalization_ambiguous=len(core_variants) > 1,
            candidate_category=category, historical_audit_statuses=audit_statuses, historical_reasons=reasons,
            audit_record_ids=sorted({row["triple_id"] for row in audits}),
            normalized_record_ids=sorted({row["triple_id"] for row in preferred}),
            current_lineage_assertion_ids=sorted({row["expanded_assertion_id"] for row in lineage_graph}),
            current_core_match_assertion_ids=sorted({row["expanded_assertion_id"] for row in exact_core_graph}),
            current_alias_candidate_assertion_ids=sorted({row["expanded_assertion_id"] for row in alias_graph}),
            current_candidate_claim_ids=sorted({row["expanded_claim_id"] for row in current.values()}),
            original_source=source_pointer(original), normalized_source=source_pointer(representative),
            original_address_check=address_check(original, src),
            normalized_address_checks=[dict(record_id=row["triple_id"], **address_check(row, d["pages"][row["doc_id"], row["pdf_page_number"]])) for row in preferred],
            equivalence_limit="Lineage/core/alias mapping does not certify semantic identity, qualifier equivalence, source support or independent corroboration",
            semantic_source_review_status="not_reviewed_in_this_phase")
        occurrence_rows.append(mapped)
        group = normalized_groups.setdefault(normalized_id, dict(normalized_candidate_fact_id=normalized_id,
            core_variants=sorted(core_variants), raw_occurrence_ids=[], candidate_categories=Counter(),
            historical_statuses=set(), current_candidate_claim_ids=set(), source_pages=set(),
            semantic_verified_fact=False, conditions_not_part_of_core_key=True))
        group["raw_occurrence_ids"].append(occurrence_id)
        group["candidate_categories"][category] += 1
        group["historical_statuses"].update(audit_statuses)
        group["current_candidate_claim_ids"].update(mapped["current_candidate_claim_ids"])
        group["source_pages"].add((original["doc_id"], original["pdf_page_number"]))

    for row in graph_sources:
        assertion = assertions[row["expanded_assertion_id"]]
        claim = claims[row["expanded_claim_id"]]
        assert assertion["claim_id"] == claim["claim_id"]
        root = links.find(record_ids(row)[0])
        graph_rows.append(dict(assertion_id=assertion["assertion_id"], claim_id=claim["claim_id"],
            current_entity_ids=[claim["head_entity_id"], claim["tail_entity_id"]], core_tuple=core_tuple(row),
            parent_ids=record_ids(row), current_source=source_pointer(row),
            raw_occurrence_ids=[f"RAW-{i + 1:05d}" for i, _ in by_stage["raw"].get(root, [])],
            audit_record_ids=sorted({r["triple_id"] for _, r in by_stage["audit"].get(root, [])}),
            historical_status_is_not_current_revalidation=True,
            current_expansion_validation=row.get("expansion_validation"),
            assertion_conditions=assertion.get("conditions_source"), assertion_modality=assertion.get("modality"),
            current_address_check=address_check(row, d["pages"][row["doc_id"], row["pdf_page_number"]])))
    fact_rows = []
    for group in normalized_groups.values():
        group["candidate_categories"] = dict(group["candidate_categories"])
        for key in ["historical_statuses", "current_candidate_claim_ids", "source_pages"]:
            group[key] = sorted(group[key])
        group["raw_occurrence_count"] = len(group["raw_occurrence_ids"])
        fact_rows.append(group)

    statuses = Counter(row.get("decision", "unknown") for row in d["audit"])
    summary = dict(input_git_commit=REV, sole_base_graph="expanded1456", build_documents=len(d["manifest"]), physical_pages=len(d["pages"]),
        raw_candidate_occurrences=len(d["raw"]), unique_raw_record_ids=len({r["triple_id"] for r in d["raw"]}),
        audited_records=len(d["audit"]), audit_statuses=dict(statuses),
        normalized_candidate_core_groups=len(fact_rows), normalized_core_groups_are_not_correct_fact_count=True,
        current_assertions=len(assertions), current_claims=len(claims), current_entities=len(d["graph"]["entities"]),
        raw_occurrence_categories=dict(Counter(r["candidate_category"] for r in occurrence_rows)),
        distinct_core_groups_by_occurrence_category={key:len({r["normalized_candidate_fact_id"] for r in occurrence_rows if r["candidate_category"] == key}) for key in sorted({r["candidate_category"] for r in occurrence_rows})},
        graph_assertions_with_raw_lineage=sum(bool(r["raw_occurrence_ids"]) for r in graph_rows),
        graph_assertions_without_raw_lineage=sum(not r["raw_occurrence_ids"] for r in graph_rows),
        audited_records_without_raw_lineage=sum(len(rows) for root, rows in by_stage["audit"].items() if not by_stage["raw"].get(root)),
        normalization_ambiguous_occurrences=sum(r["normalization_ambiguous"] for r in occurrence_rows),
        source_semantically_supported_fact_count=None,
        source_semantically_supported_fact_count_reason="Not yet semantically reviewed; address checks and historical automatic gates are reported separately",
        task4_existing_knowledge_enrichment="Separate current_assertion_review ledger required; overlaps category1",
        task5_document_omission="Requires source-first sample; graph absence alone never a positive omission label",
        historical_graphs_loaded=0, formal_graph_writes=0, new_model_calls=0)
    for group in fact_rows:
        group["candidate_categories"] = dict(group["candidate_categories"])
    save(OUT / "mapping/raw_occurrence_mapping.jsonl", occurrence_rows)
    save(OUT / "mapping/normalized_candidate_facts.jsonl", fact_rows)
    save(OUT / "mapping/current_assertion_source_mapping.jsonl", graph_rows)
    save(OUT / "mapping/summary.json", summary)
    save(OUT / "mapping/input_manifest.json", dict(input_git_commit=REV, allowed_graph_prefix=GRAPH,
        input_sha256=d["inputs"].hashes, program_sha256=digest(Path(__file__).read_bytes()),
        input_module_sha256=digest((TASK / "code/inputs.py").read_bytes()), other_graph_inputs=0))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
