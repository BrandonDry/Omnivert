import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  root: '.',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // In dev, the Vite server proxies API calls to the FastAPI backend.
      '/api': 'http://127.0.0.1:8765',
    },
  },
  build: {
    rollupOptions: {
      input: 'index.html',
    },
  },
})
