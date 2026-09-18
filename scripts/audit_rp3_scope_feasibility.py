#!/usr/bin/env python3
"""Read-only oracle ceilings for fixed proposals, not a learned router result."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research_point_3.artifacts import canonical_json_bytes, file_sha256, _write_immutable


def oracle_frontier(rows):
    """Each full-teacher call repairs at most one query; abstention is not coverage."""
    positive = [r for r in rows if r['teacher_selected_ids']]
    good = [r for r in positive if r['proposal_contract_passed'] and set(r['selected_ids']) == set(r['teacher_selected_ids'])]
    n, p, g = len(rows), len(positive), len(good)
    if not n: raise ValueError('nonempty query subset required')
    return {'queries': n, 'scenario_count': len({r['scenario_id'] for r in rows}),
        'teacher_nonempty': p, 'teacher_empty': n-p, 'correct_nonempty_local': g,
        'correct_nonempty_local_query_fraction': g/n,
        'minimum_full_teacher_calls_for_all_nonempty_exact': p-g,
        'minimum_full_teacher_call_fraction': (p-g)/n,
        'maximum_oracle_no_teacher_fraction_including_empty_abstentions': 1-(p-g)/n,
        'frontier': [{'full_teacher_call_budget': b, 'max_exact_nonempty_served': min(p,g+b),
                      'max_nonempty_service_coverage': min(p,g+b)/p if p else None} for b in range(p+1)]}


def main():
    base = ROOT/'results/experiments/research_point_3'; output = base/'scope_feasibility_v1'
    if output.exists(): raise FileExistsError('preserve prior feasibility audit')
    sources = {'B0_fp32': base/'lec_v1/diagnostics_v1/predictions.jsonl'}
    for seed in (7042027,7042028,7042029):
        sources[f'A2/{seed}'] = base/f'head_ablation_v1/seed_{seed}/A2/predictions.jsonl'
        for arm in ('C0','S0','S1'):
            sources[f'{arm}/{seed}'] = base/f'set_context_v1/seed_{seed}/{arm}/predictions.jsonl'
    records = {}; identity = {}; bindings = {}
    for name, path in sources.items():
        bindings[str(path.relative_to(ROOT))] = file_sha256(path)
        rows = [r for r in map(json.loads,path.read_text().splitlines())
                if r['perturbation_id'] == 'original' and r.get('precision','fp32') == 'fp32']
        for split in ('train','validation'):
            chosen = [r for r in rows if r['split'] == split]
            current = {r['trace_id']: sorted(r['teacher_selected_ids']) for r in chosen}
            if split in identity: assert identity[split] == current
            else: identity[split] = current
            result = oracle_frontier(chosen)
            result['by_scenario'] = {s: oracle_frontier([r for r in chosen if r['scenario_id']==s]) for s in sorted({r['scenario_id'] for r in chosen})}
            records[name+'/'+split] = result
    result = {'schema': 'rp3_fixed_proposal_oracle_frontier_v1', 'input_hashes': bindings, 'records': records,
        'boundary': 'post-experiment feasibility diagnosis only; oracle observes teacher labels, never an executable policy or calibration result',
        'assumptions': ['fixed local proposal per query', 'at most one full-teacher fallback per query',
            'teacher fallback returns the frozen target exactly', 'zero teacher-relative answer-set errors',
            'abstaining on teacher-nonempty queries does not count as service'],
        'cost_unit': 'full RP2 teacher fallbacks, not 7B candidate calls, wall time, energy or network measurements',
        'development_read': False, 'external_read': False, 'model_updates': False, 'policy_selected': False, 'deployment_allowed': False}
    _write_immutable(output/'audit.json',canonical_json_bytes(result))
    lines = ['# 固定本地提案下的理想路由上限', '',
        '只读原始构建集。Oracle知道教师标签，不是可实现路由，不拟合阈值，也不为模型选择。', '',
        '设教师非空数P、本地合约通过且非空精确数G、完整教师回退预算b。零错误服务数最多min(P,G+b)，全覆盖至少需要P−G次完整教师回退。', '',
        '| 提案来源 | split | 查询 | 非空P | 本地正确G | 全非空覆盖至少回退 | 本地正确/全部查询 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for name, value in records.items():
        arm, split = name.rsplit('/',1)
        lines.append(f"| {arm} | {split} | {value['queries']} | {value['teacher_nonempty']} | {value['correct_nonempty_local']} | {value['minimum_full_teacher_calls_for_all_nonempty_exact']} | {value['correct_nonempty_local_query_fraction']:.4f} |")
    lines += ['', 'A2关闭字段/数量学习，仅为不同解码条件的乐观参考，不能直接替代完整控制器。',
        '回退成本按完整查询次数计，未冒充7B调用计数或时延节省。空教师查询的免费弃答也依赖oracle，不能当实际系统收益。',
        '当前验证只有2个场景；相同验证反复内部诊断有选择偏差，不支持独立泛化或风险认证。']
    _write_immutable(output/'audit.md', ('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines))


if __name__ == '__main__': main()
