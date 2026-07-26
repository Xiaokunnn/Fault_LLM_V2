import crypto from "node:crypto";
import { execFile } from "node:child_process";
import {
  access,
  mkdir,
  readFile,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const NODE_TYPES = new Set([
  "Equipment",
  "Component",
  "FaultMode",
  "FailureMechanism",
  "Symptom",
  "SignalFeature",
  "Cause",
  "OperatingCondition",
  "InspectionMethod",
  "InspectionAction",
  "MaintenanceAction",
  "Standard",
  "Risk",
]);

const RELATIONS = new Set([
  "contains",
  "located_in",
  "causes",
  "indicates",
  "manifests_as",
  "evolves_to",
  "diagnosed_by",
  "inspected_by",
  "mitigated_by",
  "maintained_by",
  "operates_under",
  "increases_risk_of",
  "specified_by",
]);

const EVIDENCE_ROLES = new Set([
  "symptom",
  "cause_or_mechanism",
  "inspection_or_maintenance",
  "operating_condition",
  "risk",
  "other",
]);

const FAULT_PATTERNS = {
  cavitation: [
    "\\bcavitat(?:e|es|ed|ing|ion)\\w*\\b",
  ],
  air_ingress_or_loss_of_prime: [
    "\\b(?:loss|lose|lost|fails?|failed|unable)\\b.{0,35}\\bprim(?:e|ing)\\b",
    "\\bair\\b.{0,35}\\b(?:drawn|enter|ingress|leak)\\w*\\b",
    "\\bsuction (?:line )?leak\\w*\\b",
  ],
  hydraulic_blockage: [
    "\\b(?:block(?:ed|age)|clog(?:ged|ging)?|obstruct(?:ed|ion)|chok(?:e|ed|ing))\\b",
    "\\b(?:strainer|filter)\\b.{0,30}\\b(?:dirty|blocked|clogged)\\b",
  ],
  impeller_or_wear_part_damage: [
    "\\bimpeller\\b.{0,35}\\b(?:worn|wear|damage|erosion|corrosion)\\w*\\b",
    "\\b(?:worn|wear|damage|erosion|corrosion)\\w*\\b.{0,35}\\bimpeller\\b",
    "\\bwear ring\\w*\\b",
  ],
  mechanical_seal_failure: [
    "\\b(?:mechanical )?seal\\w*\\b.{0,35}\\b(?:fail|leak|wear|worn|damage|overheat)\\w*\\b",
    "\\b(?:fail|leak|wear|worn|damage|overheat)\\w*\\b.{0,35}\\b(?:mechanical )?seal\\w*\\b",
  ],
  bearing_or_lubrication_failure: [
    "\\bbearing\\w*\\b.{0,35}\\b(?:fail|wear|worn|damage|hot|temperature|vibrat|lubricat)\\w*\\b",
    "\\b(?:insufficient|poor|lack of|loss of)\\b.{0,20}\\blubricat\\w*\\b",
  ],
  pump_motor_misalignment: [
    "\\bmisalign\\w*\\b",
    "\\bincorrect alignment\\b",
    "\\balign\\w*\\b.{0,30}\\b(?:pump|motor|coupling|shaft)\\b",
    "\\b(?:pump|motor|coupling|shaft)\\b.{0,30}\\balign\\w*\\b",
  ],
  motor_electrical_drive_failure: [
    "\\bmotor\\b.{0,40}\\b(?:fail|overload|trip|phase|current|temperature|start|stop|hot)\\w*\\b",
    "\\b(?:fail|overload|trip|phase|current|temperature|start|stop|hot)\\w*\\b.{0,40}\\bmotor\\b",
  ],
  pipe_or_valve_integrity_failure: [
    "\\b(?:pipe|piping|line|valve)\\w*\\b.{0,40}\\b(?:leak|fracture|rupture|block|stuck|fail|damage)\\w*\\b",
    "\\b(?:leak|fracture|rupture|block|stuck|fail|damage)\\w*\\b.{0,40}\\b(?:pipe|piping|line|valve)\\w*\\b",
  ],
  dry_running_or_maintenance_induced_failure: [
    "\\bdry[- ]?runn?ing\\b",
    "\\boperat\\w*\\b.{0,30}\\bwithout (?:water|liquid|lubricat\\w*)\\b",
    "\\bincorrect\\w*\\b.{0,30}\\b(?:installation|assembly|maintenance|operation)\\b",
    "\\b(?:maintenance|installation)\\b.{0,30}\\b(?:error|incorrect|improper)\\w*\\b",
  ],
};

const FAULT_IDS = new Set(Object.keys(FAULT_PATTERNS));
const PAGE_CUE_PATTERN =
  /\b(fault|failure|trouble|troubleshoot|cause|remedy|corrective|inspection|maintenance|symptom|alarm|abnormal|damage|leak|vibration|temperature|overload|cavitation|bearing|seal|impeller|suction|discharge)\w*\b/gi;
const TABLE_CUE_PATTERN =
  /\b(fault|failure|trouble|symptom)\b[\s\S]{0,240}\b(cause|reason)\b[\s\S]{0,240}\b(remedy|action|correction)\b/i;

const SYSTEM_PROMPT = `You extract candidate Silver knowledge-graph triples from ONE technical-document PDF page about ship engine-room pump systems.

Return one JSON object and no prose:
{
  "triples": [
    {
      "head": "string",
      "head_type": "allowed node type",
      "relation": "allowed relation",
      "tail": "string",
      "tail_type": "allowed node type",
      "evidence_text": "an exact contiguous quotation copied from the supplied page",
      "triple_confidence": 0.0,
      "fault_class_ids": ["zero or more allowed fault IDs"],
      "evidence_role": "allowed evidence role"
    }
  ],
  "page_summary": "short factual summary",
  "warnings": ["zero or more strings"]
}

Allowed node types:
Equipment, Component, FaultMode, FailureMechanism, Symptom, SignalFeature, Cause, OperatingCondition, InspectionMethod, InspectionAction, MaintenanceAction, Standard, Risk.

Allowed relations:
contains, located_in, causes, indicates, manifests_as, evolves_to, diagnosed_by, inspected_by, mitigated_by, maintained_by, operates_under, increases_risk_of, specified_by.

Allowed fault IDs:
cavitation, air_ingress_or_loss_of_prime, hydraulic_blockage, impeller_or_wear_part_damage, mechanical_seal_failure, bearing_or_lubrication_failure, pump_motor_misalignment, motor_electrical_drive_failure, pipe_or_valve_integrity_failure, dry_running_or_maintenance_induced_failure.

Allowed evidence roles:
symptom, cause_or_mechanism, inspection_or_maintenance, operating_condition, risk, other.

Rules:
1. Extract only relations explicitly stated on this page. Do not use outside knowledge and do not resolve facts from other pages.
2. evidence_text must be copied character-for-character as one contiguous span from PAGE_TEXT. Never insert "...", the ellipsis character, paraphrases, translations, summaries, or separately copied fragments. For a table with a merged fault cell, the quote may include intervening rows, but it must remain one exact contiguous source span. If no such span supports the triple, skip it.
3. Prefer triples useful for symptom-cause/mechanism-fault-inspection-maintenance reasoning. Ignore product marketing, addresses, copyright notices, and generic section navigation.
4. Use the narrowest valid node types and relation. Do not invent entities or relations.
5. Orient every causal edge as Cause or FailureMechanism -> causes -> Symptom, FaultMode, or Risk. Never output Symptom -> causes -> Cause. Example: {"head":"Blocked suction pipe","head_type":"Cause","relation":"causes","tail":"Low pump capacity","tail_type":"Symptom"}.
6. fault_class_ids may be added only when the class is explicitly named or directly stated by the page text. Do not classify from general engineering knowledge. Otherwise return an empty array.
7. triple_confidence measures extraction explicitness, not source authority. Use at least 0.80 only for direct, unambiguous statements.
8. If the page has no suitable explicit claim, return an empty triples array.
9. The output is an automatically extracted Silver candidate.`;

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function redactSecrets(value) {
  return String(value)
    .replace(/\b(?:sk|ak)-[A-Za-z0-9_-]+/gi, "[REDACTED]")
    .replace(/\bLTAI[A-Za-z0-9]{12,}\b/g, "[REDACTED]")
    .replace(/Bearer\s+[A-Za-z0-9._~+/-]+=*/gi, "Bearer [REDACTED]")
    .replace(
      /(["']?(?:api[_-]?key|access[_-]?token|authorization)["']?\s*[:=]\s*["']?)[^"',\s}]+/gi,
      "$1[REDACTED]",
    );
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field.length || row.length) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  const [header, ...body] = rows.filter((item) => item.some((value) => value.length));
  return body.map((values) =>
    Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""])),
  );
}

async function pathExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function writeJson(filePath, value) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function writeJsonl(filePath, values) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const content = values.map((value) => JSON.stringify(value)).join("\n");
  await writeFile(filePath, content ? `${content}\n` : "", "utf8");
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

function countRegex(text, patternSource) {
  return [...text.matchAll(new RegExp(patternSource, "gis"))].length;
}

function annotatePage(page) {
  const faultHits = {};
  for (const [faultId, patterns] of Object.entries(FAULT_PATTERNS)) {
    const count = patterns.reduce(
      (total, pattern) => total + countRegex(page.text, pattern),
      0,
    );
    if (count > 0) {
      faultHits[faultId] = count;
    }
  }
  const cueCount = [...page.text.matchAll(new RegExp(PAGE_CUE_PATTERN.source, "gi"))].length;
  const tableCue = TABLE_CUE_PATTERN.test(page.text);
  const distinctFaults = Object.keys(faultHits).length;
  const lexicalMatches = Object.values(faultHits).reduce((sum, count) => sum + count, 0);
  const score =
    distinctFaults * 12 +
    Math.min(lexicalMatches, 30) +
    Math.min(cueCount, 30) * 0.35 +
    (tableCue ? 10 : 0);
  return {
    ...page,
    selection: {
      score: Number(score.toFixed(3)),
      fault_hits: faultHits,
      cue_count: cueCount,
      table_cue: tableCue,
    },
  };
}

function selectPages(pages, maxPages, minimumCharacters) {
  const candidates = pages
    .map(annotatePage)
    .filter((page) => page.text.trim().length >= minimumCharacters)
    .filter(
      (page) =>
        page.selection.score > 0 ||
        Object.keys(page.selection.fault_hits).length > 0,
    );
  const selected = [];
  const selectedPages = new Set();
  const coveredFaults = new Set();

  while (selected.length < maxPages && selectedPages.size < candidates.length) {
    let best = null;
    let bestUtility = Number.NEGATIVE_INFINITY;
    for (const candidate of candidates) {
      if (selectedPages.has(candidate.pdf_page_number)) {
        continue;
      }
      const newFaults = Object.keys(candidate.selection.fault_hits).filter(
        (faultId) => !coveredFaults.has(faultId),
      ).length;
      const utility =
        candidate.selection.score +
        newFaults * 18 +
        (candidate.selection.table_cue ? 5 : 0);
      if (
        utility > bestUtility ||
        (utility === bestUtility &&
          candidate.pdf_page_number < (best?.pdf_page_number ?? Number.MAX_SAFE_INTEGER))
      ) {
        best = candidate;
        bestUtility = utility;
      }
    }
    if (!best) {
      break;
    }
    selected.push(best);
    selectedPages.add(best.pdf_page_number);
    Object.keys(best.selection.fault_hits).forEach((faultId) =>
      coveredFaults.add(faultId),
    );
  }

  return selected.sort((left, right) => left.pdf_page_number - right.pdf_page_number);
}

async function extractPdfPages({
  pdfPath,
  pdftotextPath,
  manifestItem,
  projectRoot,
}) {
  const { stdout, stderr } = await execFileAsync(
    pdftotextPath,
    ["-layout", "-enc", "UTF-8", pdfPath, "-"],
    {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
      windowsHide: true,
    },
  );
  if (!stdout.trim()) {
    throw new Error(`No text extracted from ${pdfPath}: ${stderr || "unknown error"}`);
  }
  const pageTexts = stdout.split("\f");
  if (!pageTexts.at(-1)?.trim()) {
    pageTexts.pop();
  }
  const relativeFile = path
    .relative(projectRoot, pdfPath)
    .split(path.sep)
    .join("/");
  return pageTexts.map((text, index) => ({
    schema_version: "marine_pump_page_v1",
    doc_id: manifestItem.doc_id,
    pdf_page_number: index + 1,
    page_or_section: `PDF p. ${index + 1}`,
    text,
    text_sha256: sha256(text),
    character_count: text.length,
    local_file: relativeFile,
    title: manifestItem.title,
    publisher: manifestItem.publisher,
    source_url: manifestItem.source_url,
    source_tier: manifestItem.source_tier,
    document_sha256: manifestItem.sha256,
  }));
}

function buildUserPrompt(page) {
  const metadata = {
    doc_id: page.doc_id,
    title: page.title,
    publisher: page.publisher,
    pdf_page_number: page.pdf_page_number,
    page_or_section: page.page_or_section,
    source_url: page.source_url,
  };
  return `Extract candidate triples from the following single PDF page. Output JSON.

DOCUMENT_METADATA
${JSON.stringify(metadata, null, 2)}

PAGE_TEXT_BEGIN
${page.text}
PAGE_TEXT_END`;
}

function apiUrl(baseUrl) {
  return `${baseUrl.replace(/\/+$/, "")}/chat/completions`;
}

async function sleep(milliseconds) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function readToolVersion(command, args) {
  try {
    const { stdout, stderr } = await execFileAsync(command, args, {
      encoding: "utf8",
      windowsHide: true,
    });
    return `${stdout}\n${stderr}`
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find(Boolean) ?? null;
  } catch (error) {
    return (
      `${error?.stdout ?? ""}\n${error?.stderr ?? ""}`
        .split(/\r?\n/)
        .map((line) => line.trim())
        .find(Boolean) ?? null
    );
  }
}

async function callBailian({
  apiKey,
  baseUrl,
  model,
  enableThinking,
  responseFormat,
  temperature,
  timeoutSeconds,
  maxRetries,
  page,
}) {
  const userPrompt = buildUserPrompt(page);
  const requestBody = {
    model,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userPrompt },
    ],
    temperature,
    response_format: responseFormat,
    enable_thinking: enableThinking,
  };
  let lastError;

  for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutSeconds * 1000);
    const requestedAt = new Date().toISOString();
    const started = Date.now();
    try {
      const response = await fetch(apiUrl(baseUrl), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      });
      const responseText = await response.text();
      const latencyMs = Date.now() - started;
      if (!response.ok) {
        const error = new Error(
          `Bailian HTTP ${response.status}: ${redactSecrets(responseText).slice(0, 1000)}`,
        );
        error.status = response.status;
        throw error;
      }
      const responseJson = JSON.parse(responseText);
      const content = responseJson.choices?.[0]?.message?.content;
      if (typeof content !== "string") {
        throw new Error("Bailian response did not contain string message content");
      }
      const cleaned = content
        .trim()
        .replace(/^```(?:json)?\s*/i, "")
        .replace(/\s*```$/, "");
      const extractedJson = JSON.parse(cleaned);
      return {
        request_id: responseJson.id ?? null,
        model: responseJson.model ?? model,
        finish_reason: responseJson.choices?.[0]?.finish_reason ?? null,
        usage: responseJson.usage ?? {},
        latency_ms: latencyMs,
        requested_at: requestedAt,
        responded_at: new Date().toISOString(),
        attempt,
        response_json: extractedJson,
        prompt_sha256: sha256(`${SYSTEM_PROMPT}\n${userPrompt}`),
      };
    } catch (error) {
      lastError = error;
      const retryable =
        error?.name === "AbortError" ||
        error?.status === 408 ||
        error?.status === 409 ||
        error?.status === 429 ||
        (Number(error?.status) >= 500 && Number(error?.status) < 600);
      if (!retryable || attempt === maxRetries) {
        break;
      }
      await sleep(Math.min(1000 * 2 ** (attempt - 1), 8000));
    } finally {
      clearTimeout(timer);
    }
  }
  throw new Error(redactSecrets(lastError?.message ?? lastError ?? "Unknown API error"));
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findEvidenceSpan(pageText, evidenceText) {
  const quote = String(evidenceText ?? "").trim();
  if (!quote) {
    return { matched: false, text: "", method: "empty" };
  }
  if (pageText.includes(quote)) {
    return { matched: true, text: quote, method: "exact" };
  }
  const tokens = quote.split(/\s+/).filter(Boolean);
  if (tokens.length < 3 || tokens.length > 240) {
    return { matched: false, text: quote, method: "not_found" };
  }
  const pattern = tokens.map(escapeRegex).join("\\s+");
  for (const [flags, method] of [
    ["m", "whitespace_normalized"],
    ["im", "case_and_whitespace_normalized"],
  ]) {
    const match = pageText.match(new RegExp(pattern, flags));
    if (match) {
      return { matched: true, text: match[0], method };
    }
  }
  return { matched: false, text: quote, method: "not_found" };
}

function findPhraseSpan(pageText, phrase) {
  const quote = String(phrase ?? "").trim();
  if (!quote) return null;
  const exactStart = pageText.indexOf(quote);
  if (exactStart >= 0) {
    return { start: exactStart, end: exactStart + quote.length };
  }
  const tokens = quote.split(/\s+/).filter(Boolean);
  if (tokens.length < 1 || tokens.length > 80) return null;
  const pattern = tokens.map(escapeRegex).join("\\s+");
  for (const flags of ["m", "im"]) {
    const match = new RegExp(pattern, flags).exec(pageText);
    if (match?.index >= 0) {
      return { start: match.index, end: match.index + match[0].length };
    }
  }
  return null;
}

function reconstructEvidenceSpan(pageText, head, tail) {
  const headSpan = findPhraseSpan(pageText, head);
  const tailSpan = findPhraseSpan(pageText, tail);
  if (!headSpan || !tailSpan) {
    return { matched: false, text: "", method: "not_found" };
  }
  const start = Math.min(headSpan.start, tailSpan.start);
  const end = Math.max(headSpan.end, tailSpan.end);
  if (end - start > 3000) {
    return { matched: false, text: "", method: "context_too_long" };
  }
  return {
    matched: true,
    text: pageText.slice(start, end).trim(),
    method: "head_tail_context_reconstructed",
  };
}

function relationTypesValid(
  relation,
  headType,
  tailType,
  relationTypeConstraints,
) {
  const constraint = relationTypeConstraints?.[relation];
  return (
    Array.isArray(constraint?.head_types) &&
    constraint.head_types.includes(headType) &&
    Array.isArray(constraint?.tail_types) &&
    constraint.tail_types.includes(tailType)
  );
}

function normalizeTriple({
  modelTriple,
  page,
  apiRecord,
  config,
  manifestItem,
  documentSplit,
  relationTypeConstraints,
}) {
  let head = String(modelTriple?.head ?? "").trim();
  let tail = String(modelTriple?.tail ?? "").trim();
  let headType = String(modelTriple?.head_type ?? "").trim();
  let tailType = String(modelTriple?.tail_type ?? "").trim();
  let relation = String(modelTriple?.relation ?? "").trim();
  const normalizationActions = [];
  if (
    relation === "causes" &&
    ["Symptom", "FaultMode", "Risk"].includes(headType) &&
    ["Cause", "FailureMechanism"].includes(tailType)
  ) {
    [head, tail] = [tail, head];
    [headType, tailType] = [tailType, headType];
    normalizationActions.push("reoriented_cause_to_effect");
  }
  if (
    ["diagnosed_by", "inspected_by"].includes(relation) &&
    ["InspectionMethod", "InspectionAction"].includes(headType) &&
    !["InspectionMethod", "InspectionAction"].includes(tailType)
  ) {
    [head, tail] = [tail, head];
    [headType, tailType] = [tailType, headType];
    normalizationActions.push(`reoriented_${relation}_target_to_method`);
  }
  if (relation === "indicates" && tailType === "MaintenanceAction") {
    relation = "mitigated_by";
    normalizationActions.push("changed_indicates_to_mitigated_by");
  }
  const modelConfidence = Math.max(
    0,
    Math.min(1, Number(modelTriple?.triple_confidence ?? 0)),
  );
  const schemaValid =
    Boolean(head && tail) &&
    NODE_TYPES.has(headType) &&
    NODE_TYPES.has(tailType) &&
    RELATIONS.has(relation) &&
    relationTypesValid(
      relation,
      headType,
      tailType,
      relationTypeConstraints,
    );
  let evidence = findEvidenceSpan(page.text, modelTriple?.evidence_text);
  if (!evidence.matched) {
    const reconstructed = reconstructEvidenceSpan(page.text, head, tail);
    if (reconstructed.matched) {
      evidence = reconstructed;
      normalizationActions.push("reconstructed_contiguous_evidence_span");
    }
  }
  const requestedFaultClassIds = Array.isArray(modelTriple?.fault_class_ids)
    ? [...new Set(modelTriple.fault_class_ids.filter((item) => FAULT_IDS.has(item)))]
    : [];
  const claimEntityText = `${head}\n${tail}`;
  const faultClassIds = requestedFaultClassIds.filter(
    (item) =>
      FAULT_PATTERNS[item].some(
        (pattern) => countRegex(claimEntityText, pattern) > 0,
      ),
  );
  const rejectedFaultClassIds = requestedFaultClassIds.filter(
    (item) => !faultClassIds.includes(item),
  );
  if (rejectedFaultClassIds.length) {
    normalizationActions.push(
      "removed_fault_class_without_head_or_tail_lexical_support",
    );
  }
  const evidenceRole = EVIDENCE_ROLES.has(modelTriple?.evidence_role)
    ? modelTriple.evidence_role
    : "other";
  const identity = [
    page.doc_id,
    page.pdf_page_number,
    head,
    headType,
    relation,
    tail,
    tailType,
    evidence.text,
  ].join("\u241f");
  const tripleId = `MPT-${sha256(identity).slice(0, 20)}`;
  const evidenceConfidence =
    evidence.method === "head_tail_context_reconstructed"
      ? Number(config.reconstructed_evidence_confidence)
      : 1;
  const sourceConfidence =
    {
      A: 1,
      B: 0.95,
      C: 0.85,
      D: 0.7,
    }[page.source_tier] ?? 0.8;
  let confidence =
    schemaValid && evidence.matched
      ? Number(
          (modelConfidence * evidenceConfidence * sourceConfidence).toFixed(3),
        )
      : Math.min(modelConfidence, 0.59);
  const semanticReviewOverride =
    config.semantic_review_overrides?.[tripleId] ?? null;
  const semanticEntailmentValid = semanticReviewOverride ? false : null;
  const semanticAuditStatus = semanticReviewOverride
    ? `${semanticReviewOverride.reviewer_type ?? "secondary_audit"}_${semanticReviewOverride.status ?? "review"}`
    : "not_manually_reviewed";
  if (semanticReviewOverride) {
    confidence = Math.min(
      confidence,
      Number(semanticReviewOverride.confidence_ceiling ?? 0.6),
    );
    normalizationActions.push("semantic_audit_override_requires_review");
  }
  const silverCandidate =
    schemaValid &&
    evidence.matched &&
    semanticEntailmentValid !== false &&
    confidence >= config.minimum_silver_candidate_confidence;
  const rejectionReasons = [];
  if (!schemaValid) {
    rejectionReasons.push("schema_or_relation_type_invalid");
  }
  if (!evidence.matched) {
    rejectionReasons.push("evidence_span_not_verified");
  }
  if (confidence < config.minimum_candidate_confidence) {
    rejectionReasons.push("below_candidate_confidence");
  }
  const pageKey = `${page.doc_id}:${page.pdf_page_number}`;
  const pageMetadata = config.page_metadata_overrides?.[pageKey] ?? {};
  const modelPageWarnings = Array.isArray(apiRecord.response_json?.warnings)
    ? apiRecord.response_json.warnings.map((warning) =>
        redactSecrets(String(warning)),
      )
    : [];

  return {
    triple_id: tripleId,
    head,
    head_type: headType,
    relation,
    tail,
    tail_type: tailType,
    doc_id: page.doc_id,
    page_or_section: page.page_or_section,
    evidence_text: evidence.text,
    triple_confidence: confidence,
    model_confidence: modelConfidence,
    extractor: `bailian:${config.model}:${config.prompt_version}`,
    validator: `local:${config.postprocessor_version}`,
    source_url: page.source_url,
    chunk_id: `${page.doc_id}_p${String(page.pdf_page_number).padStart(4, "0")}`,
    local_file: page.local_file,
    source_tier: page.source_tier,
    document_sha256: page.document_sha256,
    document_split: documentSplit,
    extraction_run_id: config.run_id,
    validation_votes: {
      schema_valid: schemaValid,
      relation_semantics_valid: relationTypesValid(
        relation,
        headType,
        tailType,
        relationTypeConstraints,
      ),
      evidence_span_matched: evidence.matched,
      evidence_match_method: evidence.method,
      evidence_confidence_component: evidenceConfidence,
      source_confidence_component: sourceConfidence,
      semantic_entailment_valid: semanticEntailmentValid,
    },
    validation_status: silverCandidate
      ? "silver_candidate"
      : "candidate_needs_review",
    fault_class_ids: faultClassIds,
    fault_class_validation_scope: "normalized_head_and_tail",
    rejected_fault_class_ids: rejectedFaultClassIds,
    normalization_actions: normalizationActions,
    semantic_review_reason: semanticReviewOverride?.reason ?? null,
    semantic_audit_status: semanticAuditStatus,
    rejection_reasons: rejectionReasons,
    model_page_warnings: modelPageWarnings,
    evidence_role: evidenceRole,
    pdf_page_number: page.pdf_page_number,
    printed_page_label: pageMetadata.printed_page_label ?? null,
    visual_layout_checked: Boolean(pageMetadata.visual_layout_checked),
    publisher: manifestItem.publisher,
    inferred_edge: false,
    model_request_id: apiRecord.request_id,
    api_latency_ms: apiRecord.latency_ms,
  };
}

function uniqueTypedNodeCount(triples, nodeTypes, fallbackRole) {
  const units = new Set();
  for (const triple of triples) {
    if (nodeTypes.has(triple.head_type)) {
      units.add(
        `${triple.doc_id}|${triple.pdf_page_number}|${triple.head_type}|${triple.head.toLowerCase()}`,
      );
    }
    if (nodeTypes.has(triple.tail_type)) {
      units.add(
        `${triple.doc_id}|${triple.pdf_page_number}|${triple.tail_type}|${triple.tail.toLowerCase()}`,
      );
    }
    if (
      fallbackRole &&
      triple.evidence_role === fallbackRole &&
      !nodeTypes.has(triple.head_type) &&
      !nodeTypes.has(triple.tail_type)
    ) {
      units.add(`${triple.doc_id}|${triple.pdf_page_number}|${triple.triple_id}`);
    }
  }
  return units.size;
}

function buildCoverage(triples, config, extractionFunnel) {
  const allEligible = triples.filter(
    (triple) =>
      triple.validation_status === "silver_candidate" &&
      triple.triple_confidence >= config.minimum_silver_candidate_confidence,
  );
  const eligible = allEligible.filter(
    (triple) => triple.document_split === "build_train",
  );
  const faultCoverage = {};

  for (const faultId of FAULT_IDS) {
    const relevant = eligible.filter((triple) =>
      triple.fault_class_ids.includes(faultId),
    );
    const symptomCount = uniqueTypedNodeCount(
      relevant,
      new Set(["Symptom"]),
      "symptom",
    );
    const causeMechanismCount = uniqueTypedNodeCount(
      relevant,
      new Set(["Cause", "FailureMechanism"]),
      "cause_or_mechanism",
    );
    const inspectionMaintenanceCount = uniqueTypedNodeCount(
      relevant,
      new Set(["InspectionMethod", "InspectionAction", "MaintenanceAction"]),
      "inspection_or_maintenance",
    );
    const documents = [...new Set(relevant.map((triple) => triple.doc_id))];
    const sourceFamilies = [
      ...new Set(relevant.map((triple) => triple.publisher)),
    ];
    const gate = {
      symptom_at_least_5: symptomCount >= 5,
      cause_or_mechanism_at_least_3: causeMechanismCount >= 3,
      inspection_or_maintenance_at_least_2:
        inspectionMaintenanceCount >= 2,
      independent_documents_at_least_2: documents.length >= 2,
      source_families_at_least_2: sourceFamilies.length >= 2,
    };
    faultCoverage[faultId] = {
      eligible_triples: relevant.length,
      unique_evidence_spans: new Set(
        relevant.map(
          (triple) =>
            `${triple.doc_id}|${triple.pdf_page_number}|${triple.evidence_text}`,
        ),
      ).size,
      symptom_evidence: symptomCount,
      cause_or_mechanism_evidence: causeMechanismCount,
      inspection_or_maintenance_evidence: inspectionMaintenanceCount,
      document_ids: documents,
      source_families: sourceFamilies,
      pilot_gate_checks: gate,
      pilot_gate_passed: Object.values(gate).every(Boolean),
    };
  }

  return {
    report_version: "marine_pump_pilot_coverage_v1",
    interpretation:
      "Pilot screening over selected pages only. It does not authorize bulk graph construction unless the formal build-set coverage gate is separately passed.",
    total_candidate_triples: triples.length,
    extraction_funnel: extractionFunnel,
    schema_and_evidence_verified_candidates: triples.filter(
      (triple) => triple.validation_votes.schema_valid && triple.validation_votes.evidence_span_matched,
    ).length,
    high_confidence_silver_candidates: allEligible.length,
    review_pending_candidates: triples.filter(
      (triple) => triple.validation_status === "candidate_needs_review",
    ).length,
    semantic_audit_overrides_requiring_review: triples.filter(
      (triple) =>
        triple.validation_votes.semantic_entailment_valid === false,
    ).length,
    build_set_high_confidence_silver_candidates: eligible.length,
    development_candidates_excluded_from_gate: allEligible.filter(
      (triple) => triple.document_split === "development",
    ).length,
    unmapped_high_confidence_candidates: allEligible.filter(
      (triple) => triple.fault_class_ids.length === 0,
    ).length,
    fault_coverage: faultCoverage,
    fault_classes_passing_pilot_gate: Object.values(faultCoverage).filter(
      (item) => item.pilot_gate_passed,
    ).length,
  };
}

function buildMarkdownReport({
  config,
  split,
  selection,
  runManifest,
  coverage,
  triples,
}) {
  const selectionRows = selection.documents
    .map(
      (document) => {
        const pages = document.selected_pages
          .map((page) => {
            const metadata =
              config.page_metadata_overrides?.[
                `${document.doc_id}:${page.pdf_page_number}`
              ] ?? {};
            return metadata.printed_page_label
              ? `${page.pdf_page_number}（印刷页${metadata.printed_page_label}）`
              : String(page.pdf_page_number);
          })
          .join(", ");
        return `| ${document.doc_id} | ${document.split} | ${document.parsed_pages} | ${pages} |`;
      },
    )
    .join("\n");
  const coverageRows = Object.entries(coverage.fault_coverage)
    .map(
      ([faultId, item]) =>
        `| ${faultId} | ${item.symptom_evidence} | ${item.cause_or_mechanism_evidence} | ${item.inspection_or_maintenance_evidence} | ${item.document_ids.length} | ${item.source_families.length} | ${item.pilot_gate_passed ? "通过" : "未通过"} |`,
    )
    .join("\n");
  const funnelRows = runManifest.per_document_extraction_stats
    .map(
      (item) =>
        `| ${item.doc_id} | ${item.raw_model_proposals} | ${item.retained_candidates} | ${item.high_confidence_silver_candidates} | ${item.review_pending_candidates} | ${item.rejected_before_candidate} | ${item.model_page_warning_count} | ${item.retention_rate_percent}% |`,
    )
    .join("\n");
  const sampleSections = config.representative_doc_ids
    .map((docId) => {
      const sample = triples
        .filter(
          (triple) =>
            triple.doc_id === docId &&
            triple.validation_status === "silver_candidate",
        )
        .sort(
          (left, right) =>
            left.evidence_text.length - right.evidence_text.length ||
            left.triple_id.localeCompare(right.triple_id),
        )[0];
      if (!sample) return "";
      const printed = sample.printed_page_label
        ? `；印刷页 ${sample.printed_page_label}`
        : "";
      return `### ${sample.doc_id}：PDF p. ${sample.pdf_page_number}${printed}

- 三元组：${sample.head} — \`${sample.relation}\` → ${sample.tail}
- 来源：[原始PDF](${sample.source_url})
- 原文连续跨度：

\`\`\`text
${sample.evidence_text}
\`\`\``;
    })
    .filter(Boolean)
    .join("\n\n");

  return `# qwen3.7-max 船舶机舱泵系三元组试抽取报告

## 运行边界

- 模型：\`${config.model}\`
- 提示词版本：\`${config.prompt_version}\`
- 后处理版本：\`${config.postprocessor_version}\`
- 文档划分：\`${split.version}\`
- 数据属性：Silver候选，未进行完整人工标注
- API密钥：未写入任何配置、结果或日志
- 运行状态：${runManifest.complete ? "已完成全部选定页面" : "部分完成，可安全续跑"}
- 百炼用途：仅用于离线Silver候选数据构建；其云端API时延不作为低算力在线检索时延指标

## 页面选择

| 文档 | 划分 | 解析页数 | 本轮选定PDF页 |
|---|---|---:|---|
${selectionRows}

试抽取页先由词法故障线索、故障表结构和检查/维护提示词筛选，再冻结为4份代表文档各1页，并逐页渲染核对版面。词法命中只用于选页，不直接构成三元组或Silver标签。

## 抽取结果

- 选定页面：${runManifest.selected_pages}
- 已完成API页面：${runManifest.completed_pages}
- API失败页面：${runManifest.failed_pages}
- 待运行页面：${runManifest.remaining_pages}
- 候选三元组：${coverage.total_candidate_triples}
- 模型原始提议：${runManifest.raw_model_proposals}
- 候选阈值前拒绝：${runManifest.rejected_before_candidate}
- 去重移除：${runManifest.duplicates_removed}
- Schema及原文跨度校验通过：${coverage.schema_and_evidence_verified_candidates}
- 高置信Silver候选：${coverage.high_confidence_silver_candidates}
- 待复核候选：${coverage.review_pending_candidates}
- 二次AI语义抽样审计明确降审：${coverage.semantic_audit_overrides_requiring_review}
- 构建集高置信Silver候选：${coverage.build_set_high_confidence_silver_candidates}
- 开发集候选（不计入覆盖门槛）：${coverage.development_candidates_excluded_from_gate}
- 未映射到故障类的高置信候选：${coverage.unmapped_high_confidence_candidates}
- 离线API调用时延：均值 ${runManifest.api_latency_ms.mean} ms，中位数 ${runManifest.api_latency_ms.median} ms，最大 ${runManifest.api_latency_ms.max} ms

### 逐文档抽取漏斗

| 文档 | 原始提议 | 保留候选 | 高置信Silver候选 | 待复核 | 阈值前拒绝 | 模型页级警告 | 保留率 |
|---|---:|---:|---:|---:|---:|---:|---:|
${funnelRows}

拒绝原因分布：\`${JSON.stringify(runManifest.rejection_reason_counts)}\`。模型返回的页级警告已原样保存在运行清单和逐条候选中，只用于质量审计，不直接替代本地校验。MP008开发页只保留 ${runManifest.per_document_extraction_stats.find((item) => item.doc_id === "MP008")?.retained_candidates ?? 0}/${runManifest.per_document_extraction_stats.find((item) => item.doc_id === "MP008")?.raw_model_proposals ?? 0} 条原始提议，说明当前跨厂商表格抽取规则尚未稳定；其结果只用于暴露迁移问题，不能据此声称已通过跨厂商验证。

## 构建集试抽取覆盖

| 故障类 | 症状 | 原因/机理 | 检查/维修 | 文档数 | 来源族数 | 试抽取门槛 |
|---|---:|---:|---:|---:|---:|---|
${coverageRows}

计数按节点类型和“文档-PDF页-规范化实体”去重，MP008开发集仅用于跨厂商迁移检查，不补足构建集门槛。即使某类在试抽取中显示“通过”，仍须在完整构建集上按去重后的“文档-页码-原文主张”重新执行正式覆盖门槛，未通过前不得批量构图。

## 四文档抽样结果

${sampleSections}
`;
}

function splitForDoc(split, docId) {
  if (split.build_train_doc_ids.includes(docId)) return "build_train";
  if (split.development_doc_ids.includes(docId)) return "development";
  if (split.held_out_test_doc_ids.includes(docId)) return "held_out_test";
  return "unassigned";
}

export async function runPilotExtraction(options = {}) {
  const projectRoot = path.resolve(options.projectRoot ?? ".");
  const configPath = path.join(
    projectRoot,
    "configs",
    "triple_extraction_qwen3_7_max_pilot_v1.json",
  );
  const splitPath = path.join(
    projectRoot,
    "configs",
    "document_split_marine_pump_pilot_v1.json",
  );
  const manifestPath = path.join(
    projectRoot,
    "data",
    "source_docs",
    "marine_pump",
    "source_manifest.csv",
  );
  const schemaPath = path.join(
    projectRoot,
    "data",
    "kg",
    "marine_pump",
    "schema",
    "provenance_schema_v1.json",
  );
  const config = await readJson(configPath);
  const split = await readJson(splitPath);
  const provenanceSchema = await readJson(schemaPath);
  const resolvedBaseUrl = options.baseUrl ?? config.base_url;
  const requestConfigSha256 = sha256(
    JSON.stringify({
      model: config.model,
      base_url: resolvedBaseUrl,
      enable_thinking: config.enable_thinking,
      response_format: config.response_format,
      temperature: config.temperature,
      system_prompt_sha256: sha256(SYSTEM_PROMPT),
    }),
  );
  if (
    [...NODE_TYPES].some(
      (nodeType) => !provenanceSchema.node_types.includes(nodeType),
    ) ||
    provenanceSchema.node_types.some((nodeType) => !NODE_TYPES.has(nodeType)) ||
    [...RELATIONS].some(
      (relation) => !provenanceSchema.relations.includes(relation),
    ) ||
    provenanceSchema.relations.some((relation) => !RELATIONS.has(relation))
  ) {
    throw new Error(
      "Prompt node/relation enums do not match provenance_schema_v1.json",
    );
  }
  const manifest = parseCsv(await readFile(manifestPath, "utf8"));
  const manifestById = new Map(manifest.map((item) => [item.doc_id, item]));
  const pdftotextPath = options.pdftotextPath ?? "pdftotext";
  const parsedRoot = path.join(
    projectRoot,
    "data",
    "interim",
    "parsed_pages",
    "representative_pilot_v1",
  );
  const candidateRoot = path.join(
    projectRoot,
    "data",
    "interim",
    "candidate_triples",
    config.run_id,
  );
  const experimentRoot = path.join(
    projectRoot,
    "results",
    "experiments",
    config.run_id,
  );
  const benchmarkRoot = path.join(
    projectRoot,
    "results",
    "benchmarks",
    config.run_id,
  );
  const rawRoot = path.join(experimentRoot, "raw_responses");
  await Promise.all([
    mkdir(parsedRoot, { recursive: true }),
    mkdir(candidateRoot, { recursive: true }),
    mkdir(rawRoot, { recursive: true }),
    mkdir(benchmarkRoot, { recursive: true }),
  ]);

  const selection = {
    selection_version: "representative_page_selection_v1",
    created_at: new Date().toISOString(),
    config_version: config.version,
    split_version: split.version,
    method: Array.isArray(config.trial_page_keys)
      ? "Frozen four-document representative-page pilot plan, chosen after lexical/table screening and visual layout review."
      : "Coverage-prioritized lexical and table-cue screening; screening is not a label.",
    documents: [],
  };
  const selectedPages = [];

  for (const docId of config.representative_doc_ids) {
    const item = manifestById.get(docId);
    if (!item) {
      throw new Error(`Document ${docId} missing from source manifest`);
    }
    const pdfPath = path.join(
      projectRoot,
      "data",
      "source_docs",
      "marine_pump",
      "raw",
      item.file_name,
    );
    const pages = await extractPdfPages({
      pdfPath,
      pdftotextPath,
      manifestItem: item,
      projectRoot,
    });
    await writeJsonl(path.join(parsedRoot, `${docId}.pages.jsonl`), pages);
    const trialPageKeys = new Set(config.trial_page_keys ?? []);
    const selected = trialPageKeys.size
      ? pages
          .map(annotatePage)
          .filter((page) =>
            trialPageKeys.has(`${page.doc_id}:${page.pdf_page_number}`),
          )
      : selectPages(
          pages,
          config.max_pages_per_document,
          config.minimum_page_characters,
        );
    selectedPages.push(...selected);
    selection.documents.push({
      doc_id: docId,
      title: item.title,
      publisher: item.publisher,
      split: splitForDoc(split, docId),
      parsed_pages: pages.length,
      manifest_pages: Number(item.pages),
      page_count_matches_manifest: pages.length === Number(item.pages),
      selected_pages: selected.map((page) => ({
        pdf_page_number: page.pdf_page_number,
        page_or_section: page.page_or_section,
        text_sha256: page.text_sha256,
        score: page.selection.score,
        fault_hits: page.selection.fault_hits,
        cue_count: page.selection.cue_count,
        table_cue: page.selection.table_cue,
      })),
    });
  }
  if (
    Array.isArray(config.trial_page_keys) &&
    selectedPages.length !== new Set(config.trial_page_keys).size
  ) {
    const found = new Set(
      selectedPages.map((page) => `${page.doc_id}:${page.pdf_page_number}`),
    );
    const missing = config.trial_page_keys.filter((pageKey) => !found.has(pageKey));
    throw new Error(`Configured trial pages were not found: ${missing.join(", ")}`);
  }
  const requestPriority = new Map(
    (config.request_priority ?? []).map((pageKey, index) => [pageKey, index]),
  );
  selectedPages.sort((left, right) => {
    const leftKey = `${left.doc_id}:${left.pdf_page_number}`;
    const rightKey = `${right.doc_id}:${right.pdf_page_number}`;
    const leftPriority =
      requestPriority.get(leftKey) ?? Number.MAX_SAFE_INTEGER;
    const rightPriority =
      requestPriority.get(rightKey) ?? Number.MAX_SAFE_INTEGER;
    if (leftPriority !== rightPriority) return leftPriority - rightPriority;
    const docOrder =
      config.representative_doc_ids.indexOf(left.doc_id) -
      config.representative_doc_ids.indexOf(right.doc_id);
    return docOrder || left.pdf_page_number - right.pdf_page_number;
  });
  await writeJson(path.join(experimentRoot, "page_selection.json"), selection);

  if (options.dryRun) {
    return {
      dry_run: true,
      run_id: config.run_id,
      parsed_documents: selection.documents.length,
      parsed_pages: selection.documents.reduce(
        (sum, item) => sum + item.parsed_pages,
        0,
      ),
      selected_pages: selectedPages.length,
      selection_file: path.join(experimentRoot, "page_selection.json"),
      selected_by_document: Object.fromEntries(
        selection.documents.map((document) => [
          document.doc_id,
          document.selected_pages.map((page) => page.pdf_page_number),
        ]),
      ),
    };
  }

  const apiKey = options.apiKey;
  if (!apiKey) {
    throw new Error(
      "No API key supplied. Pass apiKey in memory or set DASHSCOPE_API_KEY in the CLI runner.",
    );
  }
  const maxNewRequests = Number.isFinite(options.maxNewRequests)
    ? Math.max(0, Number(options.maxNewRequests))
    : Number.POSITIVE_INFINITY;
  let newRequests = 0;
  const pageRecords = [];
  const failures = [];

  for (const page of selectedPages) {
    const rawPath = path.join(
      rawRoot,
      `${page.doc_id}_p${String(page.pdf_page_number).padStart(4, "0")}.json`,
    );
    let apiRecord = null;
    if (await pathExists(rawPath)) {
      const cached = await readJson(rawPath);
      const expectedPromptSha256 = sha256(
        `${SYSTEM_PROMPT}\n${buildUserPrompt(page)}`,
      );
      const cachePromptMatches =
        cached.api_record?.prompt_sha256 === expectedPromptSha256;
      const cacheRequestMatches =
        cached.request_config_sha256 === requestConfigSha256 ||
        !cached.request_config_sha256;
      if (
        cached.prompt_version === config.prompt_version &&
        cached.model_requested === config.model &&
        cached.page_text_sha256 === page.text_sha256 &&
        cachePromptMatches &&
        cacheRequestMatches &&
        cached.status === "success"
      ) {
        apiRecord = cached.api_record;
        if (!cached.request_config_sha256) {
          await writeJson(rawPath, {
            ...cached,
            request_config_sha256: requestConfigSha256,
          });
        }
      }
    }
    if (!apiRecord && newRequests >= maxNewRequests) {
      continue;
    }
    if (!apiRecord) {
      try {
        apiRecord = await callBailian({
          apiKey,
          baseUrl: resolvedBaseUrl,
          model: config.model,
          enableThinking: config.enable_thinking,
          responseFormat: config.response_format,
          temperature: config.temperature,
          timeoutSeconds: config.request_timeout_seconds,
          maxRetries: config.max_retries,
          page,
        });
        newRequests += 1;
        await writeJson(rawPath, {
          status: "success",
          prompt_version: config.prompt_version,
          model_requested: config.model,
          request_config_sha256: requestConfigSha256,
          page_text_sha256: page.text_sha256,
          doc_id: page.doc_id,
          pdf_page_number: page.pdf_page_number,
          api_record: apiRecord,
        });
      } catch (error) {
        newRequests += 1;
        const failure = {
          status: "failed",
          prompt_version: config.prompt_version,
          model_requested: config.model,
          request_config_sha256: requestConfigSha256,
          page_text_sha256: page.text_sha256,
          doc_id: page.doc_id,
          pdf_page_number: page.pdf_page_number,
          error: redactSecrets(error?.message ?? error),
        };
        failures.push(failure);
        await writeJson(rawPath, failure);
        continue;
      }
    }
    pageRecords.push({ page, apiRecord });
  }

  const normalizedProposals = [];
  const triples = [];
  for (const { page, apiRecord } of pageRecords) {
    const item = manifestById.get(page.doc_id);
    const modelTriples = Array.isArray(apiRecord.response_json?.triples)
      ? apiRecord.response_json.triples
      : [];
    for (const modelTriple of modelTriples) {
      const normalized = normalizeTriple({
        modelTriple,
        page,
        apiRecord,
        config,
        manifestItem: item,
        documentSplit: splitForDoc(split, page.doc_id),
        relationTypeConstraints: provenanceSchema.relation_type_constraints,
      });
      normalizedProposals.push(normalized);
      if (normalized.triple_confidence >= config.minimum_candidate_confidence) {
        triples.push(normalized);
      }
    }
  }
  const deduplicated = [
    ...new Map(triples.map((triple) => [triple.triple_id, triple])).values(),
  ].sort((left, right) =>
    `${left.doc_id}:${String(left.pdf_page_number).padStart(4, "0")}:${left.triple_id}`.localeCompare(
      `${right.doc_id}:${String(right.pdf_page_number).padStart(4, "0")}:${right.triple_id}`,
    ),
  );
  await writeJsonl(
    path.join(candidateRoot, "candidate_triples.jsonl"),
    deduplicated,
  );
  const rejectedProposals = normalizedProposals.filter(
    (triple) =>
      triple.triple_confidence < config.minimum_candidate_confidence,
  );
  await writeJsonl(
    path.join(candidateRoot, "rejected_proposals.jsonl"),
    rejectedProposals,
  );
  const duplicateCount = triples.length - deduplicated.length;
  const rejectionReasonCounts = {};
  for (const proposal of rejectedProposals) {
    for (const reason of proposal.rejection_reasons) {
      rejectionReasonCounts[reason] =
        Number(rejectionReasonCounts[reason] ?? 0) + 1;
    }
  }
  const perDocumentExtractionStats = config.representative_doc_ids.map(
    (docId) => {
      const raw = normalizedProposals.filter(
        (proposal) => proposal.doc_id === docId,
      );
      const retained = deduplicated.filter(
        (proposal) => proposal.doc_id === docId,
      );
      const highConfidence = retained.filter(
        (proposal) => proposal.validation_status === "silver_candidate",
      );
      const pageWarningCount =
        pageRecords.find((record) => record.page.doc_id === docId)?.apiRecord
          .response_json?.warnings?.length ?? 0;
      return {
        doc_id: docId,
        document_split: splitForDoc(split, docId),
        raw_model_proposals: raw.length,
        retained_candidates: retained.length,
        high_confidence_silver_candidates: highConfidence.length,
        review_pending_candidates: retained.length - highConfidence.length,
        rejected_before_candidate: raw.filter(
          (proposal) =>
            proposal.triple_confidence < config.minimum_candidate_confidence,
        ).length,
        model_page_warning_count: pageWarningCount,
        retention_rate_percent: raw.length
          ? Number(((retained.length / raw.length) * 100).toFixed(1))
          : 0,
      };
    },
  );
  const modelPageWarningsByDocument = Object.fromEntries(
    pageRecords.map((record) => [
      record.page.doc_id,
      Array.isArray(record.apiRecord.response_json?.warnings)
        ? record.apiRecord.response_json.warnings.map((warning) =>
            redactSecrets(String(warning)),
          )
        : [],
    ]),
  );

  const allRawStatuses = [];
  for (const page of selectedPages) {
    const rawPath = path.join(
      rawRoot,
      `${page.doc_id}_p${String(page.pdf_page_number).padStart(4, "0")}.json`,
    );
    if (await pathExists(rawPath)) {
      const raw = await readJson(rawPath);
      allRawStatuses.push({
        doc_id: page.doc_id,
        pdf_page_number: page.pdf_page_number,
        status: raw.status,
      });
    }
  }
  const completedPages = allRawStatuses.filter(
    (record) => record.status === "success",
  ).length;
  const failedPages = allRawStatuses.filter(
    (record) => record.status === "failed",
  ).length;
  const remainingPages = selectedPages.length - completedPages;
  const usage = pageRecords.reduce(
    (accumulator, record) => {
      accumulator.prompt_tokens += Number(
        record.apiRecord.usage?.prompt_tokens ?? 0,
      );
      accumulator.completion_tokens += Number(
        record.apiRecord.usage?.completion_tokens ?? 0,
      );
      accumulator.total_tokens += Number(record.apiRecord.usage?.total_tokens ?? 0);
      return accumulator;
    },
    { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  );
  const latencies = pageRecords
    .map((record) => Number(record.apiRecord.latency_ms ?? 0))
    .filter((value) => Number.isFinite(value) && value >= 0)
    .sort((left, right) => left - right);
  const latencyAt = (quantile) =>
    latencies.length
      ? latencies[
          Math.min(
            latencies.length - 1,
            Math.max(0, Math.ceil(quantile * latencies.length) - 1),
          )
        ]
      : 0;
  const latencyStats = {
    count: latencies.length,
    min: latencies[0] ?? 0,
    median: latencyAt(0.5),
    p95: latencyAt(0.95),
    max: latencies.at(-1) ?? 0,
    mean: latencies.length
      ? Math.round(
          latencies.reduce((sum, value) => sum + value, 0) / latencies.length,
        )
      : 0,
  };
  const artifactPaths = {
    extraction_script: path.join(
      projectRoot,
      "src",
      "research_point_1_graph_evidence",
      "stage02_triple_extraction",
      "bailian_qwen_pilot.mjs",
    ),
    cli_runner: path.join(projectRoot, "scripts", "run_bailian_triple_pilot.mjs"),
    extraction_config: configPath,
    document_split: splitPath,
    provenance_schema: schemaPath,
    source_manifest: manifestPath,
  };
  const artifactSha256 = {};
  for (const [name, filePath] of Object.entries(artifactPaths)) {
    artifactSha256[name] = sha256(await readFile(filePath));
  }
  const runtimeVersions = {
    node:
      globalThis.process?.version ??
      (await readToolVersion(options.nodePath ?? "node", ["--version"])),
    node_executable:
      globalThis.process?.execPath ?? options.nodePath ?? null,
    pdftotext: await readToolVersion(pdftotextPath, ["-v"]),
  };
  const runManifest = {
    run_id: config.run_id,
    updated_at: new Date().toISOString(),
    complete: completedPages === selectedPages.length,
    config_version: config.version,
    split_version: split.version,
    schema_version: provenanceSchema.schema_version,
    model_requested: config.model,
    base_url: resolvedBaseUrl,
    api_protocol: config.api_protocol,
    prompt_version: config.prompt_version,
    postprocessor_version: config.postprocessor_version,
    system_prompt_sha256: sha256(SYSTEM_PROMPT),
    request_config_sha256: requestConfigSha256,
    artifact_sha256: artifactSha256,
    runtime_versions: runtimeVersions,
    api_key_persisted: false,
    selected_pages: selectedPages.length,
    completed_pages: completedPages,
    failed_pages: failedPages,
    remaining_pages: Math.max(0, remainingPages),
    new_requests_this_invocation: newRequests,
    candidate_triples: deduplicated.length,
    raw_model_proposals: normalizedProposals.length,
    candidate_proposals_before_dedup: triples.length,
    rejected_before_candidate: rejectedProposals.length,
    duplicates_removed: duplicateCount,
    rejection_reason_counts: rejectionReasonCounts,
    per_document_extraction_stats: perDocumentExtractionStats,
    model_page_warnings_by_document: modelPageWarningsByDocument,
    usage,
    api_latency_ms: latencyStats,
    models_returned: [
      ...new Set(pageRecords.map((record) => record.apiRecord.model)),
    ],
    failures,
    outputs: {
      parsed_pages: path.relative(projectRoot, parsedRoot).split(path.sep).join("/"),
      page_selection: path
        .relative(projectRoot, path.join(experimentRoot, "page_selection.json"))
        .split(path.sep)
        .join("/"),
      raw_responses: path.relative(projectRoot, rawRoot).split(path.sep).join("/"),
      candidate_triples: path
        .relative(projectRoot, path.join(candidateRoot, "candidate_triples.jsonl"))
        .split(path.sep)
        .join("/"),
      rejected_proposals: path
        .relative(projectRoot, path.join(candidateRoot, "rejected_proposals.jsonl"))
        .split(path.sep)
        .join("/"),
    },
  };
  await writeJson(path.join(experimentRoot, "run_manifest.json"), runManifest);
  const coverage = buildCoverage(deduplicated, config, {
    raw_model_proposals: normalizedProposals.length,
    retained_candidates: deduplicated.length,
    rejected_before_candidate: rejectedProposals.length,
    duplicates_removed: duplicateCount,
    rejection_reason_counts: rejectionReasonCounts,
    per_document: perDocumentExtractionStats,
  });
  await writeJson(path.join(benchmarkRoot, "pilot_coverage_report.json"), coverage);
  const report = buildMarkdownReport({
    config,
    split,
    selection,
    runManifest,
    coverage,
    triples: deduplicated,
  });
  await writeFile(path.join(benchmarkRoot, "pilot_extraction_report.md"), report, "utf8");

  return {
    run_id: config.run_id,
    complete: runManifest.complete,
    selected_pages: runManifest.selected_pages,
    completed_pages: runManifest.completed_pages,
    failed_pages: runManifest.failed_pages,
    remaining_pages: runManifest.remaining_pages,
    new_requests: runManifest.new_requests_this_invocation,
    candidate_triples: runManifest.candidate_triples,
    high_confidence_silver_candidates:
      coverage.high_confidence_silver_candidates,
    fault_classes_passing_pilot_gate:
      coverage.fault_classes_passing_pilot_gate,
    usage: runManifest.usage,
    manifest_file: path.join(experimentRoot, "run_manifest.json"),
    report_file: path.join(benchmarkRoot, "pilot_extraction_report.md"),
  };
}

export const promptMetadata = {
  promptVersion: "marine_pump_triple_prompt_v2",
  systemPromptSha256: sha256(SYSTEM_PROMPT),
};
