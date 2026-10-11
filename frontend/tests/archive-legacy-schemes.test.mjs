import assert from 'node:assert/strict'
const { legacyArchiveSchemes } = await import('../src/query-system/archive-schemes.ts')
const old = [{version:1,name:'jin',state:{keyword:'0007',enabled:'false',categories:[3,4],productCategory:2,pageSize:100,columns:{selected_column_keys:['project_code'],columnState:[]},conditions:[{field:'customer',operator:'notEquals',value:'X',valueEnd:null}]}}]
const storage = {getItem:key=>key==='pms:archive:query-plans:9'?JSON.stringify(old):null}
const result=legacyArchiveSchemes(storage,9,'project-archive')
assert.deepEqual(result.warnings,[])
assert.equal(result.schemes.length,1)
const scheme=result.schemes[0]
assert.equal(scheme.definitions.find(d=>d.field==='keyword').value,'0007','综合搜索不能缩成项目编码匹配')
assert.equal(scheme.definitions.find(d=>d.field==='customer').schemaVersion,1,'旧否定条件不改变NULL语义')
assert.equal(scheme.definitions.find(d=>d.field==='is_enabled').value,0)
assert.deepEqual(scheme.definitions.find(d=>d.field==='archive_category').value,[3,4])
assert.equal(scheme.definitions.find(d=>d.field==='product_category').value,2)
assert.equal(scheme.preferences.pageSize,100)
assert.equal(legacyArchiveSchemes(storage,10,'project-archive').schemes.length,0,'旧方案按用户隔离')
assert.equal(legacyArchiveSchemes(storage,9,'other').schemes.length,0)
assert.equal(old[0].state.keyword,'0007','不重写旧存储')
const conflict={getItem:()=>JSON.stringify([{...old[0],state:{...old[0].state,conditions:[{field:'is_enabled',operator:'equals',value:1}]}}])}
assert.equal(legacyArchiveSchemes(conflict,9,'project-archive').schemes.length,0,'冲突条件不能悄悄丢弃')
console.log('archive legacy schemes: user isolation, keyword semantics, old null semantics, preferences and conflicts passed')
