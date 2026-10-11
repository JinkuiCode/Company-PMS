import { adaptConditions, cloneQuery, type QueryCondition } from './core.ts'
import type { QueryScheme } from './workspace.ts'

export function legacyArchiveSchemes(storage: Pick<Storage,'getItem'>, userId: number|string, listKey: string): {schemes:QueryScheme[];warnings:string[]} {
  const result:{schemes:QueryScheme[];warnings:string[]}={schemes:[],warnings:[]}
  if(listKey!=='project-archive'||!userId)return result
  const raw=storage.getItem(`pms:archive:query-plans:${userId}`)
  if(!raw)return result
  let plans:unknown
  try{plans=JSON.parse(raw);if(!Array.isArray(plans))throw Error()}
  catch{result.warnings.push('旧档案方案格式无效，原记录已保留');return result}
  for(const input of plans as Record<string,any>[]) {
    const name=typeof input?.name==='string'?input.name:''
    try {
      const state=input.state
      if(input.version!==1||!name||!state||!['true','false','all'].includes(state.enabled)||!Array.isArray(state.categories)||typeof state.keyword!=='string')throw Error('格式无效')
      const conditions=adaptConditions(state.conditions||[])
      const add=(field:string,operator:QueryCondition['operator'],value:QueryCondition['value'])=>{
        if(conditions.some(c=>c.field===field))throw Error('同一字段存在重复条件，请人工整理')
        conditions.push({id:conditions.length+1,field,operator,value,valueEnd:null,schemaVersion:2})
      }
      if(state.keyword)add('keyword','contains',state.keyword)
      if(state.enabled!=='all')add('is_enabled','equals',state.enabled==='true'?1:0)
      if(state.categories.length)add('archive_category','in',state.categories)
      if(state.productCategory!=null)add('product_category','equals',state.productCategory)
      if(conditions.length>20||result.schemes.some(p=>p.name===name))throw Error('条件过多或方案重名')
      result.schemes.push({version:2,name,isDefault:false,definitions:conditions.map(({id,...c})=>({...c,shown:true})),preferences:cloneQuery({pageSize:state.pageSize,columns:state.columns})})
    } catch(error){result.warnings.push(`旧方案“${name||'未命名'}”未读取：${error instanceof Error?error.message:'格式无效'}；原记录已保留`)}
  }
  return result
}
