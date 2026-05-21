import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import vueDevTools from 'vite-plugin-vue-devtools'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Multi-page: three Vue SPAs (client / workshop / admin) plus the
    // standalone static SEO landing (web/landing/index.html — plain HTML, no
    // Vue), served at the apex per docs/architecture.md. Each SPA has its own
    // HTML entry loading its app's main.ts; in prod the Caddy edge routes a
    // subdomain to each. See web/DESIGN.md for the per-app dev URLs.
    rollupOptions: {
      input: {
        landing: fileURLToPath(new URL('./landing/index.html', import.meta.url)),
        client: fileURLToPath(new URL('./client.html', import.meta.url)),
        workshop: fileURLToPath(new URL('./workshop.html', import.meta.url)),
        admin: fileURLToPath(new URL('./admin.html', import.meta.url)),
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Dev: forward API calls to the FastAPI backend.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
