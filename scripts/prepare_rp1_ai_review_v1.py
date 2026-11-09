#!/usr/bin/env python3
"""Record an explicitly non-blind AI audit; freeze method before opening holdout.

The authored decisions below are Codex source reviews, not a learned classifier
or an independent human submission. Historical evidence is never overwritten.
"""
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from check_rp1_independent_review_v1 import load_selected
from rp1_offline_contract_v3 import bind

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/experiments/research_point_1'
OLD = BASE / 'independent_review_v1'
OUT = BASE / 'ai_review_v1'
PROTOCOL = ROOT / 'docs/research/RP1_AI_REVIEW_AND_HOLDOUT_V1_20261004.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        if path.suffix == '.jsonl':
            for row in value:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        else:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def verify_hashes(manifest, root=ROOT):
    for name, digest in manifest.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or sha(path) != digest:
            raise ValueError('Changed or missing dependency: ' + name)


# All decisions authored after reading all six source pages and the 22 payloads.
# U means semantic attachment/interpretation is unresolved, not a known error.
JUDGMENTS = {
    'IR001': ('S', 'Before starting the pump check that', '完整检查宾语唯一对应轴自由转动且无异常声；启动前限定保留。'),
    'IR002': ('E', 'When using the pump once again, firstly tighten the vent plug and drainage valve.', '恢复使用不是要预防的不良事件；prevented_by语义不成立。属于运行程序，且全章维护停机条件不能自动替代排液后恢复使用语境。'),
    'IR003': ('S', 'For safety reasons the pump is only allowed to operate against closed discharge valve', '风险而非必然爆炸；条件保留相邻许可范围的否定、5分钟、标准泵80°C及OR意义。'),
    'IR004': ('S', 'Indentations or cavities in the inner and outer races.', '表中Indentations行外观直接支持；手册轴承及泵型范围在applicability中保留。'),
    'IR005': ('U', 'A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.', '低扬程、流量增大、汽蚀存在句内链式联系；原子直接边的附着不唯一。保留possible，仍不强行断言直接因果错误或正确。'),
    'IR006': ('U', 'A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.', '源文包含流量中间事件，低扬程到功耗的直接性未明确；保留整句、未决及隔离状态。'),
    'IR007': ('E', 'Documents containing maintenance requirements for systems, equipment items or components are to be reviewed at least annually', '原文确有文件复审要求，但Standard不在inspected_by主语域，且年度条件丢失；应作为背景要求，不是泵部件检查。'),
    'IR008': ('S', 'BEARING DEFECTS', '标题及Indentations同一表行支持该缺陷发生于轴承；局部手册范围保留，不推断具体泵故障发生。'),
    'IR009': ('U', 'Together with a reading of the differential pressure the quantity of water delivered can be determined against the characteristics of the pump.', '已保留整句条件，但Together with与前文电流/功率检查的附着仍不确定；不把单独压差读数认作完整测流方法。'),
    'IR010': ('S', 'Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.', '引用风险句，额外condition_logic保存完整许可前文及NOT，泵型/阈值未丢失。'),
    'IR011': ('U', 'A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.', '与IR006相同源句及因果直接性争议；两个提示输出不是两个独立工程案例。'),
    'IR012': ('U', 'A considerably smaller delivery head than expected will increase the quantity of liquid delivered, causing increased power consumption and perhaps cavitation in pump and piping.', '与IR005相同源句，possible保留但直接附着未决；不能由普通知识自动选唯一边。'),
    'IR013': ('S', 'Disassemble the impeller nut or the impeller bolt (1820).', '部件、7.6.5程序及第3步均正确，明确须保留前序步骤且不是完整程序。'),
    'IR014': ('S', 'Check working pressure if a pressure meter is installed.', '本schema允许SignalFeature为检查目标；启动前、已安装压力表及检查动作完整，未将仪表本身当故障目标。'),
    'IR015': ('S', 'Pull the impeller (0120) off the pump shaft, using a proper puller.', '部件号、适当拉拔器、7.6.5第5步和程序依赖保留。'),
    'IR016': ('E', 'The measurement factors used for trending may be as follows:', '温度/压力/功率是趋势分析输入，不是被Trend Analysis测定出的对象；当前diagnosed_by语义倒置，且仅属背景。'),
    'IR017': ('S', 'If valves on inlet pipes are completely opened or not.', '标题赋予检查动作；If...or not是嵌入问句，不是以阀已全开为前提。'),
    'IR018': ('E', 'Should the pump not function as intended, please proceed according to the fault-finding list.', '页内只有查表指引，没有表中具体诊断方法；应保留交叉引用辅助项，不能当作本页完整方法。'),
    'IR019': ('S', 'Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.', '泵损害风险与完整许可范围否定绑定，保留possible及标准泵限制。'),
    'IR020': ('S', 'Otherwise there is a risk of damage to the pump and, at worst, of a steam explosion.', '与IR019语义同类，保留原阈值和风险强度，不由重复输出增加独立证据量。'),
    'IR021': ('S', 'The mechanical seal is adjusted automatically.', '本节泵的机械密封及后句泵输送液润滑/冷却支持局部部件归属；仅结构知识，不增加核心维修数量。'),
    'IR022': ('S', 'the pump casing is filled with liquid.', '源文启动前检查列表明确泵壳灌液检查，宾语与主语唯一绑定。'),
}

SCOPES = [
    ('operation', 'MP007:p0012', 'The outlet valve shall be opened slowly after the pump is started up.', '运行程序与维护动作分列；启动检查仍可计核心检查，局部启动后条件优先于章节标题。'),
    ('bearing_scope', 'MP018:p0026', 'BEARING DEFECTS', '按同一手册轴承章节继承局部泵型；保留PROBABLE CAUSE、同行证据及例外，不推广为所有船舶泵。'),
    ('negative_maintenance', 'MP007:p0015', 'Pump bearing and shaft seal require no maintenance.', '无需维护、禁止操作及建议维护分别表示；schema不可表达者作为辅助要求，不伪造正向维护关系。'),
    ('causal_direction', 'MP004:p0010', JUDGMENTS['IR005'][1], '明示低扬程→流量增加可判断；跨中间事件或分词唯一附着不足的直接边列未决，不强行判错或重写。'),
    ('condition_logic', 'MP004:p0010', 'For safety reasons the pump is only allowed to operate against closed discharge valve for a short time (max. 5 minutes and at a max. temperature of 80°C for standard pumps).', 'Otherwise对应完整许可条件的否定，保留标准泵、阈值与possible，不要求两个限制同时违反。'),
]


def validate_witness(page, witness):
    if witness['kind'] == 'native_table_cells':
        cells = {c['cell_id']: c for t in page['tables'] for r in t['rows'] for c in r['cells']}
        for c in witness['cells']:
            if cells.get(c['cell_id']) != c:
                raise ValueError('Native cell changed')
        return
    text = page['page_text']
    if witness['kind'] != 'page_span':
        cell = next(c for t in page['tables'] for r in t['rows'] for c in r['cells'] if c['cell_id'] == witness['cell_id'])
        text = cell['text']
        if witness.get('bbox') != cell.get('bbox'):
            raise ValueError('Native bbox changed')
    if text[witness['start']:witness['end']] != witness['text']:
        raise ValueError('Source witness mismatch')


def review():
    OUT.mkdir(exist_ok=False)
    # Preserve every prior review artifact; only README later gains a new link.
    prior = [p for parent in [OLD, BASE/'clause_binding_v1'] for p in parent.rglob('*') if p.is_file()]
    save(OUT/'historical_evidence.json', {str(p.relative_to(ROOT)): sha(p) for p in prior})
    seal = json.loads((OLD/'candidate_method_seal.json').read_text())
    verify_hashes(seal['sha256'])
    pages = {p['page_key']:p for p in rows(BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl')}
    with (OLD/'03_candidate_review.csv').open(encoding='utf-8-sig', newline='') as f:
        candidates = list(csv.DictReader(f))
    assert {r['review_id'] for r in candidates} == set(JUDGMENTS)
    decisions = []
    for row in candidates:
        label, quote, reason = JUDGMENTS[row['review_id']]
        witness = bind(pages[row['page_key']], quote)
        if witness is None:
            raise ValueError('Missing authored source quote: ' + row['review_id'])
        a = json.loads(row['assertion_json'])
        decisions.append(dict(review_id=row['review_id'], page_key=row['page_key'],
            assertion=a, verdict=label, reason_zh=reason, source_witnesses=[witness],
            source_page_sha256=row['source_page_sha256'], reviewer='Codex AI assistant',
            blind_to_prior_labels=False, human_review=False, previous_local_model_label='S'))
    save(OUT/'candidate_adjudications.jsonl', decisions)
    scope = []
    for issue, key, quote, decision in SCOPES:
        witness = bind(pages[key], quote)
        if witness is None:
            raise ValueError('Scope quote absent: ' + issue)
        scope.append(dict(issue_id=issue, page_key=key, decision_zh=decision,
            source_witnesses=[witness], unresolved_policy='retain_with_reason_do_not_force_negative', human_review=False))
    save(OUT/'scope_decisions.jsonl', scope)

    refs = rows(BASE/'offline_contract_v3/reference_overlay.jsonl')
    revised = []
    for r in refs:
        a = copy.deepcopy(r['v21_reference_unchanged'])
        key, num = r['page_key'], int(r['reference_id'].split(':')[-1])
        verdict, channel = 'valid', r['v3_evaluation_channel']
        notes = {
            'MP004:p0010':'复核完整段落的风险、检查目标、条件与may措辞；不把风险解释为必然。',
            'MP007:p0012':'复核启动前检查标题和局部if/after；具体检查与运行操作分列。',
            'MP007:p0015':'复核维护总前提、喷嘴/季节/霜冻条件及操作顺序；不扩展到任意电机。',
            'MP015:p0039':'逐步核对7.6.4–7.6.8对象、材料、轴承架、顺序及部件号；引用步骤不是完整程序。',
            'MP018:p0026':'逐行核对表头、缺陷/外观/可能原因方向及手册范围；概率原因不代表唯一诊断。',
        }
        reason = notes[key]
        if key == 'MP004:p0010' and num in {9,10,14}:
            verdict, channel = 'unresolved', 'unresolved'
            reason = '因果分词或Together with的唯一附着不足；保留整句，不强选直接因果或单一测流方案。'
        elif key == 'MP015:p0039' and num in {10,11}:
            verdict, channel = 'unresolved', 'unresolved'
            reason = '相邻章节将1860分别称nut和key；保持原文，不用常识改号，部件身份未决。'
        elif key == 'MP004:p0010' and num in {2,3}:
            verdict = 'needs_revision'
            a.update(relation='increases_risk_of', modality='possible')
            reason = '使用现有风险关系和允许的possible模态规范化；风险不是必然结果，许可限制保持。'
        elif key == 'MP007:p0015' and num in {3,5}:
            verdict = 'needs_revision'
            a['conditions_zh'].append('本节维护前确认泵已停机；仅对维护操作继承，不覆盖恢复使用的局部时序')
            a['evidence'].append(bind(pages[key], 'Before maintenance, confirm that the pump is shut off so as to avoid accident.'))
            reason = '补保存维护总前提，霜冻位置/停用条件和原动作不变。'
        elif key == 'MP018:p0026' and num in {22,23}:
            verdict = 'needs_revision'
            a['conditions_zh'] = [c for c in a['conditions_zh'] if '不构成废弃理由' not in c]
            a['exception_notes_zh'] = ['适度变色不构成报废理由；这是维护例外，不是润滑→变色的因果前提。']
            reason = '从因果/外观成立条件中分离报废例外，仍保留同一行原生证据。'
        a['reference_status'] = 'AI_reviewed_development_reference_non_exhaustive'
        a['expert_review'] = 'not_performed_not_required_for_AI_protocol'
        revised.append(dict(reference_id=r['reference_id'], page_key=key, verdict=verdict,
            evaluation_channel=channel, revised_reference=a, reason_zh=reason, human_review=False,
            prior_reference_unchanged=True, independent_source_first=False))
    save(OUT/'reference_review.jsonl', revised)
    coverage = []
    for key, p in sorted(pages.items()):
        coverage.append(dict(page_key=key, source_page_sha256=p['page_text_sha256'],
            full_source_and_native_rows_read=True, source_first_independent=False,
            revised_core_references=sum(r['page_key']==key and r['evaluation_channel']=='core' for r in revised),
            source_inventory='existing_development_inventory_reused_and_audited_non_exhaustive',
            background_page_without_core=(key=='MP002:p0089'),
            auxiliary_inventory_path='results/experiments/research_point_1/adjudication_targeted_v2_1/auxiliary_and_unresolved.jsonl',
            reference_gap_note='辅助/不可表达/跨页项目另存；没有宣称完整工程知识或补写人工源文清单。'))
    save(OUT/'page_review.jsonl', coverage)
    summary = dict(status='AI_DEVELOPMENT_REVIEW_COMPLETED', created_at=now(),
        authority='user explicitly accepted AI review instead of unavailable human review',
        reviewer='Codex AI assistant; non-blind development review', human_review=False,
        candidates=dict(Counter(r['verdict'] for r in decisions)), candidates_reviewed=len(decisions),
        references=dict(Counter(r['verdict'] for r in revised)), reference_channels=dict(Counter(r['evaluation_channel'] for r in revised)),
        reference_count=len(revised), scope_decisions=len(scope), pages=len(coverage),
        original_development_metrics_recomputed=False, population_accuracy_estimate=False,
        source_independent_or_expert_validation=False, new_external_API_calls=0,
        remaining_errors_do_not_block_measurement=True, method_change=False,
        disposition='freeze_existing_method_for_AI_holdout_measurement_not_publication')
    save(OUT/'review_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def check():
    verify_hashes(json.loads((OUT/'historical_evidence.json').read_text()))
    verify_hashes(json.loads((OLD/'candidate_method_seal.json').read_text())['sha256'])
    pages = {p['page_key']:p for p in rows(BASE/'adjudication_targeted_v2_1/pilot_sources.jsonl')}
    ds, rs, ss = [rows(OUT/name) for name in ['candidate_adjudications.jsonl','reference_review.jsonl','scope_decisions.jsonl']]
    if len(ds)!=22 or {d['review_id'] for d in ds}!=set(JUDGMENTS) or len(rs)!=85 or len(ss)!=5:
        raise ValueError('Incomplete AI audit')
    for d in ds + ss:
        if d.get('human_review') is not False or not d['source_witnesses']:
            raise ValueError('Mislabelled or unevidenced AI audit')
        for w in d['source_witnesses']:
            validate_witness(pages[d['page_key']], w)
    for r in rs:
        for w in r['revised_reference']['evidence']:
            validate_witness(pages[r['page_key']], w)
    freeze_path = OUT/'ai_method_freeze.json'
    if freeze_path.exists():
        verify_hashes(json.loads(freeze_path.read_text())['sha256'])
    return dict(status='AI_AUDIT_AND_HASHES_VERIFIED', candidates=22, references=85,
        scope_decisions=5, human_review=False, heldout_contents_opened_by_check=0)


def freeze():
    report = check()
    deps = list(json.loads((OLD/'candidate_method_seal.json').read_text())['sha256'])
    deps += [str(p.relative_to(ROOT)) for p in OUT.iterdir() if p.is_file()]
    deps += [str(p.relative_to(ROOT)) for p in [PROTOCOL, Path(__file__),
        ROOT/'scripts/check_rp1_independent_review_v1.py',
        ROOT/'tests/unit/test_rp1_ai_review_v1.py',
        OLD/'holdout_plan.json', OLD/'review_input_manifest.json',
        BASE/'adjudication_targeted_v2_1/auxiliary_and_unresolved.jsonl']]
    save(OUT/'ai_method_freeze.json', dict(status='FROZEN_FOR_AI_REFERENCE_EVALUATION',
        frozen_at=now(), protocol=str(PROTOCOL.relative_to(ROOT)), review_checks=report,
        sha256={name:sha(ROOT/name) for name in sorted(set(deps))},
        heldout_contents_opened_before_freeze=0, human_review=False,
        method='unchanged E1 + mechanical_filter + v4.1 roles + clause_binding_v1 repair',
        publication_or_deployment_promotion=False))
    print('Existing method frozen for AI reference evaluation. No human validation claimed.')


def prepare_holdout():
    if not (OUT/'ai_method_freeze.json').exists():
        raise ValueError('Freeze the method before opening holdout sources')
    check()
    plan = json.loads((OLD/'holdout_plan.json').read_text())
    if len(plan['pages']) != 29:
        raise ValueError('Changed holdout manifest')
    pages = load_selected(ROOT/'data/interim/parsed_pages/corpus_v2', plan['pages'])
    target = OUT/'heldout_sources'
    target.mkdir(exist_ok=False)
    save(target/'source_only.jsonl', pages)
    save(target/'opening_record.json', dict(opened_at=now(), pages=len(pages),
        documents=len({p['doc_id'] for p in pages}),
        ai_method_freeze_sha256=sha(OUT/'ai_method_freeze.json'),
        source_bundle_sha256=sha(target/'source_only.jsonl'),
        purpose='AI source-first reference before new extraction outputs',
        historical_candidates_read=False, new_model_calls=0, human_review=False))
    print('Prepared 29 source-only pages after AI method freeze; extraction not run.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['review','check','freeze','prepare-holdout'])
    arg = parser.parse_args().stage
    if arg == 'check':
        print(json.dumps(check(), ensure_ascii=False, indent=2))
    else:
        {'review':review, 'freeze':freeze, 'prepare-holdout':prepare_holdout}[arg]()
