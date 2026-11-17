/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: { 50: '#fff6ed', 100: '#ffead4', 200: '#ffd2a8', 300: '#ffb170', 400: '#ff8736', 500: '#f96a12', 600: '#ea500a', 700: '#c23b0a', 800: '#9a2f10', 900: '#7c2a10' },
        leaf: { 50: '#effaf1', 100: '#d8f3de', 500: '#22a14d', 600: '#178a3d', 700: '#146e34' },
        surface: 'rgb(var(--surface) / <alpha-value>)',
        card: 'rgb(var(--card) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
      },
      boxShadow: { soft: '0 8px 30px -12px rgba(120, 53, 15, 0.25)' },
      keyframes: {
        rise: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'none' } },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
      },
      animation: { rise: 'rise .35s ease both' },
    },
  },
  plugins: [],
}
