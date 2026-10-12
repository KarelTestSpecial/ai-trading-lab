// Copies the committed paper journal into the Vite public dir so the built site
// ships the exact same tamper-evident data that is in git.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "../../journal/decisions.jsonl");
const outDir = resolve(here, "../public");
const target = resolve(outDir, "decisions.jsonl");

mkdirSync(outDir, { recursive: true });
const data = existsSync(source) ? readFileSync(source, "utf8") : "";
writeFileSync(target, data);
const records = data.trim() ? data.trim().split("\n").length : 0;
console.log(`copy-journal: ${records} record(s) -> ${target}`);
