#!/usr/bin/env python3
"""Read-only RP3 server preflight. No weights are loaded or downloaded."""
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def collect_report(root=ROOT):
    from src.research_point_3.artifacts import normalized_text_sha256, file_sha256
    from src.research_point_3.teacher_freeze import RP2_PAPER_FREEZE_NORMALIZED_SHA256, CANONICAL_RP2_PAPER_FREEZE_PATH
    root=Path(root).resolve()
    config=json.loads((root/"configs/research_point_3/teacher_graph_rp3_v1.json").read_text(encoding="utf-8"))
    failures=[]
    versions={}
    for package in ("torch","transformers","sentence-transformers","numpy","onnx","onnxruntime","pytest"):
        try:
            versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            failures.append("missing Python package: "+package)
    for path in config["required_model_paths"]:
        model_root=root/path
        if not (model_root/"config.json").is_file() or not any(model_root.glob("*.safetensors")) and not any(model_root.glob("*.bin")):
            failures.append("missing model config/weights: "+path)
    frozen=root/CANONICAL_RP2_PAPER_FREEZE_PATH
    if normalized_text_sha256(frozen)!=RP2_PAPER_FREEZE_NORMALIZED_SHA256:
        failures.append("RP2 paper freeze identity mismatch")
    else:
        for row in json.loads(frozen.read_text(encoding="utf-8"))["artifacts"]:
            path=root/row["path"]
            if not path.is_file() or row["sha256"] not in {normalized_text_sha256(path),file_sha256(path)}:
                failures.append("missing/mismatched RP2 frozen input: "+row["path"])
    pages=root/"data/interim/parsed_pages/corpus_v2/MP008.pages.v2.jsonl"
    if not pages.is_file():
        failures.append("missing MP008 calibration source pages")
    report={"python":sys.version,"platform":platform.platform(),"versions":versions,
        "strict208_index_present":(root/config["vector_index_dir"]/"embeddings.npy").is_file(),
        "blockers":failures,"status":"blocked" if failures else "dependencies_ready_models_not_loaded",
        "next":"teacher-smoke builds missing BGE index and verifies fresh RP2 replay"}
    return report

def main():
    report=collect_report()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 2 if report["blockers"] else 0

if __name__=="__main__":
    raise SystemExit(main())
