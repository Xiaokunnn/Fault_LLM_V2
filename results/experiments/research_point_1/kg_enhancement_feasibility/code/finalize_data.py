"""Close data investigation before literature-based route comparison."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from investigate import Archive,ROOT,TASK,REV,PREFIXES,read,save,sha

OUT=TASK/"runs/20261113_v1"

def fraction(n,d,meaning):return dict(count=n,denominator=d,percentage=round(100*n/d,4) if d else None,meaning=meaning)

def graphml_check(ar,label,prefix):
    path=prefix+"graph.graphml" if label=="expanded1456" else ("data/kg/marine_pump/graph_versions/KG_v1_validated/marine_pump_graph.graphml" if label=="strict208" else prefix.rsplit("/triples/",1)[0]+"/graph_versions/KG_v1_validated/marine_pump_graph.graphml")
    root=ET.fromstring(ar.raw(path));ns={"g":"http://graphml.graphdrawing.org/xmlns"};g=root.find("g:graph",ns)
    nodes={n.attrib["id"] for n in g.findall("g:node",ns)};edges=g.findall("g:edge",ns)
    claims=ar.get(prefix+"claims.jsonl");entities=ar.get(prefix+"entities.jsonl");evidence=ar.get(prefix+"evidence_assertions.jsonl")
    expected_nodes={r["entity_id"] for r in entities};endpoints={(e.attrib["source"],e.attrib["target"]) for e in edges}
    if label=="expanded1456":
        expected_edges={(c["head_entity_id"],c["tail_entity_id"]) for c in claims}
        edge_ids={e.attrib["id"] for e in edges};valid=nodes==expected_nodes and expected_edges<=endpoints and edge_ids=={c["claim_id"] for c in claims}
    else:
        expected_nodes|={c["claim_id"] for c in claims}|{e["evidence_id"] for e in evidence}
        links=ar.get(prefix+"claim_evidence_links.jsonl")
        expected_edges={(c["head_entity_id"],c["claim_id"]) for c in claims}|{(c["claim_id"],c["tail_entity_id"]) for c in claims}|{(lk["claim_id"],lk["evidence_id"]) for lk in links}
        valid=nodes==expected_nodes and endpoints==expected_edges and len(edges)==len(claims)*2+len(links)
    if not valid:raise ValueError("GraphML projection differs: "+label)
    return dict(layer=label,path=path,nodes=len(nodes),edges=len(edges),jsonl_topology_consistent=True)

def main():
    ar=Archive();graphml=[graphml_check(ar,k,p) for k,p in PREFIXES.items()]
    inv=read(OUT/"inventory/summary.json");integ=read(OUT/"integrity/summary.json");pub=read(OUT/"publication/summary.json");deep=read(OUT/"deeper/summary.json");review=read(OUT/"case_review/summary.json")
    problems=[
      dict(id="P01",name="Evidence-qualified records not released to the Chinese graph",definition="Declared automatic evidence gate passed but source-record identity not in standard1326; not LLM-generation omission or expert-confirmed missed facts.",
        metric=fraction(pub["outside_standard"],pub["qualified_records"],"release membership only"),evidence=["publication/qualified_record_membership.jsonl"],
        diagnosis_impact="Potential source evidence unavailable to downstream graph queries; actual diagnostic relevance is not established for every record.",data_sufficiency="372 traceable records, but no independent semantic completeness labels.",
        engineering="Terminology status/protected-token governance first; lowering thresholds does not verify meaning.",algorithm_research="INCONCLUSIVE",evaluation_boundary="Can prove version membership and executable gate reason, not factual recall or safe usability."),
      dict(id="P02",name="Source-surface identity split and type ambiguity",definition="Same typed conservative source form maps to more than one published node; unlike same label with different types, it is an alignment candidate, not automatic equivalence.",
        metric=fraction(10,2022,"10 implicated nodes in 5 candidate groups; candidate incidence, not an error rate"),candidate_groups=5,confirmed_AI_groups=4,unresolved_groups=1,cases=["C01","C02","C03","C04","C05"],evidence=["integrity/entity_alignment_candidates.jsonl","deeper/alias_sensitivity.json"],
        diagnosis_impact="Equivalent symptoms/actions can fragment retrieval and apparent chains.",data_sufficiency="Only five probe groups; no evidence that a learned aligner is necessary.",engineering="Dictionary/nominalization cleanup is plausible; four-group AI review and all-five hypothetical merge are not interchangeable.",algorithm_research="NO-GO for a new aligner justified only by these cases",evaluation_boundary="Shows lexical splits and sensitivity without proving general semantic equivalence."),
      dict(id="P03",name="Polarity and normative/observational meaning mismatch",definition="Positive graph reading is not justified by the source prohibition or design obligation; source location and legal endpoint types do not establish entailment.",
        metric=fraction(3,1326,"At least 3 AI-audited semantic mismatches among 1326; targeted English probes, not an unbiased defect-rate estimate"),subtypes={"literal_prohibition_mismatch":1,"normative_statement_cast_as_positive_cause":2},cases=["C07","C08","C09","C10"],
        evidence=["packets/record_issue_candidates.jsonl","deeper/negated_causal_candidates.jsonl"],diagnosis_impact="A prohibition may become an unsuitable operating condition; a design requirement may become an unsupported causal explanation.",
        data_sufficiency="Three source-anchored cases plus one retained-negation counterexample; too small for algorithm efficacy claims.",engineering="Known cases allow conservative blocking/correction; generic operator preservation still needs empirical assessment, not assumed inability of rules.",algorithm_research="INCONCLUSIVE",evaluation_boundary="Source-proposition mismatch, not proof of real-world causal impossibility or equipment diagnostic accuracy."),
      dict(id="P04",name="Declared domain scope not respected by some source propositions",definition="Published targets explicitly name other machinery despite a document scope restricted to pumps/piping; transferable mechanisms remain unresolved rather than automatically excluded.",
        metric=fraction(7,1326,"7 AI-supported out-of-declared-scope records observed; 10 keyword candidates reviewed, 3 scope-transfer cases unresolved; not full corpus error rate"),cases=["C10","C11"],
        evidence=["deeper/scope_candidates.jsonl","../../case_specs.json"],diagnosis_impact="Propeller/crankshaft procedures may contaminate pump queries or misleading evidence chains.",data_sufficiency="Ten probe records, seven supported within the declared boundary.",
        engineering="Document/section/equipment applicability checks should precede model design.",algorithm_research="NO-GO as a stand-alone innovation from current evidence",evaluation_boundary="Can flag explicit scope mismatch; cannot decide all cross-machine transferability from keywords."),
      dict(id="P05",name="Qualifiers not independently bound in semantic payload",definition="Source condition/negation/modality/alternative/sequence wording may live in evidence or endpoints, with no explicit operator-bound fields. Lack of fields alone is not lost knowledge.",
        metric=fraction(integ["standard1326"]["source_cue_records"],1326,"English cue-bearing evidence records; a proxy, not 630 defective relations"),source_cue_not_in_endpoints=fraction(374,1326,"374 cue-category differences between evidence and endpoint text; evidence remains retained"),
        cases=["C08","C16","C17","C18","C19","C20"],evidence=["integrity/qualifier_proxies.jsonl","case_review/cases.jsonl"],diagnosis_impact="Different operating modes, units, branches and temporal prerequisites may be used outside their actual context.",
        data_sufficiency="Several traceable positive/counterexamples and broad lexical candidates, but no exhaustive operator-label benchmark or same-budget method failure proof.",engineering="Schema/serialization and literal qualifier retention are necessary transparent controls; difficult binding cases not yet isolated from them.",
        algorithm_research="INCONCLUSIVE; priority for further problem isolation, not a chosen architecture",evaluation_boundary="Can measure observable representation placement; cannot infer global semantic loss or prevalence from cue matches."),
      dict(id="P06",name="Fragmented topology versus actual missing knowledge",definition="A FaultMode does not simultaneously have an incoming causal edge and outgoing mitigation/prevention edge; this chosen graph pattern is not a universal diagnostic requirement.",
        metric=fraction(integ["standard1326"]["structural_role_gap_fault_nodes"],integ["standard1326"]["fault_nodes"],"223/239 structural-role gaps, not missing-fact rate"),
        other_layer_role_counterparts=3,evidence=["integrity/fault_role_gaps.jsonl","integrity/topology.jsonl","deeper/role_gap_cross_layer.jsonl","deeper/alias_sensitivity.json"],
        diagnosis_impact="Graph traversal can stop because of naming, release selection or intentionally atomic knowledge, not because a physical causal link exists but is absent.",
        data_sufficiency="All structural nodes checked; no independent labelled missing-edge universe.",engineering="At least three gap roles occur in another existing tier; alias projection reduces four components without adding knowledge edges.",
        algorithm_research="NO-GO for treating topology gaps as training positives or prespecifying link prediction",evaluation_boundary="Can count connectivity and role incidence; cannot derive causal transitivity or evidence for a new edge."),
      dict(id="P07",name="Sparse independent-source corroboration",definition="Multiple evidence occurrences from one source family are not independent confirmations. Different-family canonical matches still require object/condition verification.",
        metric=fraction(integ["standard1326"]["multi_family_claims"],1281,"0/1281 governed claims with multiple recorded source families; metadata proxy, not proof no corroborating text exists"),multi_evidence_same_family_claims=28,
        candidate_different_family_matches=4,conditional_evidence_addition=1,insufficient_matches=3,cases=["C06","C12","C13"],evidence=["integrity/claim_source_families.jsonl","publication/cross_family_candidate_matches.jsonl"],
        diagnosis_impact="Repeated pages/languages can be mistaken for corroboration; generic endpoints can create false matches.",data_sufficiency="One condition-supported additional evidence candidate, not a new atomic relation; no adequate independent-source truth benchmark.",
        engineering="Source-family deduplication and retaining object-specific evidence first.",algorithm_research="INCONCLUSIVE for probabilistic truth discovery; current corroboration labels inadequate",evaluation_boundary="Counts recorded families, not statistical independence or truth probability."),
      dict(id="P08",name="First-record attribute projection loss",definition="For one merged claim the graph builder's retained fault_class_ids does not contain the union of its source-record tags.",
        metric=fraction(1,1281,"one observed claim projection discrepancy"),cases=["C06"],evidence=["integrity/claim_attribute_projection_loss.jsonl"],
        diagnosis_impact="A claim-level fault-category lookup may fail despite source evidence and category tags still being present.",data_sufficiency="One fully traceable multi-language claim, enough for an engineering regression test but not an algorithm paper.",
        engineering="Set-union projection is a transparent prospective repair; verify category semantics separately. No repair applied here.",algorithm_research="NO-GO",evaluation_boundary="Proves aggregation mismatch, not correctness of every upstream automatic fault tag."),
      dict(id="P09",name="Export view lacks detailed native addresses but full source archive retains them",definition="Evidence export and graph display omit some offsets/cells that are still stored in source_records; this is a view/interface boundary, not deleted source evidence.",
        metric=fraction(1326,1326,"all standard evidence exports lack explicit evidence_start/evidence_units fields; full records retain E1/E2 data"),
        full_E1_exact=1189,full_E2_whitespace_equal_records=137,evidence=["deeper/export_projection.jsonl","deeper/address_completeness.jsonl","case_review/native_cell_text_differences.jsonl"],
        diagnosis_impact="A consumer reading only the compact view may be unable to inspect the exact table or local context.",data_sufficiency="All source addresses inspected; five standard cell-text byte differences are whitespace-only, not missing evidence.",
        engineering="Explicit source-record joins or lossless view adapters; no inferred bbox and no frozen artifact retrofit.",algorithm_research="NO-GO",evaluation_boundary="Shows field projection and address roundtrip, not relation entailment."),
      dict(id="P10",name="Formal qualifier contract differs from experimental sidecars",definition="v3 Claim/EvidenceAssertion definitions have no explicit conditions/polarity/modality fields; DocumentSource has broad applicability_scope, and experimental records add sidecar context outside that formal contract.",
        metric=fraction(0,2,"0 of the two relevant formal record definitions explicitly models the selected per-assertion operator fields; not a schema-invalid-record count"),
        cases=["C16","C17","C18","C20"],evidence=["case_review/summary.json"],diagnosis_impact="Conditions cannot yet be independently validated/queried through one common formal interface; broad document scope cannot substitute local procedure guards.",
        data_sufficiency="Direct schema inspection establishes the interface gap, not the benefit of any particular reasoning model.",engineering="Versioned schema/interface design and compatibility tests before research models; do not modify the existing frozen schema in this investigation.",
        algorithm_research="INCONCLUSIVE for semantic binding; schema work alone is engineering",evaluation_boundary="Static inspection is not full JSON-Schema conformance or factual verification.")
    ]
    hashes=read(OUT/"inventory/local_source_hashes.jsonl");checks=[]
    for r in hashes:
        p=ROOT/r["relative_path"];actual=sha(p.read_bytes()) if p.exists() else None
        if actual!=r["sha256"]:raise ValueError("Source PDF changed")
        checks.append(dict(path=r["relative_path"],sha256=actual,preserved=True))
    save(OUT/"verification/graphml_consistency.jsonl",graphml);save(OUT/"verification/source_preservation.jsonl",checks)
    save(TASK/"problem_register.json",dict(input_git_commit=REV,problems=problems,independent_ground_truth=False,
        categories_overlap=True,all_denominators_explicit=True,new_model_calls=0,formal_graph_modifications=0))
    decision=dict(status="INCONCLUSIVE",question="Whether knowledge enhancement should become a new RP1 core algorithm contribution",
        most_actionable_now="Source-qualified semantic meaning/applicability preservation plus confirmed engineering normalization/projection defects",
        supported_observations="20 disclosed AI diagnostic propositions, 30 referenced record IDs, 26 source pages; not independent field cases or a true accuracy benchmark",
        beyond_simple_rules_demonstrated=False,
        algorithm_architecture_selected=False,prespecified_B0_B1_B2_B3_cancelled=True,
        topology_only_missing_edge_research="NO-GO under this evidence basis",
        reason="Current evidence establishes data/representation problems and counterexamples, not stable failure of transparent engineering controls or a sufficient independent evaluation dataset.",
        no_new_algorithm_implemented=True,stop_after_report_and_wait_for_user=True)
    save(TASK/"decision_before_literature.json",decision)
    save(OUT/"verification/data_phase_seal.json",dict(input_git_commit=REV,extra_graphml_input_sha256=ar.hashes,
        problem_register_sha256=sha((TASK/"problem_register.json").read_bytes()),
        evidence_hashes={str(p.relative_to(OUT)):sha(p.read_bytes()) for p in [OUT/"inventory/summary.json",OUT/"integrity/summary.json",OUT/"publication/summary.json",OUT/"case_review/summary.json",OUT/"case_review/cases.jsonl"]},
        step4_literature_search_not_yet_started=True))
    print(json.dumps(dict(graphml_checks=graphml,source_PDFs_preserved=len(checks),problems=len(problems),decision=decision),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
