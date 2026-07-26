"""Structured, provenance-preserving PDF ingestion for research point 1."""

from .manifest_loader import DocumentDescriptor, load_document_manifest
from .models import ParsedPage
from .pdf_parser import PdfDocumentParser, detect_source_language, infer_column_role

__all__ = [
    "DocumentDescriptor",
    "ParsedPage",
    "PdfDocumentParser",
    "detect_source_language",
    "infer_column_role",
    "load_document_manifest",
]
