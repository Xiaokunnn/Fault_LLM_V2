"""Frozen E1 encoder and dimension-matched H512 control; no label inputs.

This module does not replace the deployed hashing provider. E1 is an isolated
build-set feasibility experiment, not a calibrated online controller.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .artifacts import file_sha256
from .contracts import CARD_SLOT_ROLES
from .features import hash_text

MODEL_ID = "BAAI/bge-small-zh-v1.5"
REVISION = "7999e1d3359715c523056ef9478215996d62a620"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
MODEL_FILES = ("README.md", "config.json", "model.safetensors", "tokenizer.json",
               "tokenizer_config.json", "special_tokens_map.json", "vocab.txt",
               "sentence_bert_config.json")


def query_text(query):
    return " ".join((query.question_zh, query.fault_name_zh, query.requested_role.value))


def evidence_text(record):
    return " ".join((record.head_label_zh, record.relation, record.tail_label_zh, record.evidence_text))


def evidence_metadata(record):
    values = [0.0] * 32
    if record.role in CARD_SLOT_ROLES:
        values[CARD_SLOT_ROLES.index(record.role)] = 1.0
    values[4:20] = hash_text(" ".join(record.fault_class_ids), 16)
    values[20] = float(record.evidence_contract_confidence or 0.0)
    return tuple(values)


def model_bindings(directory):
    return {name: file_sha256(Path(directory)/name) for name in MODEL_FILES}


class FrozenSemanticEncoder:
    """Local pinned safetensors, CPU FP32 CLS/L2, no fitting or query cache."""

    def __init__(self, directory, expected_hashes):
        import torch
        from transformers import AutoModel, AutoTokenizer
        if model_bindings(directory) != expected_hashes:
            raise ValueError("semantic encoder files differ from frozen snapshot")
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(directory, local_files_only=True, trust_remote_code=False,
                                               use_safetensors=True, attn_implementation="eager")
        self.model.to(device="cpu", dtype=torch.float32).eval().requires_grad_(False)
        if self.model.config.hidden_size != 512:
            raise ValueError("E1 requires the prespecified 512-dimensional encoder")
        self.parameter_count = sum(p.numel() for p in self.model.parameters())
        self.weight_bytes = sum(p.numel()*p.element_size() for p in self.model.parameters())

    def encode(self, texts, *, query=False, batch_size=16):
        import torch
        values = [QUERY_INSTRUCTION+t if query else t for t in texts]
        result = []
        with torch.inference_mode():
            for offset in range(0, len(values), batch_size):
                batch = self.tokenizer(values[offset:offset+batch_size], padding=True, truncation=True,
                                       max_length=512, return_tensors="pt")
                hidden = self.model(**batch).last_hidden_state[:, 0]
                result.extend(torch.nn.functional.normalize(hidden, p=2, dim=-1).tolist())
        return result

    def text_audit(self, texts, *, query=False):
        result = []
        for text in texts:
            value = QUERY_INSTRUCTION+text if query else text
            tokens = self.tokenizer(value, truncation=False, verbose=False)["input_ids"]
            result.append({"source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                           "input_text_sha256": hashlib.sha256(value.encode()).hexdigest(),
                           "tokens_before_truncation": len(tokens), "truncated": len(tokens) > 512})
        return result


def optimistic_break_even(*, queries, delta_correct, delta_local_ms):
    """Difference of two oracle costs, NOT an actual-policy cost guarantee."""
    if queries <= 0:
        raise ValueError("queries must be positive")
    if delta_correct <= 0:
        return {"teacher_cost_threshold_ms": None,
                "strict_call_saving_possible": False,
                "dominated_in_homogeneous_oracle_model": delta_local_ms > 0}
    return {"teacher_cost_threshold_ms": queries*delta_local_ms/delta_correct,
            "strict_call_saving_possible": True,
            "dominated_in_homogeneous_oracle_model": False}
