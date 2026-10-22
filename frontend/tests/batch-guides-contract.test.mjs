import {test} from 'node:test'
import assert from 'node:assert/strict'
import {pageGuides} from '../src/page-guide/registry.ts'
const text=items=>items.map(i=>i.label+' '+i.logic).join('\n')
test('archive guide reflects four draft identities, optional dates and category-dependent requirements',()=>{
 const a=pageGuides.archive,d=pageGuides.archiveDrafts
 assert.match(text(a.operations),/草稿须填档案类别、项目编号、项目名称和产品线/)
 assert.match(text(d.fields),/四项必输/)
 assert.match(a.fields.find(i=>i.label==='合同签订日期 / 合同出货日期').logic,/均可留空/)
 assert.match(a.fields.find(i=>i.label==='数量 / 单位').logic,/pcs/)
 assert.match(a.fields.find(i=>i.label==='档案类别 / 机型').logic,/非主机.*可留空/)
})
test('archive guide covers namespace, bounded history preservation and first business column',()=>{
 const a=text(pageGuides.archive.operations)
 assert.match(a,/待审批变更/);assert.match(a,/含禁用/);assert.match(a,/仅更换负责人/)
 assert.match(a,/首个业务列/);assert.match(a,/恢复草稿不补写默认/)
 assert.match(text(pageGuides.archive.fields),/非主机.*保留旧值/)
})
test('material reference instructions are limited to the three material reports',()=>{
 for(const key of ['purchase','inventory','stock']){
  const ops=pageGuides[key].operations
  assert.equal(ops.filter(i=>i.label==='物料多选引用').length,1)
  assert.match(text(ops),/确认才回填，取消不变/)
 }
 for(const key of ['archive','progress','tasks','users'])assert.ok(!pageGuides[key].operations.some(i=>i.label==='物料多选引用'))
 assert.match(text(pageGuides.stock.operations),/同一快照/)
 assert.match(text(pageGuides.purchase.operations),/物料编码.*物料名称前/)
})
test('personal scheme guide states current browser ownership and explicit query fallback',()=>{
 for(const key of ['archive','purchase','inventory','stock']){
  const item=pageGuides[key].operations.find(i=>i.label==='方案与临时条件')
  assert.match(item.logic,/当前浏览器/);assert.match(item.logic,/系统默认只读不可删除/)
  assert.match(item.logic,/保存、删除不自动查询/)
 }
})
