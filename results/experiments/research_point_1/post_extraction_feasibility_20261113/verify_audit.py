#!/usr/bin/env python3
"""Check audit consistency and source preservation, without rerunning inference."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main():
    manifest=read(HERE/'source_manifest.json')
    for name,meta in manifest['inputs'].items():assert sha(ROOT/name)==meta['sha256'],name
    assert sha(HERE/'audit_post_extraction.py')==manifest['script_sha256']
    summary=read(HERE/'summary.json')
    assert summary['counts']['audit']==8003
    assert sum(summary['primary_pipeline_categories'].values())==8003
    assert sum(summary['locator_pool_decisions'].values())==summary['counts']['locator_pool']==3956
    assert len(rows(HERE/'candidate_locator_audit.jsonl'))==8003
    assert len(rows(HERE/'raw_candidate_lineage.jsonl'))==8007
    assert len(rows(HERE/'version_parent_crosswalk.jsonl'))==1456
    assert len(rows(HERE/'existing17_full_chain.jsonl'))==17
    assert len(rows(HERE/'casebook_records.jsonl'))==19
    assert summary['published_address_pass']==1456
    for name in ['strict208','standard1326','expanded1456']:
        graph=summary['graphs'][name]
        assert sum(int(v) for v in graph['entity_types'].values())==graph['entities']
        assert sum(int(v) for v in graph['claim_relations'].values())==graph['claims']
        assert sum(int(v) for v in graph['degree_histogram'].values())==graph['entities']
        assert sum(int(size)*n for size,n in graph['component_size_histogram'].items())==graph['entities']
        assert sum(graph['component_size_histogram'].values())==graph['weak_components']
        assert graph['claims_without_assertions']==0
    for record in rows(HERE/'casebook_records.jsonl'):
        for page in record['source_pages']:
            assert (ROOT/page['source_path']).is_file()
    for filename in ['rp1_data_lineage.md','rp1_casebook.md','rp1_direction_decision.md','rp1_problem_statistics.csv','README.md']:
        assert (HERE/filename).stat().st_size>100
    with (HERE/'rp1_problem_statistics.csv').open() as f:
        stats=list(csv.DictReader(f))
    assert all(r['source'] and r['confidence_limit'] for r in stats)
    broken=[]
    for file in HERE.glob('*.md'):
        text=file.read_text();assert text.count('```')%2==0,file
        for match in re.finditer(r'\[[^\]]*\]\(([^)]+)\)',text):
            target=match.group(1)
            if target.startswith(('http:','https:','#')):continue
            if not (file.parent/target.split('#')[0]).exists():broken.append((file.name,target))
    assert not broken,broken
    reproduction=read(HERE/'reproduction_check.json')
    assert reproduction['identical_derived_files'] is True
    report=dict(status='PASS',input_files=len(manifest['inputs']),source_hashes_preserved=True,
       data_counts_consistent=True,existing_graphs_unchanged=True,cases=19,statistics_rows=len(stats),
       reproduction_files=reproduction['files_compared'],new_model_calls=0,new_graph_writes=0,
       algorithm_implementation_started=False,second_stage_started=False)
    (HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
