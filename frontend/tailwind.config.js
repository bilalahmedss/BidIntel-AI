/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: '#0f172a', card: '#1e293b', elevated: '#334155' },
      },
    },
  },
  plugins: [],
}
