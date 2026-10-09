<script setup lang="ts">
import {ref,watch} from 'vue'
import request from '@/utils/request'
const props=defineProps<{archiveId:number}>()
const source=ref<any>(null),loading=ref(false),failed=ref(false)
let version=0
async function load(){
 const current=++version
 source.value=null;failed.value=false;loading.value=true
 try{
  const result=await request.get('/offline-archives/archives/'+props.archiveId+'/source')
  if(current===version)source.value=result
 }catch{if(current===version)failed.value=true}
 finally{if(current===version)loading.value=false}
}
watch(()=>props.archiveId,load,{immediate:true})
</script>
<template>
 <section v-if="loading || failed || source" class="archive-source" aria-label="原表来源">
  <h3 class="archive-source-title">原表来源</h3>
  <p v-if="loading">正在读取来源…</p>
  <p v-else-if="failed" role="alert">来源读取失败。<el-button size="small" @click="load">重试</el-button></p>
  <template v-else-if="source">
   <p>批次 {{ source.batch_id }} · 追溯 ID {{ source.source_id }}</p>
   <p>{{ source.source_sheet }} · 原表第 {{ source.source_row }} 行</p>
   <p>原项目编号：{{ source.original_code }}</p>
   <p v-if="source.operation">本批处理：{{ source.operation === 'updated' ? '同号补充' : source.operation === 'unchanged' ? '保留原档案' : '新增归档' }}</p>
  </template>
  <p v-else>暂无原表来源记录</p>
 </section>
</template>


<style scoped>
.archive-source { padding: 8px 0; font-size: 12px; line-height: 1.5; color: var(--pms-text-secondary); border-bottom: 1px solid var(--pms-border-soft); }
.archive-source-title { margin: 0 0 6px; font-size: 12px; font-weight: 700; color: var(--pms-text); }
.archive-source p { margin: 4px 0; overflow-wrap: anywhere; }
</style>
