// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://help.xinca.com',
  output: 'static',
  trailingSlash: 'always',
  build: {
    assets: 'assets'
  },
  integrations: [
    tailwind(),
    sitemap({
      // /admin is a pipeline dashboard; /qa and /faq are redirect stubs; the
      // five /kb/ slugs below are shadowed by other canonical pages — keep all
      // of them out of the public sitemap
      filter: (page) =>
        !page.includes('/admin') &&
        !page.includes('/qa/') &&
        !page.includes('/faq/') &&
        ![
          'ai-building-energy-management',
          'data-center-energy-efficiency',
          'data-center-glycol-cooling',
          'energy-efficiency-building-codes-asia',
          'iaq-monitoring-commercial-buildings',
        ].some((slug) => page.includes(`/kb/${slug}/`)),
    }),
  ],
});
