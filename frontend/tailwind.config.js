/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0f172a',
        cloud: '#f8fafc',
        envblue: '#2E75B6',
      },
    },
  },
  plugins: [],
};
