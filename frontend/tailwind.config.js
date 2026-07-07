/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        dark: { 50: '#f0f0f5', 100: '#d9dae3', 200: '#b3b5c7', 300: '#8d8fab', 400: '#67698f', 500: '#0d0d1a', 600: '#0a0a15', 700: '#080810', 800: '#05050a', 900: '#020205' },
        accent: { 50: '#f0efff', 100: '#d1ceff', 200: '#a39dff', 300: '#756cff', 400: '#6c5ce7', 500: '#5a4bd4', 600: '#4a3dbf', 700: '#3b30a8', DEFAULT: '#6c5ce7' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
}
