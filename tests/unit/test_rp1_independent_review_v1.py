"""Gate and holdout identity checks with synthetic sources only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('review_check',ROOT/'scripts/check_rp1_independent_review_v1.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReviewGateTests(unittest.TestCase):
    def test_empty_and_model_review_cannot_pass(self):
        self.assertTrue(m.reviewer_issues({}))
        r=dict(reviewer_name='Synthetic unit-test model',professional_background='not a person',completed_at='2026-10-03T00:00:00+00:00',reviewer_kind='model',independent_of_existing_AI_labels=True,source_first_review_completed=True,method_disposition='evaluate_current_method')
        self.assertIn('independent human reviewer not identified',m.reviewer_issues(r))
    def test_revise_disposition_cannot_freeze_current_method(self):
        self.assertIn('method disposition not ready for current frozen implementation',m.reviewer_issues({'method_disposition':'revise_before_freeze'}))
    def test_submission_must_be_within_review_directory(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'submissions').mkdir();(root/'outside.md').write_text('synthetic')
            self.assertIsNone(m.submission(root,'outside.md'))
            (root/'submissions/ok.md').write_text('synthetic')
            self.assertIsNotNone(m.submission(root,'submissions/ok.md'))
    def test_external_document_rejected_before_source_access(self):
        with self.assertRaisesRegex(ValueError,'outside build corpus'):
            m.load_selected(Path('/not/a/source'),[{'page_key':'MP009:p0001'}])
    def test_selected_page_hash_and_identity_checked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);text='synthetic page, not research data';h=hashlib.sha256(text.encode()).hexdigest()
            row=dict(doc_id='MP001',pdf_page_number=7,document_split='build_train',page_text=text,page_text_sha256=h)
            (root/'MP001.pages.v2.jsonl').write_text(json.dumps(row)+'\n')
            got=m.load_selected(root,[dict(page_key='MP001:p0007',page_text_sha256=h)])
            self.assertEqual(len(got),1)
            with self.assertRaisesRegex(ValueError,'hash/split mismatch'):
                m.load_selected(root,[dict(page_key='MP001:p0007',page_text_sha256='bad')])
    def test_missing_or_duplicate_page_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'MP001.pages.v2.jsonl').write_text('')
            r=dict(page_key='MP001:p0007',page_text_sha256='example')
            with self.assertRaisesRegex(ValueError,'missing frozen page'):m.load_selected(root,[r])
            with self.assertRaisesRegex(ValueError,'duplicate holdout identity'):m.load_selected(root,[r,r])
if __name__=='__main__':unittest.main()
