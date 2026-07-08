/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Spatial/glass theme — warm neutral backdrop, ink-navy text (matches
        // the frosted glass + navy-serif reference look), soft accent blue/violet.
        canvas: { 50: '#faf9f7', 100: '#f1efe9', 200: '#e7e3da', 300: '#d9d3c6' },
        ink: { 50: '#eef0f7', 300: '#7d84a6', 500: '#3d4266', 700: '#22253f', 900: '#12142a' },
        accent: { 50: '#eef1ff', 100: '#dbe0ff', 200: '#b3bcff', 300: '#8b96ff', 400: '#5f6bef', 500: '#4147c4', 600: '#33389c', DEFAULT: '#4147c4' },
        good: { DEFAULT: '#1d9a6c', bg: '#e4f6ee' },
        bad: { DEFAULT: '#d13b3b', bg: '#fceaea' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Playfair Display"', 'serif'],
      },
      backdropBlur: { '3xl': '48px' },
      borderRadius: { '2xl': '20px', '3xl': '28px', '4xl': '36px' },
    },
  },
  plugins: [],
}
