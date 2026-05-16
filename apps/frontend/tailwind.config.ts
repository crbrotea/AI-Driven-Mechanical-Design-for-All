import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        success: { DEFAULT: 'hsl(var(--success))', foreground: 'hsl(var(--success-foreground))' },
        warning: { DEFAULT: 'hsl(var(--warning))', foreground: 'hsl(var(--warning-foreground))' },
        danger: { DEFAULT: 'hsl(var(--danger))', foreground: 'hsl(var(--danger-foreground))' },
        info: { DEFAULT: 'hsl(var(--info))', foreground: 'hsl(var(--info-foreground))' },
        brotea: {
          violet: '#8081FF',
          'violet-soft': '#B3B4FF',
          'violet-deep': '#5F60D9',
          glow: '#E6FFA9',
          'glow-soft': '#F0FFCC',
          'glow-deep': '#CDE88B',
          pink: '#FA699F',
          'pink-deep': '#E24E87',
          eggplant: '#09092D',
          green: '#022922',
          garnet: '#330A0F',
          bone: '#F3F1EA',
        },
      },
      fontFamily: {
        sans: ['"PP Neue Machina"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"PP Neue Machina Inktrap"', '"PP Neue Machina"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        pixel: ['"Biform Pixel"', '"PP Neue Machina"', 'monospace'],
        mono: ['ui-monospace', '"JetBrains Mono"', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}

export default config
