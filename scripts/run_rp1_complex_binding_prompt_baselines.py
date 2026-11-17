#!/usr/bin/env python3
"""Runtime adapter: Schema prompting + post-validation, no token grammar.

Preserves the original controlled executor, rules, seeds, prompts and budgets.
The unavailable grammar implementation is removed explicitly, not optimized
from target scores. Every formal trial is new; setup attempts are excluded.
"""
import argparse
import shutil
from run_rp1_complex_binding_baselines import *
import run_rp1_complex_binding_baselines as baseline

FORMAL=OUT/'formal'

def prepare():
    out=FORMAL
    for name in ['sources.jsonl','targets.jsonl','trials.jsonl','methods.json','output_schema.json','resources.json','runtime_environment.json']:
        save(out/name,read(OUT/name))
    for directory in ['inputs','trace','independent']:
        for p in (OUT/directory).rglob('*'):
            if p.is_file():save(out/p.relative_to(OUT),p.read_text())
    protocol=read(OUT/'protocol.json')
    protocol['arms'].update(B1='B0 + generic JSON Schema prompt + post-generation validation; no token grammar',B2='B1 + generic complex-semantic instructions',B3='B2 draft + generic rereading, both calls charged')
    protocol.update(runtime_decoder='ordinary model sampling in ALL arms; lm-format-enforcer not used during generation; stage.runtime.json records actual settings, overriding the old executor request.constrained intention flag',setup_exclusion={'directory':str(OUT.relative_to(ROOT)),'reason':'token grammar stalled in tokenizer trie; traceback in generation log; no semantic-method conclusion and no setup outputs reused'},semantic_prompts_unchanged=True,independent_sample_unchanged='fixed before generated results; no semantic prompt/threshold tuning using this sample',retries=0)
    save(out/'protocol.json',protocol)
    original=read(OUT/'freeze.json');paths=[p for p in out.rglob('*') if p.is_file() and p.name!='freeze.json']
    code=[ROOT/p for p in original['sha256'] if '/src/' in '/'+p or p.startswith('scripts/') or p.startswith('tests/')]
    code += [Path(__file__),ROOT/'scripts/rp1_complex_binding_cross_evaluation.py',ROOT/'scripts/summarize_rp1_complex_binding.py']
    save(out/'freeze.json',dict(git_head=original['git_head'],sha256={str(p.relative_to(ROOT)):sha(p) for p in paths+code},old_result_sha256=original['old_result_sha256'],teacher_sha256=original['teacher_sha256'],inherited_sources_from=sha(OUT/'freeze.json')))
    save(OUT/'RUNTIME_ABORTED.json',dict(status='setup_only_excluded_from_formal_comparison',formal_directory=str(out.relative_to(ROOT)),reason='Interrupted B3 recovery after prolonged tokenizer-trie traversal; SIGINT traceback establishes constrained-decoder infrastructure failure.',completed_setup_trials=len(list((OUT/'runs').glob('*/result.json'))),unknown_partial_output='B3_MP020_p0018_2026111002 stage2; not recovered, not retried under the old decoder; token usage is bounded by its saved request ceiling',original_reviews='evaluation/ invalid source-vs-output confusion; retained, excluded',corrected_reviews='cross_evaluation/ setup-only because generations used unavailable grammar; retained, excluded'))
    print('Frozen prompt-only formal study:',out)

def execute(out=FORMAL):
    verify(out)
    import faulthandler
    import signal
    faulthandler.register(signal.SIGUSR1,all_threads=True)
    from transformers import AutoModelForCausalLM
    load=AutoModelForCausalLM.from_pretrained
    def instrumented_load(*args,**kwargs):
        model=load(*args,**kwargs);generate=model.generate
        def ordinary_generate(*a,**kw):
            intended=kw.pop('prefix_allowed_tokens_fn',None)
            active=max((out/'runs').glob('*/stage*.request.json'),key=lambda p:p.stat().st_mtime_ns)
            save(active.with_name(active.name.replace('.request.json','.runtime.json')),dict(token_grammar_actually_applied=False,old_executor_requested_constraint=bool(intended),actual_generation_settings={k:kw[k] for k in ['max_new_tokens','do_sample','temperature','top_p','pad_token_id','use_cache'] if k in kw},adapter_sha256=sha(Path(__file__))))
            return generate(*a,**kw)
        model.generate=ordinary_generate
        return model
    AutoModelForCausalLM.from_pretrained=instrumented_load
    baseline.execute(out)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','execute']);args=ap.parse_args()
    globals()[args.stage]()
