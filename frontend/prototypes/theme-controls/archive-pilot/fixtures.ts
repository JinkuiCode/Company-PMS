import { reactive } from 'vue'
import { AxiosError, type AxiosAdapter } from 'axios'
import request from '@/utils/request'
import { matchesConditions, type QueryField } from '@/query-system/core'
import { sortClientRows } from '@/query-system/client-row-sort'
import fixture from '../../../tests/fixtures/archive-field-linkage.json'

export const stats=reactive({listReads:0,memoryDraftWrites:0,blockedWrites:0,unknownReads:[] as string[]})
export const pilotUser={id:101,username:'theme-pilot',real_name:'主题试点用户',dept_id:1,mobile:null,status:1,role_codes:[],permissions:['project:archive:view','project:archive:add','project:archive:edit'],data_scope:1,product_line_ids:[1,2,3]}
const users=[{id:101,username:'theme-pilot',real_name:'主题试点用户'},{id:102,username:'reviewer',real_name:'示例部门负责人'}]
const lines={options:fixture.lines,label_map:Object.fromEntries(fixture.lines.map(item=>[item.value,item.label]))}
const rows=Array.from({length:64},(_,index)=>({
  id:index+1,project_code:`THEME-${String(index+1).padStart(4,'0')}`,project_name:['槽式清洗设备','晶圆清洗设备','单片清洗设备'][index%3],
  product_line_id:index%2+1,archive_category:1,customer:'示例客户'+(index%3+1),manager_id:101,manager_name:'主题试点用户',
  machine_model:1,equipment_series:1,serial_no:`DEMO-${index+1}`,quantity:1,quantity_unit:7,is_enabled:1,
  can_edit:true,can_maintain:false,change_mode:'approval',change_version:'a'.repeat(64),approver_id:102,approver_name:'示例部门负责人',
  erp_sync_status:'historical',data_origin:'offline_initial',erp_sync_policy:'manual',governance_legacy:true,created_at:'2026-10-19T09:00:00',remarks:'仅用于主题试点',
}))
const fields:QueryField[]=fixture.metadata.items.filter(item=>!['is_enabled','product_line_id'].includes(item.field_key)).map(item=>{
  const code='enum_code' in item?item.enum_code:null
  const source=code?(fixture.enums as Record<string,{items:{value:string|number;label:string}[]}>)[code]:null
  return {field:item.field_key,label:item.label,type:source?'enum':item.value_type==='number'?'number':item.value_type==='date'?'date':'text',options:source?.items.map(option=>({...option,value:Number(option.value)}))}
})
fields.push({field:'is_enabled',label:'启用状态',type:'enum',options:[{value:1,label:'启用'},{value:0,label:'禁用'}]})
fields.push({field:'product_line_id',label:'产品线',type:'enum',options:lines.options})
const drafts=new Map<string,any>()
function reject(config:any,message:string){return new AxiosError(message,'PILOT_ONLY',config,undefined,{config,data:{detail:message},headers:{},status:422,statusText:'Unprocessable Entity'})}
const adapter:AxiosAdapter=async config=>{
  const url=new URL(request.getUri(config),'http://isolated.local'),path=url.pathname.replace(/^\/api/,''),method=(config.method??'get').toUpperCase()
  let data:unknown
  const payload=typeof config.data==='string'?JSON.parse(config.data):config.data
  if(path==='/auth/me')data=pilotUser
  else if(path==='/users/options')data=users
  else if(['/product-lines/options','/product-lines/labels','/form-drafts/archive-create/product-lines'].includes(path))data=lines
  else if(path==='/projects/archives/fields')data=fixture.metadata
  else if(path==='/projects/archives/regions')data=[{value:'demo-province',label:'示例省份',children:[{value:'demo-city',label:'示例城市'}]}]
  else if(path.startsWith('/dicts/code/'))data=(fixture.enums as Record<string,unknown>)[path.split('/').at(-1)!]??{items:[],label_map:{}}
  else if(path==='/offline-archives/initialization-status')data={enabled:false}
  else if(path==='/projects/archives/list'){
    stats.listReads++
    const conditions=JSON.parse(url.searchParams.get('filters')||'[]'),sort=JSON.parse(url.searchParams.get('sort')||'[]')
    let found=rows.filter(row=>matchesConditions(row,conditions,fields))
    found=sortClientRows(found,sort,(row,key)=>row[key as keyof typeof row])
    const page=Number(url.searchParams.get('page')||1),size=Number(url.searchParams.get('page_size')||50)
    data={items:found.slice((page-1)*size,page*size),total:found.length,query_version:2}
  }else if(path==='/form-drafts/archive-create'&&method==='GET')data={items:[...drafts.values()],total:drafts.size}
  else if(path==='/form-drafts/archive-create'&&method==='POST'){
    stats.memoryDraftWrites++
    data={id:payload.id,version:(drafts.get(payload.id)?.version||0)+1,status:'active',payload:payload.payload,project_code:payload.payload.project_code,project_name:payload.payload.project_name,updated_at:'2026-10-19T10:00:00'}
    drafts.set(payload.id,data)
  }else if(path.startsWith('/form-drafts/archive-create/')&&method==='GET')data=drafts.get(path.split('/')[3])??null
  else if(path==='/projects/archive-changes')data={items:[],total:0}
  else if(/^\/projects\/archive-changes\/\d+\/preview$/.test(path))data={mode:'approval',approver_id:102,approver_name:'示例部门负责人',expected_version:'a'.repeat(64),updates:payload.updates,differences:Object.keys(payload.updates).map(key=>({field_key:key,field_label:fixture.metadata.items.find(item=>item.field_key===key)?.label||key,before_display:'试点原值',after_display:String(payload.updates[key])}))}
  else if(method!=='GET'){stats.blockedWrites++;throw reject(config,'独立主题试点只保存本地测试草稿，未连接业务后端')}
  else {stats.unknownReads.push(path);throw reject(config,'试点未配置此读取：'+path)}
  return {data,status:200,statusText:'OK',headers:{},config}
}
export function installPilotAdapter(){request.defaults.adapter=adapter}
