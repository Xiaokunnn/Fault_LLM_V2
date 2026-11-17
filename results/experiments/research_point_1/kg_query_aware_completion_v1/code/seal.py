"""Final additive seal; do not regenerate any previous-study manifest."""
from io_utils import *


def main():
    assert read(EXP/'verification/final_complete.json')['passed']
    assert read(EXP/'native_role_correction/verification.json')['passed']
    assert read(EXP/'verification/checks.json')['passed']
    assert '7 passed' in (EXP/'tests.log').read_text()
    assert '2 passed' in (EXP/'native_role_tests.log').read_text()
    assert len(list((EXP/'models').glob('*/best.pt')))==60
    assert len(list((EXP/'evaluation').glob('*/metrics.json')))==93
    rows=[]
    for p in sorted(EXP.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name=='delivery_manifest.json':continue
        rows.append(dict(path=str(p.relative_to(EXP)),bytes=p.stat().st_size,sha256=file_sha(p)))
    save(EXP/'verification/delivery_manifest.json',dict(files=rows,formal_graph_changes=0,previous_assets_modified=False,expert_Gold=False))
    print('SEALED',len(rows),'files',sum(x['bytes'] for x in rows),'bytes; all stages complete.')


if __name__=='__main__':main()
