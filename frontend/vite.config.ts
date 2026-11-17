import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// envDir '..' lets the single root .env supply VITE_* values; only VITE_-prefixed keys reach the browser.
export default defineConfig({
  plugins: [react()],
  envDir: '..',
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { chunkSizeWarningLimit: 900, sourcemap: false },
})
