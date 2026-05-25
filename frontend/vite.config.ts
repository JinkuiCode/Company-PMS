import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',  // 监听所有网卡，允许内网访问
    port: 5173,
    // 开发环境禁用缓存，确保总是加载最新代码
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
