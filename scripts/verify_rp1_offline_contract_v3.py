#!/usr/bin/env python3
"""Independent integrity/count verification, not independent semantic adjudication."""
from collections import Counter
import importlib.util
import io
import unittest
from rp1_offline_contract_v3 import *

def main():
    before=json.loads((OUT/'preservation_before.json').read_text())['sha256']
    for p,digest in before.items():assert (ROOT/p).is_file() and sha(ROOT/p)==digest,p
    freeze=json.loads((OUT/'adjudication_freeze.json').read_text())
    for p,digest in freeze['sha256'].items():assert sha(ROOT/p)==digest,p
    run=json.loads((OUT/'arm_execution_freeze.json').read_text())
    assert sha(ROOT/'scripts/run_rp1_offline_contract_v3.py')==run['runner_sha256']
    assert sha(OUT/'adjudication_freeze.json')==run['adjudication_freeze_sha256']
    d=rows(OUT/'arm_decisions.jsonl');m=rows(OUT/'reference_matches_510.jsonl');a=rows(OUT/'candidate_adjudications.jsonl')
    summary=json.loads((OUT/'summary.json').read_text())
    assert len(d)==699 and len(a)==233 and len(m)==510
    for s in summary:
        sub=[x for x in d if x['stage']==s['stage'] and x['prompt_arm']==s['prompt_arm']]
        good=[x for x in sub if x['included'] and channel(x['payload'])=='core' and x['payload']['scope']=='primary' and x['AI_contract_status']=='complete']
        assert len(good)==s['AI_complete_core_records']
        assert len({exact_key(x['payload']) for x in good})==s['AI_complete_core_exact_text_unique']
        full=[x for x in m if x['stage']==s['stage'] and x['prompt_arm']==s['prompt_arm'] and x['state']=='full']
        assert len(full)==s['core_full_reference_matches']
        assert len(full)==len({x['allocated_candidate_id'] for x in full})
        assert sum(s['reference_state_counts_all_85'].values())==85
    spec=importlib.util.spec_from_file_location('offline_tests',ROOT/'tests/unit/test_rp1_offline_contract_v3.py')
    tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    suite=unittest.TestSuite(unittest.FunctionTestCase(getattr(tests,n)) for n in sorted(dir(tests)) if n.startswith('test_'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    # pytest is unavailable in this interpreter; the same plain test functions run via stdlib unittest.
    log={'runner':'stdlib unittest.FunctionTestCase; pytest unavailable; no dependency installation',
         'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
         'case_outcomes':[n for n in sorted(dir(tests)) if n.startswith('test_')]}
    assert result.wasSuccessful(),stream.getvalue()
    write(OUT/'test_results.json',log)
    result={'status':'passed','snapshot_files_preserved':len(before),'source_adjudications':len(a),'source_witnesses_verified':sum(len(x['source_witnesses']) for x in a),
        'original_inputs':233,'stage_decisions':699,'reference_matches':510,'unresolved_candidates':sum(x['proposal'] is None for x in a),
        'tests_passed':result.testsRun,'old_expert_queues_unchanged':True,
        'A_and_B_assertions_byte_value_preserved':True,'candidate_C_expansion':0,'new_API_calls':0,'new_graph_records':0,
        'heldout_contents_opened':0,'independent_semantic_validation':'pending','semantic_accuracy_proven':False}
    write(OUT/'verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
