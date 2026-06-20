import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import vueDevTools from 'vite-plugin-vue-devtools'
import { defineConfig } from 'vite'

function roleHistoryFallback() {
  const prefixes = ['/client', '/workshop', '/admin']
  return {
    name: 'role-history-fallback',
    configureServer(server: import('vite').ViteDevServer) {
      server.middlewares.use((req, _res, next) => {
        const rawUrl = req.url ?? ''
        const [pathname, query] = rawUrl.split('?')
        const prefix = prefixes.find(
          (candidate) => pathname === candidate || pathname.startsWith(`${candidate}/`),
        )
        const lastSegment = pathname.split('/').at(-1) ?? ''
        if (prefix && !lastSegment.includes('.')) {
          req.url = `${prefix}/index.html${query ? `?${query}` : ''}`
        }
        next()
      })
    },
  }
}

// Dev API proxy target — localhost for host-based dev, the backend service in Docker compose.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [roleHistoryFallback(), vue(), vueDevTools(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Multi-page: standalone landing plus the three role SPAs.
    rollupOptions: {
      input: {
        landing: fileURLToPath(new URL('./landing/index.html', import.meta.url)),
        client: fileURLToPath(new URL('./client/index.html', import.meta.url)),
        workshop: fileURLToPath(new URL('./workshop/index.html', import.meta.url)),
        admin: fileURLToPath(new URL('./admin/index.html', import.meta.url)),
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Dev: forward API calls to the FastAPI backend.
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/docs': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/api-docs': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/api-redoc': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
