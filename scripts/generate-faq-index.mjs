#!/usr/bin/env node
/**
 * generate-faq-index.mjs
 *
 * Reads all FAQ markdown files from src/content/faq/**\/*.md,
 * parses frontmatter, extracts a description from the first paragraph,
 * and writes a JSON index to src/data/faq-index.json.
 *
 * This runs automatically before `astro build` and `astro dev` via the
 * prebuild/predev scripts. When new .md files are added to
 * src/content/faq/, the index updates on the next build — no manual
 * steps needed.
 */

import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync } from 'node:fs';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const FAQ_DIR = join(ROOT, 'src', 'content', 'faq');
const CATEGORIES_PATH = join(FAQ_DIR, 'categories.json');
const OUTPUT_PATH = join(ROOT, 'src', 'data', 'faq-index.json');

/**
 * Recursively collect all .md files in a directory.
 */
function collectMdFiles(dir) {
  const results = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMdFiles(fullPath));
    } else if (entry.name.endsWith('.md')) {
      results.push(fullPath);
    }
  }
  return results;
}

/**
 * Extract frontmatter and first paragraph from a markdown file.
 * Returns { title, category, description, slug }.
 */
function parseFaqFile(filePath) {
  const raw = readFileSync(filePath, 'utf-8');
  const relativePath = relative(FAQ_DIR, filePath);

  // Extract frontmatter between --- markers
  const fmMatch = raw.match(/^---\n([\s\S]*?)\n---/);
  const fm = {};
  if (fmMatch) {
    const lines = fmMatch[1].split('\n');
    for (const line of lines) {
      const kv = line.match(/^(\w+):\s*['"]?(.+?)['"]?\s*$/);
      if (kv) fm[kv[1]] = kv[2];
    }
  }

  // Extract first meaningful paragraph after frontmatter
  const afterFM = raw.replace(/^---\n[\s\S]*?\n---\n*/, '').trim();
  // Skip heading lines (start with #) and blank lines, grab first paragraph
  const paragraphs = afterFM.split(/\n\s*\n/).filter(p => {
    const trimmed = p.trim();
    return trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('---');
  });
  const description = paragraphs[0]
    ? paragraphs[0].replace(/\n/g, ' ').replace(/\s+/g, ' ').trim().substring(0, 300)
    : '';

  // Generate slug: category/filename-without-ext
  const categoryDir = relativePath.split('/')[0]; // e.g. 'air', 'controls', 'water'
  const fileName = relativePath.split('/').pop().replace(/\.md$/, '');
  const slug = `${categoryDir}/${fileName}`;

  return {
    title: fm.title || fileName.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    category: fm.category || categoryDir,
    description,
    slug,
  };
}

// Load category metadata (names, descriptions)
let categoryMeta = {};
try {
  const catRaw = readFileSync(CATEGORIES_PATH, 'utf-8');
  const catData = JSON.parse(catRaw);
  categoryMeta = catData.categories || {};
} catch {
  console.warn('⚠ Could not read categories.json; using raw category slugs');
}

// Main
const mdFiles = collectMdFiles(FAQ_DIR);
console.log(`Found ${mdFiles.length} FAQ .md files`);

const entries = mdFiles.map(parseFaqFile);

// Sort entries deterministically by slug
entries.sort((a, b) => a.slug.localeCompare(b.slug));

// Compute actual per-category counts from entries
const counts = {};
for (const e of entries) {
  counts[e.category] = (counts[e.category] || 0) + 1;
}

// Build categories with computed counts, preserving metadata order
const categories = {};
for (const [slug, meta] of Object.entries(categoryMeta)) {
  categories[slug] = {
    name: meta.name,
    description: meta.description,
    count: counts[slug] || 0,
  };
}
// Include any categories present in files but missing from categories.json
for (const slug of Object.keys(counts).sort()) {
  if (!categories[slug]) {
    categories[slug] = {
      name: slug.charAt(0).toUpperCase() + slug.slice(1),
      description: `FAQ entries about ${slug}`,
      count: counts[slug],
    };
  }
}

const index = {
  generated: new Date().toISOString(),
  total: entries.length,
  categories,
  entries,
};

// Ensure output directory exists
mkdirSync(dirname(OUTPUT_PATH), { recursive: true });

// JSON.stringify with </script> escape to prevent data-island breakout
const json = JSON.stringify(index).replace(/<\//g, '<\\/');
writeFileSync(OUTPUT_PATH, json + '\n');
console.log(`✅ Wrote FAQ index (${entries.length} entries) to ${relative(ROOT, OUTPUT_PATH)}`);
