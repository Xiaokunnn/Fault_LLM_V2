"""Training-only evidence-contract regularization; no new inference thresholds."""
from .model import CardFieldStateIndex, require_torch


def capped_support_count(probabilities, cap):
    """Poisson-binomial DP: last bucket contains ALL counts >= cap, O(M*cap)."""
    require_torch()
    import torch
    if probabilities.ndim != 2 or cap < 1:
        raise ValueError('batched probabilities and positive cap required')
    if not torch.isfinite(probabilities).all() or torch.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError('support probabilities must be finite in [0,1]')
    state = probabilities.new_zeros((probabilities.shape[0], cap + 1))
    state[:, 0] = 1.0
    for p in probabilities.unbind(1):
        p = p[:, None]
        state = torch.cat((state[:, :1] * (1-p),
                           state[:, 1:cap] * (1-p) + state[:, :cap-1] * p,
                           state[:, cap:] + state[:, cap-1:cap] * p), dim=1)
    return state


def contract_mass(support_logits, field_logits, count_logits, candidate_mask):
    """Feasible probability mass for ONE requested field per row.

    N<=sum(B); empty states iff N=0; supported N>=1; conflict N>=2.
    Candidate independence is an auxiliary modeling assumption, not a fact claim.
    """
    import torch
    if candidate_mask.dtype != torch.bool or candidate_mask.shape != support_logits.shape:
        raise ValueError('explicit boolean eligible-candidate mask required')
    if (support_logits.ndim != 2 or field_logits.shape != (support_logits.shape[0], 4)
            or count_logits.ndim != 2 or count_logits.shape[0] != support_logits.shape[0]
            or count_logits.shape[1] < 2):
        raise ValueError('requested field/count logits do not align')
    cap = count_logits.shape[-1] - 1
    probabilities = torch.where(candidate_mask, torch.sigmoid(support_logits), 0.0)
    distribution = capped_support_count(probabilities, cap)
    survival = distribution.flip(-1).cumsum(-1).flip(-1)
    fields = field_logits.softmax(-1)
    empty = fields[:, CardFieldStateIndex.INSUFFICIENT] + fields[:, CardFieldStateIndex.NOT_APPLICABLE]
    supported = fields[:, CardFieldStateIndex.SUPPORTED]
    conflict = fields[:, CardFieldStateIndex.CONFLICT]
    compatible = torch.stack([empty, supported] + [supported + conflict] * (cap-1), dim=1)
    return (count_logits.softmax(-1) * compatible * survival).sum(-1).clamp(0.0, 1.0)


def requested_logits(output, batch):
    import torch
    mask = batch['requested_field_mask'].to(output.support_logits.device)
    if mask.dtype != torch.bool or mask.shape != output.cardinality_logits.shape[:2] or torch.any(mask.sum(-1) != 1):
        raise ValueError('exactly one requested field required')
    candidate_mask = batch['requested_candidate_mask'].to(output.support_logits.device)
    if candidate_mask.dtype != torch.bool or candidate_mask.shape != output.support_logits.shape:
        raise ValueError('candidate role mask must align')
    candidate_mask = candidate_mask & output.availability_mask
    return output.field_state_logits[mask], output.cardinality_logits[mask], candidate_mask, mask


def hard_empty_rows(labels, eligible_mask, requested_counts):
    """Unknown support is excluded, never relabeled as a negative."""
    return ((requested_counts == 0) & eligible_mask.any(-1)
            & ((labels == 0) | ~eligible_mask).all(-1))


def hard_negative_support_loss(support_logits, labels, eligible_mask, requested_counts, reference_rate):
    import torch
    import torch.nn.functional as F
    if not 0 < reference_rate <= 1:
        raise ValueError('reference rate must be the frozen train H/rows in (0,1]')
    active = hard_empty_rows(labels, eligible_mask, requested_counts)
    per_row = torch.where(eligible_mask, F.softplus(support_logits), 0.0).sum(-1)
    return torch.where(active, per_row, 0.0).mean() / reference_rate


def joint_auxiliary_losses(output, batch, *, reference_rate):
    """Read supervision only for the hard-negative term; semantic term uses predictions."""
    field, count, eligible, requested = requested_logits(output, batch)
    labels = batch['support_labels'].to(output.support_logits.device)
    target_counts = batch['cardinality_labels'].to(count.device)[requested]
    hard = hard_negative_support_loss(output.support_logits, labels, eligible, target_counts, reference_rate)
    mass = contract_mass(output.support_logits, field, count, eligible)
    semantic = -mass.clamp_min(1e-12).log().mean()
    return hard, semantic
