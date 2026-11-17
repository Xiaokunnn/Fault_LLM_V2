"""Conservative train-only suspected target-paraphrase guard; preserve v1."""
import re
import difflib
from collections import Counter
from role_io import *


GUARD=r'最大|最小|最高|最低|增加|减少|升高|降低|打开|关闭|进口|出口|吸入|排出|正转|反转|前|后|不|禁止|never|not|\d+(?:\.\d+)?'


def suspected_copy(a,b):
    a=I.norm(a);b=I.norm(b)
    return set(re.findall(GUARD,a))==set(re.findall(GUARD,b)) and difflib.SequenceMatcher(None,a,b).ratio()>=.85


def main():
    original=P/'runs/20261116_role_contribution_v1';assert NEW!=original
    save(NEW/'PROTOCOL.md',(original/'PROTOCOL.md').read_text()+'''\n\n## 训练源文歧义修正版本\n首轮逐例阅读发现train-only同义答案副本，19个唯一对照/场景涉及该风险。旧实验完整保留；此版本将近似字符串且数值/否定/方向词一致的端点标为疑似副本并排除强监督，不改原事实标签。最大/最小、数字编号、前后等差异受保护。该规则不是已确认同义判断，也不保证找到所有语义转述；存在保守误排可能。\n仅重跑gate_kgc、absolute_only、full、shuffled四核心处理，3seed×2场景24个新模型。其余四种学习目标/补偿路径仅作为首轮探索，不能与清理版混为严格同数据消融。模型和超参数均不变；数据修正来自训练源文审查，不依据测试MRR筛选。旧测试仍为已公开历史任务。\n''')
    cat=read(RUN/'data/catalogue.json')['entities'];old=original/DATASET;excluded=[]
    for f in (old/'data').glob('*'):
        if f.name.startswith('utility_') or f.name=='freeze.json':continue
        save(OUT/'data'/f.name,f.read_text())
    for seed in SEEDS:
        src=read(old/f'data/utility_{seed}.jsonl');clean=[]
        for x in src:
            bad=[t for t in set([x['y']]+x['positive_tail_ids']) if suspected_copy(cat[x['neighbor']]['label_zh'],cat[t]['label_zh'])]
            if bad:excluded.append(dict(seed=seed,pair_id=x['pair_id'],neighbor=x['neighbor'],suspected_target_ids=bad,strong=x['strong_contrast'],reason='Conservative target-paraphrase ambiguity, not factual negative'))
            else:clean.append(x)
        summary=dict(read(old/f'data/utility_{seed}.json'),scored=len(clean),strong_pairs=sum(x['strong_contrast'] for x in clean),
            strong_fit=sum(x['strong_contrast'] and x['split']=='fit' for x in clean),strong_probe=sum(x['strong_contrast'] and x['split']=='probe' for x in clean),
            suspected_copies_excluded=len(src)-len(clean),kinds=dict(Counter(x['negative_kind'] for x in clean if x['strong_contrast'])))
        save(OUT/f'data/utility_{seed}.jsonl',clean);save(OUT/f'data/utility_{seed}.json',summary);print(DATASET,summary,flush=True)
    save(OUT/'data/suspected_target_copies.jsonl',excluded)
    save(NEW/'administrative_entity_aliases.json',read(original/'administrative_entity_aliases.json'))
    save(OUT/'data/freeze.json',dict(parent_source_freeze=read(old/'data/freeze.json'),guard=GUARD,similarity_threshold=.85,
        files={str(f.relative_to(OUT)):file_sha(f) for f in (OUT/'data').glob('*')}))
    save(OUT/'data/utility_freeze.json',dict(files={f.name:file_sha(f) for f in (OUT/'data').glob('utility_*')},train_only_ambiguity_correction=True))


if __name__=='__main__':main()
