"""Verify the completed RP1 second-opinion delivery without loading model weights."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/experiments/research_point_1/scope_repair_v2'
V1 = ROOT / 'results/experiments/research_point_1/loss_page_audit_v1'


def read(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def main():
    from transformers import AutoTokenizer

    before = json.loads((OUT / 'preservation_before.json').read_text())
    changed = [k for k, v in before.items() if not (ROOT / k).is_file() or sha(ROOT / k) != v]
    assert not changed, changed
    exp = json.loads((OUT / 'experiment_freeze.json').read_text())
    assert all(sha(ROOT / k) == v for k, v in exp['inputs'].items())
    freeze = json.loads((OUT / 'second_opinion/freeze.json').read_text())
    assert sha(ROOT / 'scripts/run_rp1_v2_blind_second_opinion.py') == freeze['runner_sha256']
    assert sha(ROOT / 'docs/research/RP1_SCOPE_AND_EVALUATION_V2_20260930.md') == freeze['protocol_sha256']
    assert sha(OUT / 'second_opinion/blind_inputs.jsonl') == freeze['blinded_inputs_sha256']
    runtime = json.loads((OUT / 'second_opinion/runtime.json').read_text())
    model_path = ROOT / freeze['model']
    assert sha(model_path / 'tokenizer_config.json') == runtime['tokenizer_config_sha256']
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    mapping = read(OUT / 'second_opinion/private_mapping.jsonl')
    inputs = {r['blind_id']: r for r in read(OUT / 'second_opinion/blind_inputs.jsonl')}
    packets = {r['audit_id']: r for r in read(V1 / 'record_review_packets.jsonl')}
    judgments = {r['audit_id']: r for r in read(V1 / 'record_findings.jsonl')}
    # Independently rebuild the fixed targeted sample and six controls.
    critical = {k for k, r in judgments.items() if r['primary_audit_explanation'] in
                {'possible_rule_false_rejection', 'unresolved'} or r['original_decision'] == 'qualified'
                and r['primary_audit_explanation'] in {'semantic_or_relation_error', 'scope_mismatch'}}
    expected = set(critical)
    for decision in ['qualified', 'quarantined', 'rejected']:
        pool = [k for k, r in judgments.items() if k not in critical and r['sample_kind'] == 'probability'
                and r['original_decision'] == decision and r['semantic_support'] == 'supported']
        expected.update(sorted(pool, key=lambda k: hashlib.sha256(f'20260930/review_control/{k}'.encode()).hexdigest())[:2])
    assert len(mapping) == len(inputs) == len(expected) == 26
    assert {r['audit_id'] for r in mapping} == expected
    ordered = sorted(expected, key=lambda k: hashlib.sha256(f'20260930/blind_order/{k}'.encode()).hexdigest())
    assert [r['audit_id'] for r in mapping] == ordered
    code = {'supported': 'S', 'unsupported': 'N', 'unresolved': 'U'}
    confusion = Counter()
    opinions = []
    for m in mapping:
        x = inputs[m['blind_id']]
        original = packets[m['audit_id']]
        assert not x['source_was_clipped']
        assert x['source_excerpt'] == ' '.join(original['page']['page_text'].split())
        assert x['source_page_sha256'] == original['page']['page_text_sha256']
        assert x['proposed_quote'] == original['record'].get('evidence_text', '')
        assert x['candidate'] == {k: original['record'][k] for k in
                                  ['head_surface', 'head_type', 'relation', 'tail_surface', 'tail_type']}
        payload = {k: x[k] for k in ['candidate', 'proposed_quote', 'source_excerpt', 'source_was_clipped']}
        messages = [{'role': 'system', 'content': freeze['system_prompt']},
                    {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        opinion = json.loads((OUT / f"second_opinion/{m['blind_id']}.json").read_text())
        assert hashlib.sha256(prompt.encode()).hexdigest() == opinion['prompt_sha256']
        assert len(tokenizer.encode(prompt, add_special_tokens=False)) == opinion['input_tokens'] <= freeze['max_input_tokens']
        assert opinion['model_called'] and opinion['status'] == 'assessed'
        assert opinion['unrestricted_next_token'] == opinion['label']
        assert opinion['unrestricted_next_token_in_choices'] and not opinion['expert_review']
        logits = opinion['label_logits']
        assert max(logits, key=logits.get) == opinion['label']
        maximum = max(logits.values())
        normalizer = sum(math.exp(v - maximum) for v in logits.values())
        for label, v in logits.items():
            assert abs(math.exp(v - maximum) / normalizer - opinion['conditional_label_probabilities_not_calibrated'][label]) < 1e-6
        confusion[code[judgments[m['audit_id']]['semantic_support']] + '->' + opinion['label']] += 1
        opinions.append(opinion)
    summary = json.loads((OUT / 'second_opinion/summary.json').read_text())
    assert summary['cross_tab'] == dict(confusion)
    assert summary['agreement'] == sum(v for k, v in confusion.items() if k[0] == k[-1]) == 13
    assert summary['disagreement'] == 13 and summary['assessed'] == 26
    assert summary['second_opinion_label_counts'] == dict(Counter(r['label'] for r in opinions))
    completion = json.loads((OUT / 'second_opinion/completion.json').read_text())
    assert freeze['frozen_at'] < runtime['started_at'] < completion['completed_at']
    assert all(r['expert_adjudication'] == 'pending' for r in read(OUT / 'second_opinion/adjudication_packets.jsonl'))
    docs = [ROOT / 'docs/research/RP1_SCOPE_AND_EVALUATION_V2_20260930.md',
            ROOT / 'docs/research/RP1_SCOPE_REPAIR_V2_RESULTS_20260930.md', OUT / 'README.md']
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            assert (doc.parent / target).exists(), (doc, target)
    result = {'status': 'passed', 'verified_at': datetime.now(timezone.utc).isoformat(),
              'preexisting_files_byte_identical': len(before), 'fixed_26_item_sample_reconstructed': True,
              'all_26_prompts_and_token_counts_reconstructed': True,
              'prior_labels_and_decisions_absent_from_model_payload': True,
              'page_text_truncations': 0, 'context_budget_skips': 0,
              'saved_classifications_and_probabilities_recomputed': True,
              'agreement': 13, 'disagreement': 13, 'semantic_truth_verified': False,
              'model_inference_during_delivery_verification': False,
              'domain_expert_adjudication': 'pending', 'local_report_links_valid': True}
    with (OUT / 'delivery_verification_20261002.json').open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
