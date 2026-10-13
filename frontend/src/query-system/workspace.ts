import { cloneQuery, hasConditionValue, isPositiveQueryCondition, operatorsForField, validateConditions, type QueryCondition, type QueryField, type QueryOperator, type QueryValue, type QueryScalar } from './core.ts'

export type QueryDefinition = { field:string; shown:boolean; operator:QueryOperator; value:QueryValue; valueEnd:QueryScalar; schemaVersion?:1|2 }
export type QueryScheme = { version:2; name:string; definitions:QueryDefinition[]; isDefault:boolean; preferences:object }
type Storage = Pick<globalThis.Storage,'getItem'|'setItem'>
const blank = (value:unknown) => value == null || value === '' || Array.isArray(value) && !value.length
export function schemeStorageKey(userId:unknown,listKey:string) {
  if(!userId)throw Error('请先登录再维护查询方案')
  return `pms:query-workspace:v2:${String(userId)}:${listKey}`
}
export function instantiateDefinitions(definitions:QueryDefinition[]):QueryCondition[] {
  return cloneQuery(definitions.filter(d=>d.shown).map((d,i)=>({id:i+1,field:d.field,operator:d.operator,value:d.value,valueEnd:d.valueEnd,schemaVersion:d.schemaVersion??2})))
}
export function prepareDefinitions(definitions:QueryDefinition[],fields:QueryField[]) {
  const available=new Set(fields.map(field=>field.field))
  return {
    definitions:cloneQuery(definitions.filter(definition=>available.has(definition.field))),
    invalidFields:[...new Set(definitions.filter(definition=>!available.has(definition.field)).map(definition=>definition.field))],
  }
}
export function activeQuery(source:QueryCondition[],fields:QueryField[]) {
  const conditions=source.filter(c=>hasConditionValue(c)||!blank(c.value)||!blank(c.valueEnd))
  const errors=validateConditions(conditions,fields)
  for(const field of fields.filter(f=>f.required)) {
    const c=source.find(c=>c.field===field.field)
    if(!c||blank(c.value)||['isEmpty','notEmpty','notEquals','notIn','notContains'].includes(c.operator))errors[c?.id||0]=`${field.label}为必输条件`
  }
  for (const group of new Set(fields.map(f=>f.requiredGroup).filter(Boolean))) {
    const members = fields.filter(f=>f.requiredGroup===group).map(f=>f.field)
    if (!source.some(c=>members.includes(c.field)&&isPositiveQueryCondition(c)&&hasConditionValue(c)))
      errors[source.find(c=>members.includes(c.field))?.id||0]=`${group}条件至少填写一项正向匹配`
  }
  return {conditions:cloneQuery(conditions),errors}
}
export function settingsDefinitions(definitions:QueryDefinition[],draft:QueryCondition[],fields:QueryField[]):QueryDefinition[] {
  const current=draft.map(c=>({field:c.field,operator:c.operator,value:c.value,valueEnd:c.valueEnd,shown:true,schemaVersion:c.schemaVersion}))
  return cloneQuery([...current,...definitions.filter(d=>!draft.some(c=>c.field===d.field)).map(d=>({...d,shown:false})),
    ...fields.filter(f=>!definitions.some(d=>d.field===f.field)&&!draft.some(c=>c.field===f.field)).map(f=>({field:f.field,shown:!!f.required,operator:f.type==='enum'?'in' as const:operatorsForField(f).find(op=>op!=='reference')!,value:null,valueEnd:null}))])
}
export function validateDefinitions(definitions:QueryDefinition[],fields:QueryField[]) {
  const errors:Record<string,string>={},used=new Set<string>()
  for(const d of definitions) {
    const f=fields.find(f=>f.field===d.field)
    if(!f){errors[d.field]='字段已失效';continue}
    if(used.has(d.field))errors[d.field]='默认条件字段不能重复'
    used.add(d.field)
    if(f.required&&!d.shown)errors[d.field]='必输条件不能隐藏'
    const validation=activeQuery([{...d,id:1,schemaVersion:d.schemaVersion??2}], [{...f,required:false,requiredGroup:undefined}])
    if(Object.keys(validation.errors).length)errors[d.field]=Object.values(validation.errors)[0]!
    if(!operatorsForField(f).includes(d.operator))errors[d.field]='匹配方式已失效'
  }
  for(const f of fields.filter(f=>f.required))if(!definitions.some(d=>d.field===f.field&&d.shown))errors[f.field]='必输条件不能隐藏'
  for (const group of new Set(fields.map(f=>f.requiredGroup).filter(Boolean))) {
    const members = fields.filter(f=>f.requiredGroup===group).map(f=>f.field)
    if (!definitions.some(d=>d.shown&&members.includes(d.field)&&isPositiveQueryCondition({...d,id:1})))
      errors[members[0]||String(group)]=`${group}至少展示一项正向匹配条件`
  }
  if(definitions.filter(d=>d.shown).length>20)errors[0]='最多展示20个条件'
  return errors
}
export function readSchemes(storage:Storage,key:string):QueryScheme[] {
  const value=JSON.parse(storage.getItem(key)||'[]')
  if(!Array.isArray(value)||value.some(p=>p?.version!==2||typeof p.name!=='string'||!Array.isArray(p.definitions))||value.filter(p=>p.isDefault).length>1)throw Error('查询方案格式无效，请重新配置')
  return cloneQuery(value)
}
export function saveScheme(storage:Storage,key:string,schemes:QueryScheme[],input:Omit<QueryScheme,'version'|'preferences'>&{preferences?:object},fields:QueryField[],originalName='') {
  const name=input.name.trim()
  if(!name||name.length>60)throw Error('请填写方案名称（最多60字）')
  if(schemes.some(p=>p.name===name&&p.name!==originalName))throw Error('存在同名方案，请修改名称')
  const errors=validateDefinitions(input.definitions,fields)
  if(Object.keys(errors).length)throw Error(Object.values(errors).join('；'))
  const next=schemes.filter(p=>p.name!==originalName).map(p=>({...p,isDefault:input.isDefault?false:p.isDefault}))
  next.push(cloneQuery({version:2,name,definitions:input.definitions,isDefault:input.isDefault,preferences:input.preferences||{}}))
  storage.setItem(key,JSON.stringify(next))
  return next
}
export function selectScheme(schemes:QueryScheme[],name:string,defaults:QueryDefinition[]) {
  const scheme=schemes.find(p=>p.name===name)
  return {definitions:cloneQuery(scheme?.definitions||defaults),conditions:instantiateDefinitions(scheme?.definitions||defaults),preferences:cloneQuery(scheme?.preferences||{}),columnFilters:[] as QueryCondition[]}
}
export async function validateReferences(conditions:QueryCondition[],fields:QueryField[],current=()=>true) {
  const failures:Record<number,string>={}
  for(const c of conditions.filter(c=>c.operator==='reference'&&fields.find(f=>f.field===c.field)?.reference)) {
    const source=fields.find(f=>f.field===c.field)!.reference!,ids=c.value as (string|number)[],available=new Set<string|number>()
    for(let page=1;;page++) {
      const result=await source.load({ids,conditions,page,pageSize:100})
      if(!current())return null
      result.items.forEach(r=>available.add(r.value))
      if(available.size>=result.total||!result.items.length)break
      if(page>=100)throw Error('引用校验结果超出支持范围')
    }
    if(ids.some(id=>!available.has(id)))failures[c.id]='部分引用记录不在当前产品线或权限范围，请重新选择'
  }
  return failures
}
