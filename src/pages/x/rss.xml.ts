// x/rss.xml.ts — RSS feed of X posts (automated posting source for fleet accounts)
import { readFileSync } from 'node:fs';

const xPosts = JSON.parse(
  readFileSync(new URL('./src/data/x-posts.json', `file://${process.cwd()}/`), 'utf-8')
);

const SITE = 'https://ai.xinca.com';

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const fmtDate = (d: string) => new Date(d + 'T00:00:00+08:00').toUTCString();

export const GET = async () => {
  const items = xPosts
    .map(
      (p) => `    <item>
      <title>${esc(p.title)}</title>
      <link>${SITE}/x/${p.slug}/</link>
      <guid isPermaLink="false">${p.slug}</guid>
      <pubDate>${fmtDate(p.date)}</pubDate>
      <category>${esc(p.account)}</category>
      <description><![CDATA[${p.text}]]></description>
    </item>`
    )
    .join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>ai.xinca.com — X Posts</title>
    <link>${SITE}/x/</link>
    <description>Short-form X posts distilled from ai.xinca.com articles. Per-account category tag identifies the posting account.</description>
    <language>en</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
