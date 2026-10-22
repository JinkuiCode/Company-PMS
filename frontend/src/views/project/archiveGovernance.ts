import {reconcileArchiveLinkedFields, type ArchiveFieldLinkage} from './archiveFieldLinkage.ts'
export const ARCHIVE_BASIC_ORDER = ['archive_category','project_code','project_name','customer','sales_company','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no']
interface Field {key:string;label?:string}
export function orderArchiveGroups<T extends Field>(groups:Array<{key:string;label:string;fields:T[]}>) {
  const fields=new Map(groups.flatMap(group=>group.fields).map(field=>[field.key,field]))
  const basic=ARCHIVE_BASIC_ORDER.map(key=>fields.get(key)).filter((field):field is T=>Boolean(field))
  return [{key:'basic',label:'基本信息',fields:basic.map(field=>field.key==='customer'?{...field,label:'客户名称'}:field)},
    ...groups.filter(group=>group.key!=='basic'&&group.key!=='plan').map(group=>({...group,fields:group.fields.filter(field=>!ARCHIVE_BASIC_ORDER.includes(field.key)&&!field.key.startsWith('plan_'))})).filter(group=>group.fields.length)]
}
export function governanceFieldVisible(key:string,record:Record<string,unknown>,creating=false,policy?:{form_hidden?:boolean;form_visible_when?:{field:string;values:Array<string|number>}|null}) {
  if(policy?.form_hidden)return false
  const when=policy?.form_visible_when
  if(when&&!when.values.some(value=>String(value)===String(record[when.field])))return false
  return !key.startsWith('plan_')&&(key!=='customer_full_name'||(!creating&&Boolean(record.customer_full_name)))
}
export function governanceFieldRequired(policy:{required:boolean;governance_required?:boolean;required_effective_at?:string|null;required_when?:{field:string;values:Array<string|number>}|null},record:Record<string,any>,creating:boolean,original?:Record<string,any>) {
  const when=policy.required_when
  const conditional=Boolean(when&&when.values.some(value=>String(value)===String(record[when.field])))
  if(when&&!conditional)return false
  const conditionChanged=Boolean(conditional&&original&&when&&String(original[when.field])!==String(record[when.field]))
  if(policy.governance_required&&(creating||record.governance_legacy!==true||conditionChanged))return when?conditional:true
  if(policy.governance_required&&!when)return false
  if(!creating&&!(policy.governance_required&&conditionChanged)&&policy.required_effective_at&&record.created_at&&new Date(record.created_at).getTime()<new Date(policy.required_effective_at).getTime())return false
  return policy.required
}

export interface ArchiveFormProjection {
  field_key?:string
  visible?:boolean
  editable?:boolean
  form_hidden?:boolean
  form_visible_when?:{field:string;values:Array<string|number>}|null
  default_value?:unknown
}
/** Use only when initializing a genuinely new form, never on restore or edit. */
export function archiveNewFormDefaults(fields:ArchiveFormProjection[]) {
  return Object.fromEntries(fields.filter(field=>field.visible&&field.editable&&field.field_key
    &&Object.hasOwn(field,'default_value')).map(field=>[field.field_key!,field.default_value]))
}
export function archiveCreateFieldIncluded(key:string,values:Record<string,unknown>,policy?:ArchiveFormProjection,serialCorrection=false,preserveRegional=false,explicitlyEdited=false) {
  if(policy?.visible===false||policy?.editable===false)return false
  if(governanceFieldVisible(key,values,true,policy)||(key==='serial_no'&&serialCorrection))return true
  // Regional hiding is presentation only. Preserve meaningful input/history,
  // including a copied draft; never emit a blank initializer over hidden history.
  const regional=Boolean(policy?.form_hidden||policy?.form_visible_when)
  if(regional&&explicitlyEdited&&values[key]!==undefined)return true
  return preserveRegional&&regional&&values[key]!==null&&values[key]!==undefined&&values[key]!==''
}

/** Preserve only a regionally hidden historical series; ordinary visible linkage is unchanged. */
export function reconcileArchiveFormLine(metadata:ArchiveFieldLinkage|null,values:Record<string,unknown>,policy?:ArchiveFormProjection) {
  const original=values.equipment_series
  const hidden=Boolean(policy?.form_visible_when&&!governanceFieldVisible('equipment_series',values,false,policy))
  const cleared=reconcileArchiveLinkedFields(metadata,values)
  const seriesCorrection=hidden&&cleared.includes('equipment_series')
  if(seriesCorrection)values.equipment_series=original
  return {seriesCorrection,cleared:cleared.filter(key=>!seriesCorrection||key!=='equipment_series')}
}

/** Presentation-only parity with the bounded owner-maintenance service.
 * The server still checks permission, provenance, version and every field.
 * This does not mark a record historical for required-field compatibility.
 */
export function preservesLegacyManagerAddress(
  maintenance: boolean, original: Record<string, any> | null | undefined,
  values: Record<string, any>, updates: Record<string, unknown>,
): boolean {
  if (!maintenance || !original || original.can_maintain !== true || original.is_enabled !== 1
    || original.data_origin !== 'kingdee_initial' || original.governance_legacy !== true) return false
  const keys = Object.keys(updates)
  if (keys.length !== 1 || keys[0] !== 'manager_id' || !Number.isInteger(updates.manager_id)
    || Number(updates.manager_id) <= 0 || updates.manager_id === original.manager_id
    || updates.manager_id !== values.manager_id) return false
  return ['address_province', 'address_city', 'address_detail']
    .every(key => (values[key] ?? '') === (original[key] ?? ''))
}
