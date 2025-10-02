// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html','./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // panel/surface
        card:    { light: '#ffffff', dark: '#1f2937' },   // panel bg
        borderc: { light: '#e5e7eb', dark: '#374151' },   // borders
        // text tokens
        fg: {
          strong: '#111827',  // dark slate
          base:   '#1f2937',
          muted:  '#6b7280',
        },
        // brand
        primary: {
          500: '#4f46e5',
          600: '#4338ca',
          700: '#3730a3',
        },
      },
    },
  },
  plugins: [],
}
