"""Deterministic dense evidence index persisted as NumPy arrays and JSON metadata."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from .dataset import EvidenceCandidate


class Encoder(Protocol):
    def encode(self, texts: Iterable[str]): ...


def evidence_index_text(item: EvidenceCandidate) -> str:
    return (
        f"头实体：{item.head_label_zh}\n关系：{item.relation}\n"
        f"尾实体：{item.tail_label_zh}\n证据：{item.evidence_text}"
    )


@dataclass(frozen=True)
class DenseHit:
    evidence_id: str
    score: float


class DenseEvidenceIndex:
    def __init__(self, evidence_ids, matrix) -> None:
        import numpy as np

        self.evidence_ids = tuple(str(value) for value in evidence_ids)
        array = np.asarray(matrix, dtype="float32")
        if array.ndim != 2 or array.shape[0] != len(self.evidence_ids):
            raise ValueError("Dense index dimensions do not match evidence IDs")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        self.matrix = array / np.maximum(norms, 1e-12)

    @classmethod
    def build(cls, candidates: Iterable[EvidenceCandidate], encoder: Encoder) -> "DenseEvidenceIndex":
        rows = sorted(candidates, key=lambda item: item.evidence_id)
        texts = [evidence_index_text(item) for item in rows]
        return cls([item.evidence_id for item in rows], encoder.encode(texts))

    def search(self, query_text: str, encoder: Encoder, *, top_n: int = 64) -> list[DenseHit]:
        import numpy as np

        query = np.asarray(encoder.encode([query_text])[0], dtype="float32")
        query = query / max(float(np.linalg.norm(query)), 1e-12)
        scores = self.matrix @ query
        order = np.argsort(-scores, kind="stable")[: max(0, top_n)]
        return [DenseHit(self.evidence_ids[int(index)], float(scores[int(index)])) for index in order]

    def save(self, output_dir: str | Path, *, metadata: dict | None = None) -> None:
        import numpy as np

        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        np.save(output / "embeddings.npy", self.matrix)
        (output / "evidence_ids.json").write_text(
            json.dumps(self.evidence_ids, ensure_ascii=False), encoding="utf-8"
        )
        digest = hashlib.sha256((output / "embeddings.npy").read_bytes()).hexdigest()
        manifest = {
            "record_count": len(self.evidence_ids),
            "dimension": int(self.matrix.shape[1]),
            "embeddings_sha256": digest,
            **(metadata or {}),
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, output_dir: str | Path) -> "DenseEvidenceIndex":
        import numpy as np

        root = Path(output_dir)
        return cls(
            json.loads((root / "evidence_ids.json").read_text(encoding="utf-8")),
            np.load(root / "embeddings.npy"),
        )
