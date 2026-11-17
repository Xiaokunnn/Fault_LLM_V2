"""Final immutable delivery manifest; historical results and teachers untouched."""
import subprocess
from collab_io import *


def main():
    assert read(STUDY/'verification/checks.json')['passed']
    assert read(STUDY/'tables/complete.json')['evaluated']==96
    assert read(STUDY/'discovery/source_review_summary.json')['records']==12
    assert read(STUDY/'discovery/source_review_summary.json')['complete_new_facts_confirmed']==0
    before=read(STUDY/'code_freeze_pretest.json')['files']
    core=['model.py','fit_collab.py','prepare_collab.py','controls.py','cache_text.py','evaluate_collab.py','intervene.py']
    for name in core:assert file_sha(PILOT/'code_collab_v1'/name)==before['code_collab_v1/'+name]
    for dataset in ['cold','structured']:
        release=read(STUDY/dataset/'configs/test_release.json')
        assert release['design_sha256']==file_sha(STUDY/'DESIGN_FROZEN.md')
        assert read(STUDY/dataset/'interventions/complete.json')['models']==9
        assert read(STUDY/dataset/'analysis/exposure_audit.json')['candidate_training_exposure']['distinct_used']>0
    for log in ['unit_tests_cold.log','unit_tests_structured.log']:assert '7 passed' in (STUDY/log).read_text()
    readme='''# RP1关系感知可信候选协同补全：已完成研究包

本轮已完成87个新训练模型、9个旧冷场景模型复用、96个主评价和18个冻结权重干预。三种子全保留。完整提出方法未稳定优于G2或LAN，可信门趋于全部打开；此负结果和下一次针对性修改完整保留。

- [实测报告](REPORT.md)：强基线、消融、规模/质量、冷与结构场景、区间及限制。
- [模型公式与计算流程](METHOD.md)、[公开研究区别](RELATED_WORK.md)、[失败机制与下一次单改动](FAILURE_MECHANISM.md)。
- [逐例源文核查](discovery/SOURCE_REVIEW.md)、[排名收益/负迁移案例](analysis/CASEBOOK.md)、[复现命令](REPRODUCE.md)。
- `tables/`：全96行、32个条件组、配对区间、18个冻结干预、候选曝光和门值诊断；`figures/`为PNG+SVG。
- `cold/`和`structured/`：各自数据、模型、逐轮日志、输入/测试释放哈希、原始分数与上下文贡献。
- `discovery/`：26,328条未校准推断、12条实际源文AI阅读、分层结果。两池外提议不等于正确新知识，当前确认新完整事实0。
- `verification/delivery_complete.json`为当前完成状态；较早postprocess/analysis完成文件里的source-review-pending只表示当时等待实际阅读，已由此最终记录替代。

正式expanded1456和RP2/RP3未修改。原20261114_controlled_v1的1896个封存文件及原始输入/PDF通过保全核验。本研究尚未commit/push。
'''
    save(STUDY/'README.md',readme)
    files=sorted(p for root in [STUDY,PILOT/'code_collab_v1'] for p in root.rglob('*') if p.is_file()
        and p.suffix!='.lock' and '__pycache__' not in p.parts and p.name not in ['delivery_manifest.json','delivery_complete.json'])
    entries=[dict(path=str(p.relative_to(PILOT)),bytes=p.stat().st_size,sha256=file_sha(p)) for p in files]
    save(STUDY/'verification/delivery_manifest.json',dict(files=entries,training_core_unchanged_after_pretest_snapshot=core,
         domain_object='833c8040058055434c7f6a9595ec524c3935755f',execution_git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         report_only_fixes=['seed suffix parsing','source-review final report','completed-run idempotent return'],new_models_frozen=True))
    save(STUDY/'verification/delivery_complete.json',dict(completed=True,new_foundations=15,new_adapters=72,reused_models=9,main_evaluations=96,
        frozen_weight_interventions=18,seeds=SEEDS,cold_test_claims=213,structured_test_claims=18,structured_base_supported_claims=6,
        source_AI_reviews=12,source_review_pending=False,old_delivery_files_preserved=1896,original_input_files_preserved=24,original_PDFs_preserved=15,
        unit_tests_each_dataset=7,new_complete_facts_confirmed=0,formal_graph_updates=0,RP2_RP3_modified=False,
        innovation_experimentally_supported=False,decision=read(STUDY/'decision.json'),manifest_files=len(entries),manifest_sha256=file_sha(STUDY/'verification/delivery_manifest.json')))
    print('Sealed new completed study:',len(entries),'files; no formal graph/Git writes',flush=True)


if __name__=='__main__':main()
