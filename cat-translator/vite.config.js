import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Relative base so the built files load from file:// inside Electron.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
})
