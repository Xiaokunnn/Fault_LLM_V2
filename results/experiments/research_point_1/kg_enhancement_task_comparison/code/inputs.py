"""Read-only, allowlisted inputs for the expanded1456-only task comparison."""
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import unicodedata

ROOT = Path(__file__).resolve().parents[5]
TASK = Path(__file__).resolve().parents[1]
REV = "833c8040058055434c7f6a9595ec524c3935755f"
GRAPH = "data/kg/marine_pump/versions/expanded_v1_20261012/"
RAW = "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1/candidate_triples.raw_zh.jsonl"
AUDIT = "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_evidence_repaired/candidate_triples.evidence_repaired.jsonl"
NORMALIZED = "data/interim/candidate_triples/qwen3_7_max_full_corpus_v1_zh_local_full/candidate_triples.zh_local_full.jsonl"
SCHEMA = "data/kg/marine_pump/schema/provenance_schema_v3.json"
MANIFEST = "data/source_docs/marine_pump/source_manifest.csv"
BUILD = {f"MP{i:03d}" for i in [*range(1, 8), *range(15, 23)]}
PAGES = {doc: f"data/interim/parsed_pages/corpus_v2/{doc}.pages.v2.jsonl" for doc in sorted(BUILD)}
ALLOWED = {RAW, AUDIT, NORMALIZED, SCHEMA, MANIFEST, *PAGES.values(),
           *(GRAPH + name for name in ["entities.jsonl", "claims.jsonl", "evidence_assertions.jsonl", "source_records.jsonl", "graph.graphml"])}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def norm(text):
    # Do not remove model numbers, negation, units, alternatives or condition words.
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).casefold().split())


def identifier(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True).encode())[:24]


def save(path, value):
    path = Path(path)
    if not path.resolve().is_relative_to(TASK.resolve()):
        raise ValueError("Output escaped experiment")
    if isinstance(value, str):
        data = value.encode()
    elif path.suffix == ".jsonl":
        data = b"".join(json.dumps(r, ensure_ascii=False, sort_keys=True).encode() + b"\n" for r in value)
    else:
        data = json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n"
    if path.exists() and path.read_bytes() != data:
        raise ValueError("Immutable diagnostic output differs: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)


class Inputs:
    def __init__(self):
        self.hashes = {}

    def raw(self, path):
        if path not in ALLOWED:
            raise ValueError("Input not permitted by expanded1456-only scope: " + path)
        data = subprocess.check_output(["git", "show", REV + ":" + path], cwd=ROOT)
        self.hashes[path] = digest(data)
        return data

    def rows(self, path):
        data = self.raw(path)
        return [json.loads(line) for line in data.splitlines() if line.strip()] if path.endswith(".jsonl") else json.loads(data)


def record_ids(record):
    ids = {record.get(key) for key in ["triple_id", "legacy_triple_id", "expansion_parent_triple_id"]}
    ids.add(record.get("terminology_governance", {}).get("previous_ids", {}).get("triple_id"))
    return sorted(value for value in ids if value)


def source_identity(record):
    return tuple(record.get(k) for k in ["doc_id", "pdf_page_number", "head_surface", "relation", "tail_surface", "evidence_text"])


def core_tuple(record):
    return tuple([record.get("head_type"), norm(record.get("head_canonical_zh", record.get("head_surface"))),
                  record.get("relation"), record.get("tail_type"), norm(record.get("tail_canonical_zh", record.get("tail_surface")))])


def source_pointer(record):
    return {key: record.get(key) for key in ["triple_id", "legacy_triple_id", "doc_id", "pdf_page_number",
        "document_sha256", "page_text_sha256", "source_url", "source_family_id", "source_language",
        "pump_type", "service", "applicability_scope", "head_surface", "head_type", "relation", "tail_surface", "tail_type",
        "head_canonical_zh", "tail_canonical_zh", "evidence_text", "evidence_mode", "evidence_start", "evidence_end",
        "evidence_unit_ids", "evidence_units", "expansion_source_witnesses", "conditions_source", "modality"] if key in record}


def native_units(page):
    result = {row["block_id"]: row for row in page.get("text_blocks", [])}
    result.update({cell["cell_id"]: cell for table in page.get("tables", []) for row in table["rows"] for cell in row["cells"]})
    return result


def address_check(record, page):
    text = record.get("evidence_text", "")
    start, end = record.get("evidence_start"), record.get("evidence_end")
    offset = isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(page["page_text"]) and page["page_text"][start:end] == text
    units = native_units(page)
    provided = record.get("evidence_units") or []
    cell_results = []
    for unit in provided:
        original = units.get(unit.get("cell_id"))
        cell_results.append(bool(original and norm(original["text"]) == norm(unit["text"])))
    witnesses = record.get("expansion_source_witnesses") or record.get("source_witnesses") or []
    native_results = []
    for witness in witnesses:
        unit = units.get(witness.get("cell_id") or witness.get("block_id"))
        a, b = witness.get("start"), witness.get("end")
        native_results.append(bool(unit and isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= len(unit["text"]) and unit["text"][a:b] == witness.get("text")))
    return {"exact_contiguous_offset": bool(offset), "provided_cells": len(provided), "matched_cells": sum(cell_results),
            "all_provided_cells_match": bool(provided and all(cell_results)), "provided_native_witnesses": len(witnesses),
            "matched_native_witnesses": sum(native_results), "all_native_witnesses_match": bool(witnesses and all(native_results)),
            "page_text_contains_literal_quote": bool(text and norm(text) in norm(page["page_text"])),
            "metadata_hashes_match": all(str(record.get(key, "")).lower() == str(page.get(key, "")).lower() for key in ["document_sha256", "page_text_sha256"]),
            "semantic_entailment_established": False}


class IdLinks:
    def __init__(self):
        self.parents = {}

    def find(self, key):
        self.parents.setdefault(key, key)
        while self.parents[key] != key:
            key = self.parents[key]
        return key

    def add(self, keys):
        for key in keys[1:]:
            self.parents[self.find(key)] = self.find(keys[0])
        if keys:
            self.find(keys[0])


def load():
    inputs = Inputs()
    data = {"inputs": inputs, "raw": inputs.rows(RAW), "audit": inputs.rows(AUDIT), "normalized": inputs.rows(NORMALIZED)}
    data["graph"] = {key: inputs.rows(GRAPH + key + ".jsonl") for key in ["entities", "claims", "evidence_assertions", "source_records"]}
    data["schema"] = inputs.rows(SCHEMA)
    data["pages"] = {}
    for doc, path in PAGES.items():
        for page in inputs.rows(path):
            if page["doc_id"] != doc:
                raise ValueError("Unexpected document in build pages")
            data["pages"][doc, page["pdf_page_number"]] = page
    for rows in [data["raw"], data["audit"], data["normalized"], data["graph"]["source_records"]]:
        if any(row["doc_id"] not in BUILD for row in rows):
            raise ValueError("Non-build candidate in input")
    data["manifest"] = [row for row in csv.DictReader(io.StringIO(inputs.raw(MANIFEST).decode("utf-8-sig"))) if row["doc_id"] in BUILD]
    return data
