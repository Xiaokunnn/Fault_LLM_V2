import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from rp1_offline_contract_v3 import REGISTRY,filter_flags
spec=importlib.util.spec_from_file_location('ldc',ROOT/'src/research_point_1_graph_evidence/stage03_schema_validation/layout_direction_context_v1.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def block(i,text,x=30,y=30,w=230):
    return dict(block_id=str(i),text=text,bbox=dict(x0=x,x1=x+w,top=y,bottom=y+10))


def page(blocks):
    return dict(page_text='\n'.join(b['text'] for b in blocks),text_blocks=blocks,tables=[],page_width=600)


def record(**kw):
    a=dict(head_surface='scalding',head_type='Risk',relation='increases_risk_of',tail_surface='hot liquid',
        tail_type='OperatingCondition',conditions=['When draining'],modality='asserted',polarity='positive',
        scope='primary',applicability='test pump',evidence_text='Avoid scalding when pumping hot liquid.',evidence_unit_ids=[])
    return dict(a,**kw)


def parent(a,p):
    return dict(payload=copy.deepcopy(a),included=False,barriers=[],screen_flags=filter_flags(a,p),source_witnesses=[],rules=[])


class LayoutContractTests(unittest.TestCase):
    def test_columns_recover_quote_and_reject_row_splice(self):
        left=['Pump inlet pressure must remain sufficient','otherwise cavitation may damage the unit','during continuous operation at high speed']
        right=['The motor has separate lubrication requirements','Inspect the motor bearings every month','according to the motor manufacturer instructions']
        bs=[block(str(i)+'L',a,y=30+i*13) for i,a in enumerate(left)]+[block(str(i)+'R',a,x=330,y=30+i*13) for i,a in enumerate(right)]
        p=page(sorted(bs,key=lambda b:(b['bbox']['top'],b['bbox']['x0'])))
        hits,g=m.locate(p,left[0]+' '+left[1]);self.assertTrue(g['two_columns']);self.assertEqual(len(hits),1)
        self.assertEqual(len(hits[0]['witnesses']),2)
        self.assertEqual(m.locate(p,left[0]+' '+right[0])[0],[])

    def test_distant_fragments_do_not_form_quote(self):
        self.assertEqual(m.locate(page([block(1,'Check the shaft',y=30),block(2,'before startup',y=600)]),'Check the shaft before startup')[0],[])

    def test_source_witness_offsets_roundtrip(self):
        p=page([block(1,'  Check the shaft'),block(2,'for wear.  ',y=43)])
        hits,_=m.locate(p,'Check the shaft for wear.');units={b['block_id']:b for b in p['text_blocks']}
        for w in hits[0]['witnesses']:
            self.assertEqual(units[w['block_id']]['text'][w['start']:w['end']],w['text'])
            self.assertEqual(units[w['block_id']]['bbox'],w['bbox'])
            self.assertEqual(w['kind'],'native_block_subspan')

    def test_duplicate_locations_do_not_trigger_flip(self):
        a=record();p=page([block(1,a['evidence_text']),block(2,a['evidence_text'],y=60)])
        r=m.refine(a,p,parent(a,p),REGISTRY,filter_flags);self.assertEqual(r['payload'],a);self.assertFalse(r['included'])

    def test_inverse_needs_source_roles(self):
        a=record();b=m.unique_flip(a,a['evidence_text'],REGISTRY)
        self.assertEqual(b['head_surface'],'hot liquid');self.assertEqual(b['modality'],'possible');self.assertEqual(b['conditions'],a['conditions'])
        self.assertIsNone(m.unique_flip(a,'scalding and hot liquid',REGISTRY))
        self.assertIsNone(m.unique_flip(a,'Avoid scalding near a motor',REGISTRY))

    def test_valid_original_and_negative_not_flipped(self):
        a=record(polarity='negative');self.assertIsNone(m.unique_flip(a,a['evidence_text'],REGISTRY))
        a=record(head_type='OperatingCondition',tail_type='Risk');self.assertIsNone(m.unique_flip(a,a['evidence_text'],REGISTRY))

    def test_unrelated_barrier_survives(self):
        a=record();p=page([block(1,a['evidence_text'])]);b=parent(a,p);b['barriers']=['unresolved_source_scope']
        r=m.refine(a,p,b,REGISTRY,filter_flags);self.assertFalse(r['included']);self.assertEqual(r['payload'],a)

    def test_local_condition_not_remote_warning(self):
        q='Inspect the seal.'
        a=record(head_surface='seal',head_type='Component',relation='inspected_by',tail_surface=q,tail_type='InspectionAction',evidence_text=q,conditions=[])
        p=page([block(1,'If the pump is stopped, Inspect the seal.'),block(2,'If the motor is hot, do not touch it.',y=43)])
        r=m.refine(a,p,parent(a,p),REGISTRY,filter_flags)
        self.assertEqual(r['payload']['conditions'],['If the pump is stopped']);self.assertEqual(r['payload']['evidence_text'],q)

    def test_alternative_action_quarantined(self):
        a=record(head_surface='vibration',head_type='FaultMode',relation='mitigated_by',tail_surface='Improve the supports',tail_type='MaintenanceAction',evidence_text='Improve the supports; alternatively replace the mounts.')
        p=page([block(1,a['evidence_text'])]);r=m.refine(a,p,parent(a,p),REGISTRY,filter_flags)
        self.assertFalse(r['included']);self.assertIn('alternative_action_not_preserved',r['barriers'])

    def test_pure_runtime_preserves_input(self):
        a=record();p=page([block(1,a['evidence_text'])]);b=parent(a,p);before=copy.deepcopy((a,p,b))
        with patch('builtins.open',side_effect=AssertionError('runtime IO')):r=m.refine(a,p,b,REGISTRY,filter_flags)
        self.assertEqual(before,(a,p,b));self.assertTrue(r['included'])


if __name__=='__main__':unittest.main()
