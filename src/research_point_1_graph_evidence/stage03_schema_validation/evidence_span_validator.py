"""Strict source-span validation for marine-pump evidence candidates.

The validator distinguishes three evidence levels:

* E1: a direct page-text span (exact or whitespace-normalized).
* E2: verified table evidence; validated in ``table_alignment_validator``.
* E3: a reconstructed context spanning independently located head/tail
  surfaces.  E3 may be retained for review but is never automatically
  eligible for the Silver layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Final


E1: Final[str] = "E1"
E2: Final[str] = "E2"
E3: Final[str] = "E3"
_ELLIPSIS_MARKERS: Final[tuple[str, ...]] = ("...", "…")


@dataclass(frozen=True)
class SurfaceSpan:
    """An exact span in the source page."""

    surface: str
    source_text: str
    start: int
    end: int
    match_method: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceSpanValidation:
    """Result of validating one text evidence proposal."""

    valid: bool
    evidence_level: str | None
    evidence_text: str
    evidence_start: int | None
    evidence_end: int | None
    match_method: str
    head_span: SurfaceSpan | None
    tail_span: SurfaceSpan | None
    silver_eligible: bool
    hard_veto_reasons: tuple[str, ...] = ()
    silver_veto_reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        return result


def _escaped_whitespace_pattern(value: str) -> str | None:
    tokens = value.strip().split()
    if not tokens or len(tokens) > 240:
        return None
    return r"\s+".join(re.escape(token) for token in tokens)


def _locate(
    source: str,
    query: str,
    *,
    window_start: int = 0,
    window_end: int | None = None,
) -> SurfaceSpan | None:
    """Locate ``query`` in ``source`` while returning exact source offsets."""

    query = str(query or "").strip()
    if not query:
        return None
    end = len(source) if window_end is None else min(len(source), window_end)
    start = max(0, window_start)
    window = source[start:end]

    exact_index = window.find(query)
    if exact_index >= 0:
        absolute_start = start + exact_index
        return SurfaceSpan(
            surface=query,
            source_text=source[absolute_start : absolute_start + len(query)],
            start=absolute_start,
            end=absolute_start + len(query),
            match_method="exact",
        )

    pattern = _escaped_whitespace_pattern(query)
    if pattern is None:
        return None
    match = re.search(pattern, window)
    method = "whitespace_normalized"
    if match is None:
        match = re.search(pattern, window, flags=re.IGNORECASE)
        method = "case_and_whitespace_normalized"
    if match is None:
        return None
    absolute_start = start + match.start()
    absolute_end = start + match.end()
    return SurfaceSpan(
        surface=query,
        source_text=source[absolute_start:absolute_end],
        start=absolute_start,
        end=absolute_end,
        match_method=method,
    )


def locate_surface(page_text: str, surface: str) -> SurfaceSpan | None:
    """Public surface locator used by validation and tests."""

    return _locate(page_text, surface)


def validate_evidence_span(
    *,
    page_text: str,
    evidence_text: str,
    head_surface: str,
    tail_surface: str,
    allow_reconstruction: bool = True,
    maximum_reconstructed_characters: int = 3000,
) -> EvidenceSpanValidation:
    """Validate direct evidence or conservatively construct an E3 context.

    Direct evidence must be one resolvable page span and must contain both
    entity surface forms.  A reconstruction is allowed only to support review;
    it carries an explicit Silver veto.
    """

    page_text = str(page_text or "")
    proposed = str(evidence_text or "").strip()
    if not page_text:
        return EvidenceSpanValidation(
            valid=False,
            evidence_level=None,
            evidence_text=proposed,
            evidence_start=None,
            evidence_end=None,
            match_method="empty_page",
            head_span=None,
            tail_span=None,
            silver_eligible=False,
            hard_veto_reasons=("empty_page_text",),
        )
    if not proposed:
        direct = None
    elif any(marker in proposed for marker in _ELLIPSIS_MARKERS):
        return EvidenceSpanValidation(
            valid=False,
            evidence_level=None,
            evidence_text=proposed,
            evidence_start=None,
            evidence_end=None,
            match_method="ellipsis_forbidden",
            head_span=None,
            tail_span=None,
            silver_eligible=False,
            hard_veto_reasons=("evidence_contains_ellipsis",),
        )
    else:
        direct = _locate(page_text, proposed)

    if direct is not None:
        head_span = _locate(
            page_text,
            head_surface,
            window_start=direct.start,
            window_end=direct.end,
        )
        tail_span = _locate(
            page_text,
            tail_surface,
            window_start=direct.start,
            window_end=direct.end,
        )
        missing: list[str] = []
        if head_span is None:
            missing.append("head_surface_not_in_evidence")
        if tail_span is None:
            missing.append("tail_surface_not_in_evidence")
        return EvidenceSpanValidation(
            valid=not missing,
            evidence_level=E1,
            evidence_text=direct.source_text,
            evidence_start=direct.start,
            evidence_end=direct.end,
            match_method=direct.match_method,
            head_span=head_span,
            tail_span=tail_span,
            silver_eligible=not missing,
            hard_veto_reasons=tuple(missing),
            review_reasons=(
                ("case_normalized_source_match",)
                if direct.match_method == "case_and_whitespace_normalized"
                else ()
            ),
        )

    if not allow_reconstruction:
        return EvidenceSpanValidation(
            valid=False,
            evidence_level=None,
            evidence_text=proposed,
            evidence_start=None,
            evidence_end=None,
            match_method="not_found",
            head_span=None,
            tail_span=None,
            silver_eligible=False,
            hard_veto_reasons=("evidence_span_not_verified",),
        )

    head_span = _locate(page_text, head_surface)
    tail_span = _locate(page_text, tail_surface)
    if head_span is None or tail_span is None:
        missing = []
        if head_span is None:
            missing.append("head_surface_not_found_on_page")
        if tail_span is None:
            missing.append("tail_surface_not_found_on_page")
        return EvidenceSpanValidation(
            valid=False,
            evidence_level=None,
            evidence_text=proposed,
            evidence_start=None,
            evidence_end=None,
            match_method="not_found",
            head_span=head_span,
            tail_span=tail_span,
            silver_eligible=False,
            hard_veto_reasons=tuple(missing),
        )

    start = min(head_span.start, tail_span.start)
    end = max(head_span.end, tail_span.end)
    if end - start > maximum_reconstructed_characters:
        return EvidenceSpanValidation(
            valid=False,
            evidence_level=E3,
            evidence_text="",
            evidence_start=start,
            evidence_end=end,
            match_method="reconstructed_context_too_long",
            head_span=head_span,
            tail_span=tail_span,
            silver_eligible=False,
            hard_veto_reasons=("reconstructed_context_too_long",),
        )

    reconstructed = page_text[start:end].strip()
    adjusted_start = page_text.find(reconstructed, start, end + 1)
    if adjusted_start < 0:
        adjusted_start = start
    return EvidenceSpanValidation(
        valid=True,
        evidence_level=E3,
        evidence_text=reconstructed,
        evidence_start=adjusted_start,
        evidence_end=adjusted_start + len(reconstructed),
        match_method="head_tail_context_reconstructed",
        head_span=head_span,
        tail_span=tail_span,
        silver_eligible=False,
        silver_veto_reasons=("evidence_level_e3_not_silver",),
        review_reasons=("reconstructed_evidence_requires_review",),
    )

