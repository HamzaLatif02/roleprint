/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Bebas Neue"', 'cursive'],
        mono: ['"Space Mono"', 'monospace'],
        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
      },
      colors: {
        void: {
          950: '#04050c',
          900: '#06070e',
          800: '#0a0c18',
          700: '#0e1020',
          600: '#13162a',
          500: '#1a1e34',
          400: '#232840',
        },
        border: {
          DEFAULT: '#1e2238',
          bright: '#2d3354',
          glow: '#3d4a7a',
        },
        amber: {
          glow: '#f5a623',
          dim: '#c47d12',
          muted: '#7a4d0a',
          faint: '#2a1a04',
        },
        teal: {
          signal: '#2dd4bf',
          dim: '#0f9d8b',
          faint: '#041e1b',
        },
        rose: {
          signal: '#f05151',
          dim: '#b33636',
          faint: '#200d0d',
        },
        ink: {
          100: '#d4d8f0',
          200: '#a8aed4',
          300: '#7c83b0',
          400: '#565878',
          500: '#363855',
        },
      },
      backgroundImage: {
        'grid-faint': 'linear-gradient(rgba(30,34,56,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(30,34,56,0.5) 1px, transparent 1px)',
      },
      backgroundSize: {
        'grid-sm': '24px 24px',
      },
      boxShadow: {
        'amber-glow': '0 0 20px rgba(245,166,35,0.15)',
        'amber-glow-sm': '0 0 8px rgba(245,166,35,0.2)',
        'teal-glow': '0 0 20px rgba(45,212,191,0.12)',
        'card': '0 4px 24px rgba(0,0,0,0.4)',
        'card-hover': '0 8px 40px rgba(0,0,0,0.6)',
      },
      animation: {
        'fade-up': 'fadeUp 0.4s ease forwards',
        'fade-in': 'fadeIn 0.3s ease forwards',
        'pulse-amber': 'pulseAmber 2s ease-in-out infinite',
        'scan': 'scan 8s linear infinite',
        'shimmer': 'shimmer 1.8s ease-in-out infinite',
        'slide-in-left': 'slideInLeft 0.3s ease forwards',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseAmber: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 8px rgba(245,166,35,0.3)' },
          '50%': { opacity: '0.7', boxShadow: '0 0 20px rgba(245,166,35,0.6)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideInLeft: {
          '0%': { opacity: '0', transform: 'translateX(-16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
