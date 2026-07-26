"""Serializable document-layout models.

The graph pipeline treats source layout as evidence, not presentation metadata.
Every table cell therefore keeps its page coordinates and structural identity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    x0: float
    top: float
    x1: float
    bottom: float

    @classmethod
    def from_tuple(cls, value: tuple[float, float, float, float]) -> "BoundingBox":
        return cls(*(round(float(part), 3) for part in value))


@dataclass(frozen=True)
class TextBlock:
    block_id: str
    text: str
    bbox: BoundingBox
    reading_order: int
    block_type: str = "text_line"


@dataclass(frozen=True)
class TableCell:
    cell_id: str
    table_id: str
    row_id: str
    row_group_id: str
    row_index: int
    column_index: int
    column_name: str
    column_role: str
    text: str
    page_text_start: int | None
    page_text_end: int | None
    page_text_source: str | None
    bbox: BoundingBox


@dataclass(frozen=True)
class TableRow:
    row_id: str
    row_group_id: str
    row_index: int
    cells: list[TableCell] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedTable:
    table_id: str
    bbox: BoundingBox
    column_names: list[str]
    column_roles: list[str]
    rows: list[TableRow] = field(default_factory=list)


@dataclass(frozen=True)
class PrintedPageLabel:
    value: str | None
    confidence: float
    method: str
    bbox: BoundingBox | None = None


@dataclass(frozen=True)
class ParsedPage:
    schema_version: str
    parser_version: str
    doc_id: str
    document_split: str
    source_family_id: str
    publisher: str
    title: str
    source_url: str
    source_tier: str
    pump_type: str | None
    service: str | None
    applicability_scope: str | None
    local_file: str
    document_sha256: str
    pdf_page_number: int
    page_width: float
    page_height: float
    page_text: str
    page_text_sha256: str
    source_language: str
    source_language_confidence: float
    language_detection_method: str
    printed_page: PrintedPageLabel
    visual_layout_checked: bool
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
