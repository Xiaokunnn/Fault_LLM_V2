#!/usr/bin/env python3
"""Verify a staged RP3 upload, back up existing target files, then apply.

Run from the extracted staging directory, not inside the target repository.
No files are deleted. --apply is explicit; default only reports differences.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path

def digest(path):
    value=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1048576),b""):
            value.update(chunk)
    return value.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target",required=True)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    stage=Path(__file__).resolve().parents[1]
    target=Path(args.target).expanduser().resolve()
    if not (target/"src").is_dir() or not (target/"configs").is_dir() or target==stage:
        raise ValueError("target must be an existing distinct project checkout")
    manifest=json.loads((stage/"RP3_UPLOAD_MANIFEST.json").read_text(encoding="utf-8"))
    planned=[]
    for row in manifest["files"]:
        rel=Path(row["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("unsafe manifest path")
        source=(stage/rel).resolve()
        dest=(target/rel).resolve()
        source.relative_to(stage)
        dest.relative_to(target)
        if digest(source)!=row["sha256"]:
            raise ValueError("staged file checksum mismatch: "+str(rel))
        if dest.exists() and not dest.is_file():
            raise ValueError("destination is not a file: "+str(rel))
        existing=digest(dest) if dest.exists() else None
        if existing!=row["sha256"]:
            planned.append((rel,source,dest,existing))
    print(json.dumps({"target":str(target),"changed_files":[str(x[0]) for x in planned],
        "apply":args.apply},ensure_ascii=False,indent=2))
    if not args.apply:
        return
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup=target/".rp3_upload_backups"/stamp
    backup.mkdir(parents=True,exist_ok=False)
    journal=[]
    for rel,source,dest,existing in planned:
        if existing is not None:
            archived=backup/rel
            archived.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,archived)
        journal.append({"path":str(rel),"previous_sha256":existing,"new_sha256":digest(source)})
    (backup/"journal.json").write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
    for rel,source,dest,existing in planned:
        # Detect a concurrent server edit since planning/backing up.
        current=digest(dest) if dest.exists() else None
        if current!=existing:
            raise RuntimeError("server file changed concurrently; stopping before overwrite: "+str(rel))
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
        if digest(dest)!=digest(source):
            raise RuntimeError("uploaded file checksum failed: "+str(rel))
    print(json.dumps({"status":"installed_and_hash_verified","backup":str(backup),"changed":len(planned)}))

if __name__=="__main__":
    main()
