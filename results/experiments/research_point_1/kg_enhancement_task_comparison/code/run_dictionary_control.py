"""Typed current-record terminology dictionary, not a learned aligner."""
from collections import defaultdict
import json
from pathlib import Path
from inputs import TASK, REV, load, norm, save, digest
from run_baselines import OUT, read


def main():
    d=load();dictionary=defaultdict(set);provenance=defaultdict(set)
    for row in d["graph"]["source_records"]:
        for side in ["head","tail"]:
            typ=row[side+"_type"];label=norm(row[side+"_canonical_zh"])
            forms=[row[side+"_surface"],row[side+"_canonical_zh"]]
            forms.extend(f["surface"] for f in row.get("chinese_canonicalization",{}).get(side,{}).get("source_forms",[]) if f.get("surface"))
            for form in forms:
                key=typ,norm(form);dictionary[key].add(label);provenance[key].add(row["expanded_assertion_id"])
    entries=[dict(entity_type=k[0],normalized_form=k[1],canonical_candidates=sorted(v),assertion_ids=sorted(provenance[k]),
                  unique_dictionary_candidate=len(v)==1,semantic_equivalence_certified=False) for k,v in sorted(dictionary.items())]
    candidate_matches=[]
    for item in read(OUT/"review/A_sample.jsonl"):
        source=item["proposed_source"]
        candidate_matches.append(dict(opportunity_id=item["opportunity_id"],
            typed_dictionary_candidates={side:sorted(dictionary.get((source[side+"_type"],norm(source[side+"_surface"])),set())) for side in ["head","tail"]},
            limit="No match is not novelty; a unique form is not condition identity"))
    claims=defaultdict(list)
    for row in d["graph"]["source_records"]:claims[row["expanded_claim_id"]].append(row)
    summary=dict(sole_base_graph="expanded1456",dictionary_form_type_entries=len(entries),
        ambiguous_dictionary_keys=sum(not r["unique_dictionary_candidate"] for r in entries),
        source="Current source_records and their stored terminology/source_forms only; unqualified candidate proposals are not added as true aliases",
        multi_evidence_claims=sum(len(rs)>1 for rs in claims.values()),
        multi_source_family_claims=sum(len({r["source_family_id"] for r in rs})>1 for rs in claims.values()),
        raw_same_core_occurrences=read(OUT/"mapping/summary.json")["raw_occurrence_categories"]["same_normalized_core_tuple_no_lineage"],
        independent_truth_support_count=None,formal_graph_edits=0)
    save(OUT/"controls/typed_dictionary.jsonl",entries)
    save(OUT/"controls/A_dictionary_lookup.jsonl",candidate_matches)
    save(OUT/"controls/dictionary_summary.json",summary)
    save(OUT/"controls/dictionary_manifest.json",dict(input_git_commit=REV,input_sha256=d["inputs"].hashes,program_sha256=digest(Path(__file__).read_bytes()),other_graphs_loaded=0))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
