import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // same-origin /api in dev: no CORS, and SSE streams straight through
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
