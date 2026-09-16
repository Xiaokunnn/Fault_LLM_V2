"""Versioned CPU feature baseline shared by offline training and online queries.

No BGE, corpus vocabulary fitting, teacher scores or benchmark labels are used.
This is a signed character-ngram hashing baseline, NOT a pretrained semantic
encoder. Encoder comparisons must account for the encoder's full edge cost.
"""
from __future__ import annotations

import hashlib
import math
import unicodedata
from .artifacts import stable_sha256
from .contracts import CARD_SLOT_ROLES, ContractError

ENCODER_MANIFEST = {
    "id": "rp3_signed_char_ngram_v1", "query_dimension": 256,
    "evidence_dimension": 288, "ngrams": [1, 2, 3],
    "normalization": "NFKC_casefold_remove_whitespace_l2",
    "hash": "sha256_signed_first8bytes_little_endian",
    "max_characters": 4096, "learned_parameters": 0,
    "requires_online_bge": False, "baseline_not_semantic_encoder": True,
}

def hash_text(text: str, dimension: int = 256) -> tuple[float, ...]:
    text = "".join(unicodedata.normalize("NFKC", text).casefold().split())[:4096]
    values = [0.0] * dimension
    for n in (1, 2, 3):
        for start in range(len(text) - n + 1):
            digest = hashlib.sha256(text[start:start+n].encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "little") % dimension
            values[index] += 1.0 if digest[8] & 1 else -1.0
    norm = math.sqrt(sum(x*x for x in values)) or 1.0
    return tuple(x/norm for x in values)

def query_vector(query):
    # No query ID, scenario ID, split, relevance label or teacher output.
    return hash_text(" ".join((query.question_zh, query.fault_name_zh, query.requested_role.value)))

def evidence_vector(record):
    text = " ".join((record.head_label_zh, record.relation, record.tail_label_zh, record.evidence_text))
    metadata = [0.0] * 32
    if record.role in CARD_SLOT_ROLES:
        metadata[CARD_SLOT_ROLES.index(record.role)] = 1.0
    # Available deployed scope metadata, not hidden query relevance labels.
    metadata[4:20] = hash_text(" ".join(record.fault_class_ids), 16)
    metadata[20] = float(record.evidence_contract_confidence or 0.0)
    return hash_text(text) + tuple(metadata)

class HashingFeatureProvider:
    feature_encoder_manifest_sha256 = stable_sha256(ENCODER_MANIFEST)

    def features_for(self, *, query, candidates, query_dimension, evidence_dimension):
        if (query_dimension, evidence_dimension) != (256, 288):
            raise ContractError("hashing provider requires 256/288 dimensions")
        return query_vector(query), tuple(
            evidence_vector(item.record) if item.available and item.record is not None
            else (0.0,) * 288 for item in candidates
        )
