/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        xinca: {
          cyan: '#7EBEC5',
          teal: '#5DA3AA',
          dark: '#0a0a0a',
          darker: '#050505',
          card: '#1a1a2e',
          border: '#2a2a3e',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
