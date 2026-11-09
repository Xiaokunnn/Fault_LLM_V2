#!/usr/bin/env python3
"""Generation only: original assertions + six pages; never reads v3 adjudications."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import io
from rp1_offline_contract_v3 import rows,sha,write,object_sha,filter_flags,REGISTRY,ROOT,BASE,SOURCE,REVIEW
OUT=BASE/'automatic_contract_v4_1'
MODULE=ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/automatic_contract_v4_1.py'

def module():
    spec=importlib.util.spec_from_file_location('automatic_contract_v4',MODULE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    test_path=ROOT/'tests/unit/test_rp1_automatic_contract_v4_1.py'
    spec=importlib.util.spec_from_file_location('v4_tests',test_path);tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    if not result.wasSuccessful():raise AssertionError(stream.getvalue())
    write(OUT/'synthetic_tests.json',{'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'runner':'stdlib unittest'})
    files=[MODULE,Path(__file__),test_path,ROOT/'scripts/rp1_offline_contract_v3.py',ROOT/'data/kg/marine_pump/schema/provenance_schema_v3.json',
           ROOT/'docs/research/RP1_AUTOMATIC_CONTRACT_V4_1_AMENDMENT_20261003.md',SOURCE/'pilot_sources.jsonl',REVIEW/'arm_masked_review_packets.jsonl',REVIEW/'private_arm_mapping.jsonl']
    write(OUT/'execution_freeze.json',{'stage':'before first v4 batch generation and effect metrics','sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},
        'stages':{'P0':'context','P1':'roles'},'runtime_annotation_access':False,'heldout_contents_opened':0,'extra_API_calls':0})
    pages={p['page_key']:p for p in rows(SOURCE/'pilot_sources.jsonl')};arms={r['review_id']:r['arm'] for r in rows(REVIEW/'private_arm_mapping.jsonl')}
    model=module();outputs=[]
    for stage,mode in [('P0','context'),('P1','roles')]:
        for packet in rows(REVIEW/'arm_masked_review_packets.jsonl'):
            page=pages[packet['page_key']]
            for a in packet['assertions']:
                raw={k:v for k,v in a.items() if k not in ['candidate_review_id','mechanical']}
                result=model.transform(raw,page,REGISTRY,filter_flags,mode)
                outputs.append({'stage':stage,'mode':mode,'candidate_review_id':a['candidate_review_id'],'prompt_arm':arms[packet['review_id']],
                    'page_key':packet['page_key'],'source_page_sha256':page['page_text_sha256'],'original_sha256':object_sha(raw),**result})
    assert len(outputs)==466
    write(OUT/'automatic_outputs.jsonl',outputs)
    write(OUT/'generation_completion.json',{'stages':2,'input_assertions_per_stage':233,'decisions':466,'runtime':'pure finite English source-grammar transducer',
        'generation_used_expert_or_v3_labels':False,'quality_metrics':'not_yet_computed','output_sha256':sha(OUT/'automatic_outputs.jsonl')})
    print(json.dumps({'stage':'generated and frozen for separate technical review','outputs':len(outputs),'synthetic_tests':result if False else 19,'new_API_calls':0}))
if __name__=='__main__':main()
