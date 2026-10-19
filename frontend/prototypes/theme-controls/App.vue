<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, markRaw, nextTick } from 'vue'
import { Search, RefreshLeft, Plus, Setting, Document, Folder, DataAnalysis, ArrowDown, Check, Menu, Edit, Bell, User, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type GridApi } from 'ag-grid-community'
import { PmsTextControl, PmsSelectControl, PmsTreeSelectControl, PmsDateControl, PmsNumberControl, PmsTextareaControl, PmsCheckboxControl, PmsSwitchControl, PmsFormField, PmsFormDrawer } from '@/form-system'
import PmsQueryConditionRow from '@/query-system/PmsQueryConditionRow.vue'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import { cloneQuery, hasConditionValue, isEmpty, matchesConditions, validateConditions, type QueryCondition } from '@/query-system/core'
import { clientColumnCandidates, matchesColumnFilters, type ColumnFilter, type ColumnQueryContext } from '@/query-system/column-filters'
import { columnSortModel, sortClientRows, type ClientRowSort } from '@/query-system/client-row-sort'
import { PMS_GRID_OPTIONS, PAGE_SIZE_OPTIONS } from '@/config/listUi'
import GridEditor from './GridEditor.vue'
import ProgressPreview from './ProgressPreview.vue'
import { THEMES, applyTheme, createThemePreference, normalizeTheme } from './theme.mjs'
import { fields, initialRows, productLines, categoryOptions, treeData } from './fixtures'

ModuleRegistry.registerModules([AllCommunityModule])
let storage:Storage|undefined
try { storage=localStorage } catch { /* The preview remains usable without persistence. */ }
const preference=createThemePreference(storage,'isolated-5184','preview-user')
const initial=new URLSearchParams(location.search).get('theme')
const theme=ref(initial?normalizeTheme(initial):preference.read())
applyTheme(document.documentElement,theme.value)
const active=ref(new URLSearchParams(location.search).get('scene')==='progress'?'progress':'query'), drawer=ref(false), dialog=ref(false), saved=ref(false), scheme=ref('default')
const rows=ref(initialRows.map(row=>({...row}))), page=ref(1), pageSize=ref(50), queryCount=ref(0)
const conditions=ref<QueryCondition[]>([
  {id:1,field:'code',operator:'contains',value:'',valueEnd:null,schemaVersion:2},
  {id:2,field:'product_line_id',operator:'reference',value:[],valueEnd:null,schemaVersion:2},
  {id:3,field:'date',operator:'between',value:null,valueEnd:null,schemaVersion:2},
])
const applied=ref<QueryCondition[]>([]), filters=ref<ColumnFilter[]>([])
const queryErrors=ref<Record<number,string>>({}), sorts=ref<ClientRowSort[]>([])
const matched=computed(()=>rows.value.filter(row=>matchesConditions(row,applied.value,fields)))
const ordered=computed(()=>sortClientRows(matched.value,sorts.value,(row,key)=>row[key as keyof typeof row]))
const snapshot=computed(()=>ordered.value.slice((page.value-1)*pageSize.value,page.value*pageSize.value))
const shown=computed(()=>snapshot.value.filter(row=>matchesColumnFilters(row,filters.value,fields)))
let api:GridApi|undefined
const context:ColumnQueryContext={
  fields:()=>fields, filters:()=>filters.value,
  load:async(field,keyword,p)=>clientColumnCandidates(snapshot.value,fields,filters.value,field,keyword,p),
  apply:(field,filter)=>{filters.value=[...filters.value.filter(f=>f.field!==field),...(filter?[filter]:[])]},
  sort:(field,sort)=>api?.applyColumnState({state:[{colId:field,sort}],defaultState:{sort:null}}),
}
const columns:ColDef[]=[
  {field:'product_line_id',headerName:'产品线',width:145,valueFormatter:p=>productLines.find(l=>l.value===p.value)?.label||'',cellEditor:markRaw(GridEditor),cellEditorParams:{kind:'line'}},
  {field:'code',headerName:'项目编码',width:148,editable:false},
  {field:'name',headerName:'项目名称',width:200,cellEditor:markRaw(GridEditor)},
  {field:'customer',headerName:'客户名称',width:155,editable:false},
  {field:'owner',headerName:'负责人',width:110,editable:false},
  {field:'quantity',headerName:'数量',width:90,cellEditor:markRaw(GridEditor),cellEditorParams:{kind:'number'},cellStyle:{textAlign:'right'}},
  {field:'date',headerName:'登记日期',width:140,cellEditor:markRaw(GridEditor),cellEditorParams:{kind:'date'}},
  {field:'status',headerName:'状态',width:100,editable:false,cellClass:p=>p.value==='启用'?'status-enabled':'status-disabled'},
]
const defaultColDef:ColDef={
  resizable:true, sortable:true, editable:()=>active.value==='grid',
  headerComponent:markRaw(PmsQueryColumnHeader),headerComponentParams:(p:{column:{getColId():string}})=>({field:p.column.getColId(),contextQuery:()=>context}),
  cellClassRules:{'preview-filtered-cell':p=>filters.value.some(f=>f.field===p.colDef.field)},
}
const form=ref({name:'槽式清洗设备',category:null as any,lines:[1,2,6] as any,department:['b1','s1'] as any,date:'2026-10-19' as any,range:['2026-10-01','2026-10-19'] as any,quantity:3 as number|undefined|null,note:'',enabled:true,checked:true})
const emptyName=ref(''), validation=ref('请输入项目名称'), loading=ref(false), formMessage=ref('')
const inlineText=ref('可编辑备注'), inlineEditing=ref(false)
let inlineOriginal=inlineText.value
async function beginInline(){inlineOriginal=inlineText.value;inlineEditing.value=true;await nextTick();document.getElementById('preview-inline')?.focus()}
async function finishInline(cancel=false){if(cancel)inlineText.value=inlineOriginal;inlineEditing.value=false;await nextTick();document.querySelector<HTMLButtonElement>('.inline-value')?.focus()}
function syncThemeUrl(){const url=new URL(location.href);url.searchParams.set('theme',theme.value);history.replaceState(null,'',url)}
function chooseTheme(value:string|number|object){
  theme.value=applyTheme(document.documentElement,String(value))
  if(!preference.write(theme.value)) ElMessage.warning('外观已切换，本次无法记住选择')
  syncThemeUrl()
}
function storageChanged(event:StorageEvent){if(event.key===preference.key){theme.value=applyTheme(document.documentElement,preference.read());syncThemeUrl()}}
onMounted(()=>window.addEventListener('storage',storageChanged))
onBeforeUnmount(()=>window.removeEventListener('storage',storageChanged))
function query(){
  const candidates=conditions.value.filter(c=>hasConditionValue(c)||(c.operator==='between'&&(!isEmpty(c.value)||!isEmpty(c.valueEnd))))
  queryErrors.value=validateConditions(candidates,fields)
  if(Object.keys(queryErrors.value).length)return
  applied.value=cloneQuery(candidates);filters.value=[];page.value=1;queryCount.value++
}
function reset(){conditions.value.forEach(c=>{c.value=c.operator==='reference'?[]:null;c.valueEnd=null});applied.value=[];queryErrors.value={};filters.value=[];page.value=1}
function addCondition(){if(conditions.value.length>=8)return;conditions.value.push({id:Math.max(...conditions.value.map(c=>c.id),0)+1,field:'name',operator:'contains',value:'',valueEnd:null,schemaVersion:2})}
function updateCondition(value:QueryCondition){const index=conditions.value.findIndex(c=>c.id===value.id);conditions.value[index]=value;delete queryErrors.value[value.id]}
function sortChanged(){
  const next=columnSortModel(api?.getColumnState()??[])
  if(JSON.stringify(next)===JSON.stringify(sorts.value))return
  sorts.value=next;filters.value=[];page.value=1
}
function pagination(){filters.value=[]}
function saveDemo(){validation.value=emptyName.value.trim()?'':'请输入项目名称';formMessage.value=validation.value?'请补全标红字段':'样稿校验通过，未写入业务数据'}
let timer:ReturnType<typeof setTimeout>|undefined
function simulateLoading(){loading.value=true;timer=setTimeout(()=>{loading.value=false;ElMessage.success('样稿加载完成')},1500)}
onBeforeUnmount(()=>clearTimeout(timer))
</script>

<template>
  <a class="skip-link" href="#preview-content">跳到内容</a>
  <div class="oa-shell">
    <header class="oa-top"><strong>OA <span>AELsystem</span></strong><div class="oa-search"><el-icon><Search /></el-icon><span>流程 · 搜索</span></div><div class="oa-user"><el-icon><Bell /></el-icon><el-icon><User /></el-icon>演示用户</div></header>
    <aside class="oa-side" aria-label="OA布局示意"><div class="oa-caption">协同办公</div><span v-for="name in ['公司系统','报表','人事','研发项目','售后功能','公共功能']" :key="name"><el-icon><Document /></el-icon>{{name}}</span><span class="oa-active"><el-icon><Folder /></el-icon>PMS</span></aside>
    <section class="pms-shell">
      <aside class="pms-rail"><strong>P</strong><el-tooltip content="项目管理" placement="right"><button aria-label="项目管理"><el-icon><Folder /></el-icon></button></el-tooltip><el-tooltip content="报表中心" placement="right"><button aria-label="报表中心"><el-icon><DataAnalysis /></el-icon></button></el-tooltip><el-tooltip content="系统设置" placement="right"><button aria-label="系统设置"><el-icon><Setting /></el-icon></button></el-tooltip></aside>
      <header class="pms-header"><el-icon><Menu /></el-icon><h1>{{active==='progress'?'采购进度查询':'项目档案'}}</h1><span class="preview-label">控件样稿 · 模拟数据</span><el-dropdown trigger="click" @command="chooseTheme"><el-button class="theme-choice" aria-label="切换外观"><span class="swatch" :style="{background:THEMES[theme as keyof typeof THEMES].brand}"></span>{{THEMES[theme as keyof typeof THEMES].name}}<el-icon><ArrowDown /></el-icon></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="(item,key) in THEMES" :key="key" :command="key"><span class="swatch" :style="{background:item.brand}"></span>{{item.name}}<el-icon v-if="theme===key"><Check /></el-icon></el-dropdown-item></el-dropdown-menu></template></el-dropdown></header>
      <main id="preview-content" class="preview-content">
        <nav class="preview-tabs" aria-label="控件验收场景"><button v-for="item in [{id:'query',name:'查询与引用'},{id:'form',name:'表单与状态'},{id:'grid',name:'表格编辑'},{id:'progress',name:'进度与异常'}]" :key="item.id" :aria-pressed="active===item.id" @click="active=item.id">{{item.name}}</button><span v-if="active==='grid'">双击产品线、项目名称、数量或日期单元格编辑</span></nav>
        <ProgressPreview v-if="active==='progress'" />
        <section v-else-if="active!=='form'" class="list-surface">
          <div class="preview-toolbar pms-query-density"><el-button type="primary" :icon="Plus" @click="drawer=true">新增档案</el-button><el-button :icon="Edit" @click="drawer=true">编辑样稿</el-button><span class="toolbar-spacer"></span><el-button :icon="Document" @click="dialog=true">说明</el-button><el-popover trigger="click" :width="220" :persistent="false"><template #reference><el-button :icon="Setting">列设置</el-button></template><div class="column-settings"><strong>显示字段</strong><PmsCheckboxControl v-for="col in columns" :key="col.field" :model-value="true" disabled>{{col.headerName}}</PmsCheckboxControl><small>样稿固定展示验收字段</small></div></el-popover></div>
          <div class="query-actions pms-query-density"><PmsSelectControl v-model="scheme" :options="[{value:'default',label:'系统默认'},{value:'mine',label:'长名称方案（显示测试）'}]" aria-label="查询方案" size="compact" /><el-button :icon="Setting" @click="dialog=true">方案设置</el-button><el-button type="primary" :icon="Search" @click="query">查询</el-button><el-button :icon="RefreshLeft" @click="reset">重置</el-button><el-button :icon="Plus" @click="addCondition">添加条件</el-button><span class="query-count" aria-live="polite">{{queryCount?`已查询 ${queryCount} 次`:'本地演示数据'}}</span></div>
          <div class="query-conditions pms-query-density"><PmsQueryConditionRow v-for="condition in conditions" :key="condition.id" :condition="condition" :conditions="conditions" :fields="fields" :error="queryErrors[condition.id]" removable prefix="样稿" @update="updateCondition" @remove="conditions=conditions.filter(c=>c.id!==condition.id)" /></div>
          <div class="grid-container ag-theme-quartz pms-form-grid"><AgGridVue style="height:100%;width:100%" theme="legacy" :grid-options="PMS_GRID_OPTIONS" :column-defs="columns" :default-col-def="defaultColDef" :row-data="shown" :get-row-id="p=>String(p.data.id)" :stop-editing-when-cells-lose-focus="true" :row-selection="{mode:'multiRow',enableClickSelection:false}" @grid-ready="api=$event.api" @sort-changed="sortChanged" @cell-value-changed="saved=true" /></div>
          <footer class="list-footer pms-query-density"><span>共 {{matched.length}} 条<span v-if="filters.length"> · 本页显示 {{shown.length}} 条</span><span v-if="saved" class="local-saved"> · 编辑仅在样稿保留</span></span><el-pagination v-model:current-page="page" :page-size="pageSize" :total="matched.length" layout="prev, pager, next" @current-change="pagination" /><PmsSelectControl v-model="pageSize" :options="PAGE_SIZE_OPTIONS.map(value=>({value,label:`${value} 条/页`}))" aria-label="每页条数" size="compact" @update:model-value="page=1;pagination()" /></footer>
        </section>
        <section v-else class="state-surface">
          <div class="state-heading"><h2>输入与选择</h2><el-button :icon="Edit" @click="drawer=true">打开抽屉</el-button></div>
          <div class="state-grid">
            <PmsFormField field-id="preview-name" label="项目名称" required><PmsTextControl id="preview-name" v-model="form.name" size="compact" aria-label="项目名称输入" clearable aria-required="true" /></PmsFormField>
            <PmsFormField field-id="preview-category" label="档案类别" required><PmsSelectControl id="preview-category" v-model="form.category" :options="categoryOptions" filterable clearable placeholder="请选择" size="compact" aria-label="档案类别" /></PmsFormField>
            <PmsFormField field-id="preview-lines" label="产品线多选"><PmsSelectControl id="preview-lines" v-model="form.lines" :options="productLines" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="1" filterable size="compact" aria-label="产品线多选" /></PmsFormField>
            <PmsFormField field-id="preview-tree" label="部门树多选"><PmsTreeSelectControl id="preview-tree" v-model="form.department" :data="treeData" multiple show-checkbox check-strictly collapse-tags collapse-tags-tooltip :max-collapse-tags="1" filterable size="compact" aria-label="部门树多选" /></PmsFormField>
            <PmsFormField field-id="preview-date" label="单个日期"><PmsDateControl id="preview-date" v-model="form.date" size="compact" aria-label="单个日期" /></PmsFormField>
            <PmsFormField field-id="preview-range" label="日期范围"><PmsDateControl id="preview-range" v-model="form.range" type="daterange" size="compact" aria-label="日期范围" start-placeholder="开始日期" end-placeholder="结束日期" /></PmsFormField>
            <PmsFormField field-id="preview-quantity" label="数量"><PmsNumberControl id="preview-quantity" v-model="form.quantity" :min="0" :precision="2" size="compact" aria-label="数量输入" controls-position="right" /></PmsFormField>
            <PmsFormField field-id="preview-empty" label="空选项"><PmsSelectControl id="preview-empty" :model-value="null" :options="[]" filterable size="compact" aria-label="空选项" placeholder="搜索无结果" no-data-text="暂无可选记录" /></PmsFormField>
          </div>
          <div class="state-heading"><h2>反馈与不可编辑状态</h2><el-button :loading="loading" @click="simulateLoading">模拟加载</el-button></div>
          <div class="state-grid">
            <PmsFormField field-id="preview-error" label="校验错误" required :error="validation"><template #default="{describedBy,invalid}"><PmsTextControl id="preview-error" v-model="emptyName" :error="validation" :aria-invalid="invalid" :aria-describedby="describedBy" size="compact" aria-label="校验错误" placeholder="请输入项目名称" /></template></PmsFormField>
            <PmsFormField field-id="preview-readonly" label="只读文本"><PmsTextControl id="preview-readonly" model-value="DEMO-202601" readonly size="compact" aria-label="只读文本" /></PmsFormField>
            <PmsFormField field-id="preview-disabled" label="禁用输入"><PmsTextControl id="preview-disabled" model-value="当前状态不可编辑" disabled size="compact" aria-label="禁用输入" /></PmsFormField>
            <PmsFormField field-id="preview-loading" label="加载选择"><PmsSelectControl id="preview-loading" :model-value="null" :options="[]" loading disabled size="compact" aria-label="加载选择" placeholder="正在加载" /></PmsFormField>
            <PmsFormField field-id="preview-readonly-select" label="只读选择"><PmsSelectControl id="preview-readonly-select" :model-value="1" :options="categoryOptions" readonly size="compact" aria-label="只读选择" /></PmsFormField>
            <PmsFormField field-id="preview-disabled-date" label="禁用日期"><PmsDateControl id="preview-disabled-date" model-value="2026-10-19" disabled size="compact" aria-label="禁用日期" /></PmsFormField>
          </div>
          <div class="state-bottom"><div><PmsCheckboxControl v-model="form.checked" aria-label="启用勾选">启用档案</PmsCheckboxControl><PmsCheckboxControl :model-value="true" disabled>不可修改</PmsCheckboxControl><PmsSwitchControl v-model="form.enabled" aria-label="通知开关" /></div><span class="status-pill success">启用</span><span class="status-pill warning">待审核</span><span class="status-pill danger">校验失败</span></div>
          <div class="state-grid note-grid"><PmsFormField field-id="preview-note" label="长文本"><PmsTextareaControl id="preview-note" v-model="form.note" :rows="3" placeholder="请输入说明" aria-label="长文本" /></PmsFormField><PmsFormField field-id="preview-inline" label="详情行内编辑"><PmsTextControl v-if="inlineEditing" id="preview-inline" v-model="inlineText" size="compact" aria-label="行内备注" @blur="inlineEditing=false" @keydown.enter.prevent="finishInline()" @keydown.esc.prevent.stop="finishInline(true)" /><button v-else class="inline-value" @click="beginInline">{{inlineText}}<el-icon><Edit /></el-icon></button></PmsFormField></div>
          <div class="state-footer"><span role="status" :class="{'is-success':!validation}">{{formMessage}}</span><el-button @click="emptyName='';validation='';formMessage=''">重置</el-button><el-button type="primary" @click="saveDemo">校验样稿</el-button><el-button disabled>禁用操作</el-button><el-button type="danger" plain @click="dialog=true">危险操作示例</el-button></div>
        </section>
      </main>
    </section>
  </div>
  <PmsFormDrawer v-model="drawer" title="新增档案 · 控件样稿"><h3 class="pms-form-drawer__section">基本信息</h3><PmsFormField field-id="drawer-category" label="档案类别" required><PmsSelectControl id="drawer-category" v-model="form.category" :options="categoryOptions" filterable clearable size="compact" aria-label="抽屉档案类别" /></PmsFormField><PmsFormField field-id="drawer-code" label="项目编码"><PmsTextControl id="drawer-code" model-value="保存后生成" readonly size="compact" /></PmsFormField><PmsFormField field-id="drawer-name" label="项目名称" required><PmsTextControl id="drawer-name" v-model="form.name" size="compact" /></PmsFormField><PmsFormField field-id="drawer-line" label="产品线"><PmsSelectControl id="drawer-line" v-model="form.lines" :options="productLines" multiple collapse-tags collapse-tags-tooltip size="compact" aria-label="抽屉产品线" /></PmsFormField><PmsFormField field-id="drawer-quantity" label="数量"><PmsNumberControl id="drawer-quantity" v-model="form.quantity" size="compact" :min="0" /></PmsFormField><PmsFormField field-id="drawer-note" label="说明"><PmsTextareaControl id="drawer-note" v-model="form.note" /></PmsFormField><template #secondary><span class="preview-label">仅模拟，不保存业务数据</span></template><template #footer><el-button @click="drawer=false">取消</el-button><el-button type="primary" @click="drawer=false;ElMessage.success('样稿已确认，未写入业务数据')">确认样稿</el-button></template></PmsFormDrawer>
  <el-dialog v-model="dialog" title="样稿说明" width="480px" destroy-on-close><p>本页使用 PMS 的真实共享控件，展示三套主题及展开、焦点、错误、禁用、只读和编辑状态。</p><p>所有档案均为模拟数据，不连接 PMS 后端，不保存真实查询方案，也不修改业务规则。</p><template #footer><el-button type="primary" @click="dialog=false">知道了</el-button></template></el-dialog>
</template>
