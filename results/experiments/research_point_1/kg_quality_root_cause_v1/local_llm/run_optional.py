"""Reuse the server-blocked optional reviewer; force caches into this study."""
from pathlib import Path
import runpy,sys

HERE=Path(__file__).resolve().parent
if '--cache-dir' in sys.argv:raise SystemExit('Cache override is disabled; preserve existing experiments')
sys.argv += ['--cache-dir',str(HERE/'cache')]
runner=HERE.parent.parent/'kg_enhancement_document_gap_v1/local_llm/run_optional.py'
runpy.run_path(str(runner),run_name='__main__')
