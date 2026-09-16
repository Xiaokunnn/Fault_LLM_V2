#!/usr/bin/env python3
"""Validate and freeze TeacherGraph_RP3_v1 without invoking any model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.research_point_3.teacher_freeze import (
    audit_teacher_freeze,
    freeze_teacher_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/research_point_3/teacher_graph_rp3_v1.json",
    )
    parser.add_argument(
        "--output",
        default="configs/frozen/teacher_graph_rp3_v1.freeze.json",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Report blockers and never write the frozen manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    audit = audit_teacher_freeze(
        ROOT,
        config,
        progress=lambda message: print(f"[RP3 inventory] {message}", flush=True),
    )
    print(json.dumps(audit.manifest, ensure_ascii=False, indent=2))
    if not audit.ready:
        print("TeacherGraph_RP3_v1 remains BLOCKED:")
        for blocker in audit.blockers:
            print(f"- {blocker}")
        return 2
    if args.validate_only:
        print("All freeze prerequisites are present; no file was written.")
        return 0
    freeze_teacher_manifest(ROOT / args.output, audit)
    print(f"Frozen manifest: {ROOT / args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
