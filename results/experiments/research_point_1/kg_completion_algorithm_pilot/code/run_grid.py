"""Execute prespecified baseline rows; training runners never read test files."""
import argparse
import subprocess
import sys
import time
from common import RUN,SEEDS,save,read


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--family',choices=['complex_core','complex_stress','anyburl','simkgc'],required=True);args=parser.parse_args()
    rows=[]
    if args.family=='complex_core':
        rows=[dict(view=v,seed=s) for s in SEEDS for v in ['G1','G2','G3','G3_flat','G3_uniform','G3_labels','G4']]
    elif args.family=='complex_stress':
        rows=[dict(view='G3',seed=s,fraction=f,noise=0.) for s in SEEDS for f in [.25,.5]]+[
            dict(view='G3',seed=s,fraction=1.,noise=n) for s in SEEDS for n in [.25,.5]]
    elif args.family=='anyburl':rows=[dict(view=v,seed=s) for s in SEEDS for v in ['G1','G2','G3','G3_flat','G4']]
    else:rows=[dict(view=v,seed=s) for s in SEEDS for v in ['G1','G2','G3','G4']]
    save(RUN/'configs'/(args.family+'.json'),dict(rows=rows,model_selection='validation link MRR only; no test read; earliest equal best retained',
         seeds=SEEDS,test_release='after prototype and ablation configs frozen',stress='synthetic type-preserving corruptions, not known false facts'))
    script='train_complex.py' if args.family.startswith('complex') else 'run_anyburl.py' if args.family=='anyburl' else 'train_simkgc.py'
    statuses=[]
    for row in rows:
        suffix='_'.join(f'{k}{v}' for k,v in row.items());log=RUN/'logs'/args.family/(suffix+'.log')
        command=[sys.executable,str(__file__).replace('run_grid.py',script)]
        for k,v in row.items():command+=['--'+k,str(v)]
        if log.exists():
            # Runner itself checks sealed complete.json; keep previous real log.
            log=log.with_name(log.stem+'_resume_'+str(time.time_ns())+'.log')
        log.parent.mkdir(parents=True,exist_ok=True)
        started=time.perf_counter()
        with log.open('x') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        statuses.append(dict(row=row,returncode=result.returncode,seconds=time.perf_counter()-started,log=str(log.relative_to(RUN))))
        print(args.family,row,'returncode',result.returncode,flush=True)
        if result.returncode:save(RUN/'configs'/(args.family+'_failure_'+str(time.time_ns())+'.json'),statuses);raise SystemExit(result.returncode)
    save(RUN/'configs'/(args.family+'_execution.json'),statuses)


if __name__=='__main__':main()
