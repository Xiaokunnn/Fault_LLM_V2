"""The uploader must preserve existing remote edits and reject bad inputs."""
import hashlib
import json
import sys

import pytest
from scripts import install_rp3_upload as installer


def _stage(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    target = tmp_path / "server_project"
    for path in (stage / "scripts", stage / "src", target / "src", target / "configs"):
        path.mkdir(parents=True, exist_ok=True)
    source = stage / "src/lec.py"
    source.write_bytes(b"new RP3 bytes\r\n")
    destination = target / "src/lec.py"
    destination.write_bytes(b"old user edit\n")
    manifest = {"files": [{"path": "src/lec.py", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
    (stage / "RP3_UPLOAD_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(installer, "__file__", str(stage / "scripts/install_rp3_upload.py"))
    return stage, target, source, destination


def test_upload_dry_run_and_apply_keep_recoverable_original(tmp_path, monkeypatch):
    stage, target, source, destination = _stage(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["install", "--target", str(target)])
    installer.main()
    assert destination.read_bytes() == b"old user edit\n"
    assert not (target / ".rp3_upload_backups").exists()
    monkeypatch.setattr(sys, "argv", ["install", "--target", str(target), "--apply"])
    installer.main()
    assert destination.read_bytes() == source.read_bytes()
    backups = list((target / ".rp3_upload_backups").glob("*/src/lec.py"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"old user edit\n"


def test_upload_rejects_tampered_bytes_before_writing(tmp_path, monkeypatch):
    stage, target, source, destination = _stage(tmp_path, monkeypatch)
    source.write_bytes(b"tampered")
    monkeypatch.setattr(sys, "argv", ["install", "--target", str(target), "--apply"])
    with pytest.raises(ValueError, match="checksum"):
        installer.main()
    assert destination.read_bytes() == b"old user edit\n"
    assert not (target / ".rp3_upload_backups").exists()


def test_upload_rejects_parent_path_before_writing(tmp_path, monkeypatch):
    stage, target, source, destination = _stage(tmp_path, monkeypatch)
    (stage / "RP3_UPLOAD_MANIFEST.json").write_text(json.dumps({"files": [
        {"path": "../outside.py", "sha256": "a" * 64}]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["install", "--target", str(target), "--apply"])
    with pytest.raises(ValueError, match="unsafe"):
        installer.main()
    assert destination.read_bytes() == b"old user edit\n"
