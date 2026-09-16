from scripts.prepare_rp3_mp008 import locate_contiguous_evidence_quote


def test_mp008_quote_alignment_preserves_exact_source_span() -> None:
    source = "a) Inlet pressure too low (cavitation).\n    Make sure the tank is filled."
    quote = "a) Inlet pressure too low (cavitation). Make sure the tank is filled."

    located = locate_contiguous_evidence_quote(source, quote)

    assert located is not None
    start, end, exact_source, method = located
    assert exact_source == source[start:end]
    assert "\n    " in exact_source
    assert method == "whitespace_normalized"


def test_mp008_quote_alignment_rejects_ellipsis_reconstruction() -> None:
    source = "Pump delivers little water. unrelated table cell. Air in suction pipe."
    quote = "Pump delivers little water. ... Air in suction pipe."

    assert locate_contiguous_evidence_quote(source, quote) is None
