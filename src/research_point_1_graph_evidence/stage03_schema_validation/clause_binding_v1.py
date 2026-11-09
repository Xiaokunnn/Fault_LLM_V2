"""Bounded source-clause refinement of an automatic baseline; no labels or IO.

Only the three declared grammar families are checked. Passing this component
is neither general textual entailment nor expert factual certification.
"""
import copy
import re

SEMANTIC_FIELDS = (
    'head_surface', 'head_type', 'relation', 'tail_surface', 'tail_type',
    'conditions', 'modality', 'polarity', 'scope', 'applicability', 'condition_logic',
)


def flat(text):
    return ' '.join(text.split())


def norm(text):
    return re.sub(r'[^\w]+', ' ', flat(text).lower()).strip()


def source_spans(text, quote):
    if not quote.strip():
        return []
    positions = [i for i, ch in enumerate(text) if not ch.isspace()]
    joined = ''.join(text[i] for i in positions)
    needle = ''.join(quote.split())
    found, offset = [], 0
    while True:
        k = joined.find(needle, offset)
        if k < 0:
            return found
        start, end = positions[k], positions[k + len(needle) - 1] + 1
        found.append(dict(kind='page_span', start=start, end=end, text=text[start:end]))
        offset = k + len(needle)


def minimum_unique(original, proposals):
    """All weights are one; ties between distinct semantic candidates abstain."""
    unique = []
    for proposal in proposals:
        if not any(all(proposal.get(k) == p.get(k) for k in SEMANTIC_FIELDS) for p in unique):
            unique.append(proposal)
    if not unique:
        return None
    costs = [sum(original.get(k) != p.get(k) for k in SEMANTIC_FIELDS) for p in unique]
    winners = [p for p, cost in zip(unique, costs) if cost == min(costs)]
    return copy.deepcopy(winners[0]) if len(winners) == 1 else None


def refine(raw, page, baseline, screen, mode='repair'):
    if mode not in {'filter', 'repair'}:
        raise ValueError(mode)
    raw = {k: copy.deepcopy(raw[k]) for k in SEMANTIC_FIELDS[:10] + ('evidence_text', 'evidence_unit_ids')}
    result = copy.deepcopy(baseline)
    original = copy.deepcopy(baseline['payload'])
    q, text = flat(raw['evidence_text']), flat(page['page_text'])
    proposals, issues, witnesses = [], [], []
    clearable = set()

    # A full candidate check complement, rather than an old erroneous subject,
    # must match one explicit bullet. This is intentionally not fuzzy matching.
    if 'nonunique_inspection_object' in result['barriers']:
        issues.append('multi_object_inspection')
        chunks = re.split(r'\s+(?:-|●)\s+', q)
        complement = re.sub(r'^check that\s+', '', flat(raw['tail_surface']), flags=re.I)
        if len(chunks) > 2 and re.search(r'\bcheck that\s*$', chunks[0], re.I):
            for clause in chunks[1:]:
                if norm(complement) != norm(clause):
                    continue
                subject = re.match(r'(?:the\s+)?(.+?)\s+(?:is|are|rotates?|turns?)\b', clause, re.I)
                if not subject or subject.group(1).lower() not in {'shaft', 'pump casing', 'coupling', 'rotor', 'seal'}:
                    continue
                clause_hits = source_spans(page['page_text'], clause)
                context_hits = source_spans(page['page_text'], chunks[0])
                if len(clause_hits) != 1 or len(context_hits) != 1:
                    continue
                proposal = copy.deepcopy(original)
                proposal.update(head_surface=subject.group(1), head_type='Component',
                                tail_surface=raw['tail_surface'], tail_type='InspectionAction',
                                relation='inspected_by', conditions=copy.deepcopy(raw['conditions']))
                if chunks[0] not in proposal['conditions']:
                    proposal['conditions'].append(chunks[0])
                proposals.append(proposal)
                witnesses.extend(clause_hits + context_hits)
            clearable.add('nonunique_inspection_object')

    # Bracketed restrictions are one source atom. Do not silently distribute
    # qualifiers, infer a numeric failure threshold, or weaken an AND to an OR.
    risk_relation = raw['relation'] in {'causes', 'increases_risk_of'}
    if risk_relation and re.search(r'\bOtherwise\b', q, re.I):
        issues.append('otherwise_permission_scope')
        pattern = r'((?:For safety reasons\s+)?the\s+[\w -]+?\s+is\s+only allowed to\b[^()!?]*\([^()]+\)\.)\s*(Otherwise\b[^.!?]*\.)'
        for match in re.finditer(pattern, text, re.I):
            permission, consequence = match.group(1).strip(), match.group(2).strip()
            whole = permission + ' ' + consequence
            # The actual candidate quote must be inside this adjacent source
            # pair, and the candidate head/tail must belong to the right sides.
            if not source_spans(whole, q):
                continue
            if norm(raw['head_surface']) not in norm(permission) or norm(raw['tail_surface']) not in norm(consequence):
                continue
            hits = source_spans(page['page_text'], whole)
            if len(hits) != 1 or raw['polarity'] != 'positive':
                continue
            proposal = copy.deepcopy(original)
            atom = {'operator': 'SOURCE_PERMISSION', 'text': permission}
            # Retain each previous condition, but classify those copied from
            # the allowance as bounds of that allowance, not positive triggers.
            bounds = [c for c in original['conditions'] if norm(c) in norm(permission)]
            unrelated = [c for c in original['conditions'] if c not in bounds]
            proposal.update(
                conditions=unrelated + ['outside the source-stated permitted operating envelope: ' + permission],
                condition_logic={'operator': 'NOT', 'argument': atom},
                source_allowance_conditions=bounds, modality='possible',
            )
            proposals.append(proposal)
            witnesses.extend(hits)

    # Keep the complete causal sentence but abstain from an unsupported direct
    # A->C edge. No assumption that a participial clause uniquely modifies B.
    if risk_relation:
        chain = re.search(r'(.+?)\s+will\s+(?:increase|decrease|raise|reduce)\s+(.+?),\s*causing\s+(.+)', q, re.I)
        if chain and norm(raw['head_surface']) in norm(chain.group(1)) and norm(raw['tail_surface']) in norm(chain.group(3)):
            issues.append('causal_attachment_not_directly_bound')
            proposals = []
            witnesses.extend(source_spans(page['page_text'], q))

    result['clause_binding'] = {'mode': mode, 'issues': issues, 'proposal_count': len(proposals),
                                'outcome': 'unchanged', 'grammar_semantic_guarantee': False}
    if not issues:
        return result
    # Candidates still have to satisfy the inherited structural screen.
    feasible = [p for p in proposals if not screen(p, page)]
    chosen = minimum_unique(original, feasible) if mode == 'repair' else None
    if chosen is not None and not (set(result['barriers']) - clearable):
        result['payload'] = chosen
        result['barriers'] = [b for b in result['barriers'] if b not in clearable]
        result['screen_flags'] = list(screen(chosen, page))
        result['included'] = not result['barriers'] and not result['screen_flags']
        result['clause_binding']['outcome'] = 'repaired' if result['included'] else 'quarantined'
    else:
        result['included'] = False
        result['barriers'] += ['clause_binding:' + issue for issue in issues]
        result['clause_binding']['outcome'] = 'quarantined'
    for witness in witnesses:
        if witness not in result['source_witnesses']:
            result['source_witnesses'].append(witness)
    delta = {k: {'before': original.get(k), 'after': result['payload'].get(k)}
             for k in set(original) | set(result['payload']) if original.get(k) != result['payload'].get(k)}
    result['rules'].append({'rule': 'SOURCE_CLAUSE_BINDING', 'reason': '; '.join(issues), 'changes': delta})
    result['clause_binding']['baseline_delta'] = delta
    # Cumulative original->current ledger, alongside the baseline->current delta.
    result['changes'] = {k: {'before': raw.get(k), 'after': result['payload'].get(k)}
                         for k in set(raw) | set(result['payload']) if raw.get(k) != result['payload'].get(k)}
    return result
