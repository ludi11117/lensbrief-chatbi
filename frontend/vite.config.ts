import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const swaggerFiles = ['swagger-ui-bundle.js', 'swagger-ui.css', 'favicon-32x32.png',
  'LICENSE', 'NOTICE', 'swagger-ui-bundle.js.LICENSE.txt']

export default defineConfig({
  plugins: [vue(), viteStaticCopy({
    targets: swaggerFiles.map(file => ({ src: 'node_modules/swagger-ui-dist/' + file, dest: 'assets/swagger-ui' })),
  })],
  server: { proxy: { '/api': 'http://127.0.0.1:8123' } }
})
