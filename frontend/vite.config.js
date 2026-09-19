import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// outDir is outside frontend/ because uvicorn serves the built bundle from the
// repository root. port 5174 and the 8001 proxy are this app's slots in the
// box-wide allocation: uvicorn = the app's registry port, Vite = 5173 + (port
// - 8000), so all four apps run at once without collisions.
//
// /health is proxied as well as /api: this app's health path is /health, not
// /api/health (apps.yml), and without the second entry the dev server answers
// it with index.html - the SPA then reports the API healthy while nothing is
// running behind it.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../frontend_dist', emptyOutDir: true },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
    },
  },
})
