// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://ai.xinca.com',
  output: 'static',
  build: {
    assets: 'assets'
  },
  integrations: [tailwind(), sitemap()],
});
