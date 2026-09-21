import { build } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'
import { mkdir, readFile, writeFile } from 'node:fs/promises'

const outDir=resolve('../.runtime/purchase-report-standalone')
await build({
  configFile:false,
  define:{'process.env.NODE_ENV':'"production"'},
  plugins:[vue()],
  resolve:{alias:{'@':resolve('src')}},
  build:{
    outDir,emptyOutDir:true,cssCodeSplit:false,
    lib:{entry:resolve('prototypes/purchase-progress/main.js'),name:'PmsPurchasePreview',formats:['iife'],fileName:()=> 'preview.js',cssFileName:'preview'},
  },
})
const js=await readFile(resolve(outDir,'preview.js'),'utf8')
const css=await readFile(resolve(outDir,'preview.css'),'utf8')
const html=`<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>采购进度查询 V2 · 业务确认样稿</title><style>${css.replaceAll('</style','<\\/style')}</style></head><body><div id="app"></div><script>${js.replaceAll('</script','<\\/script')}</script></body></html>`
const target=resolve('../release/采购进度查询-V2-业务确认样稿.html')
await mkdir(resolve('../release'),{recursive:true})
await writeFile(target,html)
console.log(`STANDALONE_HTML ${target} (${Buffer.byteLength(html)} bytes)`)
