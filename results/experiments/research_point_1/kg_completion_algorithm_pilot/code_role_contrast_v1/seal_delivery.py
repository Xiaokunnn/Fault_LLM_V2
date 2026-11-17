"""Seal new studies only, preserve old assets, and retain execution logs."""
import platform
import shutil
import subprocess
import torch
from role_io import *


def main():
    assert NEW.name == '20261116_role_contribution_clean_v2'
    for dataset in ['cold', 'structured']:
        assert read(NEW / dataset / 'verification/checks.json')['passed']
        assert read(NEW / dataset / 'evaluation/complete.json')['new_models'] == 12
    checks = []
    for name, value in read(NEW / 'code_freeze_before_test.json')['files'].items():
        assert file_sha(P / name) == value, name
        checks.append(dict(path=name, sha256=value))
    log_index = []
    for src in sorted(Path('/tmp').glob('rp1_role*.log')):
        dst = NEW / 'logs' / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            assert file_sha(src) == file_sha(dst)
        else:
            shutil.copy2(src, dst)
        log_index.append(dict(original=str(src), archived=str(dst.relative_to(NEW)), sha256=file_sha(dst)))
    save(NEW / 'verification/execution_log_index.json', log_index)
    save(NEW / 'verification/pretest_code_check.json', dict(
        all_frozen_code_byte_identical=True, files=checks,
        later_additions='casebook source-target appendix, posthoc diagnostics, report documents and this sealer; no fitting changes'))
    save(NEW / 'verification/runtime.json', dict(
        python=platform.python_version(), torch=torch.__version__, cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        repository_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        domain_input_object=I.REV, no_new_text_encoder_training=True))
    # Include all new role code and both output trees; old manifests were checked
    # above by verify.py, and are deliberately never regenerated here.
    for root in [P / 'runs/20261116_role_contribution_v1', NEW]:
        ledger = []
        for folder in [P / 'code_role_contrast_v1', root]:
            for f in sorted(folder.rglob('*')):
                if not f.is_file() or '__pycache__' in f.parts or f.name == 'role_delivery_manifest.json':
                    continue
                ledger.append(dict(path=str(f.relative_to(P)), bytes=f.stat().st_size, sha256=file_sha(f)))
        save(root / 'verification/role_delivery_manifest.json', dict(files=ledger, new_outputs_only=True))
    print('Sealed exploratory and corrected role studies; all pretest code hashes match.')


if __name__ == '__main__':
    main()
