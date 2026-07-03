import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const readRoot = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

const main = read('src/main.ts')
const login = read('src/views/Login.vue')
const layout = read('src/layout/AppLayout.vue')
const archive = read('src/views/project/ProjectArchive.vue')
const projectList = read('src/views/project/ProjectList.vue')
const progress = read('src/views/project/ProjectProgress.vue')
const gridScrollbar = read('src/components/GridHorizontalScrollbar.vue')
const ssoEntry = read('public/sso-entry.html')
const startScriptUrl = new URL('../../start-pms.command', import.meta.url)
const startScript = existsSync(startScriptUrl) ? readRoot('start-pms.command') : ''

assert.match(main, /styles\/pms-theme\.css/, 'main.ts should import the PMS theme stylesheet')

assert.match(login, /login-shell/, 'Login page should use the single-card PMS login shell')
assert.doesNotMatch(login, /linear-gradient/, 'Login page should not use the old gradient background')

assert.match(layout, /app-shell/, 'App layout should expose the refreshed shell class')
assert.doesNotMatch(layout, /background-color="#304156"/, 'App menu should not use the old dark sidebar color')
assert.doesNotMatch(
  ssoEntry,
  /setTimeout\s*\(\s*function\s*\(\)\s*\{\s*doRedirect\(\)/,
  'Static SSO entry should not automatically redirect users away from the login entry',
)

for (const [name, source] of [
  ['ProjectArchive.vue', archive],
  ['ProjectList.vue', projectList],
  ['ProjectProgress.vue', progress],
]) {
  assert.match(source, /pms-page/, `${name} should use the shared PMS page surface`)
  assert.match(source, /pms-ag-grid/, `${name} should use the shared AG Grid styling hook`)
  assert.match(source, /:theme="'legacy'"/, `${name} should opt into AG Grid legacy CSS theme mode`)
}

assert.match(archive, /archive-grid-shell/, 'Project archive should wrap AG Grid in a horizontal scroll shell')
assert.match(archive, /alwaysShowHorizontalScroll/, 'Project archive should use AG Grid native always-visible horizontal scrolling')
assert.match(archive, /GridHorizontalScrollbar/, 'Project archive should use the shared visible grid scrollbar')
assert.match(projectList, /project-list-grid-shell/, 'Project progress list should wrap AG Grid in the shared horizontal scroll shell')
assert.match(projectList, /alwaysShowHorizontalScroll/, 'Project progress list should keep horizontal scrolling available')
assert.match(projectList, /GridHorizontalScrollbar/, 'Project progress list should use the shared visible grid scrollbar')
assert.match(gridScrollbar, /ag-body-horizontal-scroll-viewport/, 'Shared scrollbar should drive AG Grid native horizontal viewport')
assert.match(gridScrollbar, /scrollWidth\s*-\s*viewport\.clientWidth/, 'Shared scrollbar should use AG Grid native scroll range')
assert.match(gridScrollbar, /grid-horizontal-scrollbar-thumb/, 'Shared scrollbar should expose a visible thumb')
assert.match(gridScrollbar, /@keydown="onKeydown"/, 'Shared scrollbar should support keyboard operation')
assert.match(gridScrollbar, /tabindex="0"/, 'Shared scrollbar should be keyboard focusable')
assert.doesNotMatch(archive, /ag-center-cols-viewport/, 'Project archive scrollbar should not drive the body viewport directly')
assert.doesNotMatch(archive, /measureArchiveScrollRange/, 'Project archive should not measure a separate custom scrollbar range')
assert.doesNotMatch(archive, /Number\.MAX_SAFE_INTEGER/, 'Project archive should not probe scroll range by mutating scrollLeft')
assert.match(archive, /archive-pagination/, 'Project archive pagination should sit directly below the grid')
assert.doesNotMatch(archive, /height:\s*calc\(100vh/, 'Project archive grid should not force pagination to the bottom of the viewport')

assert.ok(startScript, 'Repository should include a macOS one-click start-pms.command script')
assert.match(startScript, /DB_DIALECT=sqlite/, 'Start script should force local SQLite for development')
assert.match(startScript, /SQLITE_DB_PATH=.*backend\/data\/pms-dev\.db/, 'Start script should use the bundled dev SQLite database')
assert.match(startScript, /BACKEND_PORT=8000/, 'Start script should start the backend on port 8000')
assert.match(startScript, /FRONTEND_PORT=5174/, 'Start script should start the frontend on port 5174')
assert.match(startScript, /uvicorn main:app/, 'Start script should launch the FastAPI backend')
assert.match(startScript, /npm run dev -- --host 127\.0\.0\.1 --port "\$FRONTEND_PORT"/, 'Start script should launch Vite on localhost and the configured port')
assert.match(startScript, /backend\.log/, 'Start script should write backend logs')
assert.match(startScript, /frontend\.log/, 'Start script should write frontend logs')

console.log('style contract passed')
