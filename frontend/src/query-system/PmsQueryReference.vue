<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Search, RefreshLeft, DocumentCopy } from '@element-plus/icons-vue'
import { PmsTextControl, PmsSelectControl, PmsCheckboxControl, PmsTextareaControl } from '@/form-system'
import CustomPagination from '@/components/CustomPagination.vue'
import { parseReferenceBatch, referenceBatchReport, splitReferenceBatch, type QueryReference, type ReferenceRecord, type ReferenceRequest } from './reference'
const props=defineProps<{modelValue:boolean; reference:QueryReference; value:(string|number)[]}>()
const emit=defineEmits<{'update:modelValue':[value:boolean];confirm:[value:(string|number)[]]}>()
const keyword=ref(''),appliedKeyword=ref(''),selected=ref<(string|number)[]>([]),page=ref(1),pageSize=ref(50)
const line=ref<number|null>(null),appliedLine=ref<number|null>(null)
const lineOptions=computed(()=>props.reference.lineOptions?.()||[])
const rows=ref<ReferenceRecord[]>([]),total=ref(0),cache=ref(new Map<string|number,ReferenceRecord>()),host=ref<HTMLElement|null>(null)
const loading=ref(false),error=ref(''),batchOpen=ref(false),batchText=ref(''),batchField=ref<'code'|'name'>('code'),batchError=ref('')
const batch=ref<(ReturnType<typeof referenceBatchReport> & {values:string[];duplicates:number;records:ReferenceRecord[]})|null>(null)
let serial=0
const visible=computed(()=>batch.value ? batch.value.records.slice((page.value-1)*pageSize.value,page.value*pageSize.value) : rows.value)
const selectedRecords=computed(()=>selected.value.map(value=>cache.value.get(value)||{value,code:String(value),name:'记录不可用，请移除后重新选择'}))
const all=computed(()=>visible.value.length>0&&visible.value.every(r=>selected.value.includes(r.value)))
const partial=computed(()=>!all.value&&visible.value.some(r=>selected.value.includes(r.value)))
const unavailable=computed(()=>selected.value.some(value=>!cache.value.has(value)))
const hasLine=computed(()=>[...visible.value,...selectedRecords.value].some(r=>r.lineName!==undefined))
const hasStatus=computed(()=>visible.value.some(r=>r.status!==undefined))
function remember(records:ReferenceRecord[]) {for(const record of records)cache.value.set(record.value,record)}
async function collect(q:Omit<ReferenceRequest,'page'|'pageSize'>,version:number) {
  const records:ReferenceRecord[]=[]
  const queries=q.batch ? splitReferenceBatch(q.batch.values).map(values=>({...q,batch:{field:q.batch!.field,values}})) : [q]
  for(const query of queries) {
    let count=0
    for(let p=1;;p++) {
      if(version!==serial)return null
      const result=await props.reference.load({...query,page:p,pageSize:100})
      if(version!==serial) return null
      if(!result.items.length&&count<result.total) throw Error('引用结果发生变化，请重新查询')
      records.push(...result.items);count+=result.items.length
      if(count>=result.total)break
    }
  }
  return [...new Map(records.map(r=>[r.value,r])).values()]
}
async function loadPage() {
  const version=++serial;loading.value=true;error.value=''
  try {
    const result=await props.reference.load({keyword:appliedKeyword.value,line:appliedLine.value,page:page.value,pageSize:pageSize.value})
    if(version!==serial)return
    rows.value=result.items;total.value=result.total;remember(result.items)
  } catch(e) {if(version===serial)error.value=e instanceof Error?e.message:'引用查询失败，请重试'}
  finally {if(version===serial)loading.value=false}
}
async function open() {
  const version=++serial;loading.value=true;error.value='';cache.value.clear();rows.value=[];total.value=0
  selected.value=[...props.value];keyword.value='';appliedKeyword.value='';line.value=null;appliedLine.value=null;page.value=1;batch.value=null;batchOpen.value=false;batchText.value='';batchError.value=''
  try {
    if(selected.value.length) {const records=await collect({ids:selected.value},version);if(!records)return;remember(records)}
    if(version!==serial)return
    await loadPage()
    await nextTick();host.value?.querySelector<HTMLInputElement>('input')?.focus()
  }catch(e){if(version===serial){error.value=e instanceof Error?e.message:'引用加载失败';loading.value=false}}
}
watch(()=>props.modelValue,opened=>{if(opened)void open();else {++serial;loading.value=false}}, {immediate:true})
function query(){appliedKeyword.value=keyword.value;appliedLine.value=line.value;batch.value=null;page.value=1;batchError.value='';void loadPage()}
function reset(){keyword.value='';line.value=null;batchText.value='';batchField.value='code';query()}
async function queryBatch(){
  let input:ReturnType<typeof parseReferenceBatch>
  try{input=parseReferenceBatch(batchText.value)}catch(e){batchError.value=(e as Error).message;return}
  const version=++serial;loading.value=true;error.value='';batchError.value=''
  try {
    const records=await collect({batch:{field:batchField.value,values:input.values},line:line.value},version)
    if(!records)return
    remember(records);batch.value={...input,records,...referenceBatchReport(input.values,records,batchField.value)}
    page.value=1;total.value=records.length;keyword.value='';appliedKeyword.value=''
  }catch(e){if(version===serial)error.value=(e as Error).message}
  finally{if(version===serial)loading.value=false}
}
function choose(value:string|number,checked:boolean) {selected.value=checked?[...new Set([...selected.value,value])]:selected.value.filter(v=>v!==value)}
function selectPage(checked:boolean){visible.value.forEach(r=>choose(r.value,checked))}
function changePage(){if(!batch.value)void loadPage()}
function close(){emit('update:modelValue',false)}
function confirm(){if(loading.value||error.value||unavailable.value)return;emit('confirm',[...selected.value]);close()}
</script>
<template>
  <el-dialog :model-value="modelValue" :title="`引用${reference.title}`" width="min(820px, calc(100vw - 24px))" class="pms-query-reference-dialog" :style="{maxHeight:'calc(100dvh - 24px)',overflow:'auto'}" align-center append-to-body destroy-on-close :close-on-click-modal="false" @update:model-value="emit('update:modelValue',$event)">
    <div ref="host" class="reference-picker pms-query-density" :aria-busy="loading">
      <form class="reference-toolbar" @submit.prevent="query">
        <PmsTextControl v-model="keyword" size="compact" clearable :prefix-icon="Search" :placeholder="`搜索${reference.title}编码 / 名称`" aria-label="搜索引用记录" />
        <PmsSelectControl v-if="lineOptions.length" v-model="line" :options="lineOptions" size="compact" clearable placeholder="全部可选产品线" aria-label="引用产品线" />
        <el-button type="primary" :icon="Search" native-type="submit">查询</el-button>
        <el-button type="warning" plain :icon="RefreshLeft" @click="reset">重置</el-button>
        <el-button type="primary" plain :icon="DocumentCopy" :aria-pressed="batchOpen" @click="batchOpen=!batchOpen">批量粘贴</el-button>
      </form>
      <section v-if="batchOpen" class="reference-batch" aria-label="批量粘贴查询">
        <div class="reference-batch-input"><PmsTextareaControl v-model="batchText" :rows="3" aria-label="批量查询数据" placeholder="从 Excel 复制一列编码或名称，每行一个值" :error="batchError" /><div class="reference-batch-tools"><PmsSelectControl v-model="batchField" :options="[{value:'code',label:'编码'},{value:'name',label:'名称'}]" size="compact" aria-label="批量匹配字段" /><el-button type="primary" :icon="Search" @click="queryBatch">批量查询</el-button></div></div>
        <p v-if="batchError" role="alert" class="reference-error">{{ batchError }}</p>
        <div v-if="batch" class="reference-batch-report" role="status">
          <span>输入 {{ batch.values.length }} 项 · 匹配 {{ batch.records.length }} 条 · 未匹配 {{ batch.unmatched.length }} 项</span><span v-if="batch.duplicates"> · 重复 {{ batch.duplicates }} 项已合并</span>
          <p v-if="batch.unmatched.length">未匹配：{{ batch.unmatched.join('、') }}</p>
          <p v-if="batch.ambiguous.length">多条匹配，请核对勾选：{{ batch.ambiguous.map(v=>`${v.value}（${v.count}条）`).join('、') }}</p>
        </div>
      </section>
      <p v-if="error" class="reference-error" role="alert">{{ error }}</p>
      <p v-if="selected.length>1000" class="reference-error" role="alert">单个引用条件最多1000条，请减少选择或分批查询</p>
      <div class="reference-scroll" :class="{'is-loading':loading}">
        <table class="reference-table" aria-label="引用记录列表"><thead><tr><th class="reference-selection"><PmsCheckboxControl :model-value="all" :indeterminate="partial" :disabled="loading||!!error" size="compact" aria-label="全选当前页" @update:model-value="selectPage" /></th><th>编码</th><th>名称</th><th v-if="hasLine">产品线</th><th v-if="hasStatus">状态</th></tr></thead>
          <tbody><tr v-for="record in visible" :key="record.value" :class="{'is-selected':selected.includes(record.value)}"><td class="reference-selection"><PmsCheckboxControl :model-value="selected.includes(record.value)" :disabled="loading||!!error" size="compact" :aria-label="`选择${record.code} ${record.name}`" @update:model-value="choose(record.value,$event)" /></td><td :title="record.code">{{ record.code }}</td><td :title="record.name">{{ record.name }}</td><td v-if="hasLine" :title="record.lineName">{{ record.lineName }}</td><td v-if="hasStatus"><span class="pms-status" :class="record.status==='启用'?'pms-status-success':'pms-status-muted'">{{ record.status }}</span></td></tr></tbody>
        </table>
        <div v-if="loading" class="reference-empty" role="status">正在加载引用记录…</div><div v-else-if="!visible.length&&!error" class="reference-empty">没有符合条件的引用记录</div>
      </div>
      <CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" @update:model-value="changePage" @update:page-size="page=1;changePage()" />
      <section class="reference-chosen" aria-label="已选明细"><div class="reference-chosen-heading"><strong>已选明细（{{ selected.length }} 条）</strong><el-button type="warning" text :disabled="!selected.length" @click="selected=[]">清空选择</el-button></div>
        <div v-if="selected.length" class="reference-chosen-scroll"><table class="reference-table" aria-label="已选记录列表"><thead><tr><th>编码</th><th>名称</th><th v-if="hasLine">产品线</th><th class="reference-remove">操作</th></tr></thead><tbody><tr v-for="record in selectedRecords" :key="record.value"><td :title="record.code">{{ record.code }}</td><td :title="record.name">{{ record.name }}</td><td v-if="hasLine">{{ record.lineName }}</td><td class="reference-remove"><el-button type="danger" text :aria-label="`移除${record.code} ${record.name}`" @click="choose(record.value,false)">移除</el-button></td></tr></tbody></table></div><div v-else class="reference-empty-chosen">尚未选择记录</div>
      </section>
    </div>
    <template #footer><div class="reference-footer"><span>已选 {{ selected.length }} 条</span><div><el-button type="warning" plain @click="close">取消</el-button><el-button type="success" :disabled="loading||!!error||unavailable||selected.length>1000" @click="confirm">确认引用</el-button></div></div></template>
  </el-dialog>
</template>
<style scoped>
.reference-picker{min-width:0}.reference-toolbar{display:flex;gap:6px;flex-wrap:wrap;padding-bottom:8px}.reference-toolbar>.pms-form-control{flex:1 1 200px;min-width:0}.reference-toolbar>.el-button{margin:0}
.reference-toolbar>.pms-form-control:nth-child(2){flex:0 1 160px}
.reference-batch{padding-bottom:8px}.reference-batch-input{display:flex;gap:6px}.reference-batch-input>.pms-form-control{flex:1;min-width:0}.reference-batch-tools{display:flex;flex-direction:column;gap:6px;width:112px;flex-shrink:0}.reference-batch-tools>.el-button{margin:0}
.reference-error{color:var(--pms-danger);font-size:12px;margin:4px 0}.reference-batch-report{font-size:12px;margin-top:6px}.reference-batch-report p{margin:4px 0;max-height:64px;overflow:auto;overflow-wrap:anywhere;color:var(--pms-warning)}
.reference-scroll{overflow:auto;max-height:min(240px,30dvh);min-height:140px;border:1px solid var(--pms-border);border-radius:var(--pms-radius-sm)}.is-loading{opacity:.65}
.reference-table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:13px}.reference-table th{position:sticky;top:0;z-index:1;height:30px;text-align:center;background:var(--pms-surface-muted);font-size:12px;color:var(--pms-text-secondary);font-weight:600}.reference-table td{height:32px;padding:0 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;border-top:1px solid var(--pms-border-soft)}.reference-table .reference-selection{width:36px;padding:0 8px}.is-selected td{background:var(--pms-primary-soft)}
.reference-empty{padding:32px 8px;text-align:center;font-size:12px;color:var(--pms-text-muted)}.reference-chosen{border-top:1px solid var(--pms-border-soft);padding-top:6px;margin-top:8px}.reference-chosen-heading{display:flex;justify-content:space-between;align-items:center;padding-bottom:4px;font-size:12px}.reference-chosen-scroll{max-height:126px;overflow:auto;border:1px solid var(--pms-border);border-radius:var(--pms-radius-sm)}.reference-chosen-scroll th{background:var(--pms-primary-soft)}.reference-remove{width:60px;text-align:center}.reference-empty-chosen{font-size:12px;color:var(--pms-text-muted);padding:8px 0}.reference-footer{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px}.reference-footer>div{display:flex;gap:8px}.reference-footer .el-button{margin:0}
@media(max-width:500px){.reference-table{min-width:560px}.reference-toolbar>.pms-form-control{flex-basis:100%}}
</style>
<style>
.pms-query-reference-dialog .pms-form-control--binary:focus-within:not(.is-disabled){outline:none}
.pms-query-reference-dialog .pms-form-control--binary:has(:focus-visible):not(.is-disabled){outline:2px solid var(--pms-form-control-border-focus);outline-offset:2px}
</style>
