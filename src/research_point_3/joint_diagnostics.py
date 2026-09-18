"""Build-only analysis of feasible mass and joint-head violations."""
from .field_audit import field_task_metrics, counted_rate
from .diagnostics import mean
from .joint_contract import contract_mass, hard_empty_rows
from .model import CardFieldStateIndex as State


def augment_joint_row(row, output, batch_row):
    import torch
    requested = row['requested_index']
    mask = batch_row['requested_candidate_mask'] & batch_row['availability_mask']
    support = output.support_logits.detach().cpu()
    fields = output.field_state_logits.detach().cpu()[:, requested]
    counts = output.cardinality_logits.detach().cpu()[:, requested]
    z = float(contract_mass(support, fields, counts, mask[None])[0])
    state = int(fields.argmax(-1)[0]); n = int(counts.argmax(-1)[0])
    s = int(((support[0].sigmoid() >= .5) & mask).sum())
    valid = (n <= s and ((n == 0 and state in (State.INSUFFICIENT, State.NOT_APPLICABLE))
             or (n >= 1 and state == State.SUPPORTED) or (n >= 2 and state == State.CONFLICT)))
    hard = bool(hard_empty_rows(batch_row['support_labels'][None], mask[None],
                               batch_row['cardinality_labels'][requested:requested+1])[0])
    return {**row, 'joint_contract_mass': z, 'joint_violation_mass': 1-z,
            'raw_joint_violation': not valid, 'fully_assessed_hard_empty': hard,
            'eligible_candidates': int(mask.sum()), 'eligible_predicted_supported': s}


def joint_metrics(rows):
    hard = [r for r in rows if r['fully_assessed_hard_empty']]
    available = [r for r in rows if r['eligible_candidates']]
    nonempty = [r for r in rows if r['teacher_selected_ids']]
    return {'hard_empty_false_fill': counted_rate(sum(bool(r['selected_ids']) for r in hard), len(hard)),
            'raw_joint_violation': counted_rate(sum(r['raw_joint_violation'] for r in rows), len(rows)),
            'mean_violation_mass': mean(r['joint_violation_mass'] for r in rows),
            'mean_violation_mass_available': mean(r['joint_violation_mass'] for r in available),
            'mean_violation_mass_nonempty': mean(r['joint_violation_mass'] for r in nonempty),
            'mean_violation_mass_hard_empty': mean(r['joint_violation_mass'] for r in hard)}


def grouped_joint_metrics(rows):
    result = {}
    for split in ('train','validation'):
        for kind in ('all','original','derived'):
            selected = [r for r in rows if r['split']==split and
                        (kind=='all' or (r['perturbation_id']=='original')==(kind=='original'))]
            if selected:
                metrics = joint_metrics(selected)
                metrics['by_scenario'] = {s: joint_metrics([r for r in selected if r['scenario_id']==s])
                                          for s in sorted({r['scenario_id'] for r in selected})}
                metrics['scenario_macro_violation_mass'] = mean(m['mean_violation_mass'] for m in metrics['by_scenario'].values())
                result[split+'_'+kind] = metrics
    return result
