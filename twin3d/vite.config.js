import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      external: ['crypto']
    }
  },
  server: {
    port: 3000,
    host: true
  },
  define: {
    global: 'globalThis'
  }
}) 