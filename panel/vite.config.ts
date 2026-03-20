import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    headers: {
      'Strict-Transport-Security': 'max-age=63072000; includeSubDomains',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'same-origin',
      'Content-Security-Policy':
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://appssdk.zoom.us; style-src 'self' 'unsafe-inline'; connect-src 'self' ws://localhost:8900 wss://copilot-api.agency.dev https://copilot-api.agency.dev https://api.zoom.us; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self' https://*.zoom.us https://zoom.us",
    },
  },
  build: {
    outDir: 'dist',
  },
})
