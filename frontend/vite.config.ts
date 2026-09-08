import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Flask serves the single-file production build and all data APIs.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss(), viteSingleFile()],
  server: { proxy: { '/api': 'http://127.0.0.1:5000', '/preview': 'http://127.0.0.1:5000', '/interface': 'http://127.0.0.1:5000' } },
  build: {
    outDir: '../src/workhours/static/modern',
    emptyOutDir: true,
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 2000,
  },
})
