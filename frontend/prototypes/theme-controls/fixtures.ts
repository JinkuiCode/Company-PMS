import type { QueryField } from '@/query-system/core'
import type { QueryReference } from '@/query-system/reference'
export const productLines = ['8吋Bench', '12吋Bench', '光伏电镀', 'Single', 'HSPM', '研发与长名称产品线测试'].map((label, i) => ({ label, value: i + 1 }))
export const categoryOptions = [{value:1,label:'主机'},{value:2,label:'改造'},{value:3,label:'备件'},{value:4,label:'历史分类（已停用）',disabled:true}]
export const treeData = [{value:'bench',label:'Bench项目部',children:[{value:'b1',label:'8吋设备组'},{value:'b2',label:'12吋设备组'}]},{value:'single',label:'Single项目部',children:[{value:'s1',label:'单片设备组'},{value:'s2',label:'历史小组（已停用）',disabled:true}]},{value:'rd',label:'研发项目部'}]
export const initialRows = Array.from({length:24}, (_,i) => ({
  id:i+1, product_line_id:i%5+1, code:`DEMO-${202601+i}`, name:['槽式清洗设备','晶圆清洗设备','单片处理设备','设备改造项目'][i%4]!,
  customer:['示例客户甲','示例客户乙','示例客户丙'][i%3]!, owner:['李工','陈工','周工'][i%3]!, quantity:i%4+1,
  date:`2026-10-${String(i%19+1).padStart(2,'0')}`, status:i%6===5?'禁用':'启用', remark:'仅用于样稿展示',
}))
export type DemoRow = typeof initialRows[number]
const projectReference:QueryReference = {
  title:'项目档案',keyField:'code',keyType:'string',lineOptions:()=>productLines,
  async load(req) {
    const all=initialRows.filter(r => (!req.ids || req.ids.includes(r.code)) && (!req.line || r.product_line_id===req.line)
      && (!req.keyword || `${r.code} ${r.name}`.includes(req.keyword))
      && (!req.batch || req.batch.values.includes(req.batch.field==='code'?r.code:r.name)))
    return {total:all.length,items:all.slice((req.page-1)*req.pageSize,req.page*req.pageSize).map(r=>({value:r.code,code:r.code,name:r.name,lineName:productLines.find(l=>l.value===r.product_line_id)!.label,status:r.status}))}
  },
}
export const fields:QueryField[] = [
  {field:'code',label:'项目编码',type:'text',reference:projectReference},
  {field:'name',label:'项目名称',type:'text'},
  {field:'product_line_id',label:'产品线',type:'enum',options:productLines},
  {field:'customer',label:'客户名称',type:'text'},
  {field:'owner',label:'负责人',type:'text'},
  {field:'quantity',label:'数量',type:'number'},
  {field:'date',label:'登记日期',type:'date'},
  {field:'status',label:'状态',type:'enum',options:[{value:'启用',label:'启用'},{value:'禁用',label:'禁用'}]},
]
