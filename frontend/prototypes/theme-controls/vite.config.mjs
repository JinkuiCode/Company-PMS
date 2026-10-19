import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  publicDir: false,
  plugins: [{name:'isolated-application-memory-history',enforce:'pre',configureServer(server){
    server.middlewares.use((req,_res,next)=>{if(req.url?.startsWith('/page-guide/'))req.url='/application-frame.html';next()})
  },transform(source,id){
    if(id.split('?')[0]===fileURLToPath(new URL('../../src/router/index.ts',import.meta.url)))return source.replaceAll('createWebHistory','createMemoryHistory')
  }},vue()],
  resolve: { alias: [
    { find: '@/stores/auth', replacement:fileURLToPath(new URL('archive-pilot/auth.ts',import.meta.url)) },
    { find: '@/utils/request', replacement:fileURLToPath(new URL('archive-pilot/request.ts',import.meta.url)) },
    { find: '@', replacement:fileURLToPath(new URL('../../src',import.meta.url)) },
  ] },
  cacheDir: '../../node_modules/.vite-theme-controls',
  server: { host: '127.0.0.1', port: 5184, strictPort: true, fs: { allow: [fileURLToPath(new URL('../..', import.meta.url))] } },
  build: { outDir: '../../../.runtime/theme-controls-build', emptyOutDir: true, rolldownOptions: { input: { controls:fileURLToPath(new URL('index.html',import.meta.url)), archive:fileURLToPath(new URL('archive-pilot.html',import.meta.url)), application:fileURLToPath(new URL('application-pilot.html',import.meta.url)), frame:fileURLToPath(new URL('application-frame.html',import.meta.url)) } } },
})
