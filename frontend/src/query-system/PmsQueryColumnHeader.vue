<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from 'vue'
import { Close, Filter, Search, Sort } from '@element-plus/icons-vue'
import { PmsTextControl, PmsCheckboxControl } from '@/form-system'
import { cloneQuery, operatorsForField, validateConditions, type QueryCondition } from './core'
import type { ColumnQueryContext, ColumnCandidate, ColumnFilter } from './column-filters'
import PmsQueryConditionRow from './PmsQueryConditionRow.vue'
import { columnPopupGroup } from './column-popup'
const props=defineProps<{params:{contextQuery:()=>ColumnQueryContext;field:string;displayName?:string}}>()
const context=computed(()=>props.params.contextQuery()),field=computed(()=>context.value.fields().find(f=>f.field===props.params.field)!)
const opened=ref(false),mode=ref<'values'|'condition'>('values'),keyword=ref(''),items=ref<ColumnCandidate[]>([]),selected=ref<(string|number|null)[]>([]),condition=ref<QueryCondition>(),loading=ref(false),error=ref(''),hasMore=ref(false),page=ref(1),unrestricted=ref(true)
const applied=computed(()=>context.value.filters().find(f=>f.field===props.params.field))
const host=ref<HTMLElement|null>(null),panel=ref<HTMLElement|null>(null),trigger=ref<HTMLButtonElement|null>(null)
const owner=Symbol('column-filter')
let listeningDocument:Document|null=null
let serial=0
async function load(reset=true){if(!field.value)return;const run=++serial;loading.value=true;error.value='';if(reset){page.value=1;items.value=[]}try{const result=await context.value.load(field.value.field,keyword.value,page.value);if(run!==serial||!opened.value)return;items.value=[...items.value,...result.items];hasMore.value=result.hasMore;if(unrestricted.value)selected.value=items.value.map(i=>i.value)}catch{if(run===serial)error.value='候选值加载失败，请重试'}finally{if(run===serial)loading.value=false}}
function outside(event:PointerEvent){
  const path=event.composedPath()
  // Nested reference dialogs are teleported; selectors and calendars mount in this panel.
  if(path.includes(trigger.value!)||path.includes(panel.value!)||path.some(node=>node instanceof Element&&node.classList.contains('pms-query-reference-dialog')))return
  close()
}
function open(){
  if(!field.value||context.value.ready?.()===false)return
  columnPopupGroup.open(owner,close)
  opened.value=true;const current=applied.value;keyword.value='';mode.value=current?.mode||'values';selected.value=current?.mode==='values'?[...current.values]:[];unrestricted.value=!current;condition.value=current?.mode==='condition'?cloneQuery(current.condition):{id:1,field:field.value.field,operator:operatorsForField(field.value).find(op=>op!=='reference')!,value:null,valueEnd:null,schemaVersion:2}
  listeningDocument=host.value?.ownerDocument||null
  listeningDocument?.addEventListener('pointerdown',outside,true)
  listeningDocument?.defaultView?.addEventListener('blur',close)
  void load()
}
function close(){
  opened.value=false;serial++;loading.value=false
  listeningDocument?.removeEventListener('pointerdown',outside,true)
  listeningDocument?.defaultView?.removeEventListener('blur',close);listeningDocument=null
  columnPopupGroup.release(owner)
  items.value=[];selected.value=[];condition.value=undefined;error.value='';keyword.value='';hasMore.value=false
}
onBeforeUnmount(close)
function toggle(value:string|number|null,checked:unknown){unrestricted.value=false;selected.value=checked?[...new Set([...selected.value,value])]:selected.value.filter(v=>v!==value)}
function all(checked:unknown){unrestricted.value=false;for(const item of items.value)toggle(item.value,checked)}
function clear(){context.value.apply(field.value.field,null);close()}
function apply(){
  if(mode.value==='condition'){
    const failures=validateConditions([condition.value!],[field.value]);
    if(Object.keys(failures).length){error.value=Object.values(failures).join('；');return}
  }
  const value:ColumnFilter=mode.value==='values'?{field:field.value.field,mode:'values',values:[...selected.value]}:{field:field.value.field,mode:'condition',condition:cloneQuery(condition.value!)}
  if(mode.value==='values'&&unrestricted.value){clear();return}
  context.value.apply(field.value.field,value);close()
}
</script>
<template>
  <div v-if="field" ref="host" class="pms-column-header" :class="{'is-filtered':applied}">
    <span class="pms-column-header-label" :title="params.displayName||field.label">{{params.displayName||field.label}}</span>
    <el-popover :visible="opened" :persistent="false" placement="bottom" :width="336" trigger="click">
      <template #reference><button ref="trigger" type="button" class="pms-column-filter-trigger" :class="{'is-filtered':applied}" :disabled="context.ready?.()===false" :aria-label="`${field.label}列筛选`" :aria-expanded="opened" @click.stop="opened?close():open()"><el-icon><Filter /></el-icon></button></template>
      <section v-if="opened" ref="panel" class="pms-column-filter-panel pms-query-density" role="dialog" :aria-label="`${field.label}列筛选面板`" @keydown.esc.stop="close">
        <header><strong>{{field.label}}筛选</strong><button type="button" class="pms-button-dismiss pms-column-filter-close" aria-label="关闭筛选" title="关闭筛选" @click="close"><el-icon><Close /></el-icon></button></header>
        <div class="pms-column-filter-sort"><el-button v-if="context.sort" class="pms-button-auxiliary" :icon="Sort" @click="context.sort(field.field,'asc')">升序</el-button><el-button v-if="context.sort" class="pms-button-auxiliary" :icon="Sort" @click="context.sort(field.field,'desc')">降序</el-button><el-button type="warning" plain :disabled="!applied" @click="clear">清除此列</el-button></div>
        <div class="pms-column-filter-tabs"><el-button class="pms-button-auxiliary" :class="{'is-active':mode==='values'}" @click="mode='values'">勾选值</el-button><el-button class="pms-button-auxiliary" :class="{'is-active':mode==='condition'}" @click="mode='condition'">按条件</el-button></div>
        <template v-if="mode==='values'">
          <form class="pms-column-search" @submit.prevent="load()"><PmsTextControl v-model="keyword" size="compact" clearable placeholder="搜索筛选值" aria-label="搜索筛选值" /><el-button type="primary" :icon="Search" :loading="loading" @click="load()">查询</el-button></form>
          <PmsCheckboxControl :model-value="items.length>0&&items.every(i=>selected.includes(i.value))" :indeterminate="items.some(i=>selected.includes(i.value))&&!items.every(i=>selected.includes(i.value))" size="compact" @update:model-value="all">全选已加载值</PmsCheckboxControl>
          <div class="pms-column-filter-values"><PmsCheckboxControl v-for="item in items" :key="JSON.stringify(item.value)" :model-value="selected.includes(item.value)" size="compact" @update:model-value="toggle(item.value,$event)"><span :title="item.label">{{item.label}}</span><span v-if="item.count!=null" class="pms-column-filter-count">{{item.count}}</span></PmsCheckboxControl><span v-if="!items.length&&!loading">暂无匹配值</span></div>
          <el-button v-if="hasMore" class="pms-button-auxiliary" :loading="loading" @click="page++;load(false)">加载更多</el-button>
        </template>
        <PmsQueryConditionRow v-else-if="condition" :condition="condition" :fields="[field]" :append-to="panel" fixed-field prefix="列筛选" @update="condition=$event;error=''" />
        <p v-if="error" role="alert" class="pms-query-error">{{error}}</p>
        <footer><span>仅筛选当前页</span><el-button type="warning" plain @click="close">取消</el-button><el-button class="pms-button-export" :disabled="loading||!!error" @click="apply">应用</el-button></footer>
      </section>
    </el-popover>
  </div>
  <span v-else>{{params.displayName||params.field}}</span>
</template>
<style>
.pms-column-filter-panel .pms-condition-row{grid-template-columns:80px 80px minmax(0,1fr);}
.pms-column-filter-trigger:disabled{opacity:.45;cursor:default;}
.pms-column-header{width:100%;min-width:0;display:flex;justify-content:center;align-items:center;gap:4px;}.pms-column-header-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}
.pms-column-filter-trigger{flex-shrink:0;display:flex;align-items:center;justify-content:center;width:18px;height:20px;border:0;background:none;color:var(--pms-text-muted);padding:0;cursor:pointer;}.pms-column-filter-trigger.is-filtered{color:var(--pms-primary);}.pms-column-filter-trigger:focus-visible{outline:2px solid var(--pms-primary);outline-offset:1px;}
.pms-column-filter-panel header,.pms-column-filter-panel footer{display:flex;align-items:center;gap:6px;justify-content:space-between;}
.pms-column-filter-sort,.pms-column-filter-tabs,.pms-column-search{display:flex;gap:6px;margin:6px 0;}
.pms-column-search>.pms-form-control{flex:1;min-width:0;}
.pms-column-filter-panel .el-button{margin:0;}
.pms-column-filter-close{width:24px;height:24px;padding:0;}
.pms-column-filter-tabs .is-active{color:var(--pms-primary);background:var(--pms-primary-soft);border-color:var(--pms-border);}
.pms-column-filter-values{max-height:230px;min-height:120px;overflow:auto;display:flex;flex-direction:column;gap:4px;padding:6px 0;}
.pms-column-filter-values span[title]{max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.pms-column-filter-count{margin-left:6px;color:var(--pms-text-muted);font-variant-numeric:tabular-nums;}
.pms-column-filter-panel footer{border-top:1px solid var(--pms-border-soft);padding-top:8px;margin-top:8px;}
.pms-column-filter-panel footer>span{margin-right:auto;font-size:11px;color:var(--pms-text-muted);}
.pms-column-filter-panel .pms-query-error{color:var(--pms-danger);font-size:12px;}
</style>
