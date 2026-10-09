<script setup lang="ts">
import {ref} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {PmsFormDrawer,PmsFormField,PmsSelectControl} from '@/form-system'
import {useAuthStore} from '@/stores/auth'
import {useProductLineOptions} from '@/composables/useProductLineOptions'
import request from '@/utils/request'
const props=defineProps<{selectedRows:Array<{id:number;updated_at:string}>}>()
const emit=defineEmits<{changed:[]}>()
const auth=useAuthStore(),lines=useProductLineOptions()
const importing=ref(false),assigning=ref(false),busy=ref(false),selectedLine=ref<number|null>(null)
const payload=ref<any>(null),preview=ref<any>(null),errors=ref<string[]>([]),batchId=ref<number|null>(null)
const assignmentRows=ref<Array<{id:number;expected_updated_at:string}>>([])
function errorMessage(e:any){
 const detail=e?.response?.data?.detail
 if(Array.isArray(detail))return detail.map(v=>v.msg||v.message||'输入无效').join('；')
 if(detail?.errors)return [detail.message,...detail.errors.map((v:any)=>[v.source_id,v.message].filter(Boolean).join('：'))].filter(Boolean).join('；')
 return String(detail?.message||detail||e?.message||'操作失败，请重试')
}
async function chooseFile(event:Event) {
 const file=(event.target as HTMLInputElement).files?.[0];if(!file)return
 payload.value=null;preview.value=null;errors.value=[];batchId.value=null;busy.value=true
 try {
  const data=new FormData();data.append('file',file)
  const prepared:any=await request.post('/offline-archives/workbook',data,{headers:{'Content-Type':'multipart/form-data'}})
  if(prepared.errors.length){errors.value=prepared.errors.map((v:any)=>v.message);return}
  payload.value=prepared.payload
  preview.value=await request.post('/offline-archives/preview',payload.value)
  if(preview.value.already_imported)batchId.value=preview.value.batch_id
  errors.value=preview.value.errors.map((v:any)=>[v.source_id,v.message].filter(Boolean).join('：'))
 } catch(e){errors.value=[errorMessage(e)]}finally{busy.value=false}
}
async function applyImport(){
 if(busy.value||!payload.value||!preview.value||errors.value.length)return
 busy.value=true
 try {
  const result:any=await request.post('/offline-archives/apply',payload.value)
  batchId.value=result.batch_id;ElMessage.success(result.msg);emit('changed')
  payload.value=null
 }catch(e){errors.value=[errorMessage(e)]}finally{busy.value=false}
}
async function rollback(){
 if(!batchId.value||busy.value)return
 try{await ElMessageBox.confirm('新增档案仅在未修改、未引用、未同步时删除；同号补充仅恢复本批补充前的值。任何一条已变更或正在同步时，整批保留。','回退本次导入',{type:'warning'})}catch{return}
 busy.value=true
 try{await request.post('/offline-archives/batches/'+batchId.value+'/rollback');ElMessage.success('该批次已回退');batchId.value=null;preview.value=null;emit('changed')}
 catch(e){errors.value=[errorMessage(e)]}finally{busy.value=false}
}
async function openAssign(){
 if(busy.value)return
 importing.value=false
 assignmentRows.value=props.selectedRows.map(r=>({id:r.id,expected_updated_at:r.updated_at}))
 selectedLine.value=null;errors.value=[];assigning.value=true;await lines.load()
}
async function assign(){
 if(!selectedLine.value||busy.value)return
 busy.value=true
 try{const result:any=await request.post('/offline-archives/assign-product-line',{items:assignmentRows.value,product_line_id:selectedLine.value});ElMessage.success(result.msg);assigning.value=false;emit('changed')}
 catch(e){errors.value=[errorMessage(e)]}finally{busy.value=false}
}
</script>
<template>
 <el-button v-if="auth.hasPermission('project:archive:import') && auth.hasPermission('business:data:all')" size="small"  :disabled="busy" @click="assigning=false;importing=true;errors=[]">期初导入</el-button>
 <el-button v-if="auth.hasPermission('project:archive:assign-line') && auth.hasPermission('business:data:all')" size="small" :disabled="!selectedRows.length" @click="openAssign">分配产品线</el-button>
 <PmsFormDrawer v-model="importing" title="期初项目档案导入" :busy="busy">
  <p>选择已确认的档案修订表。同号档案仅补齐空值，保留已有名称、产品线和金蝶关联；新档案仅归档，不自动同步金蝶。</p>
  <PmsFormField field-id="archive-import-file" label="档案修订表">
   <input id="archive-import-file" type="file" accept=".xlsx" :disabled="busy" @change="chooseFile" />
  </PmsFormField>
  <p v-if="preview">识别 {{ preview.total }} 条记录{{ preview.already_imported ? '，该批次已导入' : '' }}。</p>
  <p v-if="preview && !preview.already_imported && preview.created !== undefined">新增归档 {{ preview.created }} 条，同号补充 {{ preview.updated }} 条，保持不变 {{ preview.unchanged }} 条。</p>
  <div v-if="errors.length" role="alert"><p>请处理以下问题后重新选择文件：</p><ul><li v-for="(error,i) in errors" :key="i">{{ error }}</li></ul></div>
  <p v-if="batchId">导入批次：{{ batchId }}</p>
  <template #secondary><el-button v-if="batchId" :disabled="busy" @click="rollback">回退本次导入</el-button></template>
  <template #footer><el-button :disabled="busy" @click="importing=false">关闭</el-button><el-button type="primary" :disabled="!payload || !preview || errors.length>0 || preview.already_imported" :loading="busy" @click="applyImport">确认导入</el-button></template>
 </PmsFormDrawer>
 <PmsFormDrawer v-model="assigning" title="批量分配产品线" :busy="busy">
  <p>已选 {{ assignmentRows.length }} 条档案，本次操作不会触发金蝶同步。</p>
  <PmsFormField field-id="batch-product-line" label="产品线" required>
   <PmsSelectControl id="batch-product-line" v-model="selectedLine" :options="lines.options.value" :disabled="busy" :loading="lines.loading.value" filterable clearable placeholder="请选择产品线" />
  </PmsFormField>
  <p v-if="lines.failed.value" role="alert">产品线读取失败。<el-button @click="lines.load()">重试</el-button></p>
  <p v-for="(error,i) in errors" :key="i" role="alert">{{ error }}</p>
  <template #footer><el-button :disabled="busy" @click="assigning=false">取消</el-button><el-button type="primary" :disabled="!selectedLine || lines.failed.value" :loading="busy" @click="assign">确认分配</el-button></template>
 </PmsFormDrawer>
</template>
