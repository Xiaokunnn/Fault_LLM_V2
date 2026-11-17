"""Author AnyBURL jar learning/application, adapted view export and score parsing."""
import argparse
from pathlib import Path
import subprocess
import time
import numpy as np
from common import PILOT,RUN,SEEDS,save,read,file_sha
from views import build
from eval_core import Evaluator

JAVA=next((PILOT/'dependencies/jre17').glob('*/bin/java'))
JAR=PILOT/'dependencies/AnyBURL-23-1x.jar'


def name_entity(i):return f'E{i:05d}'
def name_relation(i):return f'R{i:03d}'
def line(t):return f'{name_entity(t[0])}\t{name_relation(t[1])}\t{name_entity(t[2])}\n'


def invoke(folder,stage,config):
    log=folder/(stage+'.stdout.log')
    if stage=='learn' and log.exists() and '>>> Bye, bye.' in log.read_text() and all((folder/f'rules-{s}').exists() for s in [10,30]):
        save(folder/'learn_recovery.json',dict(author_normal_exit=1,reason='Learn.java normal terminal branch calls System.exit(1); both sealed snapshots and Bye log present',wall_seconds=None,no_relearning=True))
        return 0.
    start=time.perf_counter()
    with log.open('x') as f:
        result=subprocess.run([str(JAVA),'-Xmx2G','-cp',str(JAR),'de.unima.ki.anyburl.'+('Learn' if stage=='learn' else 'Apply'),str(config)],cwd=folder,stdout=f,stderr=subprocess.STDOUT,check=False,timeout=180)
    normal_author_exit=stage=='learn' and result.returncode==1 and '>>> Bye, bye.' in log.read_text() and all((folder/f'rules-{s}').exists() for s in [10,30])
    save(folder/(stage+'.exit.json'),dict(returncode=result.returncode,normal_author_terminal_exit=normal_author_exit,seconds=time.perf_counter()-start))
    if result.returncode and not normal_author_exit:raise RuntimeError('Author command failed: '+str(log))
    return time.perf_counter()-start


def parse(path,cat):
    lines=path.read_text().splitlines();scores={}
    for i in range(0,len(lines),3):
        if i+2>=len(lines):break
        h,r,t=lines[i].split();triple=(int(h[1:]),int(r[1:]),int(t[1:]))
        for task,s in [('head',lines[i+1]),('tail',lines[i+2])]:
            values=s.split(':',1)[1].split();a=np.zeros(cat['nbase'])
            for j in range(0,len(values)-1,2):
                ent=values[j]
                if ent.startswith('E') and ent[1:].isdigit():
                    idx=int(ent[1:])
                    if idx<len(a):a[idx]=float(values[j+1])
            scores[triple,task]=a
    return scores


def apply(folder,train,rules,queries,name,cat):
    query_file=folder/(name+'.tsv');save(query_file,''.join(line(t) for t in queries))
    empty=folder/'empty.tsv';save(empty,'')
    out=folder/(name+'.predictions')
    config=folder/(name+'.properties')
    # Above the entire entity/context universe: do not censor positive scores at top200.
    top_k=len(cat['entities'])+15000
    save(config,'\n'.join([f'PATH_TRAINING = {train}',f'PATH_TEST = {query_file}',f'PATH_VALID = {empty}',f'PATH_RULES = {rules}',f'PATH_OUTPUT = {out}',
                           'WORKER_THREADS = 1',f'TOP_K_OUTPUT = {top_k}','AGGREGATION_TYPE = maxplus','SAFE_PREFIX_MODE = false'])+'\n')
    if out.exists() and (folder/(name+'.exit.json')).exists() and read(folder/(name+'.exit.json'))['returncode']==0:
        return parse(out,cat),0.
    seconds=invoke(folder,name,config)
    return parse(out,cat),seconds


def fit(args):
    folder=RUN/'models'/f'anyburl_{args.view}_s{args.seed}_f{args.fraction}_n{args.noise}'
    if (folder/'complete.json').exists():print('REUSE',folder,flush=True);return
    if folder.exists():assert (folder/'rules-30').exists(),'Preserve interrupted author run; use new run suffix'
    folder.mkdir(parents=True,exist_ok=True)
    data=build(args.view,args.fraction,args.noise,args.seed);cat=data['catalogue']
    triples=[line(t) for t in data['base']]
    for row in data['aux_rows']:
        h,r,t=row['triple']
        if args.view in ['G2','G3_flat']:triples.append(line([h,r,t]))
        else:triples.append(f'{name_entity(h)}\tC{r:03d}_{row["bucket"]}\t{name_entity(t)}\n')
    if args.view in ['G4','G4_bridge']:
        # Evidence co-occurrence context, NOT an asserted domain relation or a SimKGC substitute.
        for description in read(RUN/'data/training_entity_text.jsonl'):
            for uid in description['context_ids']:
                triples.append(f'{name_entity(description["entity_index"])}\tTEXT_UNIT\tU{uid:06d}\n')
    train=folder/'train.tsv';save(train,''.join(sorted(set(triples))))
    config=folder/'learn.properties';prefix=folder/'rules'
    save(config,'\n'.join([f'PATH_TRAINING = {train}',f'PATH_OUTPUT = {prefix}','SNAPSHOTS_AT = 10,30','WORKER_THREADS = 1',
                           'THRESHOLD_CORRECT_PREDICTIONS = 2','MAX_LENGTH_CYCLIC = 3','SAFE_PREFIX_MODE = false'])+'\n')
    save(folder/'config.json',dict(vars(args),implementation='Author AnyBURL-23-1x jar Learn/Apply; status-predicate/evidence-context adapter; official maxplus output scores with average tie rank',
         jar_sha256=file_sha(JAR),view=data['summary'],seed_limit='Author code exposes no deterministic random seed; seed labels input/noise generation and repeat id, not author learner RNG'))
    seconds=invoke(folder,'learn',config);validation=Evaluator.validation(cat);history=[];best=-1;chosen=None
    for snapshot in [10,30]:
        rules=folder/f'rules-{snapshot}'
        if not rules.exists():raise FileNotFoundError(rules)
        scores,cost=apply(folder,train,rules,[r['triple'] for r in validation.targets],f'valid_full_{snapshot}',cat);seconds+=cost
        def callback(h,r,t,task):
            if task=='relation':return np.zeros(len(cat['relations']))
            return scores.get(((h,r,t),task),np.zeros(cat['nbase']))
        metrics,rows=validation.score(callback)
        history.append(dict(snapshot_seconds=snapshot,validation=metrics,rule_count=sum(bool(s.strip()) for s in rules.read_text().splitlines())))
        if metrics['link_MRR']>best:best=metrics['link_MRR'];chosen=snapshot
        save(folder/f'validation_{snapshot}.jsonl',rows)
        print(folder.name,'snapshot',snapshot,'val_link_MRR',metrics['link_MRR'],flush=True)
    save(folder/'history.jsonl',history)
    save(folder/'complete.json',dict(best_snapshot=chosen,validation_link_MRR=best,seconds=seconds,jar_sha256=file_sha(JAR),rules_sha256=file_sha(folder/f'rules-{chosen}'),
         no_test_read=True,learn_wall_unavailable=(folder/'learn_recovery.json').exists(),relation_evaluation='not measured during validation selection; evaluated separately across candidate predicates'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--view',default='G1');p.add_argument('--seed',type=int,default=SEEDS[0]);p.add_argument('--fraction',type=float,default=1.);p.add_argument('--noise',type=float,default=0.);fit(p.parse_args())
