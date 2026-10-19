import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
const source = new URL('../src/theme-system/core.ts', import.meta.url)
const core = existsSync(source) ? await import(source.href) : {}
function fixture() {
  const values = new Map(), attrs = new Map(), styles = new Map()
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
  const root = { getAttribute: key => attrs.get(key) ?? null, setAttribute: (key, value) => attrs.set(key, value), removeAttribute: key => attrs.delete(key), style: { getPropertyValue: key => styles.get(key) ?? '', getPropertyPriority: () => '', setProperty: (key, value) => styles.set(key, value), removeProperty: key => styles.delete(key) } }
  return { values, attrs, styles, storage, root, events: new EventTarget() }
}
const create = (f, environment='local') => { assert.equal(typeof core.createThemeSession,'function','shared theme session is missing');return core.createThemeSession({...f,environment}) }
test('user and environment preferences remain separate', () => {
  const f=fixture(), session=create(f)
  session.setUser(1);session.choose('teal');const first=session.key
  session.setUser(2);assert.equal(session.theme,'blue');session.choose('graphite')
  session.setUser(1);assert.equal(session.theme,'teal');assert.equal(session.key,first)
  const other=create(f,'other');other.setUser(1);assert.equal(other.theme,'blue');assert.notEqual(other.key,session.key)
})
test('bad stored values fall back to the approved office blue palette', () => {
  const f=fixture(),session=create(f);session.setUser(1);f.values.set(session.key,'purple');session.setUser(null);session.setUser(1)
  assert.equal(session.theme,'blue');assert.equal(f.styles.get('--pms-primary'),'#2563eb')
})
test('unavailable storage preserves the current volatile choice but not across users', () => {
  const f=fixture();f.storage={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}}
  const session=create(f);session.setUser(1);assert.equal(session.choose('graphite').persisted,false)
  assert.equal(session.theme,'graphite');session.setUser(1);assert.equal(session.theme,'graphite')
  session.setUser(2);assert.equal(session.theme,'blue')
})
test('only the current user storage event applies, without writing again', () => {
  const f=fixture(),session=create(f);session.setUser(1);let changed=0;const off=session.subscribe(()=>changed++)
  f.values.set(session.key,'teal');const event=new Event('storage');Object.assign(event,{key:session.key});f.events.dispatchEvent(event)
  assert.equal(session.theme,'teal');assert.equal(changed,1)
  f.events.dispatchEvent(Object.assign(new Event('storage'),{key:'unrelated'}));assert.equal(changed,1);off();session.dispose()
})
test('logout and disposal restore the prior theme tokens without changing unrelated styles', () => {
  const f=fixture();f.styles.set('--pms-primary','prior');f.styles.set('--unrelated','keep');f.attrs.set('data-pms-theme','prior')
  const session=create(f);session.setUser(1);session.choose('teal');session.setUser(null)
  assert.equal(f.styles.get('--pms-primary'),'prior');assert.equal(f.attrs.get('data-pms-theme'),'prior');assert.equal(f.styles.get('--unrelated'),'keep')
  assert.equal(session.choose('graphite').applied,false);session.setUser(1);session.dispose()
  assert.equal(f.styles.get('--pms-primary'),'prior');assert.equal(f.styles.get('--unrelated'),'keep')
})
test('all themes retain fixed semantic progress and notification colors', () => {
  const f=fixture(),session=create(f);session.setUser(1)
  for(const name of ['blue','teal','graphite']){session.choose(name);assert.equal(f.styles.get('--pms-progress-low'),'#c83434');assert.equal(f.styles.get('--pms-progress-mid'),'#b68b00');assert.equal(f.styles.get('--pms-success'),'#087e65')}
})
