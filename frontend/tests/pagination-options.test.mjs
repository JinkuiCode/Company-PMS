import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'
import * as listUi from '../src/config/listUi.ts'
import { reportPreferences, reportReference } from '../src/query-system/report-adapter.ts'
import { archiveReference } from '../src/query-system/archive-reference.ts'
import { optionReference } from '../src/query-system/reference.ts'

const expected = [15, 20, 50, 100, 200, 300, 500]

test('shared page sizes include seven approved choices and retain default 50', () => {
  assert.deepEqual(listUi.PAGE_SIZE_OPTIONS, expected)
  assert.equal(listUi.DEFAULT_PAGE_SIZE, 50)
})

test('pagination renders every shared option', async () => {
  const filename = new URL('../src/components/CustomPagination.vue', import.meta.url)
  const { descriptor } = parse(readFileSync(filename, 'utf8'))
  const script = compileScript(descriptor, { id: 'pagination-contract', inlineTemplate: true })
  const code = ts.transpileModule(script.content, { compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext } }).outputText
    .replace(/from ["']vue["']/g, `from '${import.meta.resolve('vue')}'`)
    .replace(/from ["']\.\.\/config\/listUi(?:\.ts)?["']/g, `from '${new URL('../src/config/listUi.ts', import.meta.url).href}'`)
    .replace(/import\s*\{\s*PmsSelectControl\s*\}\s*from\s*['"]@\/form-system['"];?/,`const PmsSelectControl={props:['modelValue','options'],setup(props){return()=>renderH('select',{},props.options.map(item=>renderH('option',{value:item.value,selected:item.value===props.modelValue},item.label)))}}`)
  // Test the pagination's public chooser props; the browser below exercises the real control.
  const { default: component } = await import(`data:text/javascript;base64,${Buffer.from(`import {h as renderH} from '${import.meta.resolve('vue')}';\n`+code).toString('base64')}`)
  for (const pageSize of expected) {
    const html = await renderToString(createSSRApp(component, { total: 1001, modelValue: 1, pageSize }))
    const options = [...html.matchAll(/<option value="(\d+)"([^>]*)>/g)]
    assert.deepEqual(options.map(option => Number(option[1])), expected)
  }
})

test('browser selects all seven sizes and emits numeric pageSize updates', async () => {
  const cacheDir = mkdtempSync(join(tmpdir(), 'pms-pagination-'))
  let browser
  const server = await createServer({ cacheDir, server: { host: '127.0.0.1', port: 0 },
    plugins: [{ name: 'pagination-harness', configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (req.url !== '/pagination-contract.html') return next()
        res.setHeader('Content-Type', 'text/html')
        res.end(await server.transformIndexHtml(req.url, `<div id="app"></div><script type="module">
          import { createApp, h, ref } from 'vue'
          import ElementPlus from 'element-plus'
          import 'element-plus/dist/index.css'
          import '/src/styles/pms-theme.css'
          import '/src/form-system/form-tokens.css'
          import Pagination from '/src/components/CustomPagination.vue'
          const size = ref(50)
          window.updates = []
          createApp({ setup: () => () => h(Pagination, { total: 1001, modelValue: 1, pageSize: size.value,
            'onUpdate:pageSize': value => { size.value = value; window.updates.push(value) } }) }).use(ElementPlus).mount('#app')
        </script>`))
      })
    } }],
  })
  try {
    await server.listen()
    browser = await chromium.launch({ channel: 'msedge', headless: true })
    const page = await browser.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/pagination-contract.html`)
    const select = page.locator('.page-size-select')
    await expect(select).toContainText('50 条/页')
    assert.equal(Math.round(await page.locator('.pagination-right > .pms-form-control').evaluate(el=>el.getBoundingClientRect().height)),26)
    for (const size of expected) {
      await select.locator('.el-select__wrapper').click()
      assert.deepEqual(await page.getByRole('option').allTextContents(),expected.map(value=>`${value} 条/页`))
      await page.getByRole('option',{name:`${size} 条/页`,exact:true}).click()
      await expect(select).toContainText(`${size} 条/页`)
    }
    assert.deepEqual(await page.evaluate(() => window.updates), expected)
    await select.getByRole('combobox',{name:'每页条数',exact:true}).focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('option',{name:'500 条/页',exact:true})).toBeVisible()
    await page.keyboard.press('ArrowUp');await page.keyboard.press('Enter')
    await expect(select).toContainText('300 条/页')
    assert.deepEqual(errors, [])
  } finally {
    await browser?.close()
    await server.close()
    rmSync(cacheDir, { recursive: true, force: true })
  }
})

test('report preferences restore exactly the shared numeric page sizes', () => {
  for (const pageSize of expected) assert.equal(reportPreferences({ pageSize }, []).pageSize, pageSize)
  for (const pageSize of [0, 14, 16, 201, 499, 501, 1000, '500', null, NaN]) {
    assert.equal(reportPreferences({ pageSize }, []).pageSize, undefined)
  }
})

test('reference adapters send 500 unchanged and local references retain the next page', async () => {
  const calls = []
  const report = reportReference('Reference', 'id', 'number', async params => {
    calls.push(params)
    return { items: [], total: 501 }
  })
  const archive = archiveReference(async params => {
    calls.push(params)
    return { items: [], total: 501 }
  }, () => '')
  for (const reference of [report, archive]) {
    await reference.load({ page: 2, pageSize: 500 })
    assert.equal(calls.at(-1).page_size, 500)
    assert.equal(calls.at(-1).page, 2)
  }
  const local = optionReference('Options', 'enum', Array.from({ length: 501 }, (_, i) => ({ value: i, label: String(i) })))
  const first = await local.load({ page: 1, pageSize: 500 })
  const second = await local.load({ page: 2, pageSize: 500 })
  assert.equal(first.total, 501)
  assert.equal(first.items.length, 500)
  assert.deepEqual(second.items.map(row => row.value), [500])
})
