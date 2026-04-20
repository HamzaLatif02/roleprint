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
        // These reference CSS variables so dark/light mode switching works.
        // The variables are defined in index.css and swapped via html.light.
        void: {
          950: 'var(--void-950)',
          900: 'var(--void-900)',
          800: 'var(--void-800)',
          700: 'var(--void-700)',
          600: 'var(--void-600)',
          500: 'var(--void-500)',
          400: 'var(--void-400)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          bright: 'var(--color-border-bright)',
          glow: 'var(--color-border-glow)',
        },
        ink: {
          100: 'var(--ink-100)',
          200: 'var(--ink-200)',
          300: 'var(--ink-300)',
          400: 'var(--ink-400)',
          500: 'var(--ink-500)',
        },
        // Static accent colors — same in both modes
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
