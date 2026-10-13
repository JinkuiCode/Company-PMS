<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '../../src/stores/auth'
import PmsQueryWorkspace from '../../src/query-system/PmsQueryWorkspace.vue'
const auth = useAuthStore()
auth.user = { id: 9901, username: 'isolated', permissions: [] } as any
const ready = ref(false), loading = ref(true), documentDraft = ref<any[]>([])
const documentQueries = ref<any[]>([]), reportQueries = ref<any[]>([])
const lateFields = ref<any[]>([]), lateQueries = ref(0)
const enumFields=ref<any[]>([{field:'status',label:'状态',type:'enum',options:[]}]),enumQueries=ref(0)
const enumDefaults=[{field:'status',shown:true,operator:'in' as const,value:[1],valueEnd:null}]
const referenceWaiters=ref<Array<(v:any)=>void>>([]),referenceQueries=ref(0)
const referenceFields=ref<any[]>([{field:'project',label:'项目',type:'text',reference:{title:'项目档案',keyField:'code',keyType:'string',load:()=>new Promise(resolve=>referenceWaiters.value.push(resolve))}}])
const referenceDefaults=[{field:'project',shown:true,operator:'reference' as const,value:['P1'],valueEnd:null}]
function releaseReference(){const pending=referenceWaiters.value.splice(0);pending.forEach(resolve=>resolve({items:[{value:'P1',code:'P1',name:'项目'}],total:1}))}
const fields = [{ field: 'code', label: '编码', type: 'text' as const }]
const defaults = [{ field: 'code', shown: true, operator: 'contains' as const, value: null, valueEnd: null }]
const requiredFields = [{ field: 'material', label: '物料', type: 'text' as const, required: true }]
const requiredDefaults = [{ field: 'material', shown: true, operator: 'contains' as const, value: null, valueEnd: null }]
</script>
<template>
  <main style="padding:8px;max-width:1100px">
    <button @click="ready=true">完成依赖加载</button><button @click="loading=false">完成数据加载</button>
    <button @click="lateFields=fields">加载字段目录</button>
    <button @click="enumFields=[{...enumFields[0],options:[{value:1,label:'进行中'}]}]">加载状态枚举</button>
    <button @click="referenceFields=[{...referenceFields[0],label:'项目编码'}]">刷新引用字段</button><button @click="releaseReference">完成引用校验</button>
    <section aria-label="延迟枚举测试"><PmsQueryWorkspace list-key="entry-enum" entry-mode="document" :fields="enumFields" :defaults="enumDefaults" @query="enumQueries++" /><output aria-label="枚举查询次数">{{enumQueries}}</output></section>
    <section aria-label="引用刷新测试"><PmsQueryWorkspace list-key="entry-reference" entry-mode="document" :fields="referenceFields" :defaults="referenceDefaults" @query="referenceQueries++" /><output aria-label="引用查询次数">{{referenceQueries}}</output><output aria-label="引用待处理数">{{referenceWaiters.length}}</output></section>
    <section aria-label="延迟字段测试"><PmsQueryWorkspace list-key="entry-late" entry-mode="document" :fields="lateFields" :defaults="defaults" @query="lateQueries++" /><output aria-label="延迟字段查询次数">{{lateQueries}}</output></section>
    <section aria-label="单据测试"><PmsQueryWorkspace v-model="documentDraft" list-key="entry-document" entry-mode="document" :ready="ready" :loading="loading" :fields="fields" :defaults="defaults" @query="(c:any)=>documentQueries.push(c)" /><output aria-label="单据查询次数">{{documentQueries.length}}</output><output aria-label="单据查询条件">{{JSON.stringify(documentQueries.at(-1))}}</output></section>
    <section aria-label="报表测试"><PmsQueryWorkspace list-key="entry-report" entry-mode="report" :ready="ready" :fields="fields" :defaults="defaults" @query="(c:any)=>reportQueries.push(c)" /><output aria-label="报表查询次数">{{reportQueries.length}}</output></section>
    <section aria-label="必输测试"><PmsQueryWorkspace list-key="entry-required" entry-mode="document" :fields="requiredFields" :defaults="requiredDefaults" /></section>
  </main>
</template>
