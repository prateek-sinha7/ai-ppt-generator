import type { Config } from 'tailwindcss'
import { tokens } from './src/styles/tokens'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      spacing: tokens.spacing,
      fontSize: tokens.fontSize,
      colors: tokens.colors,
      fontFamily: tokens.fontFamily,
    },
  },
  plugins: [],
} satisfies Config
