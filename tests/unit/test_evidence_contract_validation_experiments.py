from __future__ import annotations

import hashlib

from scripts.run_evidence_contract_validation_experiments import (
    audit_record,
    mutate_record,
)


def sample_page() -> dict[str, object]:
    text = "Low suction pressure may indicate cavitation."
    return {
        "doc_id": "MPTEST",
        "pdf_page_number": 37,
        "publisher": "Test Publisher",
        "source_family_id": "TEST_FAMILY",
        "source_url": "https://example.org/manual.pdf",
        "document_sha256": "a" * 64,
        "page_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "document_split": "build_train",
        "source_language": "en",
        "page_text": text,
        "page_width": 600.0,
        "page_height": 800.0,
        "tables": [],
    }


def sample_record() -> dict[str, object]:
    page = sample_page()
    return {
        "triple_id": "MPT-TEST",
        "claim_id": "MPC-TEST",
        "decision": "silver_candidate",
        "head": "Low suction pressure",
        "head_surface": "Low suction pressure",
        "head_type": "OperatingCondition",
        "relation": "causes",
        "tail": "cavitation",
        "tail_surface": "cavitation",
        "tail_type": "FaultMode",
        "evidence_text": page["page_text"],
        "evidence_level": "E1",
        **{
            field: page[field]
            for field in (
                "doc_id",
                "pdf_page_number",
                "publisher",
                "source_family_id",
                "source_url",
                "document_sha256",
                "page_text_sha256",
                "document_split",
                "source_language",
            )
        },
    }


def test_clean_e1_record_passes_locator_contract() -> None:
    page = sample_page()
    record = sample_record()
    result = audit_record(record, {("MPTEST", 37): page})
    assert result["locator_contract_pass"] is True
    assert result["failed_checks"] == []


def test_removed_evidence_and_corrupted_hash_are_detected() -> None:
    page = sample_page()
    pages = {("MPTEST", 37): page}
    for mutation in (
        "evidence_payload_removed",
        "page_hash_corrupted",
        "relation_tail_type_corrupted",
    ):
        result = audit_record(mutate_record(sample_record(), mutation), pages)
        assert result["locator_contract_pass"] is False


def test_shifted_page_locator_is_detected() -> None:
    page = sample_page()
    result = audit_record(
        mutate_record(sample_record(), "page_locator_shifted"),
        {("MPTEST", 37): page},
    )
    assert result["locator_contract_pass"] is False
    assert "page_resolved" in result["failed_checks"]
