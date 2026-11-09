"""Meaningful guard tests using synthetic data only; never open heldout pages."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import prepare_rp1_ai_review_v1 as review


class AIReviewGuards(unittest.TestCase):
    def test_modified_sealed_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/'method.py'
            path.write_text('original')
            manifest = {'method.py':review.sha(path)}
            review.verify_hashes(manifest, root)
            path.write_text('changed')
            with self.assertRaises(ValueError):
                review.verify_hashes(manifest, root)

    def test_hash_manifest_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'repo'
            root.mkdir()
            outside = root.parent/'outside'
            outside.write_text('external')
            with self.assertRaises(ValueError):
                review.verify_hashes({'../outside':review.sha(outside)},root)

    def test_shifted_source_span_is_rejected(self):
        page = {'page_text':'limit 80 C', 'tables':[]}
        witness = {'kind':'page_span','start':6,'end':10,'text':'80 C'}
        review.validate_witness(page,witness)
        with self.assertRaises(ValueError):
            review.validate_witness(page,dict(witness,start=5))

    def test_native_bbox_cannot_be_invented(self):
        cell = {'cell_id':'c1','text':'bearing','bbox':None}
        page = {'page_text':'','tables':[{'rows':[{'cells':[cell]}]}]}
        witness = dict(kind='native_cell_subspan',cell_id='c1',start=0,end=7,text='bearing',bbox=None)
        review.validate_witness(page,witness)
        with self.assertRaises(ValueError):
            review.validate_witness(page,dict(witness,bbox={'x0':0}))

    def test_no_holdout_opening_without_AI_freeze(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(review,'OUT',Path(folder)), patch.object(review,'load_selected') as load:
            with self.assertRaises(ValueError):
                review.prepare_holdout()
            load.assert_not_called()

    def test_external_document_rejected_before_file_read(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'outside build corpus'):
                review.load_selected(Path(folder),[{'page_key':'MP009:p0001','page_text_sha256':'x'}])

    def test_changed_page_text_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            page=dict(doc_id='MP001',pdf_page_number=1,document_split='build_train',page_text='original',page_text_sha256=hashlib.sha256(b'original').hexdigest())
            manifest=[{'page_key':'MP001:p0001','page_text_sha256':page['page_text_sha256']}]
            (root/'MP001.pages.v2.jsonl').write_text(json.dumps(page)+'\n')
            self.assertEqual(len(review.load_selected(root,manifest)),1)
            page['page_text']='tampered'
            (root/'MP001.pages.v2.jsonl').write_text(json.dumps(page)+'\n')
            with self.assertRaisesRegex(ValueError,'hash/split mismatch'):
                review.load_selected(root,manifest)


if __name__=='__main__':
    unittest.main()
