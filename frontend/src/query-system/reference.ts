import type { QueryOption, QueryCondition } from './core.ts'

export type ReferenceRecord = { value:string | number; code:string; name:string; lineName?:string; status?:string }
export type ReferenceRequest = { keyword?:string; page:number; pageSize:number; ids?:(string | number)[]; batch?:{field:'code'|'name';values:string[]}; conditions?:QueryCondition[];line?:number|null }
export type ReferenceResult = { items:ReferenceRecord[]; total:number }
export type QueryReference = { title:string; keyField:string; keyType:'number'|'string'; display?:'name'|'code-name'; load:(query:ReferenceRequest)=>Promise<ReferenceResult>;lineOptions?:()=>QueryOption[] }
export function parseReferenceBatch(text:string) {
  if (text.includes('\t')) throw Error('请只复制一列数据，不支持多列粘贴')
  const lines=text.split(/\r\n|\r|\n/).map(v=>v.trim()).filter(Boolean)
  if (!lines.length) throw Error('请粘贴需要查询的编码或名称')
  if (lines.some(v=>v.length>256)) throw Error('单项最多256个字符')
  const values=[...new Set(lines)]
  if (values.length>1000) throw Error('单次批量查询最多1000项，请分批查询')
  return {values,duplicates:lines.length-values.length}
}
export function referenceBatchReport(values:string[],records:ReferenceRecord[],field:'code'|'name') {
  const counts=new Map<string,number>()
  const key=(value:string)=>value.trim().toLowerCase()
  for(const record of records) counts.set(key(record[field]),(counts.get(key(record[field]))||0)+1)
  return {unmatched:values.filter(v=>!counts.has(key(v))),ambiguous:values.filter(v=>(counts.get(key(v))||0)>1).map(value=>({value,count:counts.get(key(value))!}))}
}
export function splitReferenceBatch(values:string[]):string[][] {
  const chunks:string[][]=[]
  let current:string[]=[]
  for(const value of values) {
    if(current.length && (current.length>=100 || encodeURIComponent(JSON.stringify([...current,value])).length>4000)) {chunks.push(current);current=[]}
    current.push(value)
  }
  if(current.length)chunks.push(current)
  return chunks
}
export function optionReference(title:string,keyField:string,options:QueryOption[]):QueryReference {
  const records=options.map(o=>({value:o.value,code:String(o.value),name:o.label}))
  const namesOnly=['product_line_id','business_product_line_id','organization_id','organization_ids'].includes(keyField)
  return {title,keyField,display:namesOnly?'name':'code-name',keyType:typeof options[0]?.value==='number'?'number':'string',async load(q) {
    if(namesOnly&&q.batch?.field==='code')throw Error('产品线仅支持按名称批量匹配')
    const found=records.filter(r=>q.ids ? q.ids.includes(r.value) : q.batch ? q.batch.values.some(v=>v.toLowerCase()===r[q.batch!.field].trim().toLowerCase()) :
      !q.keyword || (namesOnly?r.name:`${r.code} ${r.name}`).toLowerCase().includes(q.keyword.trim().toLowerCase()))
    return {total:found.length,items:found.slice((q.page-1)*q.pageSize,q.page*q.pageSize)}
  }}
}
