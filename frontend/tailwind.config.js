/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f1f4f9', 100: '#e1e8f2', 200: '#c4d1e5', 300: '#97acd0', 400: '#6482b5',
          500: '#42629b', 600: '#324d80', 700: '#293f68', 800: '#1d2e4f', 900: '#14213d', 950: '#0b1428',
        },
        paper: '#fafaf7',
        verdict: { verified: '#16a34a', false: '#dc2626', misleading: '#eab308', unverified: '#9ca3af' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"Plus Jakarta Sans"', 'Inter', 'ui-sans-serif', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(20,33,61,0.04), 0 4px 16px rgba(20,33,61,0.06)',
        lift: '0 8px 30px rgba(20,33,61,0.10)',
      },
    },
  },
  plugins: [],
}
