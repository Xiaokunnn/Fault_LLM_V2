#!/usr/bin/env python3
"""Verify existing thesis inputs, delivery hashes and document completeness."""
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    sources = load(OUT / 'source_manifest.json')['inputs']
    supplementary = load(OUT / 'references/supplementary_source_manifest.json')['sources']
    for name, meta in {**sources, **supplementary}.items():
        assert sha(ROOT / name) == meta['sha256'], name
    policy = load(OUT / 'future_default_graph.json')
    for name, digest in policy['files_sha256'].items():
        assert sha(ROOT / policy['graph_path'] / name) == digest, name
    assert policy['runtime_default_changed'] is False
    assert policy['RP2_RP3_migration_executed'] is False
    links = 0
    for file in OUT.rglob('*.md'):
        text = file.read_text()
        assert text.count('```') % 2 == 0, file
        for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            link = match.group(1)
            if link.startswith(('http:', 'https:', '#', 'mailto:')):
                continue
            target = link.split('#')[0]
            if target:
                links += 1
                assert (file.parent / target).exists(), (file, target)
    chapter = (OUT / '06_CHAPTER3_DRAFT.md').read_text()
    assert len(re.findall(r'^## 3\.[1-8] ', chapter, re.M)) == 8
    assert len(re.findall(r'^算法3-[1-3] ', chapter, re.M)) == 3
    assert len(re.findall(r'\\tag\{3-[1-8]\}', chapter)) == 8
    assert chapter.count('```mermaid') == 3
    for suffix, count in [('png', 2), ('svg', 2), ('mmd', 3)]:
        assert len(list((OUT / 'figures').glob('*.' + suffix))) == count
    checks = load(OUT / 'package_checks.json')
    assert checks['source_manifest_inputs_verified'] == len(sources)
    assert checks['supplementary_inputs_verified'] == len(supplementary)
    assert checks['local_markdown_links_checked'] == links
    delivery = load(OUT / 'delivery_manifest.json')
    for name, meta in delivery['files'].items():
        assert sha(OUT / name) == meta['sha256'], name
    print(json.dumps({'status': 'PASS', 'major_inputs': len(sources),
                      'supplementary_inputs': len(supplementary),
                      'delivery_files': len(delivery['files']),
                      'local_links': links, 'new_model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
