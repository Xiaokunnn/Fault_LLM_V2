#!/usr/bin/env python3
"""Create a scoped, byte-preserving upload archive; never uploads credentials."""
import argparse
import io
import json
import tarfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.research_point_3.artifacts import file_sha256,canonical_json_bytes

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default=".tmp/rp3_upload_20260906.tar.gz")
    args=p.parse_args()
    files=set()
    for directory in ("src/research_point_3","src/research_point_2","configs/research_point_3"):
        files.update(x for x in (ROOT/directory).rglob("*") if x.is_file() and x.suffix in {".py",".json",".md"})
    for pattern in ("scripts/*rp3*.py","scripts/*rp3*.sh","tests/unit/test_research_point_3*.py","docs/RP3*.md","requirements*.txt"):
        files.update(ROOT.glob(pattern))
    files.update(ROOT/x for x in ("src/__init__.py","tests/__init__.py","tests/unit/__init__.py","scripts/run_rp2_equal_budget_v6.py","scripts/run_rp2_graphrag_v2.py",
        "configs/frozen/rp2_v6_paper_evidence_freeze.json",
        "results/experiments/research_point_2/graphrag_v6_equal_budget/retrieval_replay.jsonl",
        "data/interim/parsed_pages/corpus_v2/MP008.pages.v2.jsonl"))
    freeze=json.loads((ROOT/"configs/frozen/rp2_v6_paper_evidence_freeze.json").read_text(encoding="utf-8"))
    files.update(ROOT/x["path"] for x in freeze["artifacts"])
    for directory in ("data/kg/marine_pump/triples/KG_v1_validated","data/kg/marine_pump/silver_evidencebench/rp2_full_graph_development_v2"):
        files.update(x for x in (ROOT/directory).glob("*") if x.suffix in {".json",".jsonl"})
    files={x for x in files if x.is_file() and "__pycache__" not in x.parts}
    for file in files:
        file.resolve().relative_to(ROOT.resolve())
    output=ROOT/args.output
    output.resolve().relative_to(ROOT.resolve())
    if output.exists():
        raise RuntimeError("upload archive already exists; choose another output filename")
    manifest={"schema":"rp3_scoped_upload_manifest_v1","files":[{"path":x.relative_to(ROOT).as_posix(),
        "sha256":file_sha256(x),"bytes":x.stat().st_size} for x in sorted(files)],
        "excludes":["model_weights","credentials","original_PDFs","paper_drafts","unrelated_dirty_changes"],
        "upload_status":"not_uploaded","preserve_bytes_including_CRLF":True}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(output,"w:gz") as archive:
        for file in sorted(files):
            archive.add(file,arcname=file.relative_to(ROOT).as_posix(),recursive=False)
        payload=canonical_json_bytes(manifest)
        info=tarfile.TarInfo("RP3_UPLOAD_MANIFEST.json")
        info.size=len(payload)
        archive.addfile(info,io.BytesIO(payload))
    print(json.dumps({"archive":str(output),"file_count":len(files),"bytes":output.stat().st_size,
        "sha256":file_sha256(output),"status":"packaged_not_uploaded"},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
