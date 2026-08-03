#!/usr/bin/env python3
"""Fail closed unless the committed RP2 v3 freeze exactly matches current code and external config."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", default="configs/frozen/rp2_v3_frozen_protocol.json")
    parser.add_argument("--external-config", default="configs/rp2_graphrag_v3_external_source_heldout.json")
    parser.add_argument(
        "--amendment",
        default="configs/frozen/rp2_v3_external_infrastructure_amendment_v1.json",
    )
    args = parser.parse_args()
    freeze_path = ROOT / args.freeze
    if not freeze_path.is_file():
        raise FileNotFoundError(f"Missing RP2 v3 freeze manifest: {freeze_path}")
    tracked = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{args.freeze}"], cwd=ROOT,
        capture_output=True, text=True,
    )
    if tracked.returncode != 0:
        raise RuntimeError("Freeze manifest must be committed before external evaluation")
    committed_freeze = subprocess.check_output(
        ["git", "show", f"HEAD:{args.freeze}"], cwd=ROOT
    )
    if hashlib.sha256(committed_freeze).hexdigest() != _sha(freeze_path):
        raise RuntimeError("Working-tree freeze manifest differs from the committed Git version")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("status") != "frozen_before_external_source_heldout_v3":
        raise RuntimeError("Unexpected RP2 freeze status")
    amendment_path = ROOT / args.amendment
    amendment = None
    if amendment_path.is_file():
        amendment_tracked = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{args.amendment}"], cwd=ROOT,
            capture_output=True, text=True,
        )
        if amendment_tracked.returncode != 0:
            raise RuntimeError("External infrastructure amendment exists but is not committed")
        committed_amendment = subprocess.check_output(
            ["git", "show", f"HEAD:{args.amendment}"], cwd=ROOT
        )
        if hashlib.sha256(committed_amendment).hexdigest() != _sha(amendment_path):
            raise RuntimeError("Working-tree amendment differs from committed Git version")
        amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
        if amendment.get("original_freeze_sha256") != _sha(freeze_path):
            raise RuntimeError("External amendment does not reference the committed freeze")
    replacements = (
        amendment.get("allowed_infrastructure_replacements", {})
        if amendment else {}
    )
    for entry in freeze["artifact_sha256"].values():
        path = ROOT / entry["path"]
        current_sha = _sha(path) if path.is_file() else ""
        if current_sha == entry["sha256"]:
            continue
        if replacements.get(entry["path"]) == current_sha:
            continue
        raise RuntimeError(f"Frozen artifact changed after freeze: {entry['path']}")
    external = json.loads((ROOT / args.external_config).read_text(encoding="utf-8"))
    frozen_scenarios = freeze["frozen_scenarios"]
    external_scenarios = {row["id"]: row for row in external["scenarios"]}
    if external_scenarios != frozen_scenarios:
        raise RuntimeError("External scenarios differ from frozen finalists")
    if external["generation_contract"] != freeze["frozen_generation_contract"]:
        raise RuntimeError("External generation contract differs from frozen protocol")
    if external["retrieval"] != freeze["frozen_retrieval_defaults"]:
        raise RuntimeError("External retrieval defaults differ from frozen protocol")
    print(
        "[RP2 external freeze] PASS: committed freeze, scoped amendment, "
        "and frozen parameters verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
