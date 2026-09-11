import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const login = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
const ssoStart = readFileSync(new URL('../src/views/SsoStart.vue', import.meta.url), 'utf8')
const tokenGenerator = readFileSync(new URL('../src/views/TokenGenerator.vue', import.meta.url), 'utf8')
const launcher = readFileSync(new URL('../../start-pms.command', import.meta.url), 'utf8')

assert.doesNotMatch(login, /admin123|默认账号/, 'Login page must not expose default credentials')
assert.match(login, /username:\s*''/, 'Login username must start empty')
assert.match(login, /password:\s*''/, 'Login password must start empty')
assert.match(login, /from ['"]@\/form-system['"]/, 'Login should use the shared PMS form system')
assert.doesNotMatch(login, /<el-(input|checkbox)\b/, 'Login should not render raw Element Plus controls')

assert.match(ssoStart, /from ['"]@\/form-system['"]/, 'SSO login should use the shared PMS form system')
assert.match(ssoStart, /PmsCheckboxControl/, 'SSO remember-me should use the shared checkbox control')
assert.doesNotMatch(ssoStart, /<el-(input|checkbox)\b/, 'SSO login should not render raw Element Plus controls')
assert.match(ssoStart, /oaPasswordLogin|ssoLogin/, 'SSO authentication endpoints should remain connected')
assert.doesNotMatch(ssoStart, /placeholder=["'][^"']*(token|密码\s*[:：]|账号\s*[:：])[^"']*["']/i, 'SSO placeholders must not expose credentials or tokens')

assert.match(tokenGenerator, /from ['"]@\/form-system['"]/, 'Token generator should use the shared PMS form system')
assert.doesNotMatch(tokenGenerator, /<el-input\b/, 'Token generator should not render raw Element Plus inputs')
assert.match(tokenGenerator, /\/sso\/generate-url/, 'Token generation endpoint should remain unchanged')

assert.doesNotMatch(launcher, /admin123/, 'Launcher must not contain a fixed login password')
assert.match(launcher, /\/api\/health/, 'Launcher should verify the frontend API proxy through a health endpoint')
assert.match(launcher, /check_api_proxy/, 'Launcher should use a credential-free API proxy health check')

console.log('login security contract passed')
