// rss.xml.ts — RSS 2.0 feed of help.xinca.com articles.
// Source of truth: each article's own frontmatter consts (pageTitle / pageDescription)
// and JSON-LD datePublished — NOT src/data/articles.json (homepage leaderboard data,
// which can lag new articles). A new article file in src/pages/a/ automatically
// appears here on the next build.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const SITE = 'https://help.xinca.com';

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const unesc = (s: string) => s.replace(/\\"/g, '"').replace(/\\\\/g, '\\');

type Item = { slug: string; title: string; description: string; date: string };

function loadArticles(): Item[] {
  const dir = join(process.cwd(), 'src', 'pages', 'a');
  const items: Item[] = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith('.astro') || f === 'index.astro') continue;
    const src = readFileSync(join(dir, f), 'utf-8');
    const title = src.match(/const pageTitle = "((?:\\.|[^"\\])*)";/)?.[1];
    const description = src.match(/const pageDescription = "((?:\\.|[^"\\])*)";/)?.[1] ?? '';
    const date = src.match(/"datePublished":\s*"(\d{4}-\d{2}-\d{2})"/)?.[1];
    const slug = f.replace(/\.astro$/, '');
    if (!title || !date) {
      console.warn(`rss.xml: skipping ${f} (missing ${!title ? 'pageTitle' : 'datePublished'})`);
      continue;
    }
    items.push({ slug, title, description: unesc(description), date });
  }
  return items.sort((a, b) => b.date.localeCompare(a.date));
}

export const GET = async () => {
  const items = loadArticles()
    .map(
      (a) => `    <item>
      <title>${esc(a.title)}</title>
      <link>${SITE}/a/${a.slug}/</link>
      <guid isPermaLink="false">${a.slug}</guid>
      <pubDate>${new Date(a.date + 'T09:00:00+08:00').toUTCString()}</pubDate>
      <description><![CDATA[${a.description}]]></description>
    </item>`
    )
    .join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>help.xinca.com — HVAC Knowledge Base Articles</title>
    <link>${SITE}/</link>
    <description>Technical articles for specifiers, engineers, and building services professionals — building controls, air-side, water-side, IAQ, and energy compliance.</description>
    <language>en-au</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
