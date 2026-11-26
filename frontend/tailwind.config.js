const defaultColors = require('tailwindcss/colors');

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Nocturne Editorial — Canvas & Elevated Dark Surfaces
        canvas: 'rgb(var(--color-bg-canvas) / <alpha-value>)',
        surface: {
          DEFAULT: 'rgb(var(--color-bg-surface) / <alpha-value>)',
          1: 'rgb(var(--color-bg-surface) / <alpha-value>)',
          2: 'rgb(var(--color-bg-surface-2) / <alpha-value>)',
          3: 'rgb(var(--color-bg-surface-3) / <alpha-value>)',
          elevated: 'rgb(var(--color-bg-surface-2) / <alpha-value>)',
          hover: 'rgb(var(--color-bg-surface-3) / <alpha-value>)',
        },

        // Primary Brand Accent — Approved Coral (#F43F5E)
        brand: {
          DEFAULT: '#F43F5E',
          50: '#FFF1F2',
          100: '#FFE4E6',
          200: '#FECDD3',
          300: '#FDA4AF',
          400: '#FB7185',
          500: '#F43F5E',
          600: '#E11D48',
          700: '#BE123C',
          800: '#9F1239',
          900: '#881337',
          950: '#4C0519',
        },

        // Secondary Enterprise Accent — Partner & Admin Console
        console: {
          DEFAULT: '#8B5CF6',
          50: '#F5F3FF',
          100: '#EDE9FE',
          200: '#DDD6FE',
          300: '#C4B5FD',
          400: '#A78BFA',
          500: '#8B5CF6',
          600: '#7C3AED',
          700: '#6D28D9',
          800: '#5B21B6',
          900: '#4C1D95',
          950: '#2E1065',
        },

        // Ink / Text Hierarchy Tokens
        ink: {
          primary: 'rgb(var(--color-text-primary) / <alpha-value>)',
          secondary: 'rgb(var(--color-text-secondary) / <alpha-value>)',
          muted: 'rgb(var(--color-text-muted) / <alpha-value>)',
        },

        // Semantic Status & Editorial Highlight Accents
        status: {
          success: '#10B981',
          warning: '#F59E0B',
          danger: '#EF4444',
          info: '#38BDF8',
        },
        gold: {
          DEFAULT: '#F5C76B',
          300: '#F5C76B',
          400: '#F5C76B',
          500: '#F59E0B',
        },
        champagne: '#F5C76B',

        // Fix missing Tailwind gray shades referenced in legacy components (gray-750, gray-850)
        gray: {
          ...defaultColors.gray,
          750: '#29303D',
          850: '#171D29',
        },

        // Preserve legacy `dark` scale for backward compatibility
        dark: {
          900: '#090A0F',
          800: '#11131A',
          700: '#181B24',
          600: '#222633',
        },
      },

      textColor: {
        primary: 'rgb(var(--color-text-primary) / <alpha-value>)',
        secondary: 'rgb(var(--color-text-secondary) / <alpha-value>)',
        muted: 'rgb(var(--color-text-muted) / <alpha-value>)',
      },

      borderColor: {
        subtle: 'var(--border-subtle)',
        strong: 'var(--border-strong)',
      },

      divideColor: {
        subtle: 'var(--border-subtle)',
        strong: 'var(--border-strong)',
      },

      ringColor: {
        subtle: 'var(--border-subtle)',
        strong: 'var(--border-strong)',
      },

      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['var(--font-display)', 'var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },

      maxWidth: {
        editorial: '1320px',
      },

      borderRadius: {
        control: '0.5rem',
        card: '0.75rem',
        panel: '1rem',
        pill: '9999px',
      },

      boxShadow: {
        surface: '0 1px 2px 0 rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.04)',
        elevated: '0 12px 32px -8px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.08)',
        modal: '0 24px 60px -12px rgba(0, 0, 0, 0.78), 0 0 0 1px rgba(255, 255, 255, 0.12)',
        'brand-sm': '0 4px 14px -2px rgba(244, 63, 94, 0.28)',
        'console-sm': '0 4px 14px -2px rgba(139, 92, 246, 0.25)',
      },

      opacity: {
        12: '0.12',
        98: '0.98',
      },

      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleUp: {
          '0%': { opacity: '0', transform: 'scale(0.96) translateY(6px)' },
          '100%': { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
        slideInTop: {
          '0%': { opacity: '0', transform: 'translateY(-6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
      },

      animation: {
        fadeIn: 'fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        scaleUp: 'scaleUp 0.22s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        slideInTop: 'slideInTop 0.16s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        shimmer: 'shimmer 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
