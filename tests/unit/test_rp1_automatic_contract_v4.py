"""Synthetic boundary and invariance tests, independent of per-candidate v3 labels."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from rp1_offline_contract_v3 import REGISTRY,filter_flags
spec=importlib.util.spec_from_file_location('transducer',ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/automatic_contract_v4.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def page(text,**extra):return {'page_text':text,'tables':[],'title':'Example Pump Maintenance Manual','pump_type':'centrifugal_pump','applicability_scope':'type restricted; no marine-specific validation','service':'example',**extra}
def candidate(quote,**extra):
    return {'head_surface':'pump','head_type':'Equipment','relation':'inspected_by','tail_surface':'check pump','tail_type':'InspectionAction',
            'conditions':[],'modality':'required','polarity':'positive','scope':'primary','applicability':'example pump','evidence_text':quote,'evidence_unit_ids':[],**extra}
def run(a,p,mode='roles'):return m.transform(a,p,REGISTRY,filter_flags,mode)

class ContractTests(unittest.TestCase):
    def test_no_disjoint_or_punctuation_rewrite(self):
        self.assertEqual(m.spans('one two three','one three'),[])
        self.assertEqual(m.spans('one.','one!'),[])
        self.assertEqual(m.spans('one\n two','one two')[0]['text'],'one\n two')
    def test_no_maintenance_is_not_prohibition(self):
        q='The motor requires no maintenance.'
        a=candidate(q,head_surface='motor',relation='maintained_by',tail_surface='requires no maintenance',tail_type='MaintenanceAction',polarity='negative')
        r=run(a,page(q));self.assertTrue(r['included']);self.assertEqual(r['payload']['requirement'],'not_required')
    def test_object_not_instrument(self):
        q='Check working pressure if a pressure meter is installed.'
        a=candidate(q,head_surface='pressure meter',head_type='Component',tail_surface=q)
        r=run(a,page(q));self.assertTrue(r['included']);self.assertEqual(r['payload']['head_surface'],'working pressure');self.assertEqual(r['payload']['relation'],'diagnosed_by')
    def test_wrong_device_cannot_override_source_shaft(self):
        q='Before starting the pump check that the shaft rotates freely without jarring sounds.'
        a=candidate(q,head_surface='relief valve',head_type='Component',tail_surface='check shaft rotation')
        r=run(a,page(q));self.assertTrue(r['included']);self.assertEqual(r['payload']['head_surface'],'shaft')
    def test_competing_inspection_targets_are_ambiguous(self):
        q='Check that the shaft rotates freely without jarring sounds and the pump casing is filled with liquid.'
        r=run(candidate(q),page(q));self.assertFalse(r['included']);self.assertIn('nonunique_inspection_object',r['barriers'])
    def test_purpose_not_prevented_event(self):
        q='If you want to install the drainage valve, firstly tighten the plug, then tighten the bypass valve.'
        a=candidate(q,head_surface='install the drainage valve',head_type='MaintenanceAction',relation='prevented_by',tail_surface='tighten plug then bypass valve',tail_type='MaintenanceAction')
        r=run(a,page(q));self.assertTrue(r['included']);self.assertEqual(r['payload']['relation'],'maintained_by');self.assertEqual(r['payload']['head_surface'],'drainage valve')
    def test_unrelated_warning_not_inherited(self):
        q='In case of dry running, the bearing is damaged. When venting, avoid injury.'
        a=candidate(q,head_surface='dry running',head_type='FaultMode',relation='causes',tail_surface='bearing damage',tail_type='FaultMode',modality='asserted')
        r=run(a,page(q));self.assertTrue(r['included']);self.assertEqual(r['payload']['conditions'],['In case of dry running'])
    def test_antecedent_already_in_head_preserved(self):
        q='If the pump is out of service during a frost period, you should drain it.'
        a=candidate(q,head_surface='pump out of service during a frost period',head_type='OperatingCondition',relation='increases_risk_of',tail_surface='pump damage',tail_type='Risk')
        r=run(a,page(q));self.assertTrue(r['included']);self.assertIn('frost period',r['payload']['conditions'][0])
    def test_ambiguous_number_names_are_not_silently_changed(self):
        text='2.1 Disassembly\n1 Remove the impeller nut (9910).\n2.2 Assembly\n1 Place the impeller key (9910) into the shaft.\n'
        a=candidate('Remove the impeller nut (9910).',head_surface='impeller nut (9910)',head_type='Component',relation='maintained_by',tail_surface='remove',tail_type='MaintenanceAction')
        r=run(a,page(text));self.assertFalse(r['included']);self.assertIn('incompatible_source_part_names',r['barriers'])
    def test_program_binds_section_and_real_step(self):
        text='4.2 Assembly of cover\n1 Clean the cover.\n2 Fit the cover.\n\n'
        a=candidate('Fit the cover.',head_surface='cover',head_type='Component',relation='maintained_by',tail_surface='fit',tail_type='MaintenanceAction')
        r=run(a,page(text));self.assertTrue(r['included']);self.assertEqual(r['payload']['procedure_step']['ordinal'],2);self.assertFalse(r['payload']['procedure_step']['complete_procedure'])
    def test_duplicate_quote_across_sections_is_not_first_match(self):
        text='4.2 Assembly of cover\n1 Fit the washer.\n4.3 Assembly of seal\n1 Fit the washer.\n'
        a=candidate('Fit the washer.',head_surface='washer',head_type='Component',relation='maintained_by',tail_surface='fit',tail_type='MaintenanceAction')
        r=run(a,page(text));self.assertFalse(r['included']);self.assertIn('nonunique_source_section',r['barriers'])
    def test_runtime_does_not_open_files_and_ignores_ids(self):
        q='The motor requires no maintenance.'
        a=candidate(q,relation='maintained_by',tail_surface='requires no maintenance',tail_type='MaintenanceAction',candidate_review_id='anyA',expert_label='wrong')
        p=page(q,doc_id='first',page_key='first:page')
        expected=run(a,p)
        a.update(candidate_review_id='otherB',expert_label='correct');p.update(doc_id='second',page_key='second:page')
        with patch('builtins.open',side_effect=AssertionError('runtime IO forbidden')):
            self.assertEqual(run(a,p),expected)
    def test_unknown_source_remains_quarantined(self):
        r=run(candidate('invented source phrase'),page('unrelated source'))
        self.assertFalse(r['included']);self.assertIn('unbound_source_quote',r['barriers'])
    def test_factual_quality_not_inferred_from_screen(self):
        q='The pump runs.'
        r=run(candidate(q),page(q));self.assertFalse(r['semantic_certification'])

class NativeTableTests(unittest.TestCase):
    def table(self,prefix='x'):
        rows=[]
        for ri,values in enumerate([['DEFECT','APPEARANCE','PROBABLE CAUSE'],['Wear','Visible scars','Poor lubrication.'],['Crack','Fracture','Impact.']]):
            rows.append({'row_id':f'{prefix}r{ri}','cells':[{'cell_id':f'{prefix}r{ri}c{ci}','row_id':f'{prefix}r{ri}','row_index':ri,'column_index':ci,'text':value,'bbox':{'x0':ci*10,'top':ri*10,'x1':ci*10+9,'bottom':ri*10+9}} for ci,value in enumerate(values)]})
        return {'rows':rows}
    def test_cause_column_probability_and_primary_scope(self):
        t=self.table();p=page('BEARING DEFECTS',tables=[t])
        a=candidate('Poor lubrication.',head_surface='Poor lubrication',head_type='Cause',relation='causes',tail_surface='Wear',tail_type='FaultMode',scope='background',modality='asserted',evidence_unit_ids=['xr1c0','xr1c2'])
        r=run(a,p);self.assertTrue(r['included']);self.assertEqual(r['payload']['modality'],'probable');self.assertEqual(r['payload']['scope'],'primary')
        p['title']='General Reliability Guide';p['pump_type']='marine_machinery'
        self.assertEqual(run(a,p)['payload']['scope'],'background')
    def test_wrong_declared_row_is_not_silently_rebound(self):
        p=page('BEARING DEFECTS',tables=[self.table()])
        a=candidate('Poor lubrication.',head_surface='Poor lubrication',head_type='Cause',relation='causes',tail_surface='Crack',tail_type='FaultMode',evidence_unit_ids=['xr2c0','xr2c2'])
        r=run(a,p);self.assertFalse(r['included']);self.assertIn('quote_not_bound_to_declared_native_row',r['barriers'])
    def test_native_identifier_renaming_does_not_choose_rule(self):
        a=candidate('Visible scars',head_surface='Wear',head_type='FaultMode',relation='manifests_as',tail_surface='Visible scars',tail_type='Symptom',modality='probable',evidence_unit_ids=['xr1c0','xr1c1'])
        r=run(a,page('BEARING DEFECTS',tables=[self.table()]))
        a['evidence_unit_ids']=['zr1c0','zr1c1']
        s=run(a,page('BEARING DEFECTS',tables=[self.table('z')]))
        self.assertEqual(r['payload']['modality'],'descriptive');self.assertEqual(r['rules'],s['rules'])

if __name__=='__main__':unittest.main(verbosity=2)
