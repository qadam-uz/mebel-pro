import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
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
  plugins: [roleHistoryFallback(), vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // A font is never inlined. The two `cyrillic-ext` subsets sit under Vite's
    // 4 kB default, and as data: URIs they land base64-inflated inside the
    // render-blocking stylesheet that *every* visitor parses — to carry glyphs
    // (Ғ, Қ, Ҳ) only the uz-Cyrl locale ever paints. As files they stay
    // separately cacheable, and `unicode-range` keeps them undownloaded until
    // something on the page actually needs them.
    assetsInlineLimit: (filePath: string) => (filePath.endsWith('.woff2') ? false : undefined),
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
