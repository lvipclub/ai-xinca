/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        xinca: {
          blue: '#2ea3f2',       // primary accent (links, buttons)
          teal: '#7EBEC5',       // secondary accent (badges, cards)
          dark: '#32373c',       // button bg, nav text
          heading: '#333',       // heading text
          body: '#666',          // body text
          card: '#f8f9fa',       // card background
          border: '#e5e5e5',     // borders
          footer: '#f1f1f1',     // footer background
        }
      },
      fontFamily: {
        sans: ['Verdana', 'Helvetica', 'Arial', 'Lucida', 'sans-serif'],
        heading: ['"Trebuchet MS"', 'Trebuchet', 'Helvetica', 'Arial', 'Lucida', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      container: {
        center: true,
        padding: '1rem',
        screens: {
          xl: '1080px',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
