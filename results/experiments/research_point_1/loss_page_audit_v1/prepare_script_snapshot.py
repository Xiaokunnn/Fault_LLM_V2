"""Build-only, additive RP1 audit packets; never relabel frozen research assets.

prepare -> source-first page annotation -> seal-pages -> open-records.
All writes are exclusive. SHA-priority samples and input identities are retained.
Semantic annotations are supplied by a named reviewer, not synthesized from gates.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/experiments/research_point_1/loss_page_audit_v1"
DOCS = [f"MP{i:03d}" for i in [*range(1, 8), *range(15, 23)]]
SEED = 20260929
SOURCE = ROOT / "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl"
RAW = ROOT / "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl"
PROTOCOL = ROOT / "docs/research/RP1_LOSS_AND_PAGE_AUDIT_V1_PROTOCOL_20260929.md"
SCHEMA = ROOT / "data/kg/marine_pump/schema/provenance_schema_v3.json"
EXTRACTION = ROOT / "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/extraction_run_summary.json"
TIERS = {"strict": ROOT / "data/kg/marine_pump/triples/KG_v1_validated/source_records.jsonl"}
for tier in ("conservative", "standard"):
    TIERS[tier] = ROOT / f"data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/{tier}_graph/triples/KG_v1_validated/source_records.jsonl"


def read_rows(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write_json(name, obj):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_rows(name, rows):
    with (OUT / name).open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def priority(namespace, key):
    return hashlib.sha256(f"{SEED}/{namespace}/{key}".encode()).hexdigest()


def group(r):
    return {"silver_candidate": "qualified", "candidate_needs_review": "quarantined", "rejected": "rejected"}[r["decision"]]


def layout(r):
    return "table_proxy" if r.get("evidence_unit_ids") or "table" in r.get("evidence_mode", "").lower() else "text_proxy"


def flags(r):
    values = set(r.get("rejection_reasons", []) + r.get("review_reasons", []))
    for k in ("evidence_validation", "relation_type_validation", "relation_entailment_validation"):
        part = r.get(k, {})
        for field in ("hard_veto_reasons", "silver_veto_reasons", "reasons", "review_reasons"):
            values.update(part.get(field, []))
    return sorted(values)


def load_pages():
    pages, files = {}, []
    for doc in DOCS:
        p = ROOT / f"data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl"
        files.append(p)
        for row in read_rows(p):
            assert row["doc_id"] == doc and row["document_split"] == "build_train"
            key = f'{doc}:p{row["pdf_page_number"]:04d}'
            assert key not in pages
            assert hashlib.sha256(row["page_text"].encode()).hexdigest() == row["page_text_sha256"]
            pages[key] = row
    assert len(pages) == 1934
    return pages, files


def prepare():
    OUT.mkdir(parents=True, exist_ok=False)
    records = read_rows(SOURCE)
    assert len(records) == 8003 and {r["doc_id"] for r in records} == set(DOCS)
    assert len({r["triple_id"] for r in records}) == 8003
    assert Counter(group(r) for r in records) == {"qualified": 1698, "quarantined": 881, "rejected": 5424}
    pages, files = load_pages()
    inputs = [SOURCE, RAW, PROTOCOL, SCHEMA, EXTRACTION, Path(__file__).resolve(), *TIERS.values(), *files]
    inputs += sorted({ROOT / p["local_file"] for p in pages.values()})
    write_json("input_manifest.json", {str(p.relative_to(ROOT)): sha(p) for p in inputs})
    # Protect existing tracked and untracked research/code/log files, including binaries.
    protected = set(inputs)
    for directory in ("docs", "papers", "configs", "src", "scripts", "tests", "results", "logs"):
        for p in (ROOT / directory).rglob("*"):
            if p.is_file() and not p.is_relative_to(OUT) and "__pycache__" not in p.parts:
                protected.add(p)
    write_json("preservation_before.json", {str(p.relative_to(ROOT)): sha(p) for p in sorted(protected)})
    (OUT / "protocol_snapshot.md").write_bytes(PROTOCOL.read_bytes())
    (OUT / "prepare_script_snapshot.py").write_bytes(Path(__file__).read_bytes())

    strata = defaultdict(list)
    for r in records:
        strata[(r["doc_id"], group(r))].append(r)
    selected, sample = set(), []
    for key, population in sorted(strata.items()):
        for r in sorted(population, key=lambda r: priority("record", r["triple_id"]))[:2]:
            selected.add(r["triple_id"])
            sample.append({"triple_id": r["triple_id"], "sample_kind": "probability", "stratum": list(key), "population_n": len(population), "sample_n": 2, "inclusion_probability": 2 / len(population), "weight": len(population) / 2})
    def tokens(r):
        return {f'layout:{group(r)}:{layout(r)}', f'relation:{r["relation"]}', *[f'flag:{f}' for f in flags(r)]}
    covered = set().union(*(tokens(r) for r in records if r["triple_id"] in selected))
    all_tokens = set().union(*(tokens(r) for r in records))
    token_order = {"layout": 0, "relation": 1, "flag": 2}
    for token in sorted(all_tokens - covered, key=lambda t: (token_order[t.split(":")[0]], t)):
        if token in covered or len(sample) >= 114:
            continue
        pool = [r for r in records if r["triple_id"] not in selected and token in tokens(r)]
        r = min(pool, key=lambda r: priority("supplement", r["triple_id"]))
        selected.add(r["triple_id"])
        covered.update(tokens(r))
        sample.append({"triple_id": r["triple_id"], "sample_kind": "coverage_supplement", "coverage_trigger": token, "weight": None, "inclusion_probability": None})
    for i, s in enumerate(sample, 1):
        s["audit_id"] = f"R{i:03d}"
    write_rows("record_sample_manifest.jsonl", sample)
    write_json("record_sampling_summary.json", {"probability_n": 90, "supplement_n": len(sample)-90, "uncovered_marginal_tokens": sorted(all_tokens-covered)})
    write_rows("record_population_frame.jsonl", [{"triple_id": r["triple_id"], "doc_id": r["doc_id"], "pdf_page_number": r["pdf_page_number"], "decision": group(r), "layout_proxy": layout(r), "relation": r["relation"], "original_flags": flags(r)} for r in records])
    write_json("population_breakdowns.json", {k: dict(Counter(fn(r) for r in records)) for k, fn in {
        "decision": group, "doc_decision": lambda r: f'{r["doc_id"]}/{group(r)}',
        "layout_decision": lambda r: f'{layout(r)}/{group(r)}', "relation_decision": lambda r: f'{r["relation"]}/{group(r)}',
    }.items()} | {"overlapping_original_flags": dict(Counter(f for r in records for f in flags(r)))})

    page_strata = defaultdict(list)
    for key, p in pages.items():
        page_strata[(p["doc_id"], "has_table" if p["tables"] else "no_table")].append(key)
    page_sample = []
    for stratum, keys in sorted(page_strata.items()):
        key = min(keys, key=lambda k: priority("page", k))
        page_sample.append({"page_key": key, "stratum": list(stratum), "population_n": len(keys), "inclusion_probability": 1/len(keys)})
    assert len(page_sample) == 30
    write_rows("page_sample_manifest.jsonl", page_sample)
    write_rows("pages_source_only.jsonl", [{"page_key": s["page_key"], **pages[s["page_key"]]} for s in page_sample])
    with (OUT / "pages_source_only.md").open("x", encoding="utf-8") as f:
        for s in page_sample:
            p = pages[s["page_key"]]
            f.write(f'\n## {s["page_key"]} | {s["stratum"][1]}\n\n{p["title"]}\n\n适用范围：{p["applicability_scope"]}\n\n')
            f.write("```text\n" + "\n".join(line.rstrip() for line in p["page_text"].splitlines() if line.strip()) + "\n```\n")
    write_json("prepare_complete.json", {"seed": SEED, "created_at": datetime.now(timezone.utc).isoformat(), "records": len(sample), "pages": len(page_sample), "external_or_development_content_read": False, "new_extractor_or_teacher_calls": 0})
    print(json.dumps({"output": str(OUT), "records": len(sample), "pages": len(page_sample)}))


def seal_pages():
    annotations = OUT / "page_reference_annotations.jsonl"
    rows = read_rows(annotations)
    sample = read_rows(OUT / "page_sample_manifest.jsonl")
    assert len(rows) == 30 and {r["page_key"] for r in rows} == {s["page_key"] for s in sample}
    assert all("atoms" in r and "review_note" in r for r in rows)
    write_json("page_reference_seal.json", {"sealed_at": datetime.now(timezone.utc).isoformat(), "sha256": sha(annotations), "reviewer": "Codex assistant; single AI source-first review; not domain-expert ground truth", "page_n": 30, "atom_n": sum(len(r["atoms"]) for r in rows)})


def open_records():
    seal = json.loads((OUT / "page_reference_seal.json").read_text())
    assert seal["sha256"] == sha(OUT / "page_reference_annotations.jsonl")
    records = {r["triple_id"]: r for r in read_rows(SOURCE)}
    pages, _ = load_pages()
    memberships = {t: {r["evidence_id"] for r in read_rows(p)} for t, p in TIERS.items()}
    rows = []
    for s in read_rows(OUT / "record_sample_manifest.jsonl"):
        r = records[s["triple_id"]]
        key = f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}'
        rows.append({**s, "record": r, "page": pages[key], "published": {t: r["evidence_id"] in ids for t, ids in memberships.items()}})
    write_rows("record_review_packets.jsonl", rows)
    sample_keys = {s["page_key"] for s in read_rows(OUT / "page_sample_manifest.jsonl")}
    write_rows("page_candidate_comparison_packets.jsonl", [r for r in records.values() if f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}' in sample_keys])
    write_rows("page_raw_comparison_packets.jsonl", [r for r in read_rows(RAW) if f'{r["doc_id"]}:p{r["pdf_page_number"]:04d}' in sample_keys])
    write_json("comparison_opened.json", {"opened_at": datetime.now(timezone.utc).isoformat(), "reference_sha256": seal["sha256"]})
    print(f"Opened {len(rows)} record packets after sealing page reference")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "seal-pages", "open-records"))
    args = parser.parse_args()
    {"prepare": prepare, "seal-pages": seal_pages, "open-records": open_records}[args.stage]()
