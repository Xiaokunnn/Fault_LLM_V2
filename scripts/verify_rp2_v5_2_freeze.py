#!/usr/bin/env python3
"""Fail closed when any RP2 v5.2 frozen artifact differs from its manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs/frozen/rp2_v5_2_protocol_freeze.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if not MANIFEST.is_file():
        raise FileNotFoundError(f"Missing freeze manifest: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    for record in manifest["artifacts"]:
        path = ROOT / record["path"]
        if not path.is_file():
            failures.append(f"MISSING {record['path']}")
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != record["bytes"]:
            failures.append(
                f"SIZE {record['path']}: expected={record['bytes']} actual={actual_size}"
            )
        if actual_hash != record["sha256"]:
            failures.append(
                f"SHA256 {record['path']}: expected={record['sha256']} actual={actual_hash}"
            )
    if failures:
        print("[RP2 freeze] FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        f"[RP2 freeze] PASS: {manifest['artifact_count']} artifacts match "
        f"source commit {manifest['source_commit']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
