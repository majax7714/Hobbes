import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// The build writes straight into the Go binary's embed directory
// (ADR-022). emptyOutDir stays off so the committed .gitkeep — which
// keeps the go:embed target present in a fresh clone — survives; fixed
// output names mean each build overwrites rather than accumulating.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../go/internal/web/dist',
    emptyOutDir: false,
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'app-[name].js',
        assetFileNames: 'app.[ext]',
      },
    },
  },
  server: {
    // `npm run dev` serves the app with HMR and proxies the API to a
    // running `hobbes-web serve`, so the UI iterates without a Go build.
    proxy: { '/api': 'http://127.0.0.1:7777' },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})
