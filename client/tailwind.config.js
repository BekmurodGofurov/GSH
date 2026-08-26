/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0e17',
        surface: {
          50: '#1e293b',
          100: '#161f30',
          200: '#0f172a',
          300: '#0c1322',
          card: 'rgba(15, 23, 42, 0.75)',
        },
        border: '#1e293b',
        primary: {
          DEFAULT: '#06b6d4', // Cyan
          hover: '#0891b2',
          glow: 'rgba(6, 182, 212, 0.15)',
        },
        secondary: {
          DEFAULT: '#8b5cf6', // Violet
          hover: '#7c3aed',
          glow: 'rgba(139, 92, 246, 0.15)',
        },
        status: {
          online: '#10b981', // Emerald
          offline: '#f43f5e', // Rose
          warning: '#f59e0b', // Amber
          recovery: '#38bdf8', // Sky
        },
      },
      boxShadow: {
        glow: '0 0 20px -5px rgba(6, 182, 212, 0.25)',
        'glow-emerald': '0 0 20px -5px rgba(16, 185, 129, 0.3)',
        'glow-rose': '0 0 20px -5px rgba(244, 63, 94, 0.3)',
        'glow-violet': '0 0 20px -5px rgba(139, 92, 246, 0.3)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'ping-slow': 'ping 2.5s cubic-bezier(0, 0, 0.2, 1) infinite',
      },
    },
  },
  plugins: [],
};
