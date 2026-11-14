"""Plain explicit table-reference lookup control; not path inference."""
from collections import defaultdict
import json
import re
import sys

from inputs import load,save,norm,identifier
from selection_screen import OUT,read
from selection_discovery import tuples


def reference_join(p31,p32):
    table=p31["tables"][0]; dictionary=p32["tables"][0]
    if not any("see table 5" in norm(c["text"]) for r in table["rows"] for c in r["cells"]):
        raise ValueError("No explicit source reference; refusing cross-page join")
    meanings={}
    for row in dictionary["rows"]:
        cells=row["cells"]
        if len(cells)==2 and re.fullmatch(r"\d+",cells[0]["text"].strip()):
            meanings[int(cells[0]["text"])]=cells
    output=[]
    for row in table["rows"]:
        cells=row["cells"]
        if len(cells)!=2 or not re.fullmatch(r"[\d,\s]+",cells[1]["text"]):continue
        for number in map(int,re.findall(r"\d+",cells[1]["text"])):
            if number not in meanings:raise ValueError("Unresolved source reference")
            definition=meanings[number]
            output.append({"id":"EJ-"+identifier([cells[0]["cell_id"],number]),"doc_id":"MP015",
                "pages":[31,32],"head_surface":definition[1]["text"],"relation":"causes",
                "tail_surface":cells[0]["text"],"modality":"possible_cause_not_necessary_or_sufficient",
                "source_reference_number":number,"proof_cells":[cells[0],cells[1],*definition],
                "header_reference_cell":table["rows"][0]["cells"][1],
                "scope":"SPX Johnson FreFlow, Table 4 plus explicitly referenced Table 5",
                "source_binding":"two_table_number_lookup","trusted_fact":False})
    return output


def main():
    sys.stdout.reconfigure(encoding="utf-8");d=load()
    result=reference_join(d["pages"]["MP015",31],d["pages"]["MP015",32])
    initial=tuples(d["raw"]+d["normalized"]);current=tuples(d["graph"]["source_records"])
    for r in result:
        key=(norm(r["head_surface"]),"causes",norm(r["tail_surface"]))
        r["raw_exact_pair_present"]=key in initial;r["base_exact_pair_present"]=key in current
        r["semantically_new_claim_certified"]=False
    fixed=[r for r in result if norm(r["tail_surface"]) in ["irregular delivery","pump vibrates or is noisy"]]
    save(OUT/"discovery/reference_join_all.jsonl",result)
    save(OUT/"discovery/reference_join_review.jsonl",fixed)
    save(OUT/"discovery/reference_join_summary.json",{"source_pages":2,"source_fault_rows":13,"source_cause_definitions":33,
        "explicitly_joined_possible_cause_associations":len(result),"exact_base_pairs":sum(r["base_exact_pair_present"] for r in result),
        "exact_initial_pairs":sum(r["raw_exact_pair_present"] for r in result),"reviewed_subset":len(fixed),
        "all_joined_associations_are_not_new_claim_count":True,"no_transitive_causality_assumption":True})
    print(json.dumps(read(OUT/"discovery/reference_join_summary.json"),ensure_ascii=False,indent=2))
    for r in fixed:print(r['id'],r['head_surface'],'=>',r['tail_surface'])


if __name__=="__main__":main()
