import {test} from 'node:test'
import assert from 'node:assert/strict'
import {existsSync} from 'node:fs'
import {createThemeSession} from '../src/theme-system/core.ts'
const path=new URL('../src/theme-system/progress.ts',import.meta.url)
const progress=existsSync(path)?await import(path.href):{}
test('progress uses approved red/yellow/green boundaries and zero has no fabricated width',()=>{
  assert.equal(typeof progress.progressAppearance,'function','shared progress behavior is missing')
  for(const [value,stage] of [[0,'low'],[49.999,'low'],[50,'mid'],[99.999,'mid'],[100,'complete']])assert.equal(progress.progressAppearance(value).stage,stage)
  assert.equal(progress.progressAppearance(0).percentage,0)
  assert.equal(progress.progressAppearance(20).color,'#c83434')
  assert.equal(progress.progressAppearance(80).color,'#b68b00')
  assert.equal(progress.progressAppearance(100).color,'#087e65')
})
test('a rounded100 display cannot mark incomplete source counts complete',()=>{
  assert.equal(typeof progress.progressAppearance,'function')
  assert.equal(progress.progressAppearance(100,{completed:2499,total:2500}).stage,'mid')
  assert.equal(progress.progressAppearance(100,{completed:2500,total:2500}).stage,'complete')
  assert.equal(progress.progressAppearance(100,{completed:0,total:0}).stage,'empty')
  for(const value of [null,undefined,'',NaN,Infinity,'not-a-rate'])assert.equal(progress.progressAppearance(value).stage,'empty')
})
function fixture(){
  const values=new Map(),styles=new Map(),attrs=new Map(),events=new EventTarget()
  const storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)}
  const root={getAttribute:key=>attrs.get(key)??null,setAttribute:(key,value)=>attrs.set(key,value),removeAttribute:key=>attrs.delete(key),style:{getPropertyValue:key=>styles.get(key)||'',getPropertyPriority:()=>'',setProperty:(key,value)=>styles.set(key,value),removeProperty:key=>styles.delete(key)}}
  return{values,storage,root,events}
}
test('public help appearance follows the last selected palette without a business identity',()=>{
  const f=fixture(),privateSession=createThemeSession({...f,environment:'dev',publicUser:'public'})
  privateSession.setUser(17);privateSession.choose('teal')
  const publicSession=createThemeSession({...f,environment:'dev',publicUser:'public'})
  publicSession.setUser('public')
  assert.equal(publicSession.theme,'teal')
  assert.equal(f.values.get(publicSession.key),'teal')
  assert.ok(!publicSession.key.includes('17'))
  privateSession.setUser(18);assert.equal(privateSession.theme,'blue')
  privateSession.setUser(17);assert.equal(privateSession.theme,'teal')
  privateSession.choose('graphite')
  f.events.dispatchEvent(Object.assign(new Event('storage'),{key:publicSession.key}))
  assert.equal(publicSession.theme,'graphite')
  const other=createThemeSession({...f,environment:'different',publicUser:'public'});other.setUser('public');assert.equal(other.theme,'blue')
})
