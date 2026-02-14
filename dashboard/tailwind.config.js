/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0A0A0A',
        surface: 'rgba(10, 10, 10, 0.7)',
        border: 'rgba(255, 255, 255, 0.1)',
        primary: '#00D9FF',
        success: '#00FF88',
        warning: '#FF6B00',
        danger: '#FF2D55',
        'text-primary': '#FFFFFF',
        'text-secondary': '#A0A0A0',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      backdropBlur: {
        'glass': '16px',
      },
      boxShadow: {
        'glass': '0 0 20px rgba(0, 217, 255, 0.2)',
        'glass-strong': '0 0 30px rgba(0, 217, 255, 0.3)',
        'glow-primary': '0 0 20px rgba(0, 217, 255, 0.5)',
        'glow-success': '0 0 20px rgba(0, 255, 136, 0.5)',
        'glow-warning': '0 0 20px rgba(255, 107, 0, 0.5)',
        'glow-danger': '0 0 20px rgba(255, 45, 85, 0.5)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'dash': 'dash 30s linear infinite',
        'spin-slow': 'spin 20s linear infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(0, 217, 255, 0.2)' },
          '50%': { boxShadow: '0 0 30px rgba(0, 217, 255, 0.5)' },
        },
        'dash': {
          'to': { strokeDashoffset: '-1000' },
        },
        'blink': {
          '0%, 50%': { opacity: '1' },
          '51%, 100%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}