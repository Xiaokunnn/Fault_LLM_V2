"""Final additive manifest for this read-only diagnostic only."""
from common_audit import *


def main():
    assert read(OUT/'verification.json')['passed']
    assert all((OUT/name).exists() for name in ['REPORT.md','CASEBOOK.md','REPRODUCE.md','graph_statistics.csv','cold_endpoint_ledger.jsonl','cross_document_complete.json','implications_complete.json'])
    rows=[]
    for p in sorted(OUT.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name=='delivery_manifest.json':continue
        rows.append(dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)))
    save(OUT/'delivery_manifest.json',dict(files=rows,scope='expanded1456 + initial records + 15 manuals + frozen query-aware completion artifacts',read_only_original_inputs=True,new_model_runs=0,new_extractions=0,formal_graph_changes=0,RP2_RP3_changes=0))
    print('Sealed',len(rows),'audit files; original inputs unchanged.')


if __name__=='__main__':main()
