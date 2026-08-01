#!/usr/bin/env python3
"""Cross-platform orchestrator for the frozen-page RP1 real-API comparison."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METHODS = (
    ("B0", "marine_pump_api_ablation_b0"),
    ("B1", "marine_pump_api_ablation_b1"),
    ("B2", "marine_pump_api_ablation_b2"),
    ("B3", "marine_pump_api_ablation_b3"),
    ("Ours", "marine_pump_full_corpus_prompt_v4"),
)


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {command[1]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not os.environ.get("DASHSCOPE_API_KEY", "").strip():
        raise RuntimeError("DASHSCOPE_API_KEY is required and must be supplied only through the environment")
    base = json.loads(
        (ROOT / "configs/triple_extraction_qwen3_7_max_full_corpus_v1.json").read_text(encoding="utf-8")
    )
    for index, (method_id, prompt_version) in enumerate(METHODS, start=1):
        output = f"results/experiments/research_point_1/api_prompt_comparison_v1/{method_id}"
        config = dict(base)
        config.update(
            version=f"rp1_api_prompt_comparison_{method_id}_v1",
            status="fixed_page_real_api_comparison",
            prompt_version=prompt_version,
            output_dir=output,
        )
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False)
        try:
            with handle:
                json.dump(config, handle, ensure_ascii=False, indent=2)
            print(f"========== RP1 API {index}/{len(METHODS)}: {method_id} extraction ==========", flush=True)
            command = [
                args.python,
                "-u",
                "scripts/run_targeted_triple_extraction.py",
                "--config",
                handle.name,
                "--candidate-pool",
                "configs/rp1_api_comparison_pages_v1.jsonl",
                "--output-dir",
                output,
            ]
            if args.limit:
                command += ["--limit", str(args.limit)]
            if args.dry_run:
                command.append("--dry-run")
            _run(command)
            if not args.dry_run:
                print(f"========== RP1 API {method_id}: strict validation ==========", flush=True)
                _run(
                    [
                        args.python,
                        "-u",
                        "scripts/run_targeted_strict_validation.py",
                        "--config",
                        handle.name,
                        "--candidate-dir",
                        output,
                        "--output-dir",
                        f"{output}/strict",
                        "--schema",
                        "data/kg/marine_pump/schema/provenance_schema_v3.json",
                    ]
                )
        finally:
            Path(handle.name).unlink(missing_ok=True)
    if not args.dry_run and not args.limit:
        _run([args.python, "-u", "scripts/summarize_rp1_api_prompt_comparison.py"])
    print("[RP1 API] comparison completed; all labels remain Silver.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
