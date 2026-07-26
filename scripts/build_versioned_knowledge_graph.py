"""Build auditable raw and Chinese-ready validated graph artifacts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    normalize_identity_text,
    stable_claim_id,
    stable_entity_id,
    stable_evidence_id,
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def entity_id(record: dict[str, object], side: str) -> str:
    existing = record.get(f"{side}_entity_id")
    if existing:
        return str(existing)
    return stable_entity_id(
        str(record.get(f"{side}_canonical_zh") or record.get(side) or ""),
        str(record.get(f"{side}_type") or ""),
    )


def claim_id(record: dict[str, object]) -> str:
    return str(record.get("claim_id") or stable_claim_id(record))


def evidence_id(record: dict[str, object]) -> str:
    return str(record.get("evidence_id") or stable_evidence_id(record))


def graph_records(
    records: list[dict[str, object]], *, validated: bool
) -> list[dict[str, object]]:
    if not validated:
        return records
    return [
        record
        for record in records
        if record.get("decision") in {"silver_candidate", "accepted_silver"}
        and record.get("eligible_for_chinese_graph") is True
        and record.get("inferred_edge") is not True
    ]


def build_layers(
    records: list[dict[str, object]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    entities: dict[str, dict[str, object]] = {}
    surfaces: dict[str, set[str]] = defaultdict(set)
    claims: dict[str, dict[str, object]] = {}
    evidence: dict[str, dict[str, object]] = {}
    assertions: list[dict[str, object]] = []

    for record in records:
        endpoint_ids: dict[str, str] = {}
        for side in ("head", "tail"):
            endpoint = entity_id(record, side)
            endpoint_ids[side] = endpoint
            surface = str(record.get(f"{side}_surface") or record.get(side) or "")
            canonical = str(
                record.get(f"{side}_canonical_zh")
                or record.get(side)
                or surface
            )
            surfaces[endpoint].add(surface)
            entities.setdefault(
                endpoint,
                {
                    "entity_id": endpoint,
                    "canonical_label_zh": canonical,
                    "entity_type": str(record.get(f"{side}_type") or ""),
                    "terminology_id": record.get(f"{side}_terminology_id"),
                    "graph_display_language": "zh-CN",
                },
            )
        cid = claim_id(record)
        eid = evidence_id(record)
        claims.setdefault(
            cid,
            {
                "claim_id": cid,
                "head_entity_id": endpoint_ids["head"],
                "relation": str(record.get("relation") or ""),
                "relation_label_zh": str(
                    record.get("relation_label_zh")
                    or record.get("relation")
                    or ""
                ),
                "tail_entity_id": endpoint_ids["tail"],
                "fault_class_ids": list(record.get("fault_class_ids") or []),
            },
        )
        evidence.setdefault(
            eid,
            {
                "evidence_id": eid,
                "doc_id": record.get("doc_id"),
                "pdf_page_number": record.get("pdf_page_number"),
                "source_url": record.get("source_url"),
                "source_family_id": record.get("source_family_id"),
                "evidence_text": record.get("evidence_text"),
                "evidence_level": record.get("evidence_level"),
                "document_sha256": record.get("document_sha256"),
                "page_text_sha256": record.get("page_text_sha256"),
                "applicability_scope": record.get("applicability_scope"),
            },
        )
        assertions.append(
            {
                "assertion_id": record.get("assertion_id")
                or f"{cid}::{eid}",
                "claim_id": cid,
                "evidence_id": eid,
                "decision": record.get("decision"),
                "final_confidence": record.get("final_confidence"),
                "relation_entailment_valid": record.get(
                    "relation_entailment_valid"
                ),
                "eligible_for_chinese_graph": record.get(
                    "eligible_for_chinese_graph"
                ),
                "inferred_edge": bool(record.get("inferred_edge", False)),
                "triple_id": record.get("triple_id"),
            }
        )

    for endpoint, item in entities.items():
        item["source_surfaces"] = sorted(
            value for value in surfaces[endpoint] if value
        )
        item["normalized_identity"] = normalize_identity_text(
            item["canonical_label_zh"]
        )
    return (
        sorted(entities.values(), key=lambda item: str(item["entity_id"])),
        sorted(claims.values(), key=lambda item: str(item["claim_id"])),
        sorted(evidence.values(), key=lambda item: str(item["evidence_id"])),
        assertions,
    )


def write_graphml(
    path: Path,
    entities: list[dict[str, object]],
    claims: list[dict[str, object]],
    evidence: list[dict[str, object]],
    assertions: list[dict[str, object]],
) -> None:
    try:
        import networkx as nx
    except ImportError as exc:
        raise RuntimeError(
            "networkx is required for GraphML output; install requirements.txt"
        ) from exc

    graph = nx.MultiDiGraph()

    def attrs(item: dict[str, object]) -> dict[str, str | int | float | bool]:
        result: dict[str, str | int | float | bool] = {}
        for key, value in item.items():
            if value is None:
                result[key] = ""
            elif isinstance(value, (list, dict)):
                result[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, (str, int, float, bool)):
                result[key] = value
            else:
                result[key] = str(value)
        return result

    for item in entities:
        graph.add_node(str(item["entity_id"]), layer="entity", **attrs(item))
    for item in claims:
        cid = str(item["claim_id"])
        graph.add_node(cid, layer="claim", **attrs(item))
        graph.add_edge(str(item["head_entity_id"]), cid, role="claim_head")
        graph.add_edge(cid, str(item["tail_entity_id"]), role="claim_tail")
    for item in evidence:
        graph.add_node(
            str(item["evidence_id"]), layer="evidence", **attrs(item)
        )
    for item in assertions:
        graph.add_edge(
            str(item["claim_id"]),
            str(item["evidence_id"]),
            role="supported_by",
            **attrs(item),
        )
    nx.write_graphml(graph, path, encoding="utf-8", prettyprint=True)


def build_version(
    records: list[dict[str, object]],
    *,
    version: str,
    output_root: Path,
) -> dict[str, object]:
    selected = graph_records(records, validated=version == "KG_v1_validated")
    entities, claims, evidence, assertions = build_layers(selected)
    version_dir = output_root / "graph_versions" / version
    triple_dir = output_root / "triples" / version
    version_dir.mkdir(parents=True, exist_ok=True)
    triple_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(triple_dir / "entities.jsonl", entities)
    write_jsonl(triple_dir / "claims.jsonl", claims)
    write_jsonl(triple_dir / "evidence_assertions.jsonl", evidence)
    write_jsonl(triple_dir / "claim_evidence_links.jsonl", assertions)
    write_jsonl(triple_dir / "source_records.jsonl", selected)
    write_graphml(
        version_dir / "marine_pump_graph.graphml",
        entities,
        claims,
        evidence,
        assertions,
    )
    summary = {
        "version": version,
        "graph_language": "zh-CN",
        "source_records": len(selected),
        "entities": len(entities),
        "claims": len(claims),
        "evidence_assertions": len(evidence),
        "claim_evidence_links": len(assertions),
        "decision_counts": dict(
            Counter(str(item.get("decision", "")) for item in selected)
        ),
        "human_expert_reviewed": False,
        "label_policy": "Silver only; never Gold",
    }
    (version_dir / "graph_statistics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"[Graph Build] {version}: 记录={len(selected)}，实体={len(entities)}，"
        f"主张={len(claims)}，证据={len(evidence)}",
        flush=True,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=(
            "data/interim/candidate_triples/"
            "qwen3_7_max_full_corpus_v1_auto_adjudicated/"
            "candidate_triples.auto_adjudicated_silver.jsonl"
        ),
    )
    parser.add_argument(
        "--output-root",
        default="data/kg/marine_pump",
    )
    args = parser.parse_args()
    records = read_jsonl(PROJECT_ROOT / args.input)
    output_root = PROJECT_ROOT / args.output_root
    raw = build_version(records, version="KG_v1_raw", output_root=output_root)
    validated = build_version(
        records,
        version="KG_v1_validated",
        output_root=output_root,
    )
    if validated["source_records"] == 0:
        print(
            "[Graph Build] 警告：中文发布图谱为空。证据Silver不等于中文发布就绪；"
            "必须补充术语规范化后重建，不能把英文surface直接冒充中文规范实体。",
            flush=True,
        )
    print(
        f"[Graph Build] 完成：Raw={raw['source_records']}，"
        f"Validated={validated['source_records']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
