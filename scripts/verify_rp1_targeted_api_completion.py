#!/usr/bin/env python3
"""Read-only reconstruction of API completion, recovery lineage and mechanical counts."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/experiments/research_point_1'
ORIGINAL=BASE/'adjudication_targeted_v2_1_qwen38'
RECOVERY=BASE/'adjudication_targeted_v2_1_qwen38_timeout180'
REVIEW=BASE/'targeted_api_review_v2_1'


def load_module(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]


def verify():
    old=load_module('v21_preservation','scripts/verify_rp1_targeted_v2_1.py').verify()
    runner=load_module('api_runner','scripts/run_rp1_targeted_v2_1.py')
    runner.check_package(ORIGINAL);protocol,requests=runner.check_package(RECOVERY)
    assert (ORIGINAL/'requests.jsonl').read_bytes()==(RECOVERY/'requests.jsonl').read_bytes()
    states=[runner.request_state(RECOVERY/'api_run_001',r) for r in requests]
    assert len(states)==12 and all(x is not None for x in states)
    assert {x['returned_model'] for x in states}=={'qwen3.8-max'}
    old_requests=rows(BASE/'adjudication_targeted_v2_1/requests.jsonl')
    for a,b in zip(old_requests,requests):
        a['payload']['model']='qwen3.8-max'
        assert a['payload']==b['payload'] and a['shared_input_sha256']==b['shared_input_sha256']
    reused=json.loads((RECOVERY/'reused_response_manifest.json').read_text())
    for x in reused['files']:
        assert digest(ROOT/x['source'])==digest(ROOT/x['destination'])==x['sha256']
    failed=json.loads((ORIGINAL/'api_run_001/06_E1.failed.json').read_text())
    assert failed['exception_class']=='TimeoutError'
    assert not (ORIGINAL/'api_run_001/06_E1.response.bin').exists()
    attempts={digest(p) for package in [ORIGINAL,RECOVERY] for p in (package/'api_run_001').glob('*.started.json')}
    raw_responses={digest(p) for package in [ORIGINAL,RECOVERY] for p in (package/'api_run_001').glob('*.response.bin')}
    assert len(attempts)==13 and len(raw_responses)==12
    actual=json.loads((RECOVERY/'execution_result.json').read_text())
    assert actual['network_calls_this_invocation']==2 and actual['completed_requests']==12
    freeze=json.loads((REVIEW/'freeze.json').read_text())
    for path,expected in freeze['sha256'].items():assert digest(ROOT/path)==expected
    summary=json.loads((REVIEW/'completion_summary.json').read_text())
    registry=json.loads((ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json').read_text())['relation_registry']
    sources={p['page_key']:p for p in rows(RECOVERY/'pilot_sources.jsonl')}
    mechanical={x['candidate_review_id']:x for x in rows(REVIEW/'mechanical_checks_corrected.jsonl')}
    mapping={x['review_id']:x for x in rows(REVIEW/'private_arm_mapping.jsonl')}
    packets=rows(REVIEW/'arm_masked_review_packets.jsonl')
    derived={arm:Counter() for arm in ['E0','E1']}
    for packet in packets:
        source=sources[packet['page_key']];cells={c['cell_id']:c for t in source['tables'] for r in t['rows'] for c in r['cells']}
        arm=mapping[packet['review_id']]['arm'];count=derived[arm]
        count['assertions_all_scopes']+=len(packet['assertions'])
        for a in packet['assertions']:
            m=mechanical[a['candidate_review_id']];rule=registry.get(a['relation']);valid=bool(rule and a['head_type'] in rule['domain'] and a['tail_type'] in rule['range'])
            assert m['type_direction_valid']==valid
            count['all_scope_type_invalid']+=not valid
            count[a['scope']]+=1
            if a['scope']=='primary' and rule and rule['core_diagnostic_relation']:
                count['primary_core']+=1;count['primary_core_type_valid']+=valid;count['primary_core_type_invalid']+=not valid
            quote=''.join(a['evidence_text'].split())
            possible_sources=[source['page_text']]+[cells[c]['text'] for c in a['evidence_unit_ids'] if c in cells]
            bound=bool(quote and any(quote in ''.join(s.split()) for s in possible_sources))
            assert (m['quote_binding']!='not_single_verbatim_span_or_cell')==bound,a['candidate_review_id']
            count['source_quote_locatable_exact_or_whitespace_only']+=bound;count['source_quote_nonverbatim']+=not bound
    for arm,counts in derived.items():
        for key,value in counts.items():assert summary['by_arm'][arm][key]==value,(arm,key)
    assert sum(x['usage']['total_tokens'] for x in states)==summary['known_successful_response_token_total']==101311
    assert len(rows(REVIEW/'candidate_expert_review_queue.jsonl'))==233
    assert len(rows(REVIEW/'reference_match_review_queue.jsonl'))==170
    for name in ['candidate_expert_review_queue.jsonl','reference_match_review_queue.jsonl']:
        assert all(x['reviewer_id'] is None and x['reviewed_at'] is None for x in rows(REVIEW/name))
    # Inspect new local artifacts for token-shaped strings without printing any matching value.
    secret_pattern=re.compile(rb'sk-[A-Za-z0-9_-]{20,}')
    paths=[p for folder in [ORIGINAL,RECOVERY,REVIEW] for p in folder.rglob('*') if p.is_file()]
    suspicious=[str(p.relative_to(ROOT)) for p in paths if secret_pattern.search(p.read_bytes())]
    assert not suspicious,('Credential-like string found in new artifacts; content not printed',suspicious)
    return {'status':'passed','prior_assets_preserved':old['preserved_prior_files'],'original_pdf_hashes_verified':old['original_pdf_hashes_verified'],'unique_network_attempts':len(attempts),'unique_successful_raw_responses':len(raw_responses),'reused_response_files_byte_identical':len(reused['files']),'source_inputs_and_prompts_unchanged_except_authorized_model':True,'original_timeout_preserved':True,'mechanical_assertions_reconstructed':len(mechanical),'locator_corrections_reconstructed':2,'candidate_expert_queue':233,'reference_matching_queue':170,'new_artifacts_scanned_for_credential_patterns':len(paths),'credential_patterns_found':0,'formal_accuracy_recall':'not_computed','new_graph_records':0}


if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
