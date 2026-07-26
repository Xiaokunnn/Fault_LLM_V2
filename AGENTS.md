# Fault_llm_v2 agent handoff

## Scope and non-negotiable boundaries

- The thesis retains all three research points, but the current implementation task is research point 1 only.
- The active object is the ship engine-room pump system.
- The sibling `Edge_Fault_LLM` directory is read-only prototype reference.
- All automatically or semi-automatically produced triples, graphs, paths, queries and labels are Silver, never Gold.
- The primary graph is Chinese at the canonical semantic layer. Source-language surfaces, verbatim evidence, PDF page, bbox, URL and hashes must remain unchanged.

## Frozen document split

- Primary graph build set: MP001–MP007 and MP015–MP022 (15 documents, 1934 physical pages).
- Development only: MP008. It must not fill build coverage or enter the primary graph.
- Held-out test only: MP009–MP013. They must not enter the primary graph or tune prompts, schema, thresholds or retrieval parameters.
- MP010–MP013 are downloaded and file-level archived, but intentionally not parsed before the primary graph and retrieval protocol are frozen.
- MP014 is excluded from the formal corpus because it is an offshore ESP signal dataset rather than a ship engine-room pump evidence source.

## Current gate

- Claim-scoped mapping v1.4 yields 10/10 evidence-only fault classes passing.
- Frozen records: 534 Silver, 188 needs-review/quarantined, 1088 rejected.
- No human expert review has been performed.
- This permits full build-set extraction; it does not mean the Chinese graph or Silver EvidenceBench already exists.

## Required full-graph workflow

From the repository root on Windows PowerShell:

```powershell
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -LocalOnly -Limit 2
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1 -Limit 2
powershell -ExecutionPolicy Bypass -File scripts\run_full_graph_pipeline_secure.ps1
```

The second command is local-only and makes no API call. The third command is a real two-page smoke test. The final command resumes the same output directory and reuses completed response caches.

Never place the DashScope key in a file or command history. The PowerShell runner asks for it using hidden input and removes it from the process environment on exit.

## Full-extraction policy

- Build a plan from every build-set physical page.
- Only deterministic blank, cover/title, table-of-contents, index and exact-duplicate exclusions are allowed.
- Do not shrink the corpus again with ten-class retrieval scores.
- Current plan: 1934 physical pages, 1889 extraction pages, 45 deterministic exclusions.
- Every extraction page prints progress, elapsed time and ETA. API calls retry and are cached; rerun the same command after interruption.

## Release gates

- `KG_v1_raw` may contain all governed candidate statuses for audit.
- `KG_v1_validated` may contain only Silver, non-inferred records whose Chinese canonical endpoints pass terminology release checks.
- If the runner warns that the Chinese-ready graph is empty or incomplete, do not relabel English surfaces as Chinese entities. Complete terminology governance and rebuild.
- Only after `KG_v1_validated` is frozen may MP009–MP013 be parsed for held-out queries and external Silver claims.
- Build the Silver EvidenceBench only after the graph is frozen.

See `docs/RUN_FULL_GRAPH_ON_ANOTHER_MACHINE.md` for commands, outputs, recovery and expected duration.
