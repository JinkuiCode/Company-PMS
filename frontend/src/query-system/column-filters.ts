import { isEmpty, matchesConditions, type QueryCondition, type QueryField } from './core.ts'
export type ColumnFilter = {field:string;mode:'values';values:(string|number|null)[]} | {field:string;mode:'condition';condition:QueryCondition}
export type ColumnCandidate={value:string|number|null;label:string;count?:number}
export type ColumnQueryContext={ready?:()=>boolean;fields:()=>QueryField[];filters:()=>ColumnFilter[];load:(field:string,keyword:string,page:number)=>Promise<{items:ColumnCandidate[];hasMore:boolean}>;apply:(field:string,filter:ColumnFilter|null)=>void;sort?:(field:string,direction:'asc'|'desc')=>void}
export function matchesColumnFilters(row:Record<string,unknown>,filters:ColumnFilter[],fields:QueryField[]) {
  return filters.every(filter=>{
    if(!fields.some(f=>f.field===filter.field))return false
    if(filter.mode==='condition')return filter.condition.field===filter.field&&matchesConditions(row,[filter.condition],fields)
    const value=isEmpty(row[filter.field])?null:row[filter.field]
    return filter.values.includes(value as string|number|null)
  })
}
export function clientColumnCandidates(rows:Record<string,unknown>[],fields:QueryField[],filters:ColumnFilter[],field:string,keyword:string,page:number) {
  const meta=fields.find(f=>f.field===field)
  if(!meta)throw Error('筛选字段已失效')
  const found=new Map<string,ColumnCandidate>()
  for(const row of rows.filter(r=>matchesColumnFilters(r,filters.filter(f=>f.field!==field),fields))) {
    const raw=row[field],value=isEmpty(raw)?null:meta.type==='date'?String(raw).slice(0,10):raw as string|number
    const label=value===null?'（空白）':meta.options?.find(o=>o.value===value)?.label||String(value)
    if(!label.toLowerCase().includes(keyword.trim().toLowerCase()))continue
    const key=JSON.stringify(value),old=found.get(key)
    if(old)old.count=(old.count||0)+1;else found.set(key,{value,label,count:1})
  }
  const items=[...found.values()]
  return {items:items.slice((page-1)*100,page*100),hasMore:items.length>page*100}
}
