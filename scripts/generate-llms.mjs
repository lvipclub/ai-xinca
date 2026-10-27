#!/usr/bin/env node
// generate-llms.mjs — regenerate llms.txt from the built dist/ tree.
//
// Produces an llmstxt.org-conformant file (https://llmstxt.org):
//   # H1 — site + tagline
//   > one-paragraph blockquote summary
//   ## Sections with '- [Title](URL): description' entries
//
// Guarantees the file contains ONLY live, canonical URLs (no dead links,
// trailing slashes everywhere). Alias/redirect families are excluded:
//   /faq/* and /qa/* (meta-refresh aliases of /kb/q/), /admin/
// plus the five shadowed /kb/ pages that have a canonical elsewhere
// (the same five excluded from the sitemap).
//
// Usage: node scripts/generate-llms.mjs [distDir] [outFile]
//   default distDir = dist/ , outFile = dist/llms.txt
import fs from "node:fs";
import path from "node:path";

const distDir = path.resolve(process.argv[2] ?? "dist");
const outFile = process.argv[3] ?? path.join(distDir, "llms.txt");

const SITE = "help.xinca.com";
const TITLE_SUFFIX = ` | ${SITE}`;

const SKIP_DIRS = new Set([
  "_astro", "assets", "avatars", "articles", "images", "hvac", "admin",
  "carousel", "infocard",
]);
// Path families to drop: /faq/* and /qa/* are meta-refresh aliases of /kb/q/,
// /admin/ is non-content, and the five shadowed /kb/ pages (kept out of the
// sitemap too — see astro.config.mjs).
const SHADOWED_KB_SLUGS = new Set([
  "ai-building-energy-management",
  "data-center-energy-efficiency",
  "data-center-glycol-cooling",
  "energy-efficiency-building-codes-asia",
  "iaq-monitoring-commercial-buildings",
]);
const SKIP_PREFIXES = ["/faq/", "/qa/", "/admin/"];
const SKIP_FILES = new Set([
  "404.html", "index.html", "robots.txt", "llms.txt",
  "favicon.ico", "favicon.png", "favicon.svg", "logo.png", "rss.xml",
]);

const SECTION_TITLES = [
  ["/a/", "## Articles"],
  ["/kb/q/", "## Knowledge Base Q&A"],
  ["/kb/", "## Knowledge Base Categories"],
  ["/x/", "## X Post Archive"],
  ["/about/", "## About"],
  ["/", "## Hub Pages"],
];

function walk(dir, rel, acc) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const relPath = rel ? `${rel}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      walk(path.join(dir, entry.name), relPath, acc);
    } else if (entry.isFile() && entry.name === "index.html") {
      acc.push(relPath.slice(0, -"index.html".length));
    }
  }
}

function toUrl(relDir) {
  return `https://${SITE}/${relDir}`;
}

function kbqNum(d) {
  const m = d.match(/(\d+)\/$/);
  return m ? Number(m[1]) : Infinity;
}

function decodeEntities(s) {
  return s
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&apos;/g, "'");
}

// Extract <title> and meta description from a dist page's index.html.
function extractMeta(htmlPath) {
  const html = fs.readFileSync(htmlPath, "utf8");
  const t = html.match(/<title>([^<]*)<\/title>/i);
  let title = t ? decodeEntities(t[1].trim()) : "";
  if (title.endsWith(TITLE_SUFFIX)) title = title.slice(0, -TITLE_SUFFIX.length);
  const d = html.match(/<meta\s+name="description"\s+content="([^"]*)"/i);
  let desc = d ? decodeEntities(d[1].trim()) : "";
  desc = desc.replace(/\s+/g, " ");
  return { title, desc };
}

const pageDirs = [];
walk(distDir, "", pageDirs);

// Only keep pages (dirs with index.html), bucketed by section order.
const buckets = new Map(SECTION_TITLES.map(([p]) => [p, []]));
for (const d of pageDirs) {
  const key = "/" + d;
  if (SKIP_PREFIXES.some((p) => key.startsWith(p))) continue;
  // Shadowed /kb/ pages: skip only the exact subdirs, keep the rest of /kb/.
  if (d.startsWith("kb/") && SHADOWED_KB_SLUGS.has(d.replace(/\/$/, "").split("/").pop())) continue;
  let placed = false;
  for (const [prefix, list] of buckets) {
    if (prefix === "/") {
      if (key === "/") { list.push(d); placed = true; break; }
      continue;
    }
    if (key.startsWith(prefix) && key !== prefix.slice(0, -1)) {
      list.push(d);
      placed = true;
      break;
    }
  }
  if (!placed) buckets.get("/").push(d); // fallback: hubs section
}

// /kb/q/ entries are numbered dirs (1, 2, 3, ... 60): sort numerically.
buckets.get("/kb/q/").sort((a, b) => kbqNum(a) - kbqNum(b));

const SUMMARY =
  "help.xinca.com is a practical knowledge base for HVAC controls, IoT building " +
  "automation and commercial energy management — 50 Q&A articles answering real " +
  "day-to-day BMS engineering questions (dampers, IAQ, sensors, valves, AI tools) " +
  "plus longer-form guides on data center cooling, energy codes and controls " +
  "system design.";

const lines = [
  `# ${SITE} — HVAC Controls Engineering Knowledge Hub`,
  "",
  `> ${SUMMARY}`,
  "",
];
for (const dirList of buckets.values()) dirList.sort((a, b) => a.localeCompare(b));
// restore numeric order for /kb/q/ after the localeCompare above
buckets.get("/kb/q/").sort((a, b) => kbqNum(a) - kbqNum(b));
for (const [prefix, title] of SECTION_TITLES) {
  const dirs = buckets.get(prefix);
  if (!dirs.length) continue;
  lines.push(title, "");
  for (const d of dirs) {
    const { title: t, desc } = extractMeta(path.join(distDir, d, "index.html"));
    lines.push(`- [${t}](${toUrl(d)}): ${desc}`);
  }
  lines.push("");
}

fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, lines.join("\n"));
const entryCount = lines.filter((l) => l.startsWith("- [")).length;
console.log(`llms.txt written: ${outFile} (${pageDirs.length} pages scanned, ` +
            `${entryCount} entries)`);
