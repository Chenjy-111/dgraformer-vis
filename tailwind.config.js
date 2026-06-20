/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#f8f9fb',
        accent: {
          DEFAULT: '#c85031',
          soft: 'rgba(200, 80, 49, 0.08)',
        },
        ink: {
          50: '#f6f7f9',
          100: '#e9ecf1',
          200: '#d3d9e2',
          300: '#b0bac8',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        line: '#e2e8f0',
        kept: '#16a34a',
        filtered: '#dc2626',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['Georgia', 'serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        card: '8px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(15, 23, 42, 0.06)',
      },
    },
  },
  plugins: [],
};
