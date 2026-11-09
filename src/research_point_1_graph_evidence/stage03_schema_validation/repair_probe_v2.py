"""Additive source witnesses and relation warnings, never automatic qualification.

The frozen validator/graphs do not import this experimental module. A witness
proves location only. It deliberately cannot grant relation entailment or turn
an old reconstructed E3 record into an automatically qualified assertion.
"""
from __future__ import annotations

import hashlib
import re


def locate(source: str, surface: str):
    """Exact non-whitespace characters and order, with source offset recovery."""
    tokens = str(surface or '').split()
    if not tokens or '...' in surface or '…' in surface:
        return None
    match = re.search(r'\s+'.join(re.escape(t) for t in tokens), source)
    return (match.start(), match.end()) if match else None


def old_binding_ready(record: dict) -> bool:
    evidence = record.get('evidence_validation') or {}
    return bool(record.get('evidence_level') in {'E1', 'E2'}
                and evidence.get('valid') and evidence.get('silver_eligible'))


def _valid_box(cell: dict, page: dict):
    box = cell.get('bbox') or {}
    try:
        x0, y0, x1, y1 = [float(box[k]) for k in ('x0', 'top', 'x1', 'bottom')]
        if 0 <= x0 < x1 <= page['page_width'] and 0 <= y0 < y1 <= page['page_height']:
            return (x0, y0, x1, y1)
    except (KeyError, TypeError, ValueError):
        pass
    return None


def source_witness(record: dict, page: dict) -> dict:
    text = page['page_text']
    if hashlib.sha256(text.encode()).hexdigest() != page['page_text_sha256']:
        raise ValueError('Source page hash mismatch')
    for key in ('doc_id', 'pdf_page_number', 'page_text_sha256', 'document_sha256'):
        if record.get(key) != page.get(key):
            raise ValueError(f'Candidate provenance mismatch: {key}')
    head, tail = record['head_surface'], record['tail_surface']
    common = dict(parent_triple_id=record['triple_id'],
                  source_page_sha256=page['page_text_sha256'],
                  document_sha256=page['document_sha256'],
                  original_evidence_level=record.get('evidence_level'),
                  semantic_support_verified=False, automatically_qualified=False,
                  upstream_fields_changed=False)
    if old_binding_ready(record):
        return dict(common, status='original_binding_reused', repair_proposed=False)

    # Ambiguous or split rows are deliberately not joined, even if semantically plausible.
    pairs = []
    for table in page.get('tables', []):
        for row in table.get('rows', []):
            cells = row.get('cells', [])
            heads = [c for c in cells if locate(c.get('text', ''), head)]
            tails = [c for c in cells if locate(c.get('text', ''), tail)]
            for h in heads:
                for t in tails:
                    hb, tb = _valid_box(h, page), _valid_box(t, page)
                    if (hb and tb and h.get('table_id') == t.get('table_id') == table.get('table_id')
                            and h.get('row_id') == t.get('row_id') == row.get('row_id')
                            and min(hb[3], tb[3]) > max(hb[1], tb[1])):
                        pairs.append((h, t))
    if len(pairs) == 1:
        h, t = pairs[0]
        # Exact parser cells, with unchanged bbox and no invented semantic column roles.
        return dict(common, status='new_native_same_row_witness', repair_proposed=True,
                    kind='parser_cells', units=[h, t] if h['cell_id'] != t['cell_id'] else [h],
                    head_cell=h['cell_id'], tail_cell=t['cell_id'],
                    relation_review_required=True, human_visual_reviewed=False)
    if len(pairs) > 1:
        return dict(common, status='ambiguous_native_table_binding', repair_proposed=False)
    if page.get('tables') or record.get('evidence_level') == 'E2':
        return dict(common, status='table_layout_or_surface_unresolved', repair_proposed=False)

    quote = locate(text, record.get('evidence_text', ''))
    if not quote:
        return dict(common, status='original_quote_not_verbatim', repair_proposed=False)
    start, end = max(0, quote[0] - 400), min(len(text), quote[1] + 400)
    hs, ts = locate(text[start:end], head), locate(text[start:end], tail)
    if not hs or not ts:
        return dict(common, status='endpoint_missing_in_bounded_window', repair_proposed=False)
    lo = min(quote[0], start + hs[0], start + ts[0])
    hi = max(quote[1], start + hs[1], start + ts[1])
    if hi - lo > 1200:
        return dict(common, status='bounded_window_too_long', repair_proposed=False)
    return dict(common, status='new_contiguous_context_witness', repair_proposed=True,
                kind='page_span', start=lo, end=hi, source_text=text[lo:hi],
                head_span=[start + hs[0], start + hs[1]],
                tail_span=[start + ts[0], start + ts[1]], relation_review_required=True,
                evidence_contract_status='new_proposal_not_E1_promotion')


CONDITION = re.compile(r'\b(?:if|unless|when|only|except|provided that)\b|如果|仅当|除非|只有|除外', re.I)
NEGATIVE_WARNING = re.compile(r'\b(?:never|do not|must not|should not|shall not|no)\b|不得|禁止|严禁|不要', re.I)
PREVENT_LINK = re.compile(r'\b(?:prevent\w*|avoid\w*|protect\w*)\b|防止|预防|避免', re.I)


def relation_warnings(record: dict) -> list[str]:
    relation = record['relation']
    head, tail = record['head_surface'], record['tail_surface']
    quote = record.get('evidence_text', '')
    warnings = []
    if not record.get('relation_type_valid'):
        warnings.append('schema_type_mismatch')
    if relation == 'maintained_by' and re.search(
        r'\b(?:no maintenance|maintenance[- ]free|does not require maintenance|requires? no maintenance)\b|无需维护|免维护|不需要维护', tail, re.I
    ):
        warnings.append('negative_maintenance_requirement')
    if relation in {'diagnosed_by', 'inspected_by'} and re.fullmatch(
        r'(?:the |motor |pump |equipment )*(?:nameplate|name plate|data plate)|(?:电机|泵|设备)?铭牌', tail.strip(), re.I
    ):
        warnings.append('specification_source_not_diagnostic_action')
    if relation == 'prevented_by':
        if record.get('head_type') in {'Equipment', 'Component'}:
            warnings.append('prevention_target_is_component')
        if NEGATIVE_WARNING.search(quote + ' ' + tail) and not PREVENT_LINK.search(quote):
            warnings.append('warning_without_explicit_prevention_link')
    if CONDITION.search(quote) and not CONDITION.search(head + ' ' + tail):
        warnings.append('condition_requires_explicit_representation')
    return warnings


def probe(record: dict, page: dict) -> dict:
    witness = source_witness(record, page)
    a = old_binding_ready(record)
    b = a or witness['repair_proposed']
    flags = relation_warnings(record)
    return dict(triple_id=record['triple_id'], doc_id=record['doc_id'],
                pdf_page_number=record['pdf_page_number'], witness=witness,
                relation_warnings=flags,
                technical_readiness={'A': a, 'B': b, 'C': a and not flags, 'D': b and not flags},
                original_qualified=record['decision'] == 'silver_candidate',
                new_qualification_decision=None)
