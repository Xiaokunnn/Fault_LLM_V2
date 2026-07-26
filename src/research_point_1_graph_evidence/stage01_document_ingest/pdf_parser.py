"""Coordinate-preserving PDF parser built on pdfplumber."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable, Iterator

import pdfplumber

from .manifest_loader import DocumentDescriptor
from .models import (
    BoundingBox,
    ParsedPage,
    ParsedTable,
    PrintedPageLabel,
    TableCell,
    TableRow,
    TextBlock,
)


PARSER_VERSION = "marine_pump_pdfplumber_layout_v2_2"
PAGE_SCHEMA_VERSION = "marine_pump_page_layout_v2_2"

_COLUMN_ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "fault_or_symptom",
        (
            "fault",
            "problem",
            "symptom",
            "observation",
            "trouble",
            "故障",
            "问题",
            "现象",
            "症状",
            "异常",
        ),
    ),
    (
        "cause_or_mechanism",
        ("cause", "reason", "possible cause", "原因", "可能原因", "机理"),
    ),
    (
        "inspection_or_maintenance",
        (
            "remedy",
            "action",
            "correction",
            "solution",
            "inspection",
            "maintenance",
            "措施",
            "处理",
            "对策",
            "修复",
            "维修",
            "检查",
            "保养",
            "纠正",
        ),
    ),
)

_HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")


def detect_source_language(text: str) -> tuple[str, float, str]:
    """Return a conservative page-language label without translating text."""

    han_count = len(_HAN_PATTERN.findall(text))
    latin_count = len(_LATIN_PATTERN.findall(text))
    total = han_count + latin_count
    if total < 20:
        return "und", 0.0, "unicode_script_ratio_v1"
    han_ratio = han_count / total
    if han_ratio >= 0.70:
        return "zh", round(han_ratio, 4), "unicode_script_ratio_v1"
    if han_ratio <= 0.15:
        return "en", round(1.0 - han_ratio, 4), "unicode_script_ratio_v1"
    multilingual_confidence = 1.0 - abs(han_ratio - 0.5) * 2
    return (
        "multilingual",
        round(multilingual_confidence, 4),
        "unicode_script_ratio_v1",
    )


def infer_column_role(column_name: str) -> str:
    normalized = re.sub(r"\s+", " ", column_name).strip().lower()
    for role, terms in _COLUMN_ROLE_PATTERNS:
        if any(term in normalized for term in terms):
            return role
    return "unclassified"


def _clip_bbox_to_page(
    page: pdfplumber.page.Page,
    bbox: tuple[float, ...],
) -> tuple[tuple[float, float, float, float] | None, bool]:
    parent_x0, parent_top, parent_x1, parent_bottom = (
        float(value) for value in page.bbox
    )
    x0, top, x1, bottom = (float(value) for value in bbox)
    clipped = (
        max(parent_x0, min(x0, parent_x1)),
        max(parent_top, min(top, parent_bottom)),
        max(parent_x0, min(x1, parent_x1)),
        max(parent_top, min(bottom, parent_bottom)),
    )
    changed = any(
        abs(original - adjusted) > 1e-6
        for original, adjusted in zip((x0, top, x1, bottom), clipped)
    )
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        return None, changed
    return clipped, changed


def _extract_text_from_bbox(page: pdfplumber.page.Page, bbox: tuple[float, ...]) -> str:
    clipped, _ = _clip_bbox_to_page(page, bbox)
    if clipped is None:
        return ""
    text = page.crop(clipped).extract_text(x_tolerance=2, y_tolerance=3) or ""
    return text.strip()


def _locate_cell_in_page_text(
    page_text: str,
    cell_text: str,
) -> tuple[int | None, int | None, str | None]:
    tokens = cell_text.strip().split()
    if not tokens:
        return None, None, None
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    matches = list(re.finditer(pattern, page_text))
    if not matches:
        matches = list(re.finditer(pattern, page_text, flags=re.IGNORECASE))
    # A repeated cell string cannot be assigned a trustworthy character
    # offset from text alone; retain its bbox and leave offsets unresolved.
    if len(matches) != 1:
        return None, None, None
    match = matches[0]
    return match.start(), match.end(), page_text[match.start() : match.end()]


def _line_blocks(page: pdfplumber.page.Page, doc_id: str, page_number: int) -> list[TextBlock]:
    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=False,
    )
    grouped: dict[float, list[dict[str, object]]] = defaultdict(list)
    for word in words:
        line_key = round(float(word["top"]) / 3.0) * 3.0
        grouped[line_key].append(word)

    blocks: list[TextBlock] = []
    segments: list[list[dict[str, object]]] = []
    for _, line_words in sorted(grouped.items()):
        line_words.sort(key=lambda item: float(item["x0"]))
        current: list[dict[str, object]] = []
        for word in line_words:
            if current:
                gap = float(word["x0"]) - float(current[-1]["x1"])
                # A wide horizontal gap normally denotes a column boundary.
                # Split it instead of creating a synthetic cross-column sentence.
                if gap > 18.0:
                    segments.append(current)
                    current = []
            current.append(word)
        if current:
            segments.append(current)

    segments.sort(
        key=lambda words: (
            min(float(item["top"]) for item in words),
            min(float(item["x0"]) for item in words),
        )
    )
    for order, line_words in enumerate(segments):
        text = " ".join(str(item["text"]) for item in line_words).strip()
        if not text:
            continue
        bbox = BoundingBox(
            x0=round(min(float(item["x0"]) for item in line_words), 3),
            top=round(min(float(item["top"]) for item in line_words), 3),
            x1=round(max(float(item["x1"]) for item in line_words), 3),
            bottom=round(max(float(item["bottom"]) for item in line_words), 3),
        )
        blocks.append(
            TextBlock(
                block_id=f"{doc_id}:p{page_number:04d}:b{order:04d}",
                text=text,
                bbox=bbox,
                reading_order=order,
            )
        )
    return blocks


def _printed_page_label(page: pdfplumber.page.Page) -> PrintedPageLabel:
    words = page.extract_words() or []
    height = float(page.height)
    candidates: list[dict[str, object]] = []
    for word in words:
        token = str(word["text"]).strip()
        if not re.fullmatch(r"(?:[ivxlcdmIVXLCDM]{1,8}|\d{1,4})", token):
            continue
        top = float(word["top"])
        bottom = float(word["bottom"])
        if top <= height * 0.12 or bottom >= height * 0.88:
            candidates.append(word)
    if not candidates:
        return PrintedPageLabel(None, 0.0, "no_header_footer_numeric_candidate")

    candidates.sort(
        key=lambda item: (
            min(float(item["top"]), height - float(item["bottom"])),
            abs((float(item["x0"]) + float(item["x1"])) / 2 - float(page.width) / 2),
        )
    )
    chosen = candidates[0]
    is_footer = float(chosen["bottom"]) >= height * 0.88
    confidence = 0.8 if is_footer else 0.65
    return PrintedPageLabel(
        value=str(chosen["text"]),
        confidence=confidence,
        method="header_footer_numeric_heuristic",
        bbox=BoundingBox(
            round(float(chosen["x0"]), 3),
            round(float(chosen["top"]), 3),
            round(float(chosen["x1"]), 3),
            round(float(chosen["bottom"]), 3),
        ),
    )


def _tables(
    page: pdfplumber.page.Page,
    page_text: str,
    doc_id: str,
    page_number: int,
) -> tuple[list[ParsedTable], list[str]]:
    parsed: list[ParsedTable] = []
    warnings: list[str] = []
    for table_index, table in enumerate(page.find_tables()):
        table_id = f"{doc_id}:p{page_number:04d}:t{table_index:02d}"
        clipped_table_bbox, table_bbox_changed = _clip_bbox_to_page(
            page,
            table.bbox,
        )
        if clipped_table_bbox is None:
            warnings.append(f"{table_id}:table_bbox_outside_page_skipped")
            continue
        if table_bbox_changed:
            warnings.append(f"{table_id}:table_bbox_clipped_to_page")
        matrix = table.extract() or []
        if not matrix:
            continue
        width = max(len(row) for row in matrix)
        headers = [
            re.sub(r"\s+", " ", str(value or "")).strip()
            for value in (matrix[0] + [None] * width)[:width]
        ]
        roles = [infer_column_role(value) for value in headers]
        row_group_ids = [
            f"{table_id}:r{row_index:03d}"
            for row_index in range(len(table.rows))
        ]
        row_centers: list[float | None] = []
        for row in table.rows:
            anchor_boxes = [
                cell_bbox
                for column_index, cell_bbox in enumerate(row.cells)
                if cell_bbox is not None
                and (
                    column_index >= len(roles)
                    or roles[column_index] != "fault_or_symptom"
                )
            ]
            boxes = anchor_boxes or [
                cell_bbox for cell_bbox in row.cells if cell_bbox is not None
            ]
            row_centers.append(
                (
                    sum((float(box[1]) + float(box[3])) / 2 for box in boxes)
                    / len(boxes)
                )
                if boxes
                else None
            )
        for source_index, row in enumerate(table.rows):
            for column_index, cell_bbox in enumerate(row.cells):
                if (
                    cell_bbox is None
                    or column_index >= len(roles)
                    or roles[column_index] != "fault_or_symptom"
                ):
                    continue
                top, bottom = float(cell_bbox[1]), float(cell_bbox[3])
                covered_rows = [
                    row_index
                    for row_index, center in enumerate(row_centers)
                    if center is not None and top - 0.5 <= center <= bottom + 0.5
                ]
                if len(covered_rows) <= 1:
                    continue
                group_id = f"{table_id}:g{source_index:03d}"
                for covered_index in covered_rows:
                    row_group_ids[covered_index] = group_id
        rows: list[TableRow] = []
        for row_index, row in enumerate(table.rows):
            row_id = f"{table_id}:r{row_index:03d}"
            row_group_id = row_group_ids[row_index]
            cells: list[TableCell] = []
            for column_index, cell_bbox in enumerate(row.cells):
                if cell_bbox is None:
                    continue
                clipped_cell_bbox, cell_bbox_changed = _clip_bbox_to_page(
                    page,
                    cell_bbox,
                )
                if clipped_cell_bbox is None:
                    warnings.append(
                        f"{row_id}:c{column_index:02d}:"
                        "cell_bbox_outside_page_skipped"
                    )
                    continue
                if cell_bbox_changed:
                    warnings.append(
                        f"{row_id}:c{column_index:02d}:"
                        "cell_bbox_clipped_to_page"
                    )
                text = _extract_text_from_bbox(page, clipped_cell_bbox)
                text_start, text_end, source_text = _locate_cell_in_page_text(
                    page_text,
                    text,
                )
                column_name = headers[column_index] if column_index < len(headers) else ""
                role = roles[column_index] if column_index < len(roles) else "unclassified"
                cells.append(
                    TableCell(
                        cell_id=f"{row_id}:c{column_index:02d}",
                        table_id=table_id,
                        row_id=row_id,
                        row_group_id=row_group_id,
                        row_index=row_index,
                        column_index=column_index,
                        column_name=column_name,
                        column_role=role,
                        text=text,
                        page_text_start=text_start,
                        page_text_end=text_end,
                        page_text_source=source_text,
                        bbox=BoundingBox.from_tuple(clipped_cell_bbox),
                    )
                )
            rows.append(
                TableRow(
                    row_id=row_id,
                    row_group_id=row_group_id,
                    row_index=row_index,
                    cells=cells,
                )
            )
        parsed.append(
            ParsedTable(
                table_id=table_id,
                bbox=BoundingBox.from_tuple(clipped_table_bbox),
                column_names=headers,
                column_roles=roles,
                rows=rows,
            )
        )
    return parsed, list(dict.fromkeys(warnings))


class PdfDocumentParser:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def parse(
        self,
        document: DocumentDescriptor,
        page_numbers: Iterable[int] | None = None,
        *,
        printed_page_overrides: dict[int, str] | None = None,
        visual_layout_checked_pages: set[int] | None = None,
    ) -> list[ParsedPage]:
        return list(
            self.iter_parse(
                document,
                page_numbers,
                printed_page_overrides=printed_page_overrides,
                visual_layout_checked_pages=visual_layout_checked_pages,
            )
        )

    def iter_parse(
        self,
        document: DocumentDescriptor,
        page_numbers: Iterable[int] | None = None,
        *,
        printed_page_overrides: dict[int, str] | None = None,
        visual_layout_checked_pages: set[int] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Iterator[ParsedPage]:
        """Yield selected pages from one PDF open operation."""

        pdf_path = (
            self.project_root
            / "data/source_docs/marine_pump/raw"
            / document.file_name
        )
        selected = set(page_numbers or [])
        overrides = printed_page_overrides or {}
        visually_checked = visual_layout_checked_pages or set()
        with pdfplumber.open(pdf_path) as pdf:
            if selected and (min(selected) < 1 or max(selected) > len(pdf.pages)):
                raise ValueError(
                    f"Requested pages outside 1..{len(pdf.pages)} for {document.doc_id}"
                )
            for page_number, page in enumerate(pdf.pages, start=1):
                if selected and page_number not in selected:
                    continue
                text = page.extract_text(
                    x_tolerance=2,
                    y_tolerance=3,
                    layout=True,
                ) or ""
                printed = _printed_page_label(page)
                if page_number in overrides:
                    printed = PrintedPageLabel(
                        value=str(overrides[page_number]),
                        confidence=1.0,
                        method="versioned_manual_override",
                    )
                warnings: list[str] = []
                if not text.strip():
                    warnings.append("no_machine_readable_text")
                if printed.confidence < 0.8:
                    warnings.append("printed_page_label_requires_review")
                try:
                    parsed_tables, table_warnings = _tables(
                        page,
                        text,
                        document.doc_id,
                        page_number,
                    )
                    warnings.extend(table_warnings)
                except Exception as error:
                    parsed_tables = []
                    warnings.append(
                        "table_extraction_failed:"
                        f"{type(error).__name__}:{str(error)[:160]}"
                    )
                (
                    source_language,
                    source_language_confidence,
                    language_detection_method,
                ) = detect_source_language(text)
                if parsed_tables and page_number not in visually_checked:
                    warnings.append("table_visual_layout_requires_review")
                if source_language == "und":
                    warnings.append("source_language_undetermined")
                relative_file = pdf_path.relative_to(self.project_root).as_posix()
                parsed_page = ParsedPage(
                    schema_version=PAGE_SCHEMA_VERSION,
                    parser_version=PARSER_VERSION,
                    doc_id=document.doc_id,
                    document_split=document.document_split,
                    source_family_id=document.source_family_id,
                    publisher=document.publisher,
                    title=document.title,
                    source_url=document.source_url,
                    source_tier=document.source_tier,
                    pump_type=document.pump_type,
                    service=document.service,
                    applicability_scope=document.applicability_scope,
                    local_file=relative_file,
                    document_sha256=document.sha256,
                    pdf_page_number=page_number,
                    page_width=round(float(page.width), 3),
                    page_height=round(float(page.height), 3),
                    page_text=text,
                    page_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    source_language=source_language,
                    source_language_confidence=source_language_confidence,
                    language_detection_method=language_detection_method,
                    printed_page=printed,
                    visual_layout_checked=page_number in visually_checked,
                    text_blocks=_line_blocks(page, document.doc_id, page_number),
                    tables=parsed_tables,
                    warnings=warnings,
                )
                if progress_callback:
                    progress_callback(page_number, len(pdf.pages))
                yield parsed_page
