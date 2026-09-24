export const offlineEnumCodes: Record<string,string> = {
 archive_category:'archive_category',machine_model:'archive_machine_model',quantity_unit:'archive_quantity_unit',
 sales_company:'archive_sales_company',legacy_archive_status:'archive_legacy_archive_status',
}
export const offlineArchiveFields: Array<{key:string;label:string;value_type:'text'|'select'|'number'|'date'|'long_text';source_type:'archive'}> = [
 {key:'archive_category',label:'档案类别',value_type:'select',source_type:'archive'},
 {key:'customer_full_name',label:'客户完整名称',value_type:'text',source_type:'archive'},
 {key:'machine_model',label:'机型',value_type:'select',source_type:'archive'},
 {key:'quantity',label:'数量',value_type:'number',source_type:'archive'},
 {key:'quantity_unit',label:'单位',value_type:'select',source_type:'archive'},
 {key:'sales_company',label:'销售公司',value_type:'select',source_type:'archive'},
 {key:'legacy_archive_status',label:'原台账状态',value_type:'select',source_type:'archive'},
 {key:'legacy_code_date',label:'编码日期',value_type:'date',source_type:'archive'},
 {key:'legacy_updated_date',label:'原台账更新日期',value_type:'date',source_type:'archive'},
 {key:'delivery_note',label:'交期说明',value_type:'long_text',source_type:'archive'},
 {key:'remarks',label:'备注',value_type:'long_text',source_type:'archive'},
]
export function normalizeOfflineValue(key:string,value:unknown) {
 if(value===''||value==null)return null
 if(key==='quantity'||offlineEnumCodes[key])return Number(value)
 return value
}
