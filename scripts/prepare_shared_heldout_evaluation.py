#!/usr/bin/env python3
"""Prepare isolated RP1 quality metrics and RP2 queries from one held-out Silver output."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_point_2.dataset import EvidenceCandidate, SilverQuery, relation_role, write_benchmark  # noqa: E402


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _values(value) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(sorted({str(item) for item in value if item}))
    return (str(value),) if value else ()


def _stable(prefix: str, *parts: object) -> str:
    return prefix + hashlib.sha256("\u241f".join(map(str, parts)).encode("utf-8")).hexdigest()[:20]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/interim/heldout_external/shared_silver_v3/candidate_triples.auto_adjudicated_silver.jsonl")
    parser.add_argument("--output-root", default="results/experiments/heldout_external_v3")
    parser.add_argument("--freeze-manifest", default="configs/frozen/rp2_v3_frozen_protocol.json")
    args = parser.parse_args()
    freeze_path = ROOT / args.freeze_manifest
    if not freeze_path.is_file():
        raise FileNotFoundError("RP2 v3 freeze manifest must exist before external preparation")
    freeze_sha256 = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    records = _read_jsonl(ROOT / args.input)
    if any(row.get("document_split") != "held_out_test" for row in records):
        raise ValueError("External preparation accepts held_out_test records only")
    output = ROOT / args.output_root
    output.mkdir(parents=True, exist_ok=True)

    decisions = Counter(str(row.get("decision")) for row in records)
    silver = [
        row for row in records
        if row.get("external_evaluation_decision") == "external_silver_candidate"
        and row.get("external_silver_eligible") is True
        and row.get("inferred_edge") is not True
    ]
    if not silver:
        external_counts = Counter(
            str(row.get("external_evaluation_decision") or "missing")
            for row in records
        )
        raise RuntimeError(
            "No external_silver_candidate records were released; "
            f"external_decisions={dict(external_counts)}, primary_decisions={dict(decisions)}"
        )
    provenance_fields = ("doc_id", "pdf_page_number", "source_url", "document_sha256", "page_text_sha256", "evidence_text")
    complete = sum(all(row.get(field) not in (None, "") for field in provenance_fields) for row in silver)
    page_grounded = sum(row.get("evidence_level") in {"E1", "E2"} for row in silver)
    rp1 = {
        "scope": "MP010-MP013 source-held-out external evaluation only",
        "label_policy": "Silver only; never Gold",
        "human_expert_reviewed": False,
        "records": len(records),
        "decision_counts": dict(decisions),
        "silver_records": len(silver),
        "provenance_complete_rate": complete / len(silver) if silver else 0.0,
        "page_grounded_rate": page_grounded / len(silver) if silver else 0.0,
        "source_family_count": len({str(row.get("source_family_id")) for row in silver if row.get("source_family_id")}),
        "warning": "Automatic external consistency metrics are not human-verified accuracy.",
    }
    (output / "rp1_external_quality.json").write_text(json.dumps(rp1, ensure_ascii=False, indent=2), encoding="utf-8")

    candidates: list[EvidenceCandidate] = []
    for row in silver:
        head = str(row.get("head_canonical_zh") or row.get("head") or "")
        tail = str(row.get("tail_canonical_zh") or row.get("tail") or "")
        relation = str(row.get("relation") or "")
        evidence_id = str(row.get("evidence_id") or row.get("triple_id") or _stable("EXT-E-", row.get("doc_id"), row.get("pdf_page_number"), head, relation, tail))
        candidates.append(EvidenceCandidate(
            evidence_id=evidence_id,
            claim_id=str(row.get("claim_id") or _stable("EXT-C-", head, relation, tail)),
            head_entity_id=str(row.get("head_entity_id") or _stable("EXT-V-", head, row.get("head_type"))),
            tail_entity_id=str(row.get("tail_entity_id") or _stable("EXT-V-", tail, row.get("tail_type"))),
            head_label_zh=head,
            tail_label_zh=tail,
            head_type=str(row.get("head_type") or ""),
            tail_type=str(row.get("tail_type") or ""),
            relation=relation,
            role=relation_role(relation),
            fault_class_ids=_values(row.get("fault_class_ids")),
            evidence_text=str(row.get("evidence_text") or ""),
            source_family_id=str(row.get("source_family_id") or ""),
            doc_id=str(row.get("doc_id") or ""),
            pdf_page_number=int(row.get("pdf_page_number") or 0),
            source_url=str(row.get("source_url") or ""),
            final_confidence=float(row.get("final_confidence") or 0.0),
            evidence_level=str(row.get("evidence_level") or ""),
        ))
    cq = json.loads((ROOT / "configs/competency_questions_marine_pump_v1.json").read_text(encoding="utf-8"))
    if not candidates:
        raise RuntimeError("External Silver was released but no RP2 evidence candidates were created")
    queries = []
    fault_names = {str(item["fault_id"]): str(item["name_zh"]) for item in cq["fault_classes"]}
    role_templates = cq["role_templates"]
    for task in cq.get("task_units", []):
        fault_id = str(task["fault_id"])
        role = str(task["role"])
        fault_name = fault_names[fault_id]
        relevant = tuple(item.evidence_id for item in candidates if fault_id in item.fault_class_ids and role == item.role)
        queries.append(SilverQuery(
            query_id="EXT-" + str(task["cq_id"]),
            question_zh=str(role_templates[role]["question_template_zh"]).format(fault_name_zh=fault_name),
            fault_id=fault_id,
            fault_name_zh=fault_name,
            role=role,
            relevant_evidence_ids=relevant,
            candidate_evidence_ids=(),
            label_status="source_heldout_external_silver" if relevant else "unanswerable_external_silver",
        ))
    benchmark = output / "rp2_external_silver_benchmark"
    write_benchmark(queries, candidates, benchmark)
    manifest_path = benchmark / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "benchmark_id": "marine_pump_rp2_external_source_heldout_v3",
        "scope": "MP010-MP013 isolated external candidate corpus; created after RP2 v3 freeze",
        "held_out_test": True,
        "must_not_tune": True,
        "must_not_enter_primary_graph": True,
        "full_external_corpus_retrieval": True,
        "positive_seeded_candidate_pool": False,
        "rp2_v3_freeze_manifest_sha256": freeze_sha256,
        "external_surface_policy": "use frozen Chinese canonical label when available; otherwise preserve source surface in isolated evaluation only",
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Shared heldout] RP1 Silver={len(silver)}; RP2 candidates={len(candidates)}, answerable queries={sum(bool(q.relevant_evidence_ids) for q in queries)}/40", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
