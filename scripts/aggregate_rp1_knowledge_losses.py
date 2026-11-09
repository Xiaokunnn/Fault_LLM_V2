#!/usr/bin/env python3
"""Read-only synthesis of three archived RP1 audits; no models or repairs.

Existing AI labels are kept. Reference items, candidate records, and an
observed repair transition are separate units; no pooled accuracy is computed.
"""
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from rp1_offline_contract_v3 import channel, maximum_matching, object_sha

BASE = ROOT / 'results/experiments/research_point_1'
OUT = BASE / 'knowledge_loss_summary_20261029'
REPORT = ROOT / 'docs/research/RP1_KNOWLEDGE_LOSS_SUMMARY_20261029.md'
INPUTS = {}
BREAKDOWN = []
LEDGER = []
TARGETS = []


def read(relative):
    path = BASE / relative
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix == '.jsonl':
        return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    return json.loads(path.read_text())


def persist(path, value):
    if path.suffix == '.jsonl':
        content = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in value)
    elif path.suffix == '.json':
        content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    else:
        content = value
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content.encode():
            # Only this task's derived aggregates are regenerated. Archived
            # experiments/labels are never destinations of this function.
            if '--refresh-generated' not in sys.argv or (path != REPORT and not path.is_relative_to(OUT)):
                raise ValueError('Refuse overwrite changed file; inspect before --refresh-generated: ' + str(path))
            path.write_bytes(content.encode())
    else:
        path.write_bytes(content.encode())


def percent(n, d):
    return n / d if d else None


def row(dataset, unit, category, n, denominator, loss_denominator=None):
    r = dict(dataset=dataset, unit=unit, category=category, count=n,
             denominator=denominator, fraction=percent(n, denominator),
             loss_denominator=loss_denominator,
             fraction_of_losses=percent(n, loss_denominator) if loss_denominator else None)
    BREAKDOWN.append(r)
    return r


def audit30():
    matches = read('loss_page_audit_v1/page_match_findings.jsonl')
    summary = read('loss_page_audit_v1/summary.json')
    pages = read('loss_page_audit_v1/page_sample_manifest.jsonl')
    candidates = read('loss_page_audit_v1/page_candidate_findings.jsonl')
    assert len(matches) == 245 and len(pages) == 30 and len(candidates) == 210
    counts = Counter()
    tiers = Counter()
    for r in matches:
        if r['match_status'] == 'not_found_in_audited_candidates':
            category = '审计候选未发现对应'
        elif r['match_status'] == 'partial_or_related':
            category = '只部分表达或存在关系/条件差异'
        else:
            assert r['match_status'] == 'matched'
            if not r['matched_qualified']:
                decisions = set(r['candidate_gate_decisions'].values())
                assert decisions in ({'rejected'}, {'quarantined'})
                category = '完整参考有候选对应但被拒绝' if decisions == {'rejected'} else '完整参考有候选对应但被隔离'
            elif not r['matched_publication']['standard']:
                category = '已证据合格但标准中文发布阻断'
            else:
                category = '已进入标准中文图'
        counts[category] += 1
        if r['match_status'] == 'matched':
            for tier, ready in r['matched_publication'].items():
                tiers[tier] += bool(ready)
        LEDGER.append(dict(dataset='30页',unit='source_reference',id=r['atom_id'],
            page_key=r['page_key'],category=category,candidate_ids=r['candidate_ids'],
            original_match_status=r['match_status'],candidate_gate_decisions=r['candidate_gate_decisions'],
            source_file='loss_page_audit_v1/page_match_findings.jsonl'))
        if r['match_status'] == 'matched' and r['matched_qualified'] and not r['matched_publication']['standard']:
            TARGETS.append(dict(dataset='30页',unit='source_reference',id=r['atom_id'],
                page_key=r['page_key'],category='标准中文发布阻断',candidate_ids=r['candidate_ids'],
                head=r['head'],relation=r['relation'],tail=r['tail'],
                status='target_not_repaired_or_verified',verified_complete_recovery=0,
                limitation='已通过旧证据门且匹配旧参考；术语修复/发布重验未执行，不保证新增可用知识'))
    assert sum(counts.values()) == 245 and counts['已进入标准中文图'] == 32
    assert counts['完整参考有候选对应但被拒绝'] == 37 and counts['完整参考有候选对应但被隔离'] == 21
    assert dict(tiers) == summary['complete_reference_matches_published']
    loss_n = 245 - 32
    result = [row('30页', 'source_reference', k, v, 245, loss_n if k != '已进入标准中文图' else None) for k, v in counts.items()]
    strict_to_standard = tiers['standard'] - tiers['strict']
    candidate_counts = Counter((r['original_decision'], r['semantic_support']) for r in candidates)
    return dict(pages=30,reference_items=245,reference_unit='nonexhaustive AI source checklist item',
        standard_complete_published=32,standard_reference_losses=loss_n,loss_categories=result,
        complete_matches=93,qualified_complete_matches=35,
        published_by_tier=dict(tiers),existing_strict_to_standard_reference_difference=strict_to_standard,
        existing_release_difference_is_new_repair=False,
        verified_new_repair_recoveries=None,new_repair_arm_executed=False,
        chinese_release_targets=3,gate_blocked_reference_targets=58,
        supported_candidate_occurrences_not_qualified=sum(v for (decision, grade), v in candidate_counts.items() if decision != 'qualified' and grade == 'supported'),
        candidate_support_limit='210候选的supported标签仅为源文相对支持，明确不等于schema正确或完整条件合格；不计作130条可恢复完整知识',
        source_scope_disputed_items=summary['known_scope_disagreement_reference_atoms'],
        full_run_saved_complete_matches=summary['complete_reference_matches_in_saved_full_run_candidates'],
        page_keys=sorted(r['page_key'] for r in pages))


GROUPS29 = {
    '关系方向/类型/对象角色': {'relation_direction','relation_type','operation_role','scope_role','relation_meaning','unknown_relation'},
    '条件/阶段/范围/例外': {'procedure_context','alternative_lost','condition_logic','missing_exception','missing_scope','scope_overstatement'},
    '对象或维护动作不完整': {'incomplete_object','incomplete_maintenance'},
    '模态或否定要求': {'modality','negative_requirement','requirement_representation'},
    '来源绑定/拼列/新增后果': {'invented_consequence','column_splice','wrong_source_attachment'},
    '目录被当作操作指令': {'toc_as_instruction'},
}


def audit29():
    prefix = 'ai_review_v1/holdout_comparison_v1/'
    outputs = read(prefix + 'outputs.jsonl')
    labels = read(prefix + 'source_quality_judgments.jsonl')
    losses = read(prefix + 'correct_knowledge_losses.jsonl')
    deltas = read(prefix + 'filter_repair_deltas.jsonl')
    allocations = read(prefix + 'reference_allocations.jsonl')
    metrics = read(prefix + 'metrics.json')
    mapping = read(prefix + 'private_arm_mapping.jsonl')
    refs = read('ai_review_v1/heldout_materials/source_first_references.jsonl')
    inventory = read('ai_review_v1/heldout_materials/page_inventory.jsonl')
    labels_by_id = {r['review_id']: r for r in labels}
    label_for = {(r['candidate_id'], r['arm']): labels_by_id[r['review_id']] for r in mapping}
    arms = defaultdict(dict)
    for r in outputs:
        j = label_for[r['candidate_id'],r['arm']]
        assert object_sha(r['payload']) == j['payload_sha256'] and r['page_key'] == j['page_key']
        arms[r['arm']][r['candidate_id']] = dict(r, judgment=j)
    assert len(outputs) == 966 and all(len(v) == 322 for v in arms.values())
    counts = {}
    for arm, records in arms.items():
        core = [r for r in records.values() if r['included'] and channel(r['payload']) == 'core']
        all_kept = [r for r in records.values() if r['included']]
        ec = Counter(r['judgment']['error_category'] for r in core if r['judgment']['verdict']=='E')
        assert dict(ec) == metrics['arms'][arm]['core_error_categories']
        counts[arm] = dict(core_records=len(core),core_grades=dict(Counter(r['judgment']['verdict'] for r in core)),
            all_records=len(all_kept),all_grades=dict(Counter(r['judgment']['verdict'] for r in all_kept)),
            core_error_categories=dict(ec))
        assert counts[arm]['core_grades'] == {k:metrics['arms'][arm]['channels']['core'][k] for k in 'SEU'}
    raw = arms['raw']; filt = arms['mechanical_filter']; repair = arms['source_constrained_repair']
    categories = Counter(); fine = Counter(); raw_core = []
    for cid, r in raw.items():
        if channel(r['payload']) != 'core': continue
        raw_core.append(cid); j=r['judgment']; after=repair[cid]
        if j['verdict']=='S':
            category = '完整支持知识仍保留' if after['included'] and after['judgment']['verdict']=='S' and channel(after['payload'])=='core' else '完整支持知识被程序拒绝'
        elif j['verdict']=='U': category='源文或表示未决'
        else:
            code=j['error_category'];fine[code]+=1
            groups=[name for name,codes in GROUPS29.items() if code in codes]
            assert len(groups)==1,code
            category=groups[0]
        categories[category]+=1
        LEDGER.append(dict(dataset='29页',unit='raw_core_candidate',id=cid,page_key=r['page_key'],
            category=category,raw_verdict=j['verdict'],existing_error_category=j['error_category'],
            reason=j['reason_zh'],repair_included=after['included'],repair_verdict=after['judgment']['verdict']))
    assert len(raw_core)==123 and sum(fine.values())==95
    breakdown=[row('29页','raw_core_candidate',k,n,123,107 if k!='完整支持知识仍保留' else None) for k,n in categories.items()]
    for code,n in sorted(fine.items()):row('29页_语义问题细类','raw_core_error',code,n,95)
    repair_groups = Counter()
    for code,n in counts['source_constrained_repair']['core_error_categories'].items():
        group=next(name for name,codes in GROUPS29.items() if code in codes);repair_groups[group]+=n
    actual_gains=[]
    for cid, before in filt.items():
        after=repair[cid]
        before_ok=before['included'] and before['judgment']['verdict']=='S'
        after_ok=after['included'] and after['judgment']['verdict']=='S'
        if after_ok and not before_ok:actual_gains.append(cid)
    assert not actual_gains
    assert len(deltas)==6 and all(r['repair_verdict']=='E' for r in deltas)
    lost=[r for r in losses if r['arm']=='source_constrained_repair']
    assert len(lost)==19 and sum(r['original_core'] for r in lost)==8
    assert all('unbound_quote' in r['flags'] for r in lost)
    for r in lost:
        original=raw[r['candidate_id']]
        TARGETS.append(dict(dataset='29页',unit='candidate',id=r['candidate_id'],page_key=r['page_key'],
            category='完整支持记录被定位检查拒绝',core=r['original_core'],flags=r['flags'],
            head=original['payload']['head_surface'],relation=original['payload']['relation'],tail=original['payload']['tail_surface'],
            source_review_id=original['judgment']['review_id'],source_review_reason=original['judgment']['reason_zh'],
            status='target_not_repaired_or_verified',verified_complete_recovery=0,
            existing_source_label='S',limitation='源文支持不等于新位置已经修好；不能直接绕过定位检查'))
    allocated = defaultdict(set)
    for r in allocations:allocated[r['arm']].update(r['allocations'])
    assert {arm:len(s) for arm,s in allocated.items()} == {'raw':20,'mechanical_filter':14,'source_constrained_repair':14}
    assert not allocated['source_constrained_repair']-allocated['mechanical_filter']
    # Hypothetical restore of prior S payloads, for source-label opportunity only.
    hypothetical=dict(repair)
    for r in lost:
        hypothetical[r['candidate_id']]=dict(raw[r['candidate_id']],included=True)
    edges=defaultdict(set)
    for r in hypothetical.values():
        if r['included'] and r['judgment']['verdict']=='S' and channel(r['payload'])=='core':
            for ref in r['judgment']['reference_matches']:edges[ref].add(r['candidate_id'])
    opportunity_ref=len(maximum_matching(edges));assert opportunity_ref==20
    # Source-reference coverage has a different denominator from candidates.
    # Preserve one-to-one allocation limits rather than calling them omissions.
    core_full=set();all_full=set();partial=set()
    for r in raw.values():
        j=r['judgment']
        if j['verdict']=='S':
            all_full.update(j['reference_matches'])
            if channel(r['payload'])=='core':core_full.update(j['reference_matches'])
        partial.update(j['partial_reference_matches'])
    reference_counts=Counter()
    for ref in refs:
        key=ref['reference_id']
        if key in allocated['source_constrained_repair']:category='核心完整匹配仍保留'
        elif key in allocated['raw']:category='原本完整匹配因筛查而丢失'
        elif key in core_full:category='有核心S匹配边但受一对一计数限制'
        elif key in all_full:category='仅背景/非核心通道完整表达'
        elif key in partial:category='已有部分匹配标签'
        else:category='无已有完整或部分匹配标签'
        reference_counts[category]+=1
        LEDGER.append(dict(dataset='29页_参考',unit='source_reference',id=key,page_key=ref['page_key'],
            category=category,limit='匹配标签非穷尽；无标签不等于原始模型从未输出'))
    assert sum(reference_counts.values())==118 and reference_counts['有核心S匹配边但受一对一计数限制']==4
    for k,n in reference_counts.items():row('29页_参考','source_reference',k,n,118)
    return dict(pages=29,references=118,raw_candidates=322,raw_core_candidates=123,
        breakdown=breakdown,error_categories=fine,repair_error_groups=dict(repair_groups),arms=counts,
        actual_repair_new_complete_supported=0,actual_repair_new_complete_core=0,
        actual_repair_added_complete_references=0,actual_repair_new_error_releases=3,
        complete_correct_rejected_all=19,complete_correct_rejected_core=8,
        lost_core_fraction_of_original_supported=8/24,lost_all_fraction_of_original_supported=19/137,
        supported_rejection_flags=dict(Counter(f for r in lost for f in r['flags'])),
        reference_coverage={arm:len(s) for arm,s in allocated.items()},
        reference_losses_from_raw=sorted(allocated['raw']-allocated['source_constrained_repair']),
        hypothetical_restore_core_support=24,hypothetical_restore_reference_matches=opportunity_ref,
        hypothetical_restore_not_an_experiment=True,reference_loss_categories=dict(reference_counts),
        page_keys=sorted(r['page_key'] for r in inventory))


def audit10():
    prefix='sentence_step_extraction/validation/'
    decisions=read(prefix+'decisions.jsonl');review=read(prefix+'source_review.jsonl')
    reference=read(prefix+'source_reference.jsonl');coverage=read(prefix+'coverage_review.jsonl')
    metrics=read(prefix+'quality_metrics.json');sources=read(prefix+'sources.jsonl')
    by={r['candidate_id']:r for r in review};counts=Counter();dim=Counter();blocked=[]
    for d in decisions:
        r=by[d['candidate_id']]
        # Explicit aggregation precedence; no new semantic adjudication.
        if r['overall_grade']=='S':
            category='完整支持且程序通过' if d['automatic_pass'] else '完整支持但接口拒绝'
            if not d['automatic_pass']:blocked.append(d)
        elif r['primary_target_scope_grade']=='E':category='主图范围不符/目录控制'
        elif r['core_grade']=='E':category='关系/对象/类型/端点语义不符'
        elif r['condition_grade']=='E':category='条件/型号/条件角色或证据不完整'
        else:category='本体/范围/条件未决'
        counts[category]+=1
        for field in ['core_grade','condition_grade','primary_target_scope_grade']:
            if r[field]=='E':dim[field]+=1
        LEDGER.append(dict(dataset='最新10页',unit='candidate',id=d['candidate_id'],page_key=d['page_key'],category=category,
            existing_grades={k:r[k] for k in ['core_grade','condition_grade','primary_target_scope_grade','overall_grade']},
            flags=d['flags'],reason=r['reason']))
    assert len(decisions)==162 and counts['完整支持且程序通过']==66 and len(blocked)==3
    cov={r['reference_id']:r for r in coverage};categories=Counter()
    for ref in reference:
        if not ref['eligible_for_primary_graph']:continue
        c=cov[ref['reference_id']]
        if c['status']=='complete':
            category='完整表达且程序通过' if c['complete_joint_application_coverage'] else '完整表达但接口阻断'
        elif c['supported_candidates']:category='仅部分组成关系完整支持'
        else:category='不完整且无完整支持组成关系'
        categories[category]+=1
        LEDGER.append(dict(dataset='最新10页_参考',unit='source_reference',id=ref['reference_id'],page_key=ref['page_key'],
            category=category,matched_candidates=c['matched_candidates'],supported_candidates=c['supported_candidates'],reason=c['reason']))
    assert sum(categories.values())==73 and categories['完整表达且程序通过']==22
    for k,n in categories.items():row('最新10页_参考','source_reference',k,n,73,51 if k!='完整表达且程序通过' else None)
    for d in blocked:
        related=[r['reference_id'] for r in coverage if d['candidate_id'] in r['supported_candidates']]
        TARGETS.append(dict(dataset='最新10页',unit='candidate',id=d['candidate_id'],page_key=d['page_key'],category='完整支持但接口拒绝',
            flags=d['flags'],existing_source_label='S',reference_ids=related,status='target_not_repaired_or_verified',
            head=d.get('head',{}).get('canonical_zh'),relation=d.get('relation'),tail=d.get('tail',{}).get('canonical_zh'),
            source_review_reason=by[d['candidate_id']]['reason'],
            verified_complete_recovery=0,limitation='条件拥有者/整页动作切分修复未执行；旧S标签不是修复成功保证'))
    return dict(pages=10,raw_candidates=162,breakdown=[row('最新10页','candidate',k,n,162,96 if k!='完整支持且程序通过' else None) for k,n in counts.items()],
        existing_error_dimensions_overlapping=dict(dim),classification_priority='范围E → 核心E → 条件E → 未决；S再按程序通过分组',
        existing_source_support=69,joint_support=66,actual_verified_repair_recovery=None,repair_arm_executed=False,
        complete_supported_interface_targets=3,hypothetical_joint_support_if_all_three_fixed=69,
        hypothesis_is_not_validated=True,reference_categories=dict(categories),eligible_references=73,
        hypothetical_complete_joint_references_if_all_three_fixed=24,
        original_expansion_gate=metrics['expansion_gate'],page_keys=sorted(r['page_key'] for r in sources))


def mdtable(headers, rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+''.join('| '+' | '.join(str(v) for v in r)+' |\n' for r in rows)


def pct(n,d):return f'{100*n/d:.2f}%'


def render(a,b,c):
    text='''# 三批已有实验的知识损失与恢复量汇总

日期：2026-10-29。仅重算已有30页漏抽审计、29页保留实验、最新10页局部ID实验；没有新增API、抽取、修复执行、语义裁定或图谱发布。

“完整正确”在本汇总中指既有源文AI评价的完整支持S，不是专家事实真值。30页仅有较早的源文参考匹配/相对支持，不能直接提升成后两批的完整条件S。三批目标页互不重叠，但同属构建文档、条件标准和计数单位不同，不合成准确率/召回率，也不把数字直接相加。

## 1. 30页漏抽审计：按245项源文参考追踪流失

主表按既有标准中文图统计，避免只用严格208层代表所有应用知识。分母245项非穷尽AI参考，未进入标准图213项。

'''
    text+=mdtable(['损失阶段/保留','数量','占245项','占213项损失'],[(r['category'],r['count'],pct(r['count'],245),pct(r['count'],213) if r['category']!='已进入标准中文图' else '—') for r in a['loss_categories']])
    text+='''
37项拒绝与21项隔离合计58项。它们已有完整参考对应，但旧准入未通过；不能直接把58项都当规则误拒或可恢复正确知识。77项是在审计候选中未发现对应，不证明模型原始服务从未生成过。75项是部分表达或关系/条件不完整，不是全部没抽出。

**恢复量：**同一批参考在旧严格/保守/标准发布中的完整匹配为17/23/32。标准比严格多覆盖15项（245项的6.12%），这是已经存在的术语发布口径差异，不是本次修复新增，也不是修复算法增益。另有3项旧证据合格但标准中文发布仍阻断，列为待修复目标；没有运行修复对照，实际新恢复量未知。

58项资格阻断和75项不完整表达能修好多少，既有审计没有给出修复后合格结果，不能估算为133项。210条页面候选中130条“源文相对支持但未资格通过”，该标签明确不保证Schema或完整条件，不能当作130条完整正确知识。245项中另有7项已知通用可靠性范围争议，保持原分母并披露，不事后删除。

## 2. 29页保留实验：按123条原始核心候选分类

原始322条输出包含123条核心候选；其中24条S、95条E、4条U。以下各类互斥，以原始核心123条为分母。修复后留下16条完整核心，未形成完整核心输出的107条为损失分母；其中95条是原始语义/表示缺陷，不都是原本正确知识被丢弃。

'''
    text+=mdtable(['类别','数量','占123条','占107条损失'],[(r['category'],r['count'],pct(r['count'],123),pct(r['count'],107) if r['category']!='完整支持知识仍保留' else '—') for r in b['breakdown']])
    text+='\n原始95条问题按已有error_category合并，未经重新判读。各细类和记录ID见CSV/JSONL。\n\n'
    text+=mdtable(['问题组','原始问题量','占95条问题','修复后仍放行问题'],[(group,next(r['count'] for r in b['breakdown'] if r['category']==group),pct(next(r['count'] for r in b['breakdown'] if r['category']==group),95),b['repair_error_groups'].get(group,0)) for group in GROUPS29])
    text+='\n**已有修复到底恢复了多少：**\n\n'
    text+=mdtable(['指标','原始','机械筛查','已有源文修复'],[
        ['全通道保留',322,165,168],['全通道完整支持S',137,118,118],['核心完整支持S',24,16,16],
        ['核心问题E',95,22,25],['完整参考匹配/118',20,14,14]])
    text+='''
逐候选配对验证结果：修复相对机械筛查新增完整支持记录0条（核心也0），新增完整参考0项；发生6项处理差异，其中3项由拒绝变放行，但都仍为E。因此不能把保留165→168叫恢复3条正确知识。

**待验证回收对象：**两组均拒绝19条原本S，占原始137条S的13.87%；其中核心8条，占原始24条核心S的33.33%，也占123条核心候选的6.50%。19条都触发unbound_quote：18条只有这一项，1条另有条件未显式标记；8条核心均只有unbound_quote。优先定位修复的核心目标为8条，另11条是非核心/背景，不能将19都计核心。

若8条核心均成功恢复且不损坏其他记录，完整核心量可由16回到24，参考匹配可由14回到20（多6项）；这是用旧S标签和已有匹配边重放的假设，不是已执行定位修复，也不是新知识抽取收益。其余95条E能修成多少S尚无成功证据；现有修复结果为0条。此批118项参考仅覆盖14项仍不完整，不能只修8条定位误拒就声称页面覆盖已解决。

按118项参考再分解（不是123条候选的同一分母）：

'''
    text+=mdtable(['参考状态','数量','占118项'],[(k,n,pct(n,118)) for k,n in b['reference_loss_categories'].items()])
    text+='''
4项已有核心S匹配边但受“一条候选至多匹配一个参考”约束，不应全部算漏抽。55项无已存匹配标签，也不能直接认定模型从未输出；该清单没有穷尽标注每条错误输出与参考的局部联系。19条全通道回收目标已单列，不通过转入背景知识提高核心指标。

## 3. 最新10页局部ID：按162条全部输出分类

保留既有三个评价字段，不新增语义标签。为避免一条记录多计，错误主因按“范围E→核心关系E→条件E→未决”排序；S再分程序通过与接口拒绝。分母162，未形成联合合格输出96条。

'''
    text+=mdtable(['类别','数量','占162条','占96条损失'],[(r['category'],r['count'],pct(r['count'],162),pct(r['count'],96) if r['category']!='完整支持且程序通过' else '—') for r in c['breakdown']])
    text+='''
现有错误维度的重叠计数是核心E60、条件E13、范围E12；不能相加为85条不同错误。主表按优先级去重后是54/12/12，共78条E，另15条U。不能把程序27条schema标记或7条条件遗漏标记当作全部语义损失量。

**待验证回收对象只有3条现成完整S记录：**

'''
    target=[r for r in TARGETS if r['dataset']=='最新10页']
    text+=mdtable(['候选ID','程序拒绝原因','对应完整参考能否增加'],[(r['id'],'、'.join(r['flags']),'+1项（假设修复）' if r['id'] in ['L01:013','L07:004'] else '仍为部分参考，不能多计完整项') for r in target])
    text+='''
3条占全部162条的1.85%，占69条原本完整支持S的4.35%。没有执行修复臂，实际恢复尚未验证。若只修好这3条，联合支持66→69（40.74%→42.59%），最多新增3条本批合格记录；不是与旧图合并后净新增3条。不能把其余78条E/15条U计为可恢复正确知识。

按73项主图源文参考再检查漏抽/不完整，结果为：

'''
    text+=mdtable(['参考状态','数量','占73项'],[(k,n,pct(n,73)) for k,n in c['reference_categories'].items()])
    text+='''
24项原有完整表达中2项被接口挡住，当前联合完整22项。修复3条S候选，理论上联合参考最多22→24。另49项不完整里20项已有部分S组成关系、29项没有任何完整S组成关系，不能将“有输出文字”当成完成。参考粒度不同且非穷尽，不是正式召回率。

## 4. 恢复量并列：已实现与待验证分开

'''
    text+=mdtable(['数据批次','已有成功证据','未验证的回收目标','不能计为已恢复'],[
        ['30页','既有术语发布差异多覆盖15项参考；本次未运行新修复','3项标准中文阻断；58项准入阻断待诊断','75项不完整、77项未发现候选，恢复数未知'],
        ['29页','已有修复相对筛查恢复0条完整S、0项参考','8条核心S（全通道19条），成功后可多6项参考','已有修复多放行3条均为E'],
        ['最新10页','没有修复臂，成功恢复量未测','3条S接口阻断，成功后最多多2项完整参考','78条E与15条U没有可直接认定的恢复量']])
    text+='''
本汇总没有改变任何原标签、候选、模型响应、图谱或教师。比例仅描述各批已有样本；不作全语料外推，不将三个分母相加。30页和最新10页没有修复试验，所以“未验证”不应写成已证实不能修复；29页则有真实修复对照，新增完整S为0。

复算入口：`python scripts/aggregate_rp1_knowledge_losses.py`。

产物：`results/experiments/research_point_1/knowledge_loss_summary_20261029/`中的`summary.json`、`loss_breakdown.csv`、`record_and_reference_ledger.jsonl`、`recovery_targets.jsonl`、`source_manifest.json`。所有数量由原始逐条记录重算并与原汇总交叉核对；源文件前后SHA256不变。未增加审核层。
'''
    return text


def main():
    if sys.argv[1:] not in ([], ['--refresh-generated']):
        raise ValueError('Only optional --refresh-generated is supported')
    a,b,c=audit30(),audit29(),audit10()
    sets=[set(x['page_keys']) for x in [a,b,c]]
    overlap=dict(a30_h29=len(sets[0]&sets[1]),a30_l10=len(sets[0]&sets[2]),h29_l10=len(sets[1]&sets[2]))
    assert all(n==0 for n in overlap.values())
    for name,h in INPUTS.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    result=dict(date='2026-10-29',task='synthesis_only_no_new_labels_or_experiments',
        audit30=a,holdout29=b,local10=c,target_page_overlap=overlap,
        external_API_calls=0,repair_runs=0,graph_changed=False)
    persist(OUT/'summary.json',result)
    persist(OUT/'record_and_reference_ledger.jsonl',LEDGER)
    persist(OUT/'recovery_targets.jsonl',TARGETS)
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(BREAKDOWN[0]));w.writeheader();w.writerows(BREAKDOWN)
    persist(OUT/'loss_breakdown.csv',s.getvalue())
    persist(OUT/'source_manifest.json',dict(sha256=INPUTS,sources_unchanged=True,new_semantic_judgments=0,
        aggregation_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    persist(REPORT,render(a,b,c))
    persist(OUT/'README.md','''# 2026-10-29 知识损失汇总

只读汇总30页审计、29页保留实验和最新10页局部ID实验，不新增API、修复运行或语义标签。

- `summary.json`：三批独立分母、损失类别与恢复证据。
- `loss_breakdown.csv`：数量、分母、比例及已有错误细类。
- `record_and_reference_ledger.jsonl`：721项分类发生，包括参考和候选，不是721条独立知识。
- `recovery_targets.jsonl`：3项30页中文发布参考、19条29页支持记录（其中8条核心）、3条10页接口记录。单位不同，不把25行相加为25条净新增知识；均未在本次执行修复。
- `source_manifest.json`：19个只读源文件SHA256及汇总脚本哈希。

正文见[汇总报告](../../../../docs/research/RP1_KNOWLEDGE_LOSS_SUMMARY_20261029.md)。

复算：`python scripts/aggregate_rp1_knowledge_losses.py`。
''')
    print(json.dumps(dict(status='PASS',input_files=len(INPUTS),ledger_rows=len(LEDGER),
        recovery_target_rows=len(TARGETS),target_page_overlap=overlap,
        latest_categories={r['category']:r['count'] for r in c['breakdown']},report=str(REPORT.relative_to(ROOT))),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
