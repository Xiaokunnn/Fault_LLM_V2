import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))

def test_ai_cannot_award_empty_output_a_supported_grade():
    from rp1_complex_binding_cross_evaluation import check
    from rp1_complex_binding_common import DIMENSIONS
    body={'focus':[{'focus_id':'x'}],'anonymous_output':{'triples':[]}}
    a={'focus_id':'x',**{k:'S' for k in DIMENSIONS},'explicit_binding':'N','channel':'none','output_refs':[],'output_quote':''}
    with pytest.raises(ValueError,match='positive_grade_without_actual_output_quote'):
        check({'assessments':[a],'relation_verdicts':[]},body)

def test_output_reference_must_point_to_actual_output_not_source():
    from rp1_complex_binding_cross_evaluation import check
    from rp1_complex_binding_common import DIMENSIONS
    body={'focus':[{'focus_id':'x'}],'anonymous_output':{'triples':[{'tail_surface':'inspect before restart'}]}}
    a={'focus_id':'x',**{k:'S' for k in DIMENSIONS},'explicit_binding':'N','channel':'main','output_refs':['triples:1'],'output_quote':'inspect AFTER restart'}
    with pytest.raises(ValueError,match='positive_grade_without_actual_output_quote'):
        check({'assessments':[a],'relation_verdicts':[{'index':1,'verdict':'N'}]},body)
