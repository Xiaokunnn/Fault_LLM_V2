"""Lightweight multi-task evidence controller for research point 3.

The controller is intentionally independent of a generative language model.  It
consumes frozen query/evidence features and predicts the four decisions that must
remain auditable at the edge:

1. an evidence ranking/pointer distribution;
2. binary direct-support decisions;
3. diagnosis-card field state and cardinality (including active underfilling);
4. the three-way answer/fallback/abstain route.

PyTorch is optional for the repository as a whole.  Importing this module remains
safe without it; constructing the model raises an actionable dependency error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import CARD_SLOT_ROLES, CardFieldState, RouteAction

try:  # pragma: no cover - exercised only in a deliberately torch-free environment
    import torch
    from torch import Tensor, nn
except ImportError:  # pragma: no cover
    torch = None
    Tensor = Any
    nn = None


TORCH_INSTALL_HINT = (
    "Research point 3 model code requires PyTorch. Install a PyTorch build "
    "appropriate for the deployment machine before training or inference; the "
    "base repository intentionally does not force a CUDA-specific wheel."
)

CARD_FIELD_ROLES = tuple(role.value for role in CARD_SLOT_ROLES)
CARD_FIELD_STATES = tuple(state.value for state in CardFieldState)
ROUTE_ACTIONS = tuple(action.value for action in RouteAction)


def require_torch() -> None:
    """Raise a clear error at the first operation that actually needs PyTorch."""

    if torch is None or nn is None:
        raise RuntimeError(TORCH_INSTALL_HINT)


@dataclass(frozen=True)
class EvidenceControllerConfig:
    """Dimensions and bounded decision spaces for the evidence controller."""

    query_dim: int
    evidence_dim: int
    hidden_dim: int = 192
    max_cardinality: int = 3
    dropout: float = 0.1
    num_card_fields: int = len(CARD_FIELD_ROLES)
    num_field_states: int = len(CARD_FIELD_STATES)
    num_route_actions: int = len(ROUTE_ACTIONS)
    support_context: str = "pointwise"

    def __post_init__(self) -> None:
        if self.support_context not in ("pointwise", "local_residual", "set_residual"):
            raise ValueError("unknown support_context")
        for name in (
            "query_dim",
            "evidence_dim",
            "hidden_dim",
            "max_cardinality",
            "num_card_fields",
            "num_field_states",
            "num_route_actions",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")
        if not 0.0 <= float(self.dropout) < 1.0:
            raise ValueError("dropout must be in [0, 1)")
        if self.num_card_fields != len(CARD_FIELD_ROLES):
            raise ValueError("num_card_fields must match the frozen diagnosis-card schema")
        if self.num_field_states != len(CARD_FIELD_STATES):
            raise ValueError("num_field_states must match CardFieldState")
        if self.num_route_actions != len(ROUTE_ACTIONS):
            raise ValueError("num_route_actions must match RouteAction")

    @property
    def num_cardinality_classes(self) -> int:
        """Cardinality classes are the inclusive integer range 0..max_cardinality."""

        return self.max_cardinality + 1


@dataclass
class EvidenceControllerOutput:
    """Logits emitted by the four decision heads.

    ``rank_logits`` and ``support_logits`` are already fail-closed: unavailable
    positions contain the minimum finite value of their floating dtype.  The mask
    is returned as part of the output so losses and decoders cannot accidentally
    forget the intervention boundary.
    """

    rank_logits: Tensor
    support_logits: Tensor
    field_state_logits: Tensor
    cardinality_logits: Tensor
    route_logits: Tensor
    availability_mask: Tensor

    def masked_rank_probabilities(self, temperature: float = 1.0) -> Tensor:
        """Return a zero-mass distribution when every candidate is unavailable."""

        require_torch()
        if temperature <= 0:
            raise ValueError("temperature must be > 0")
        scaled = self.rank_logits / float(temperature)
        probabilities = torch.softmax(scaled, dim=-1)
        probabilities = probabilities * self.availability_mask.to(probabilities.dtype)
        denominator = probabilities.sum(dim=-1, keepdim=True)
        return torch.where(
            denominator > 0,
            probabilities / denominator.clamp_min(torch.finfo(probabilities.dtype).tiny),
            torch.zeros_like(probabilities),
        )


if nn is not None:

    class LightweightEvidenceController(nn.Module):
        """Small four-head policy module over a bounded local evidence memory."""

        def __init__(self, config: EvidenceControllerConfig) -> None:
            super().__init__()
            self.config = config
            hidden = config.hidden_dim

            self.query_encoder = nn.Sequential(
                nn.Linear(config.query_dim, hidden),
                nn.LayerNorm(hidden),
                nn.GELU(),
                nn.Dropout(config.dropout),
            )
            self.evidence_encoder = nn.Sequential(
                nn.Linear(config.evidence_dim, hidden),
                nn.LayerNorm(hidden),
                nn.GELU(),
                nn.Dropout(config.dropout),
            )
            self.candidate_fusion = nn.Sequential(
                nn.Linear(hidden * 4, hidden),
                nn.LayerNorm(hidden),
                nn.GELU(),
                nn.Dropout(config.dropout),
            )

            # Head 1 and head 2 operate at evidence-pointer granularity.
            self.rank_head = nn.Linear(hidden, 1)
            self.support_head = nn.Linear(hidden, 1)

            # The availability signature is explicit.  Consequently evidence-set
            # removal/interference is an observable intervention rather than an
            # impossible closed-book target.
            global_dim = hidden * 3 + 3
            self.global_fusion = nn.Sequential(
                nn.Linear(global_dim, hidden),
                nn.LayerNorm(hidden),
                nn.GELU(),
                nn.Dropout(config.dropout),
            )

            # Head 3 is one joint card head: each frozen card field receives a
            # state distribution and a bounded 0..K cardinality distribution.
            card_width = config.num_field_states + config.num_cardinality_classes
            self.card_head = nn.Linear(hidden, config.num_card_fields * card_width)

            # Head 4 uses the RouteAction enum order: answer, fallback, abstain.
            self.route_head = nn.Linear(hidden, config.num_route_actions)

            if config.support_context != "pointwise":
                from .set_support import CandidateContextSupport
                # All original parameters and the subsequent dropout RNG stream
                # remain paired with the old pointwise model at initialization.
                with torch.random.fork_rng(devices=[]):
                    self.support_residual = CandidateContextSupport(hidden, config.support_context)

        @staticmethod
        def _masked_logits(logits: Tensor, availability_mask: Tensor) -> Tensor:
            floor = torch.finfo(logits.dtype).min
            return torch.where(availability_mask, logits, torch.full_like(logits, floor))

        def _validate_inputs(
            self,
            query_features: Tensor,
            candidate_features: Tensor,
            availability_mask: Tensor,
            selection_budget: Tensor | None,
        ) -> tuple[Tensor, Tensor, Tensor, Tensor | None]:
            if query_features.ndim != 2:
                raise ValueError("query_features must have shape [batch, query_dim]")
            if candidate_features.ndim != 3:
                raise ValueError(
                    "candidate_features must have shape [batch, candidates, evidence_dim]"
                )
            if availability_mask.ndim != 2:
                raise ValueError("availability_mask must have shape [batch, candidates]")
            batch, candidates, evidence_dim = candidate_features.shape
            if query_features.shape != (batch, self.config.query_dim):
                raise ValueError(
                    f"query_features must have shape [{batch}, {self.config.query_dim}]"
                )
            if evidence_dim != self.config.evidence_dim:
                raise ValueError(
                    f"candidate feature dimension must be {self.config.evidence_dim}"
                )
            if availability_mask.shape != (batch, candidates):
                raise ValueError("availability_mask does not align with candidate_features")
            if candidates < 1:
                raise ValueError("each batch must expose at least one bounded candidate slot")
            mask = availability_mask.to(device=candidate_features.device, dtype=torch.bool)
            if selection_budget is not None:
                budget = selection_budget.to(device=candidate_features.device, dtype=torch.long)
                if budget.ndim == 0:
                    budget = budget.expand(batch)
                if budget.shape != (batch,):
                    raise ValueError("selection_budget must be a scalar or shape [batch]")
                if torch.any(budget < 0):
                    raise ValueError("selection_budget must be >= 0")
                budget = budget.clamp_max(self.config.max_cardinality)
            else:
                budget = None
            return query_features, candidate_features, mask, budget

        def forward(
            self,
            query_features: Tensor,
            candidate_features: Tensor,
            availability_mask: Tensor,
            selection_budget: Tensor | None = None,
        ) -> EvidenceControllerOutput:
            query_features, candidate_features, mask, budget = self._validate_inputs(
                query_features, candidate_features, availability_mask, selection_budget
            )
            batch, candidates, _ = candidate_features.shape
            query_hidden = self.query_encoder(query_features)
            evidence_hidden = self.evidence_encoder(candidate_features)
            expanded_query = query_hidden.unsqueeze(1).expand(-1, candidates, -1)
            candidate_hidden = self.candidate_fusion(
                torch.cat(
                    (
                        expanded_query,
                        evidence_hidden,
                        expanded_query * evidence_hidden,
                        torch.abs(expanded_query - evidence_hidden),
                    ),
                    dim=-1,
                )
            )

            rank_logits = self._masked_logits(self.rank_head(candidate_hidden).squeeze(-1), mask)
            support_logits = self.support_head(candidate_hidden).squeeze(-1)
            if self.config.support_context != "pointwise":
                support_logits = support_logits + self.support_residual(candidate_hidden, mask)
            support_logits = self._masked_logits(support_logits, mask)

            mask_float = mask.unsqueeze(-1).to(candidate_hidden.dtype)
            available_count = mask_float.sum(dim=1)
            mean_pool = (candidate_hidden * mask_float).sum(dim=1) / available_count.clamp_min(1.0)
            masked_hidden = torch.where(
                mask.unsqueeze(-1),
                candidate_hidden,
                torch.full_like(candidate_hidden, torch.finfo(candidate_hidden.dtype).min),
            )
            max_pool = masked_hidden.max(dim=1).values
            any_available = mask.any(dim=1, keepdim=True)
            max_pool = torch.where(any_available, max_pool, torch.zeros_like(max_pool))
            count = mask.sum(dim=1, keepdim=True).to(candidate_hidden.dtype)
            candidate_count = float(candidates)
            availability_signature = torch.cat(
                (
                    count / candidate_count,
                    torch.log1p(count) / torch.log1p(
                        torch.tensor(candidate_count, device=count.device, dtype=count.dtype)
                    ),
                    any_available.to(candidate_hidden.dtype),
                ),
                dim=-1,
            )
            global_hidden = self.global_fusion(
                torch.cat((query_hidden, mean_pool, max_pool, availability_signature), dim=-1)
            )

            card_width = (
                self.config.num_field_states + self.config.num_cardinality_classes
            )
            card_logits = self.card_head(global_hidden).view(
                batch, self.config.num_card_fields, card_width
            )
            field_state_logits = card_logits[..., : self.config.num_field_states]
            cardinality_logits = card_logits[..., self.config.num_field_states :]

            # With no evidence available, SUPPORTED and CONFLICT states cannot be
            # emitted.  This turns total memory removal into a fail-closed card.
            no_evidence = ~any_available.squeeze(-1)
            if torch.any(no_evidence):
                state_mask = torch.ones_like(field_state_logits, dtype=torch.bool)
                state_mask[no_evidence, :, CardFieldStateIndex.SUPPORTED] = False
                state_mask[no_evidence, :, CardFieldStateIndex.CONFLICT] = False
                field_state_logits = torch.where(
                    state_mask,
                    field_state_logits,
                    torch.full_like(
                        field_state_logits, torch.finfo(field_state_logits.dtype).min
                    ),
                )

            # A field cannot cite more items than exist in the current evidence
            # intervention.  The requested budget may tighten this upper bound,
            # but can never expand it.
            availability_cap = mask.sum(dim=1).clamp_max(
                self.config.max_cardinality
            )
            cardinality_cap = (
                torch.minimum(availability_cap, budget)
                if budget is not None
                else availability_cap
            )
            cardinalities = torch.arange(
                self.config.num_cardinality_classes,
                device=cardinality_logits.device,
            ).view(1, 1, -1)
            allowed = cardinalities <= cardinality_cap.view(-1, 1, 1)
            cardinality_logits = torch.where(
                allowed,
                cardinality_logits,
                torch.full_like(
                    cardinality_logits, torch.finfo(cardinality_logits.dtype).min
                ),
            )

            route_logits = self.route_head(global_hidden)
            if torch.any(no_evidence):
                route_mask = torch.ones_like(route_logits, dtype=torch.bool)
                route_mask[no_evidence, RouteActionIndex.ANSWER] = False
                route_logits = torch.where(
                    route_mask,
                    route_logits,
                    torch.full_like(route_logits, torch.finfo(route_logits.dtype).min),
                )

            return EvidenceControllerOutput(
                rank_logits=rank_logits,
                support_logits=support_logits,
                field_state_logits=field_state_logits,
                cardinality_logits=cardinality_logits,
                route_logits=route_logits,
                availability_mask=mask,
            )

        def parameter_count(self, *, trainable_only: bool = False) -> int:
            """Return the exact scalar parameter count for workload reporting."""

            parameters = self.parameters()
            if trainable_only:
                parameters = (item for item in parameters if item.requires_grad)
            return sum(item.numel() for item in parameters)

        def parameter_report(self) -> dict[str, int]:
            """Return counts and dense weight-size estimates for model cards."""

            total = self.parameter_count()
            trainable = self.parameter_count(trainable_only=True)
            return {
                "total_parameters": total,
                "trainable_parameters": trainable,
                "estimated_fp32_bytes": total * 4,
                "estimated_fp16_bytes": total * 2,
                "estimated_int8_bytes": total,
            }


else:  # pragma: no cover

    class LightweightEvidenceController:
        """Dependency-error placeholder used when PyTorch is unavailable."""

        def __init__(self, config: EvidenceControllerConfig) -> None:
            del config
            require_torch()


class CardFieldStateIndex:
    """Stable integer indices derived from the executable contract enum."""

    SUPPORTED = CARD_FIELD_STATES.index(CardFieldState.SUPPORTED.value)
    INSUFFICIENT = CARD_FIELD_STATES.index(CardFieldState.INSUFFICIENT.value)
    NOT_APPLICABLE = CARD_FIELD_STATES.index(CardFieldState.NOT_APPLICABLE.value)
    CONFLICT = CARD_FIELD_STATES.index(CardFieldState.CONFLICT.value)


class RouteActionIndex:
    """Stable integer indices derived from the executable contract enum."""

    ANSWER = ROUTE_ACTIONS.index(RouteAction.ANSWER.value)
    FALLBACK = ROUTE_ACTIONS.index(RouteAction.FALLBACK.value)
    ABSTAIN = ROUTE_ACTIONS.index(RouteAction.ABSTAIN.value)


__all__ = [
    "CARD_FIELD_ROLES",
    "CARD_FIELD_STATES",
    "ROUTE_ACTIONS",
    "CardFieldStateIndex",
    "EvidenceControllerConfig",
    "EvidenceControllerOutput",
    "LightweightEvidenceController",
    "RouteActionIndex",
    "TORCH_INSTALL_HINT",
    "require_torch",
]
