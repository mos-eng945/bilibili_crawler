import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),//import.meta.url是当前模块的URL, new URL('./src', import.meta.url)是相对于当前模块的URL创建一个新的URL对象, fileURLToPath将其转换为文件路径
    },
  },
})
