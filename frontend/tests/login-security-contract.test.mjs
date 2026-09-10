import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const login = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
const launcher = readFileSync(new URL('../../start-pms.command', import.meta.url), 'utf8')

assert.doesNotMatch(login, /admin123|默认账号/, 'Login page must not expose default credentials')
assert.match(login, /username:\s*''/, 'Login username must start empty')
assert.match(login, /password:\s*''/, 'Login password must start empty')

assert.doesNotMatch(launcher, /admin123/, 'Launcher must not contain a fixed login password')
assert.match(launcher, /\/api\/health/, 'Launcher should verify the frontend API proxy through a health endpoint')
assert.match(launcher, /check_api_proxy/, 'Launcher should use a credential-free API proxy health check')

console.log('login security contract passed')
