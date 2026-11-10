"""One evidence-address contract for layout and later screening stages.

This verifies quotation addresses only. It cannot certify endpoint roles,
conditions, negation, domain truth, or final graph admission. No model or IO.
"""
import copy

VERSION = "native_evidence_binding_v2"


def exact_witness_roundtrip(page, witness):
    units = {b["block_id"]: b["text"] for b in page.get("text_blocks", [])}
    units.update({c["cell_id"]: c["text"] for table in page.get("tables", [])
                  for row in table["rows"] for c in row["cells"]})
    uid = witness.get("block_id") or witness.get("cell_id")
    text = units.get(uid)
    start, end = witness.get("start"), witness.get("end")
    return (text is not None and type(start) is int and type(end) is int
            and 0 <= start < end <= len(text) and text[start:end] == witness.get("text"))


def screen_with_native_binding(assertion, page, screen):
    """Clear ONLY a quotation flag, after fresh unique native-path validation.

    Never trust an earlier pass bit: a later proposal may change its quotation.
    Existing non-quotation flags and upstream barriers remain authoritative.
    """
    from .layout_direction_context_v1 import locate

    flags = list(screen(assertion, page))
    hits, geometry = locate(page, assertion["evidence_text"], assertion.get("evidence_unit_ids", []))
    witnesses = hits[0]["witnesses"] if len(hits) == 1 else []
    normalize = lambda text: "".join(text.split())
    quote = normalize(assertion["evidence_text"])
    proof_valid = bool(quote and witnesses
                       and all(exact_witness_roundtrip(page, w) for w in witnesses)
                       and normalize("".join(w["text"] for w in witnesses)) == quote)
    removed = []
    if proof_valid and "unbound_quote" in flags:
        flags.remove("unbound_quote")
        removed.append("unbound_quote")
    return dict(version=VERSION, screen_flags=flags, native_path_count=len(hits),
                unique_native_proof_valid=proof_valid, removed_flags=removed,
                source_witnesses=copy.deepcopy(witnesses) if proof_valid else [],
                geometry=geometry, semantic_support_certified=False)
