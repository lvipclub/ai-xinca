// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://help.xinca.com',
  output: 'static',
  build: {
    assets: 'assets'
  },
  integrations: [
    tailwind(),
    sitemap({
      // /admin is a pipeline dashboard — keep it out of the public sitemap
      filter: (page) => !page.includes('/admin'),
    }),
  ],
});
