<script setup>
import { computed, ref, watch, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, FolderOpened, Setting, DataAnalysis, ArrowRight, Close, Search, Refresh, Operation, Download, Collection } from '@element-plus/icons-vue'
import PmsDataList from '../../src/components/PmsDataList.vue'
import PmsTextControl from '../../src/form-system/components/PmsTextControl.vue'
import PmsSelectControl from '../../src/form-system/components/PmsSelectControl.vue'

const rows = [
  ['A-202629','湿法清洗设备','MAT-01028','气动隔膜阀','DN25 / PTFE','只',100,100,45,'部分入库','华新流体、恒源机电'],
  ['A-202629','湿法清洗设备','MAT-01031','高纯 PFA 管','外径 12 mm','米',200,0,0,'未下单','-'],
  ['A-202629','湿法清洗设备','MAT-02016','压力传感器','0-1 MPa / 4-20 mA','个',12,8,0,'部分下单','瑞科仪表'],
  ['A-202630','自动供液系统','MAT-03008','磁力驱动泵','耐腐蚀 / 750 W','台',4,4,0,'待入库','华新流体'],
  ['A-202630','自动供液系统','MAT-04011','液位开关','非接触式 / DC24V','个',16,16,16,'全部入库','瑞科仪表'],
  ['B-202610','HE/EG 改造','MAT-05007','不锈钢快装接头','316L / DN32','只',48,48,24,'部分入库','恒源机电'],
  ['B-202610','HE/EG 改造','MAT-06002','电源模块','DC24V / 10A','个',6,0,0,'未下单','-'],
  ['A-202631','单片清洗机','MAT-07021','PLC 输入模块','16 点数字量','个',8,8,8,'全部入库','德信自动化'],
  ['A-202631','单片清洗机','MAT-08013','伺服驱动器','400 W','套',10,10,0,'待入库','德信自动化'],
  ['A-202632','槽式清洗设备','MAT-09004','加热器','石英 / 3 kW','支',20,12,6,'部分下单','华新流体'],
  ['A-202632','槽式清洗设备','MAT-10003','过滤器滤芯','10 寸 / 0.1 μm','支',60,60,60,'全部入库','华新流体'],
  ['B-202611','设备升级改造','MAT-11002','气动执行器','双作用型','套',24,24,12,'部分入库','恒源机电'],
].map((v,i) => ({ id:i+1, project:v[0], projectName:v[1], material:v[2], name:v[3], spec:v[4], unit:v[5], requested:v[6], ordered:v[7], received:v[8], progress:v[9], supplier:v[10], requestNo:'CGSQ000'+(2631+Math.floor(i/3)), line:i%3+1, requestDate:'2026-09-'+String(10+Math.floor(i/3)).padStart(2,'0'), requestStatus:'已审核', orderDate:v[7] ? '2026-09-15':'-', orderStatus:v[7]?'已审核':'-', receiptDate:v[8]?'2026-09-19':'-', receiptStatus:v[8]?'已审核':'-' }))
const query = ref(''), project = ref(''), supplier = ref(''), status = ref(''), page = ref(1), size = ref(50)
const narrow = ref(window.innerWidth < 700)
function resize() { narrow.value = window.innerWidth < 700 }
window.addEventListener('resize',resize)
onUnmounted(()=>window.removeEventListener('resize',resize))
const selected = ref(null), columnsOpen = ref(false), planOpen = ref(false), planName = ref(''), activePlan = ref('当前查询'), stamp = ref('09:30:00')
const storageKey = 'pms_purchase_mock_plans_v1'
function readPlans() { try { return JSON.parse(localStorage.getItem(storageKey)||'[]') } catch { return [] } }
const plans = ref(readPlans())
const tabs = ['全部','未下单','部分下单','待入库','部分入库','全部入库']
const options = list => list.map(value=>({value,label:value}))
const projectOptions = options([...new Set(rows.map(r=>r.project))])
const supplierOptions = options([...new Set(rows.flatMap(r=>r.supplier.split('、')).filter(v=>v!=='-'))])
const filtered = computed(()=>rows.filter(r=>(!status.value||r.progress===status.value)&&(!project.value||r.project===project.value)&&(!supplier.value||r.supplier.includes(supplier.value))&&(!query.value||[r.project,r.projectName,r.material,r.name,r.requestNo,r.supplier].some(v=>v.toLowerCase().includes(query.value.toLowerCase())))))
const paged = computed(()=>filtered.value.slice((page.value-1)*size.value,page.value*size.value))
watch([query,project,supplier,status,size],()=>page.value=1)
const groups = [
  { label:'物料', fields:[['material','物料编码',126],['spec','规格型号',142],['unit','单位',58]] },
  { label:'采购申请', fields:[['requestNo','申请单号',132],['line','行号',54],['requestDate','申请日期',108],['requestStatus','单据状态',90],['requested','申请数量',90]] },
  { label:'采购订单', fields:[['orderDate','最近下单',108],['orderStatus','单据状态',90],['ordered','下单数量',90],['supplier','供应商',170]] },
  { label:'采购入库', fields:[['receiptDate','最近入库',108],['receiptStatus','单据状态',90],['received','入库数量',90],['remaining','未入库数量',104]] },
]
const visible = ref(['unit','requestDate','requestStatus','requested','orderDate','ordered','supplier','receiptDate','received','remaining'])
const shownGroups = computed(()=>groups.map(g=>({...g,fields:g.fields.filter(f=>visible.value.includes(f[0]))})).filter(g=>g.fields.length))
function value(r,key) { return key==='remaining' ? r.requested-r.received : r[key] }
function tone(s) { return s==='全部入库'||s==='已审核'?'success':s==='未下单'?'neutral':s==='部分下单'?'warning':'info' }
function reset() { query.value='';project.value='';supplier.value='';status.value='';activePlan.value='当前查询' }
function savePlan() { if(!planName.value.trim()) return; const name=planName.value.trim(); const p={name,query:query.value,project:project.value,supplier:supplier.value,status:status.value,size:size.value,visible:[...visible.value]}; plans.value=[...plans.value.filter(v=>v.name!==name),p];localStorage.setItem(storageKey,JSON.stringify(plans.value)); activePlan.value=name;planOpen.value=false;planName.value='';ElMessage.success('查询方案已保存到本机样稿') }
function loadPlan(p) { query.value=p.query;project.value=p.project;supplier.value=p.supplier;status.value=p.status;size.value=p.size;visible.value=[...p.visible];activePlan.value=p.name;page.value=1 }
function refresh() { stamp.value=new Date().toLocaleTimeString('zh-CN',{hour12:false});ElMessage.success('模拟数据已刷新') }
function exportRows() { const table=[['项目编码','申请单号','申请行号','物料编码','物料名称','单位','申请数量','下单数量','入库数量','进度'],...filtered.value.map(r=>[r.project,r.requestNo,r.line,r.material,r.name,r.unit,r.requested,r.ordered,r.received,r.progress])]; const csv='\ufeff'+table.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='采购进度查询-模拟数据.csv';a.click();URL.revokeObjectURL(url) }
const orders = computed(()=>{
  const r=selected.value;if(!r||!r.ordered)return []
  if(r.id===1)return [
    {no:'CGDD0005821',line:1,supplier:'华新流体',qty:40,date:'2026-09-12',receipts:[{no:'CGRK0003168',line:2,date:'2026-09-15',qty:20},{no:'CGRK0003192',line:1,date:'2026-09-18',qty:15}]},
    {no:'CGDD0005846',line:3,supplier:'恒源机电',qty:35,date:'2026-09-14',receipts:[{no:'CGRK0003201',line:4,date:'2026-09-19',qty:10}]},
    {no:'CGDD0005872',line:2,supplier:'华新流体',qty:25,date:'2026-09-17',receipts:[]},
  ]
  if(r.id===10)return [
    {no:'CGDD0005860',line:1,supplier:'华新流体',qty:8,date:'2026-09-14',receipts:[{no:'CGRK0003185',line:1,date:'2026-09-16',qty:2},{no:'CGRK0003205',line:3,date:'2026-09-19',qty:4}]},
    {no:'CGDD0005865',line:2,supplier:'华新流体',qty:4,date:'2026-09-15',receipts:[]},
  ]
  return [{no:'CGDD000'+(5846+r.id),line:1,supplier:r.supplier,qty:r.ordered,date:r.orderDate,receipts:r.received?[{no:'CGRK000'+(3192+r.id),date:r.receiptDate,qty:r.received}]:[]}]
})
rows[0].orderDate='2026-09-17'
const activeOrder = ref(null)
const orderKey = order => `${order.no}/${order.line}`
const receiptRows = computed(()=>orders.value.filter(o=>!activeOrder.value||orderKey(o)===activeOrder.value).flatMap(o=>o.receipts.map(r=>({...r,line:r.line||1,orderNo:o.no,orderLine:o.line}))))
watch(selected,()=>activeOrder.value=null,{flush:'sync'})
const detailButton = ref(null)
function openDetail(r,event) { detailButton.value=event?.currentTarget;selected.value=r;nextTick(()=>document.querySelector('.trace-close')?.focus()) }
function closeDetail(){selected.value=null;nextTick(()=>detailButton.value?.focus())}
</script>

<template>
  <div class="mock-app">
    <aside class="navigation">
      <div class="brand"><span>P</span><b>PMS 管理系统</b></div>
      <div class="nav-item"><el-icon><DataAnalysis/></el-icon>仪表盘</div>
      <div class="nav-item"><el-icon><Setting/></el-icon>系统管理</div>
      <div class="nav-item"><el-icon><FolderOpened/></el-icon>项目管理</div>
      <div class="nav-child">项目档案</div><div class="nav-child">项目进度</div>
      <div class="nav-item report-nav"><el-icon><Document/></el-icon>报表中心</div>
      <div class="nav-child active">采购进度查询</div>
      <div class="nav-bottom">界面样稿 · V2</div>
    </aside>
    <div class="workspace">
      <header class="app-header"><div><span class="breadcrumb">报表中心</span><el-icon><ArrowRight/></el-icon><strong>采购进度查询</strong></div><div><span class="sample-tag">模拟数据 · 不连接金蝶</span><span class="user">系统管理员</span></div></header>
      <main>
        <PmsDataList :show-scrollbar="false">
          <template #toolbar-left>
            <el-dropdown trigger="click"><el-button><el-icon><Collection/></el-icon>{{activePlan}}<span class="down">⌄</span></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item @click="reset">全部采购申请</el-dropdown-item><el-dropdown-item v-for="p in plans" :key="p.name" @click="loadPlan(p)">{{p.name}}</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
            <el-button @click="planOpen=true">保存查询方案</el-button>
          </template>
          <template #toolbar-right>
            <span class="updated">样例时间 {{stamp}}</span><el-button :icon="Refresh" aria-label="刷新模拟数据" title="刷新模拟数据" @click="refresh"/><el-button :icon="Download" @click="exportRows">导出</el-button><el-button :icon="Operation" @click="columnsOpen=true">列设置</el-button>
          </template>
          <template #filters>
            <div class="filters">
              <PmsTextControl v-model="query" clearable aria-label="搜索采购明细" placeholder="项目 / 物料 / 申请单 / 供应商"><template #prefix><el-icon><Search/></el-icon></template></PmsTextControl>
              <PmsSelectControl v-model="project" :options="projectOptions" clearable filterable aria-label="项目" placeholder="全部项目"/>
              <PmsSelectControl v-model="supplier" :options="supplierOptions" clearable filterable aria-label="供应商" placeholder="全部供应商"/>
              <el-button @click="reset">重置</el-button>
            </div>
            <div class="status-tabs" role="group" aria-label="采购进度筛选"><button v-for="tab in tabs" :key="tab" :class="{chosen:(status||'全部')===tab}" :aria-pressed="(status||'全部')===tab" @click="status=tab==='全部'?'':tab">{{tab}}</button><span class="row-grain">一行对应一条申请明细</span></div>
          </template>
          <template #grid>
            <el-table :data="paged" class="pms-dense-table purchase-grid" height="100%" border stripe :tooltip-options="{showAfter:150}" row-key="id" :row-class-name="({row})=>selected?.id===row.id?'current-row':''">
              <el-table-column label="项目 / 物料" :fixed="narrow?false:'left'" align="center">
                <el-table-column prop="project" label="项目编码" width="124" show-overflow-tooltip/>
                <el-table-column prop="name" label="物料名称" width="154" show-overflow-tooltip/>
              </el-table-column>
              <el-table-column v-for="g in shownGroups" :key="g.label" :label="g.label" align="center">
                <el-table-column v-for="f in g.fields" :key="f[0]" :label="f[1]" :width="f[2]" :align="['requested','ordered','received','remaining','line'].includes(f[0])?'right':'left'" show-overflow-tooltip><template #default="{row}"><span :class="{numeric:['requested','ordered','received','remaining'].includes(f[0])}">{{value(row,f[0])}}</span></template></el-table-column>
              </el-table-column>
              <el-table-column label="采购进度" width="110" :fixed="narrow?false:'right'"><template #default="{row}"><span class="state" :class="tone(row.progress)"><i/>{{row.progress}}</span></template></el-table-column>
              <el-table-column label="操作" width="64" fixed="right" class-name="trace-action" align="center"><template #default="{row}"><el-button link type="primary" @click="openDetail(row,$event)">明细</el-button></template></el-table-column>
              <template #empty><div class="empty">没有符合条件的采购明细<el-button link type="primary" @click="reset">清除筛选</el-button></div></template>
            </el-table>
          </template>
          <template #pagination><div class="pagination"><span>共 {{filtered.length}} 条申请明细</span><el-pagination v-model:current-page="page" v-model:page-size="size" :page-sizes="[10,50,100]" :total="filtered.length" layout="prev,pager,next,sizes" background/></div></template>
        </PmsDataList>
      </main>
    </div>
    <section v-if="selected" class="trace-drawer" role="dialog" aria-label="采购关联明细" @keydown.esc="closeDetail">
      <header class="trace-header"><div><span class="eyebrow">{{selected.requestNo}} / 第 {{selected.line}} 行</span><h2>{{selected.name}}</h2><p>申请数量 {{selected.requested}} {{selected.unit}}</p></div><el-button class="trace-close" :icon="Close" aria-label="关闭采购明细" title="关闭" @click="closeDetail"/></header>
      <div class="trace-scroll">
        <section aria-label="关联订单明细"><div class="section-heading"><h3>关联订单明细</h3><span>{{orders.length}} 条 · 数量单位：{{selected.unit}}</span></div>
          <div class="detail-table-scroll"><table class="detail-table orders-table"><thead><tr><th>订单号</th><th>行号</th><th>订单日期</th><th>供应商</th><th>状态</th><th class="number">订单数量</th><th class="number">已入库</th></tr></thead>
            <tbody><tr v-for="o in orders" :key="orderKey(o)" :class="{picked:activeOrder===orderKey(o)}" @click="activeOrder=orderKey(o)"><td><button class="order-link" :aria-pressed="activeOrder===orderKey(o)" @click.stop="activeOrder=orderKey(o)">{{o.no}}</button></td><td>{{o.line}}</td><td>{{o.date}}</td><td>{{o.supplier}}</td><td><span class="state success">已审核</span></td><td class="number">{{o.qty}}</td><td class="number">{{o.receipts.reduce((a,r)=>a+r.qty,0)}}</td></tr>
            <tr v-if="!orders.length"><td colspan="7" class="detail-empty">尚未形成采购订单</td></tr></tbody>
            <tfoot v-if="orders.length"><tr><td colspan="5">合计</td><td class="number">{{selected.ordered}}</td><td class="number">{{selected.received}}</td></tr></tfoot>
          </table></div>
        </section>
        <section aria-label="关联入库明细"><div class="section-heading"><h3>关联入库明细</h3><span>{{receiptRows.length}} 条 · 数量单位：{{selected.unit}}</span></div>
          <div v-if="activeOrder" class="receipt-filter"><span>当前订单：{{activeOrder.replace('/',' / 第 ')}} 行</span><el-button link type="primary" @click="activeOrder=null">查看全部</el-button></div>
          <div class="detail-table-scroll"><table class="detail-table receipts-table"><thead><tr><th>入库单号</th><th>行号</th><th>入库日期</th><th>状态</th><th class="number">入库数量</th><th>来源订单号 / 行号</th></tr></thead>
            <tbody><tr v-for="r in receiptRows" :key="`${r.no}/${r.line}/${r.orderNo}/${r.orderLine}`"><td>{{r.no}}</td><td>{{r.line}}</td><td>{{r.date}}</td><td><span class="state success">已审核</span></td><td class="number">{{r.qty}}</td><td>{{r.orderNo}} / {{r.orderLine}}</td></tr>
            <tr v-if="!receiptRows.length"><td colspan="6" class="detail-empty">{{activeOrder?'此订单暂无入库记录':'暂无关联入库记录'}}</td></tr></tbody>
            <tfoot v-if="receiptRows.length"><tr><td colspan="4">{{activeOrder?'当前订单小计':'合计'}}</td><td class="number">{{receiptRows.reduce((a,r)=>a+r.qty,0)}}</td><td/></tr></tfoot>
          </table></div>
        </section>
      </div><footer class="trace-footer">仅查询，不修改金蝶单据<span>模拟数据</span></footer>
    </section>
    <el-drawer v-model="columnsOpen" title="列设置" size="380px"><p class="muted">项目、物料、进度和操作固定保留</p><section v-for="g in groups" :key="g.label" class="column-group"><h3>{{g.label}}</h3><el-checkbox-group v-model="visible"><el-checkbox v-for="f in g.fields" :key="f[0]" :value="f[0]">{{f[1]}}</el-checkbox></el-checkbox-group></section><template #footer><el-button type="primary" @click="columnsOpen=false">完成</el-button></template></el-drawer>
    <el-dialog v-model="planOpen" title="保存查询方案" width="400px"><PmsTextControl v-model="planName" aria-label="方案名称" placeholder="例如：A-202629 未完成采购" @keyup.enter="savePlan"/><template #footer><el-button @click="planOpen=false">取消</el-button><el-button type="primary" :disabled="!planName.trim()" @click="savePlan">保存</el-button></template></el-dialog>
  </div>
</template>

<style>
body { font-size:13px; } button { cursor:pointer; } .mock-app { display:flex; height:100dvh; overflow:hidden; } .navigation { width:168px;flex-shrink:0;border-right:1px solid var(--pms-border-soft);background:white;position:relative;padding:0 8px; } .brand { height:60px;display:flex;align-items:center;gap:8px;padding:0 8px;margin-bottom:14px;white-space:nowrap; } .brand span { display:grid;place-items:center;width:28px;height:30px;border-radius:6px;color:var(--pms-primary);background:var(--pms-primary-soft);border:1px solid #dedbff;font-weight:600; } .brand b { font-size:14px; } .nav-item { display:flex;gap:10px;align-items:center;height:44px;padding:0 16px;color:var(--pms-text-secondary); } .nav-item .el-icon { font-size:16px; } .nav-child { margin-left:22px;padding:10px 12px;color:var(--pms-text-secondary);border-left:1px solid var(--pms-border-soft);font-size:12px; } .report-nav { color:var(--pms-primary);margin-top:10px; } .nav-child.active { border-radius:6px;background:var(--pms-primary-soft);color:var(--pms-primary);font-weight:600; } .nav-bottom { position:absolute;bottom:20px;left:24px;font-size:11px;color:var(--pms-text-muted); } .workspace { flex:1;min-width:0;display:flex;flex-direction:column; } .app-header { height:60px;background:white;border-bottom:1px solid var(--pms-border-soft);padding:0 24px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-shrink:0; } .app-header>div { display:flex;align-items:center;gap:12px; } .breadcrumb,.user { color:var(--pms-text-secondary);font-size:12px; } .sample-tag { color:var(--pms-warning);background:var(--pms-warning-soft);padding:3px 8px;border-radius:4px;font-size:11px; } main { flex:1;min-height:0;padding:16px; } .updated,.row-grain { color:var(--pms-text-muted);font-size:11px; } .down { margin-left:12px; } .filters { display:flex;gap:8px;padding:12px 0;border-top:1px solid var(--pms-border-soft);flex-wrap:wrap; } .filters>.pms-form-control { width:170px; } .filters>.pms-form-control:first-child { width:294px; } .status-tabs { display:flex;gap:20px;align-items:center;border-bottom:1px solid var(--pms-border-soft);margin-bottom:12px;min-height:40px;flex-wrap:wrap; } .status-tabs button { background:none;border:0;border-bottom:2px solid transparent;padding:8px 0;color:var(--pms-text-secondary);font-size:12px; } .status-tabs button.chosen { color:var(--pms-primary);border-color:var(--pms-primary);font-weight:600; } .row-grain { margin-left:auto; } .purchase-grid { border-radius:6px; } .purchase-grid th { text-align:center!important; } .numeric { font-variant-numeric:tabular-nums; } .state { display:inline-flex;align-items:center;gap:5px;padding:2px 7px;border-radius:20px;font-size:11px;white-space:nowrap;line-height:20px; } .state i { width:5px;height:5px;border-radius:50%;background:currentColor; } .state.success { color:var(--pms-success);background:var(--pms-success-soft); } .state.warning { color:var(--pms-warning);background:var(--pms-warning-soft); } .state.info { color:var(--pms-info);background:var(--pms-info-soft); } .state.neutral { color:var(--pms-text-secondary);background:var(--pms-neutral-soft); } .purchase-grid .trace-action { background:var(--pms-surface-muted)!important; } .pagination { display:flex;align-items:center;justify-content:space-between;padding-top:12px;gap:10px;color:var(--pms-text-secondary);font-size:12px; } .empty { display:flex;flex-direction:column;gap:8px;align-items:center; } .trace-drawer { position:fixed;right:16px;top:76px;bottom:16px;width:520px;max-width:calc(100vw - 32px);background:white;border:1px solid var(--pms-border);border-radius:8px;box-shadow:-8px 0 28px #16203312;z-index:50;display:flex;flex-direction:column; } .trace-header { padding:20px;display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--pms-border-soft);gap:16px; } .trace-header h2 { font-size:17px;margin:5px 0;font-weight:600; } .trace-header p { margin:0;color:var(--pms-text-secondary);font-size:12px; } .eyebrow { font-size:11px;color:var(--pms-text-secondary); } .trace-close { border:0;padding:6px;background:transparent; } .trace-scroll { padding:0 20px 20px;overflow-y:auto;overscroll-behavior:contain;flex:1;min-height:0; } dl { margin:0; } dt { color:var(--pms-text-secondary);font-size:12px; } dd { margin:0;overflow-wrap:anywhere; } .identity { padding:16px 0; } .identity>div { display:grid;grid-template-columns:72px 1fr;align-items:center;gap:12px;margin:6px 0; } .quantity-strip { display:grid;grid-template-columns:repeat(4,1fr);background:var(--pms-bg-soft);border-block:1px solid var(--pms-border-soft);padding:14px 0; } .quantity-strip>div { display:flex;flex-direction:column;gap:5px;padding-left:12px;border-right:1px solid var(--pms-border); } .quantity-strip>div:last-child { border:0; } .quantity-strip span { font-size:11px;color:var(--pms-text-secondary); } .quantity-strip strong { font-size:20px;font-weight:600;font-variant-numeric:tabular-nums; } h3 { font-size:13px;font-weight:600;margin:0; } .section-heading { display:flex;align-items:center;justify-content:space-between;margin:20px 0 12px; } .section-heading>span { font-size:11px;color:var(--pms-text-secondary); } .document-line { display:flex;align-items:center;gap:10px; } .document-line>span { color:var(--pms-text-secondary);font-size:12px; } .compact-info { display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:14px 0; } .compact-info>div { display:flex;gap:12px; } .compact-info>.wide { grid-column:1 / -1; } .request-section { border-bottom:1px solid var(--pms-border-soft); } .order-block { border:1px solid var(--pms-border);border-radius:6px;margin:12px 0 16px;padding:12px; } .order-heading { display:flex;align-items:center;gap:7px;font-size:12px;flex-wrap:wrap; } .order-heading .state { margin-left:auto; } .step { width:20px;height:20px;display:grid;place-items:center;background:var(--pms-neutral-soft);border-radius:4px;color:var(--pms-text-secondary);font-size:11px; } .muted { color:var(--pms-text-secondary);font-size:12px; } .receipt-head { display:flex;justify-content:space-between;border-top:1px solid var(--pms-border-soft);padding:12px 0 8px;gap:8px;color:var(--pms-text-secondary);font-size:11px; } .receipt-table { width:100%;border-collapse:collapse;font-size:12px; } .receipt-table th { background:var(--pms-bg-soft);text-align:left;color:var(--pms-text-secondary);font-weight:500;font-size:11px; } .receipt-table th,.receipt-table td { padding:8px;border-bottom:1px solid var(--pms-border-soft); } .receipt-table td:last-child,.receipt-table th:last-child { text-align:right; } .receipt-table small { display:block;color:var(--pms-text-secondary);margin-top:4px;font-size:11px; } .waiting-receipt { padding:12px;background:var(--pms-bg-soft);color:var(--pms-text-muted);font-size:12px;text-align:center; } .no-orders { display:flex;flex-direction:column;align-items:center;gap:10px;padding:28px;color:var(--pms-text-secondary);font-size:12px; } .no-orders .el-icon { font-size:24px;color:var(--pms-text-muted); } .trace-footer { padding:12px 20px;border-top:1px solid var(--pms-border-soft);font-size:11px;color:var(--pms-text-secondary);display:flex;justify-content:space-between; } .column-group { border-bottom:1px solid var(--pms-border-soft);padding:16px 0; } .column-group h3 { margin-bottom:10px; } .column-group .el-checkbox-group { display:grid;grid-template-columns:1fr 1fr; } .column-group .el-checkbox { margin:0; } @media(max-width:900px) { .navigation { display:none; } .updated,.user,.row-grain { display:none; } .app-header { padding:0 16px; } } @media(max-width:600px) { main { padding:8px; } .app-header { height:52px; } .breadcrumb,.app-header .el-icon { display:none; } .sample-tag { font-size:10px; } .filters>.pms-form-control:first-child { width:100%; } .filters>.pms-form-control { width:calc(50% - 4px); } .status-tabs { gap:14px; } .pagination { flex-wrap:wrap; } .trace-drawer { top:60px;right:8px;bottom:8px;max-width:calc(100vw - 16px); } .pms-data-list-toolbar { flex-wrap:wrap;gap:8px; } .compact-info { grid-template-columns:1fr; } }
.trace-drawer { width:760px; }
.detail-table-scroll { overflow-x:auto;border:1px solid var(--pms-border-soft);border-radius:6px; }
.detail-table { width:100%;min-width:700px;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap; }
.detail-table th { background:var(--pms-bg-soft);color:var(--pms-text-secondary);font-size:11px;font-weight:500;text-align:left; }
.detail-table th,.detail-table td { padding:10px 8px;border-bottom:1px solid var(--pms-border-soft); }
.detail-table tbody tr:last-child td { border-bottom:0; }
.detail-table .number { text-align:right; }
.detail-table tfoot { background:var(--pms-bg-soft);font-weight:600; }
.detail-table tfoot td { border-top:1px solid var(--pms-border-soft);border-bottom:0; }
.orders-table tbody tr:hover { background:var(--pms-bg-soft);cursor:pointer; }
.orders-table tbody tr.picked { background:var(--pms-primary-soft); }
.order-link { padding:0;border:0;background:none;color:var(--pms-primary);font-size:12px; }
.detail-table .detail-empty { text-align:center;padding:26px;color:var(--pms-text-muted); }
.receipt-filter { display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:12px;color:var(--pms-text-secondary);padding:0 0 10px;flex-wrap:wrap; }
</style>
