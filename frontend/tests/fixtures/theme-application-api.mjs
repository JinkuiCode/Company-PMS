import archive from './archive-field-linkage.json' with {type:'json'}
import reports from './theme-reports.generated.json' with {type:'json'}

// Only synthetic records and static public field definitions. No fallback network.
export const pages=[
  ['/reports/purchase-progress','采购进度查询','report:purchase:view'],['/reports/inventory','即时库存查询','report:inventory:view'],['/reports/stock-detail','物料收发明细','report:stock-detail:list'],
  ['/project/archive','项目档案','project:archive:view'],['/project/list','项目进度','project:list:view'],['/project/archive-drafts','草稿管理','project:archive:draft:manage'],
  ['/feedback','问题提报','feedback:view'],['/dashboard','仪表盘','dashboard:view'],['/system/user','用户管理','system:user:view'],['/system/role','角色管理','system:role:view'],
  ['/system/parameter','参数设置','system:parameter:view'],['/system/enum','枚举管理','system:enum:view'],['/system/dict','数据字典','system:dict:view'],['/system/field-policy','字段规则','system:field-policy:view'],
  ['/system/product-line','产品线管理','system:product-line:view'],['/system/sync','同步管理','system:sync:view'],['/system/operation-log','操作日志','system:operation-log:view'],
]
const permissions=[...pages.map(p=>p[2]),'report:purchase:export','report:inventory:export','report:stock-detail:export','report:stock-detail:view','feedback:add','feedback:supplement','feedback:handle','feedback:export',
  ...['project:archive','project:list','system:user','system:role','system:enum','system:product-line'].flatMap(p=>['add','edit','delete'].map(a=>p+':'+a)),
  'project:archive:export','project:list:export','system:parameter:edit','system:field-policy:edit','system:dept:add','system:dept:edit','system:dept:delete']
export const themeUser={id:997,username:'theme-test',real_name:'主题验收用户',email:'fixture@example.invalid',mobile:null,dept_id:1,status:1,role_codes:[],permissions,data_scope:4,product_line_ids:[1,2]}
const menuItems=pages.map(([path,name],i)=>({id:i+1,path,menu_name:name,menu_type:'C',icon:'Document',children:[]}))
export const menus=[menuItems.find(x=>x.path==='/dashboard'),
  {id:100,path:'',menu_name:'项目管理',menu_type:'M',icon:'Folder',children:menuItems.filter(x=>x.path.startsWith('/project/'))},
  {id:101,path:'',menu_name:'报表中心',menu_type:'M',icon:'DataAnalysis',children:menuItems.filter(x=>x.path.startsWith('/reports/'))},
  {id:102,path:'',menu_name:'系统管理',menu_type:'M',icon:'Setting',children:menuItems.filter(x=>x.path.startsWith('/system/'))},
  menuItems.find(x=>x.path==='/feedback')]
const time='2026-10-19T09:00:00',lines=[{value:1,label:'8吋Bench'},{value:2,label:'光伏'}]
const labelMap=Object.fromEntries(lines.map(x=>[x.value,x.label]))
const users=[{...themeUser,dept_name:'示例项目部',created_at:time,roles:[{id:1,role_name:'试点角色'}]},{...themeUser,id:998,username:'fixture-reviewer',real_name:'示例部门负责人'}]
const depts=[{id:1,dept_name:'示例项目部',parent_id:0,sort:1,status:1,leader_id:998,leader_name:'示例部门负责人',product_line_ids:[1,2],children:[]}]
const roles=[{id:1,role_name:'试点角色',role_code:'fixture-role',status:1,data_scope:4,remark:'模拟角色',product_line_ids:[1,2],product_line_names:['8吋Bench','光伏']}]
export const archiveRows=Array.from({length:64},(_,i)=>({id:i+1,project_code:`THEME-${String(i+1).padStart(4,'0')}`,project_name:['槽式清洗设备','晶圆清洗设备','单片清洗设备'][i%3],customer:'示例客户',product_line_id:i%2+1,archive_category:1,
  machine_model:1,equipment_series:1,serial_no:`TEST-${i+1}`,quantity:1,quantity_unit:7,manager_id:997,manager_name:themeUser.real_name,is_enabled:1,created_at:time,updated_at:time,
  can_edit:true,can_maintain:false,change_mode:'approval',change_version:'a'.repeat(64),approver_id:998,approver_name:'示例部门负责人',erp_sync_status:'historical',data_origin:'offline_initial',governance_legacy:true}))
const overviewRows=Array.from({length:64},(_,i)=>{
  const completed=[0,25,50,75,100][i%5],receiving=completed===100?0:10,ordering=completed===100?0:5
  return{id:`line1:${i}`,organization_id:1,product_line_name:'8吋Bench',organization_name:'示例组织',project_code:`THEME-${String(i+1).padStart(4,'0')}`,project_name:'',total_lines:100,complete_lines:completed,receiving_lines:receiving,ordering_lines:ordering,not_ordered_lines:100-completed-receiving-ordering,review_lines:0,completion_rate:completed,conversion_rate:completed+receiving}
})
Object.assign(overviewRows[5],{total_lines:2500,complete_lines:2499,receiving_lines:1,ordering_lines:0,not_ordered_lines:0,completion_rate:99.96,conversion_rate:100})
const detailRows=Array.from({length:64},(_,i)=>({id:i+1,project_code:`THEME-${String(i%5+1).padStart(4,'0')}`,product_line_name:'8吋Bench',bill_no:`REQ-TEST-${i+1}`,line_no:i+1,application_date:'2026-10-19',material_code:`MAT-${i+1}`,material_name:'示例物料',specification:'DN25',unit_name:'个',apply_quantity:10,approved_quantity:10,order_quantity:5,received_quantity:0,progress:'ordering',progress_label:'部分下单',document_status:'C',document_status_label:'已审核'}))
const stocks=Array.from({length:64},(_,i)=>({FID:String(i+1),product_line_name:'8吋Bench',Organization:'示例组织',Stock:'示例仓库',MaterialCode:`MAT-${i+1}`,MaterialName:'示例阀门',FSPECIFICATION:'DN25',Brand:'示例品牌',Material:'不锈钢',SupplierNumber:'SUP-TEST',FBaseQty:String(i+1),Unit:'个'}))
const movements=Array.from({length:64},(_,i)=>({row_id:`m:${i}`,row_kind:'movement',product_line_name:'8吋Bench',material_code:'MAT-1',material_name:'示例阀门',bill_no:`DOC-TEST-${i+1}`,bill_seq:i+1,bill_name:'直接调拨单',bill_date:'2026-10-19',stock_name:'示例仓库',unit_name:'个',opening_qty:null,income_qty:6,issue_qty:0,balance_qty:(i+1)*6}))
const feedback={id:1,report_no:'FB-TEST-0001',type_id:1,module_id:1,category_id:1,category_name:'功能异常',impact_id:2,title:'隔离主题测试问题',description:'用于核对提报页面与抽屉样式，不是真实业务问题。',expected_result:'保持主题一致',steps:'主题测试步骤',status_id:1,author_id:997,author_name:themeUser.real_name,handler_name:'示例部门负责人',created_at:time,updated_at:time,version:1,mail_status:'accepted',followups:[],attachments:[],notifications:[]}
const extraEnums={project_status:['进行中','已完成','暂停'],task_status:['未开始','进行中','已完成'],feedback_type:['问题','需求'],feedback_module:['项目档案','项目进度','采购进度查询','即时库存查询','物料收发明细','系统管理','登录与OA集成','通用功能'],feedback_issue_category:['功能异常','数据异常','界面体验'],feedback_request_category:['新增功能','流程优化','报表需求'],feedback_impact:['业务无法继续','影响部分操作','不影响正常使用'],feedback_status:['待受理','处理中','待补充','已排期','已完成','已关闭'],feedback_outcome:['已修复','已交付','使用指导','无需调整'],feedback_cause:['程序逻辑','基础数据','角色权限']}
function enumDefinition(code){
  const known=archive.enums[code]
  const labels=extraEnums[code]||['示例选项']
  const items=known?.items||labels.map((label,i)=>({value:String(i+1),label,status:1,sort:i}))
  return{...known,dict_code:code,dict_name:code,items,label_map:Object.fromEntries(items.map(x=>[x.value,x.label]))}
}
const definitions=Object.keys({...archive.enums,...extraEnums}).map((code,i)=>({id:i+1,dict_code:code,dict_name:code==='archive_category'?'档案类别':code,description:'隔离测试枚举',bindings:['测试字段'],mode:'configurable',allow_add:true,status:1}))
const project={id:1,project_code:'THEME-0001',project_name:'隔离主题测试项目',product_line_id:1,product_line_name:'8吋Bench',archive_id:1,dept_id:1,dept_name:'示例项目部',manager_id:997,manager_name:themeUser.real_name,status:1,total_progress:50,task_count:3,created_at:time,updated_at:time,sheet_fields:{}}
const drafts=new Map()
function paged(items,q){const page=Number(q.get('page')||1),size=Number(q.get('page_size')||50);return{items:items.slice((page-1)*size,page*size),total:items.length,query_version:2,queried_at:time}}
export function fixtureResponse(path,q=new URLSearchParams(),method='GET',body={}){
  if(path==='/auth/me')return themeUser
  if(path==='/my-menus')return menus
  if(path==='/releases/runtime')return{product:'PMS',version:'theme-development',environment:'isolated',page_updates:{}}
  if(path==='/releases/notices')return{items:[],total:0,unread:0}
  if(path==='/releases/versions')return{items:[],total:0}
  if(path==='/report-exports'&&method==='GET')return[]
  if(path==='/reports/purchase/metadata')return reports.purchase
  if(path==='/reports/inventory/metadata')return reports.inventory
  if(path==='/reports/stock-detail/metadata')return reports.stock
  if(path==='/reports/purchase/overview')return{...paged(overviewRows,q),total_lines:overviewRows.reduce((n,row)=>n+row.total_lines,0),complete_lines:overviewRows.reduce((n,row)=>n+row.complete_lines,0),review_lines:0}
  if(path==='/reports/purchase')return paged(detailRows,q)
  if(path==='/reports/inventory')return paged(stocks,q)
  if(path==='/reports/stock-detail')return{...paged(movements,q),openings:[],summary:{...movements[0],income_qty:384,balance_qty:384}}
  if(/^\/reports\/purchase\/\d+$/.test(path))return{request:detailRows[Number(path.split('/').at(-1))-1],orders:[],receipts:[],returns:[],summary:{issues:[]},queried_at:time}
  if(path.startsWith('/reports/')&&(path.endsWith('/options')||path.endsWith('/reference-options')))return{items:[{value:'MAT-1',code:'MAT-1',label:'示例阀门',name:'示例阀门'},{value:1,code:'CK01',label:'示例仓库',name:'示例仓库'}],total:2,has_more:false}
  if(path==='/users/options')return users
  if(path==='/users')return paged(users,q)
  if(path==='/depts/tree'||path==='/depts/options')return depts
  if(path==='/roles'||path==='/roles/options')return roles
  if(path==='/menus/tree'||path==='/menus')return menus
  if(/^\/roles\/\d+\/menus$/.test(path))return{menu_ids:[],version:time}
  if(path==='/product-lines/role-options')return{items:lines}
  if(['/product-lines/options','/product-lines/labels','/form-drafts/archive-create/product-lines'].includes(path))return{options:lines,label_map:labelMap}
  if(path==='/product-lines')return paged(lines.map(x=>({id:x.value,organization_id:x.value,organization_code:`TEST-${x.value}`,organization_name:x.label,display_name:x.label,is_enabled:1,sort:1,updated_at:time})),q)
  if(path==='/product-lines/organizations')return paged(lines.map(x=>({organization_id:x.value,code:`TEST-${x.value}`,name:x.label})),q)
  if(path==='/dicts')return definitions
  if(path.startsWith('/dicts/code/'))return enumDefinition(path.split('/').at(-1))
  if(/^\/dicts\/\d+\/items$/.test(path)){const def=definitions[Number(path.split('/')[2])-1];return enumDefinition(def.dict_code).items.map((item,i)=>({id:i+1,item_value:String(item.value),item_label:item.label,status:1,sort:i,reference_count:i===0?1:0,deletable:i!==0,updated_at:time}))}
  if(path==='/projects/archives/fields')return archive.metadata
  if(path==='/projects/archives/list')return paged(archiveRows,q)
  if(path==='/projects/archives/options')return archiveRows
  if(path==='/projects/archives/regions')return[{value:'demo-province',label:'示例省份',children:[{value:'demo-city',label:'示例城市'}]}]
  if(path==='/offline-archives/initialization-status')return{enabled:false}
  if(path==='/projects/archive-changes')return paged([],q)
  if(/^\/projects\/archive-changes\/\d+\/preview$/.test(path))return{mode:'approval',approver_id:998,approver_name:'示例部门负责人',expected_version:'a'.repeat(64),updates:body.updates,differences:Object.keys(body.updates||{}).map(field=>({field_key:field,field_label:field,before_display:'模拟原值',after_display:String(body.updates[field])}))}
  if(path==='/form-drafts/archive-create'&&method==='GET')return paged([...drafts.values()],q)
  if(path==='/form-drafts/archive-create'&&method==='POST'){const draft={id:body.id,version:(drafts.get(body.id)?.version||0)+1,payload:body.payload,status:'active',updated_at:time};drafts.set(body.id,draft);return draft}
  if(path==='/form-drafts/archive-create/management')return paged([],q)
  if(path==='/archive-draft-management')return paged([],q)
  if(path==='/projects/sheet-fields')return{groups:[],fields:[],policies:[]}
  if(path==='/projects')return paged([project],q)
  if(path==='/projects/1')return project
  if(path==='/projects/1/tasks')return[{id:1,task_name:'示例设计任务',assignee_name:themeUser.real_name,progress:25,status:1,sort:1,plan_start_date:'2026-10-19',plan_end_date:'2026-11-01'}]
  if(path==='/feedback')return paged([feedback],q)
  if(path==='/feedback/1')return feedback
  if(path==='/feedback/statistics')return{total:1,open:1,completed:0,statuses:{1:1},modules:[{module_id:1,issues:1,requests:0,open:1,completed:0}],categories:[{type_id:1,category_id:1,count:1}]}
  if(path==='/dashboard/stats')return{total_projects:3,total_tasks:10,avg_progress:50,status_distribution:{ongoing:2,finished:1,paused:0},dept_distribution:[{dept_name:'示例项目部',count:3}],nearing_deadline:[],recent_projects:[project]}
  if(path==='/parameters')return{items:[{code:'archive.initialization_enabled',name:'档案初始化模式',description:'模拟参数，不会保存',group:'业务设置',value_type:'boolean',value:false,configured:true,sensitive:false,updated_at:time},{code:'mail.smtp_host',name:'SMTP服务器',group:'邮件通知',value_type:'text',value:'fixture.example.invalid',configured:true,sensitive:false,updated_at:time}]}
  if(path==='/field-policies')return{items:archive.metadata.items.map(f=>({...f,module:q.get('module'),group_label:f.group||'基本信息',visible:true,editable:true,required:false,list_available:true,updated_at:time})),groups:[]}
  if(path==='/field-catalog')return paged(archive.metadata.items.map(f=>({module:'project_archive',module_label:'项目档案',field_code:f.field_key,field_name:f.label,value_type:f.value_type,source:'fixture',description:'隔离字段资料',table_name:'fixture',enum_code:f.enum_code||null})),q)
  if(path==='/sync-tasks')return paged([],q)
  if(path==='/operation-logs')return paged([{id:1,created_at:time,module:'project_archive',action:'update',operator_name:themeUser.real_name,entity_name:'模拟档案',success:true,diff_items:[]}],q)
  throw Error(`Unconfigured isolated endpoint: ${method} ${path}`)
}
