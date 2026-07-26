"""Structural validation for E2 table evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence
import unicodedata

from .evidence_span_validator import E2


@dataclass(frozen=True)
class TableEvidenceUnit:
    table_id: str
    row_id: str
    column_name: str
    text: str
    start: int
    end: int
    row_group_id: str | None = None
    role: str | None = None
    bbox: tuple[float, float, float, float] | None = None

    @classmethod
    def from_value(
        cls, value: "TableEvidenceUnit | Mapping[str, object]"
    ) -> "TableEvidenceUnit":
        if isinstance(value, cls):
            return value
        bbox_value = value.get("bbox")
        bbox = None
        if isinstance(bbox_value, Sequence) and not isinstance(
            bbox_value, (str, bytes)
        ):
            numeric = tuple(float(item) for item in bbox_value)
            if len(numeric) == 4:
                bbox = numeric  # type: ignore[assignment]
        return cls(
            table_id=str(value.get("table_id", "")),
            row_id=str(value.get("row_id", "")),
            row_group_id=(
                str(value["row_group_id"])
                if value.get("row_group_id") not in (None, "")
                else None
            ),
            column_name=str(value.get("column_name", "")),
            text=str(value.get("text", "")),
            start=int(value.get("start", -1)),
            end=int(value.get("end", -1)),
            role=str(value["role"]) if value.get("role") is not None else None,
            bbox=bbox,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TableAlignmentValidation:
    valid: bool
    evidence_level: str
    units: tuple[TableEvidenceUnit, ...]
    alignment_method: str
    head_unit_indexes: tuple[int, ...]
    tail_unit_indexes: tuple[int, ...]
    silver_eligible: bool
    hard_veto_reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _contains(text: str, surface: str) -> bool:
    surface_value = _normalized(surface)
    return bool(surface_value) and surface_value in _normalized(text)


def validate_table_alignment(
    *,
    page_text: str,
    evidence_units: Sequence[TableEvidenceUnit | Mapping[str, object]],
    head_surface: str,
    tail_surface: str,
    visual_layout_checked: bool,
) -> TableAlignmentValidation:
    """Require one table and one row or explicitly verified merged row group."""

    units = tuple(TableEvidenceUnit.from_value(item) for item in evidence_units)
    reasons: list[str] = []
    if not units:
        reasons.append("table_evidence_units_missing")
    if not visual_layout_checked:
        reasons.append("table_visual_layout_not_checked")
    if any(not unit.table_id for unit in units):
        reasons.append("table_id_missing")
    if any(not unit.row_id for unit in units):
        reasons.append("row_id_missing")
    if any(not unit.column_name for unit in units):
        reasons.append("column_name_missing")

    table_ids = {unit.table_id for unit in units if unit.table_id}
    if len(table_ids) > 1:
        reasons.append("cross_table_evidence")

    rows = {unit.row_id for unit in units if unit.row_id}
    row_groups = {
        unit.row_group_id for unit in units if unit.row_group_id is not None
    }
    same_row = len(rows) == 1 and bool(rows)
    same_verified_group = (
        len(row_groups) == 1
        and bool(row_groups)
        and all(unit.row_group_id is not None for unit in units)
    )
    if not same_row and not same_verified_group:
        reasons.append("cross_row_table_evidence")

    bbox_located_units = 0
    for unit in units:
        offsets_resolved = (
            unit.start >= 0
            and unit.end > unit.start
            and unit.end <= len(page_text)
        )
        if offsets_resolved:
            if page_text[unit.start : unit.end] != unit.text:
                reasons.append("table_unit_text_offset_mismatch")
        elif unit.bbox is not None and unit.text.strip():
            # Table extraction is a coordinate-preserving source channel.
            # Multi-column page text need not serialize each cell contiguously.
            bbox_located_units += 1
        else:
            reasons.append("table_unit_has_neither_offsets_nor_bbox")

    head_indexes = tuple(
        index for index, unit in enumerate(units) if _contains(unit.text, head_surface)
    )
    tail_indexes = tuple(
        index for index, unit in enumerate(units) if _contains(unit.text, tail_surface)
    )
    if not head_indexes:
        reasons.append("head_surface_not_in_table_units")
    if not tail_indexes:
        reasons.append("tail_surface_not_in_table_units")

    reasons = list(dict.fromkeys(reasons))
    valid = not reasons
    method = (
        "same_visual_row"
        if same_row
        else "verified_merged_row_group"
        if same_verified_group
        else "unaligned"
    )
    return TableAlignmentValidation(
        valid=valid,
        evidence_level=E2,
        units=units,
        alignment_method=method,
        head_unit_indexes=head_indexes,
        tail_unit_indexes=tail_indexes,
        silver_eligible=valid,
        hard_veto_reasons=tuple(reasons),
        review_reasons=(
            ("table_cells_located_by_bbox",) if bbox_located_units else ()
        ),
    )
