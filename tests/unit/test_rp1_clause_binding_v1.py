"""Synthetic boundary cases; no six-page evaluation labels."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from rp1_offline_contract_v3 import REGISTRY, filter_flags

def load(name):
    path = ROOT / 'src/research_point_1_graph_evidence/stage03_schema_validation' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base, model = load('automatic_contract_v4_1'), load('clause_binding_v1')
def page(text):
    return dict(page_text=text, tables=[], title='Example pump', pump_type='pump', applicability_scope='example')
def assertion(quote, **changes):
    a = dict(head_surface='rotor', head_type='Component', relation='inspected_by',
             tail_surface='check that the rotor turns freely', tail_type='InspectionAction',
             conditions=['Before starting'], modality='required', polarity='positive',
             scope='primary', applicability='example unit', evidence_text=quote, evidence_unit_ids=[])
    a.update(changes)
    return a
def execute(a, p, mode='repair', parent=None):
    parent = parent or base.transform(a, p, REGISTRY, filter_flags, 'roles')
    return model.refine(a, p, parent, filter_flags, mode)
def risk(quote):
    return assertion(quote, head_surface='operate against a closed valve', head_type='OperatingCondition',
                     relation='increases_risk_of', tail_surface='seal damage', tail_type='Risk',
                     conditions=['max. 7 minutes', 'max. temperature of 60°C for model X'], modality='asserted')

class ClauseBindingTests(unittest.TestCase):
    allowance = ('The unit is only allowed to operate against a closed valve for a short time '
                 '(max. 7 minutes and at a max. temperature of 60°C for model X). '
                 'Otherwise there is a risk of seal damage.')
    def test_permission_complement_preserves_both_bounds_and_scope(self):
        a = risk(self.allowance); r = execute(a, page(self.allowance))
        self.assertTrue(r['included'])
        self.assertEqual(r['payload']['condition_logic']['operator'], 'NOT')
        self.assertIn('and at a max.', r['payload']['condition_logic']['argument']['text'])
        self.assertIn('for model X', r['payload']['condition_logic']['argument']['text'])
        self.assertEqual(r['payload']['modality'], 'possible')
        self.assertEqual(r['payload']['source_allowance_conditions'], a['conditions'])
    def test_filter_uses_same_detection_without_repair(self):
        a, p = risk(self.allowance), page(self.allowance)
        f, r = execute(a, p, 'filter'), execute(a, p)
        self.assertEqual(f['clause_binding']['issues'], r['clause_binding']['issues'])
        self.assertFalse(f['included']); self.assertTrue(r['included'])
    def test_consequence_only_binds_unique_preceding_permission(self):
        q = 'Otherwise there is a risk of seal damage.'
        self.assertTrue(execute(risk(q), page(self.allowance))['included'])
        self.assertFalse(execute(risk(q), page(q))['included'])
    def test_duplicate_or_distant_permission_does_not_resolve(self):
        q = 'Otherwise there is a risk of seal damage.'
        self.assertFalse(execute(risk(q), page(self.allowance + ' ' + self.allowance))['included'])
        distant = self.allowance.replace('Otherwise', 'Check supply voltage. Otherwise')
        self.assertFalse(execute(risk(q), page(distant))['included'])
    def test_unmentioned_outcome_or_operation_is_not_repaired(self):
        a = risk(self.allowance); a['tail_surface'] = 'explosion'
        self.assertFalse(execute(a, page(self.allowance))['included'])
        a = risk(self.allowance); a['head_surface'] = 'operate with a missing bearing'
        self.assertFalse(execute(a, page(self.allowance))['included'])
    def test_other_conditions_are_not_deleted(self):
        a = risk(self.allowance); a['conditions'].append('during commissioning')
        self.assertIn('during commissioning', execute(a, page(self.allowance))['payload']['conditions'])
    def test_negative_polarity_cannot_be_flipped(self):
        a = risk(self.allowance); a['polarity'] = 'negative'
        self.assertFalse(execute(a, page(self.allowance))['included'])
    def test_list_target_uses_original_complement_not_wrong_subject(self):
        q = 'Before starting check that - the shaft rotates freely without jarring sounds. - the pump casing is filled with liquid.'
        a = assertion(q, head_surface='relief valve', tail_surface='check that the pump casing is filled with liquid')
        r = execute(a, page(q))
        self.assertTrue(r['included']); self.assertEqual(r['payload']['head_surface'], 'pump casing')
        self.assertEqual(r['payload']['evidence_text'], q)
    def test_incomplete_list_complement_stays_ambiguous(self):
        q = 'Before starting check that - the shaft rotates freely without jarring sounds. - the pump casing is filled with liquid.'
        self.assertFalse(execute(assertion(q, tail_surface='check pump'), page(q))['included'])
    def test_causal_skip_is_quarantined_but_first_edge_is_not(self):
        q = 'A reduced resistance will increase the flow, causing vibration.'
        a = risk(q); a.update(head_surface='reduced resistance', relation='causes', tail_surface='vibration', tail_type='Symptom', conditions=[])
        for mode in ['repair', 'filter']:
            self.assertFalse(execute(a, page(q), mode)['included'])
        a['tail_surface'] = 'increased flow'
        self.assertEqual(execute(a, page(q))['clause_binding']['issues'], [])
    def test_minimal_repair_tie_abstains_and_order_does_not_decide(self):
        a = assertion('source'); x, y = copy.deepcopy(a), copy.deepcopy(a)
        x['head_surface'], y['head_surface'] = 'shaft', 'seal'
        self.assertIsNone(model.minimum_unique(a, [x, y])); self.assertIsNone(model.minimum_unique(a, [y, x]))
        self.assertEqual(model.minimum_unique(a, [x, a]), a)
        self.assertEqual(model.minimum_unique(a, [x, x]), x)
    def test_existing_unrelated_barrier_cannot_be_removed(self):
        a, p = risk(self.allowance), page(self.allowance)
        parent = base.transform(a, p, REGISTRY, filter_flags, 'roles')
        parent['barriers'].append('incompatible_source_part_names')
        self.assertFalse(execute(a, p, parent=parent)['included'])
    def test_runtime_no_io_no_input_mutation_no_id_dependence(self):
        a, p = risk(self.allowance), page(self.allowance)
        parent = base.transform(a, p, REGISTRY, filter_flags, 'roles'); before = copy.deepcopy((a, p, parent))
        with patch('builtins.open', side_effect=AssertionError('runtime IO')):
            r = model.refine(a, p, parent, filter_flags)
        self.assertEqual((a, p, parent), before)
        a['candidate_review_id'], p['page_key'] = 'arbitrary', 'other'
        self.assertEqual(r, model.refine(a, p, parent, filter_flags))
    def test_passthrough_does_not_claim_semantic_certification(self):
        q = 'The rotor turns freely.'; a, p = assertion(q), page(q)
        parent = base.transform(a, p, REGISTRY, filter_flags, 'roles'); r = execute(a, p)
        self.assertEqual(r['payload'], parent['payload']); self.assertFalse(r['semantic_certification'])
if __name__ == '__main__': unittest.main()
