from __future__ import annotations

from pathlib import Path

from scripts.freeze_rp2_v6_paper_evidence import _sha256


def test_sha256_is_content_stable(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b'{"silver": true}\n')
    first = _sha256(artifact)
    second = _sha256(artifact)
    assert first == second
    assert len(first) == 64
