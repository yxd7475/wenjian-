import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import legacy from '@vitejs/plugin-legacy'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue(),
    legacy({
      targets: ['defaults', 'not IE 11', 'chrome >= 49', 'safari >= 10', 'firefox >= 57'],
      additionalLegacyPolyfills: ['regenerator-runtime/runtime'],
    }),
  ],
  base: '/files/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    cssTarget: ['chrome63', 'safari11'],
    outDir: 'dist/files',
    emptyOutDir: true,
  },
  server: {
    host: '0.0.0.0',
    port: 3088,
    allowedHosts: true,
    headers: {
      'Cache-Control': 'no-store'
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8088',
        changeOrigin: true,
        timeout: 300000,
        proxyTimeout: 300000,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Connection', 'keep-alive')
          })
        }
      },
      '/ws': {
        target: 'ws://localhost:8088',
        ws: true
      },
      '/storage': {
        target: 'http://localhost:8088',
        changeOrigin: true
      }
    }
  }
})
