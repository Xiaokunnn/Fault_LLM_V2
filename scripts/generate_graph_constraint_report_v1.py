"""Generate the executable KG_v1 constraint report.

The report validates the project's layered JSONL graph packages with the
current Python governance profile.  It does not claim RDF or SHACL
conformance.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation.graph_constraint_report import (  # noqa: E402
    generate_graph_constraint_report,
    write_graph_constraint_report,
)


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate KG_v1_raw and KG_v1_validated with the project's "
            "executable Python constraint profile."
        )
    )
    parser.add_argument(
        "--graph-root",
        default="data/kg/marine_pump",
        help="Graph package root containing triples/<version>/.",
    )
    parser.add_argument(
        "--schema",
        default="data/kg/marine_pump/schema/provenance_schema_v3.json",
        help="Provenance schema whose relation registry is reused.",
    )
    parser.add_argument(
        "--terminology",
        default="configs/entity_terminology_zh_marine_pump_v4_silver.json",
        help="Frozen Chinese terminology governance file.",
    )
    parser.add_argument(
        "--document-split",
        default="configs/document_split_marine_pump_v4.json",
        help="Frozen document split used for leakage checks.",
    )
    parser.add_argument("--raw-version", default="KG_v1_raw")
    parser.add_argument("--validated-version", default="KG_v1_validated")
    parser.add_argument(
        "--output-dir",
        default=(
            "results/experiments/research_point_1/"
            "constraint_report_v1"
        ),
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Exit with code 2 when a release-blocking error is found.",
    )
    args = parser.parse_args()

    report = generate_graph_constraint_report(
        project_root=PROJECT_ROOT,
        graph_root=_project_path(args.graph_root),
        schema_path=_project_path(args.schema),
        terminology_path=_project_path(args.terminology),
        split_path=_project_path(args.document_split),
        raw_version=args.raw_version,
        validated_version=args.validated_version,
    )
    json_path, markdown_path = write_graph_constraint_report(
        report,
        output_dir=_project_path(args.output_dir),
    )
    summary = report["summary"]
    print("========== KG_v1 constraint report ==========", flush=True)
    print(f"Checks: {summary['checks']}", flush=True)
    print(f"Failed checks: {summary['failed_checks']}", flush=True)
    print(
        "Release-blocking checks: "
        f"{summary['release_blocking_checks']}",
        flush=True,
    )
    print(f"Release blocked: {summary['release_blocked']}", flush=True)
    print(f"Machine report: {json_path}", flush=True)
    print(f"Human report: {markdown_path}", flush=True)
    print(
        "Scope: project-specific Python constraints; not RDF/SHACL "
        "validation and not human expert review.",
        flush=True,
    )
    if args.fail_on_blocked and summary["release_blocked"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
