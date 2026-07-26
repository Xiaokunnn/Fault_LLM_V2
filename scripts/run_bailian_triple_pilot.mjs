import path from "node:path";
import { fileURLToPath } from "node:url";

import { runPilotExtraction } from "../src/research_point_1_graph_evidence/stage02_triple_extraction/bailian_qwen_pilot.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const dryRun = process.argv.includes("--dry-run");
const apiKey = process.env.DASHSCOPE_API_KEY;

if (!dryRun && !apiKey) {
  throw new Error(
    "Set DASHSCOPE_API_KEY in the current process environment. Never place the key in a repository file.",
  );
}

const summary = await runPilotExtraction({
  projectRoot,
  apiKey,
  dryRun,
});

console.log(JSON.stringify(summary, null, 2));
