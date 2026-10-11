import type { QueryReference, ReferenceRequest, ReferenceResult } from './reference'
import type { QueryCondition, QueryOption } from './core'
type ArchiveRow={id:number;project_code:string;project_name:string|null;product_line_id:number|null;is_enabled:number}
type ArchivePage={items:ArchiveRow[];total:number}
export function archiveReference(load:(params:Record<string,unknown>)=>Promise<ArchivePage>,label:(id:unknown)=>string,lineOptions?:()=>QueryOption[]):QueryReference {
  return {title:'项目档案',keyField:'id',keyType:'number',lineOptions,async load(q:ReferenceRequest):Promise<ReferenceResult> {
    const filters:QueryCondition[]=(q.conditions||[]).filter(c=>c.field==='product_line_id')
    if(q.line!=null)filters.push({id:997,field:'product_line_id',operator:'equals',value:q.line,valueEnd:null,schemaVersion:2})
    if(q.ids)filters.push({id:999,field:'project_code',operator:'reference',value:q.ids,valueEnd:null,schemaVersion:2})
    if(q.batch)filters.push({id:998,field:q.batch.field==='code'?'project_code':'project_name',operator:'in',value:q.batch.values,valueEnd:null,schemaVersion:2})
    const result=await load({page:q.page,page_size:q.pageSize,enabled:'all',keyword:q.keyword||undefined,filters:JSON.stringify(filters)})
    return {total:result.total,items:result.items.map(r=>({value:r.id,code:r.project_code,name:r.project_name||'',lineName:label(r.product_line_id),status:r.is_enabled?'启用':'禁用'}))}
  }}
}
