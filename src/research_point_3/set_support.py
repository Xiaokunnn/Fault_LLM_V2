"""Matched local/set residual support heads over a bounded candidate set."""
import torch
from torch import nn


class CandidateContextSupport(nn.Module):
    """Shared pointwise residual; only the source of context differs by arm.

    The final projection starts at zero to preserve the old model's initial
    function. No dropout or positional features are added. Permutation claims
    concern deterministic evaluation (upstream encoders may use dropout).
    """

    def __init__(self, hidden_dim: int, mode: str):
        super().__init__()
        if mode not in ('local_residual', 'set_residual'):
            raise ValueError('unknown support context mode')
        self.mode = mode
        width = max(1, hidden_dim // 4)
        self.residual = nn.Sequential(
            nn.Linear(4 * hidden_dim + 3, width), nn.LayerNorm(width), nn.GELU(),
            nn.Linear(width, 1),
        )
        nn.init.zeros_(self.residual[-1].weight)
        nn.init.zeros_(self.residual[-1].bias)

    def context_features(self, hidden, availability):
        slots = hidden.shape[1]
        mask = availability.unsqueeze(-1)
        clean = torch.where(mask, hidden, torch.zeros_like(hidden))
        if self.mode == 'set_residual':
            count = availability.sum(dim=1, keepdim=True).to(hidden.dtype)
            mean = clean.sum(dim=1) / count.clamp_min(1.)
            context = mean.unsqueeze(1).expand_as(hidden)
            count = count.unsqueeze(1).expand(-1, slots, -1)
        else:
            # A singleton context has no information about other candidates.
            context = clean
            count = mask.to(hidden.dtype)
        denominator = torch.log1p(torch.tensor(float(slots), dtype=hidden.dtype, device=hidden.device))
        signature = torch.cat((count / float(slots), torch.log1p(count) / denominator,
                               (count > 0).to(hidden.dtype)), dim=-1)
        return torch.cat((clean, context, clean * context, torch.abs(clean - context), signature), dim=-1)

    def forward(self, hidden, availability):
        return self.residual(self.context_features(hidden, availability)).squeeze(-1)
