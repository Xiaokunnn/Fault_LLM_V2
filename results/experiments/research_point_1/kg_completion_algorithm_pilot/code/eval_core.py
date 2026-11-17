"""Unified head/tail/relation ranking. Called on validation during fitting only."""
from collections import defaultdict
import numpy as np
from common import read,RUN,rank,aggregate


class Evaluator:
    def __init__(self,targets,known,cat,aliases):
        self.targets=targets;self.cat=cat;self.aliases=aliases
        self.harmonic=np.r_[0.,np.cumsum(1./np.arange(1,max(cat['nbase'],len(cat['relations']))+1))]
        self.tail=defaultdict(set);self.head=defaultdict(set);self.rel=defaultdict(set)
        for h,r,t in known:
            self.tail[aliases[h],r].add(aliases[t]);self.head[r,aliases[t]].add(aliases[h]);self.rel[aliases[h],aliases[t]].add(r)
        self.by_alias=defaultdict(list)
        for i,a in enumerate(aliases):self.by_alias[a].append(i)

    @classmethod
    def validation(cls,cat):
        return cls(read(RUN/'data/validation_targets.jsonl'),read(RUN/'data/validation_truth.json'),cat,read(RUN/'data/filter_entity_aliases.json'))

    def score(self,predict):
        rows=[];n=self.cat['nbase'];R=len(self.cat['relations']);entities=self.cat['entities']
        for q in self.targets:
            h,r,t=q['triple']
            for task,target in [('head',h),('tail',t),('relation',r)]:
                scores=np.asarray(predict(h,r,t,task),dtype=np.float64)
                assert len(scores)==(R if task=='relation' else n)
                if task=='tail':f=[i for a in self.tail[self.aliases[h],r] for i in self.by_alias[a]]
                elif task=='head':f=[i for a in self.head[r,self.aliases[t]] for i in self.by_alias[a]]
                else:f=list(self.rel[self.aliases[h],self.aliases[t]])
                rk,ties=rank(scores,target,f)
                first=int(round(rk-(ties-1)/2));last=first+ties-1
                expected_rr=float((self.harmonic[last]-self.harmonic[first-1])/ties)
                if task=='relation':
                    typed=[j for j,relname in enumerate(self.cat['relations']) if entities[h]['entity_type'] in self.cat['registry'][relname]['domain'] and entities[t]['entity_type'] in self.cat['registry'][relname]['range']]
                else:
                    rule=self.cat['registry'][self.cat['relations'][r]]
                    typed=[j for j,e in enumerate(entities[:n]) if e['entity_type'] in rule['domain' if task=='head' else 'range']]
                typed_rank,_=rank(scores,target,f,allowed=typed)
                visible=scores.copy();visible[f]=-np.inf;visible[target]=scores[target]
                best=int(np.argmax(visible))
                if task=='relation':
                    rr=self.cat['registry'][self.cat['relations'][best]]
                    valid=entities[h]['entity_type'] in rr['domain'] and entities[t]['entity_type'] in rr['range']
                else:
                    rr=self.cat['registry'][self.cat['relations'][r]]
                    valid=entities[best]['entity_type'] in rr['domain' if task=='head' else 'range']
                rows.append(dict(id=q['id'],triple=q['triple'],task=task,rank=rk,ties=ties,
                                 covered=bool(np.ptp(scores)>1e-8),target_score=float(scores[target]),
                                 target_rule_supported=bool(scores[target]>0) if getattr(predict,'symbolic',False) else None,
                                 top1=best,top1_score=float(scores[best]),top1_schema_valid=valid,
                                 typed_rank=typed_rank,typed_answer_count=len(typed),
                                 expected_tie_reciprocal_rank=expected_rr,
                                 endpoint_status=q['endpoint_status']))
        summary=aggregate(rows)
        for task in summary:
            summary[task]['top1_schema_violation_rate']=float(np.mean([not r['top1_schema_valid'] for r in rows if r['task']==task]))
            support=[r['target_rule_supported'] for r in rows if r['task']==task and r['target_rule_supported'] is not None]
            summary[task]['target_rule_support_coverage']=float(np.mean(support)) if support else None
            typed=[r['typed_rank'] for r in rows if r['task']==task]
            summary[task]['typed_MRR']=float(np.mean([1/r for r in typed]))
            summary[task]['tie_randomized_MRR']=float(np.mean([r['expected_tie_reciprocal_rank'] for r in rows if r['task']==task]))
        summary['link_MRR']=float(np.mean([1/r['rank'] for r in rows if r['task']!='relation']))
        return summary,rows
