export const ARCHIVE_BASIC_ORDER = ['archive_category','project_code','project_name','customer','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no']
interface Field {key:string;label?:string}
export function orderArchiveGroups<T extends Field>(groups:Array<{key:string;label:string;fields:T[]}>) {
  const fields=new Map(groups.flatMap(group=>group.fields).map(field=>[field.key,field]))
  const basic=ARCHIVE_BASIC_ORDER.map(key=>fields.get(key)).filter((field):field is T=>Boolean(field))
  return [{key:'basic',label:'基本信息',fields:basic.map(field=>field.key==='customer'?{...field,label:'客户名称'}:field)},
    ...groups.filter(group=>group.key!=='basic'&&group.key!=='plan').map(group=>({...group,fields:group.fields.filter(field=>!ARCHIVE_BASIC_ORDER.includes(field.key)&&!field.key.startsWith('plan_'))})).filter(group=>group.fields.length)]
}
export function governanceFieldVisible(key:string,record:Record<string,unknown>,creating=false) {
  return !key.startsWith('plan_')&&(key!=='customer_full_name'||(!creating&&Boolean(record.customer_full_name)))
}
export function governanceFieldRequired(policy:{required:boolean;governance_required?:boolean;required_effective_at?:string|null;required_when?:{field:string;values:Array<string|number>}|null},record:Record<string,any>,creating:boolean,original?:Record<string,any>) {
  const when=policy.required_when
  const conditional=Boolean(when&&when.values.some(value=>String(value)===String(record[when.field])))
  const conditionChanged=Boolean(conditional&&original&&when&&String(original[when.field])!==String(record[when.field]))
  if(policy.governance_required&&(creating||record.governance_legacy!==true||conditionChanged))return when?conditional:true
  if(policy.governance_required&&!when)return false
  if(!creating&&!conditionChanged&&policy.required_effective_at&&record.created_at&&new Date(record.created_at).getTime()<new Date(policy.required_effective_at).getTime())return false
  return policy.required||(!policy.governance_required&&conditional)
}
