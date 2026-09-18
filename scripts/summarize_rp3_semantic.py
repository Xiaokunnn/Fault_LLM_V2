#!/usr/bin/env python3
"""Render already frozen E1 results; does not fit or select anything."""
import csv
import io
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.research_point_3.artifacts import _write_immutable


def main():
    root=ROOT/'results/experiments/research_point_3/semantic_v1'
    summary=json.loads((root/'summary.json').read_text())
    cost=json.loads((root/'cost_feasibility.json').read_text())
    check=json.loads((root/'verification.json').read_text())
    lines=['# E1冻结语义特征结果','',
        '只用构建集。C0只读复用，H512与E1各三种子，维度/控制器初始化配对。','',
        '| 臂 | seed | 最佳epoch | 原始val F1 | 非空精确G/7 | 全val空集误填 |',
        '|---|---:|---:|---:|---:|---:|']
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['arm','seed','best_epoch','subset','pointer_precision','pointer_recall','pointer_f1',
        'raw_zero_n','nonempty_n','decoded_empty_n','raw_cardinality_accuracy','decoded_cardinality_accuracy',
        'support_recall','support_negative_false_accept','support_auc','support_ap','support_brier',
        'teacher_empty_false_n','teacher_empty_n','hard_empty_false_n','hard_empty_n'])
    for arm in ('C0','H512','E1'):
        for seed in summary['protocol']['seeds']:
            r=summary['reports'][f'{arm}/{seed}'];empty=r['metrics']['validation_all']['teacher_empty_false_fill']
            lines.append(f"| {arm} | {seed} | {r['best_epoch']} | {r['metrics']['validation_original']['pointer_f1']:.4f} | {r['oracle']['validation']['correct_nonempty_local']}/7 | {empty['numerator']}/{empty['denominator']} |")
            for subset,m in r['metrics'].items():
                z=m['nonempty_target_raw_zero'];e=m['teacher_empty_false_fill'];h=r['joint_metrics'][subset]['hard_empty_false_fill'];sp=r['support'][subset]
                writer.writerow([arm,seed,r['best_epoch'],subset,m['pointer_precision'],m['pointer_recall'],m['pointer_f1'],z['numerator'],z['denominator'],
                    m['nonempty_target_decoded_empty']['numerator'],m['requested_raw_cardinality_accuracy'],m['requested_decoded_cardinality_accuracy'],
                    sp['recall'],sp['negative_false_accept'],sp['roc_auc'],sp['auprc_average_precision'],sp['brier'],e['numerator'],e['denominator'],h['numerator'],h['denominator']])
    lines+=['','场景宏平均再跨三种子汇总（均值±SD；只有2个原始val场景）：','',
        '| 臂 | Pointer F1 | raw零预测 | 最终为空 | raw数量准确 | 最终数量准确 | 负支持误接受 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for a in summary['aggregate']:
        if a['subset']!='validation_original':continue
        f=a['quality']['pointer_f1']
        lines.append(f"| {a['arm']} | {f['mean']:.4f} ± {f['sample_std']:.4f} | {a['raw_zero']['mean']:.4f} | {a['decoded_empty']['mean']:.4f} | {a['quality']['requested_raw_cardinality_accuracy']['mean']:.4f} | {a['quality']['requested_decoded_cardinality_accuracy']['mean']:.4f} | {a['support']['scenario_macro_negative_false_accept']['mean']:.4f} |")
    lines+=['','CPU FP32同后端、查询编码每次重算、证据离线缓存；不含教师、网络与渲染：','',
        '| 臂 | 总参数 | 原始train均值ms | 原始val均值ms | 静态证据FP32字节 | 补测进程HWM MiB |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,c in cost['costs'].items():
        memory=json.loads((root/f'memory_{arm}.json').read_text())['stages']['after_40_query_forwards']
        lines.append(f"| {arm} | {c['total_parameters']} | {c['by_split']['train']['mean_ms']:.3f} | {c['by_split']['validation']['mean_ms']:.3f} | {c['static_evidence_fp32_bytes']} | {memory['VmHWM_kib']/1024:.1f} |")
    lines+=['','内存含解释器、库与载入语料，不是纯模型或目标边缘内存。原计时子进程ru_maxrss同值，保留但不用于比较；另用/proc补测。', '']
    for name,c in summary['comparisons'].items():
        lines.append(f"{name}：通过={c['improved_under_prespecified_rule']}；未通过项："+'、'.join(k for k,v in c['checks'].items() if not v)+'。')
    lines+=['',f"既有研究/日志文件{check['preserved_existing_files']}个哈希不变，模型/源码/监督/早停/目标重建核验通过。",
        '编码器固定23,953,920参数，无查询或证据超过512 token；线上重算与离线特征及40条原始选集一致。',
        '两项总体比较均失败；按预设停止本轮encoder搜索，不训练新路由、不生成校准证书。',
        '这些是教师相对内部诊断，不是专家诊断准确率；编码器替换和oracle界本身不是原创算法贡献。']
    _write_immutable(root/'summary.csv',stream.getvalue().encode())
    _write_immutable(root/'summary.md',('\n'.join(lines)+'\n').encode())
    print('\n'.join(lines))


if __name__=='__main__':main()
