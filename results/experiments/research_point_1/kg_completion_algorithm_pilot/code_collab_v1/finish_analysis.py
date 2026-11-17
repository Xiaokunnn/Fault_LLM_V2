"""Complete postprocessing and conservation while retaining pending source review."""
import subprocess
import sys
import time
from collab_io import *


def main():
    deadline=time.monotonic()+7200
    while not (STUDY/'postprocess_complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Keep completed models; pending postprocess')
        time.sleep(3)
    for script in ['diagnose.py','casebook.py','write_report.py','verify_collab.py']:
        subprocess.run([sys.executable,str(PILOT/'code_collab_v1'/script)],check=True)
    save(STUDY/'analysis_complete.json',dict(computational_checks=True,source_review_still_requires_actual_reading=True))


if __name__=='__main__':main()
