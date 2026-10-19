<script setup lang="ts">
import { ref } from 'vue'
import { CircleCheck, Warning, CircleClose, InfoFilled } from '@element-plus/icons-vue'

const rows = [
  { code:'DEMO-P001', line:'8吋Bench', total:24, pending:24, partial:0, waiting:0, complete:0, review:0, errors:0, note:'尚未开始' },
  { code:'DEMO-P002', line:'8吋Bench', total:40, pending:15, partial:5, waiting:10, complete:10, review:0, errors:0, note:'前期推进' },
  { code:'DEMO-P003', line:'12吋Bench', total:80, pending:5, partial:5, waiting:20, complete:50, review:0, errors:0, note:'持续推进' },
  { code:'DEMO-P004', line:'光伏电镀', total:32, pending:0, partial:0, waiting:0, complete:32, review:0, errors:0, note:'已完成' },
  { code:'DEMO-P005', line:'Single', total:80, pending:3, partial:5, waiting:20, complete:50, review:2, errors:0, note:'2行待核对' },
  { code:'DEMO-P006', line:'HSPM', total:50, pending:7, partial:5, waiting:15, complete:20, review:3, errors:1, note:'1行已确认错误' },
  { code:'DEMO-P007', line:'8吋Bench', total:30, pending:0, partial:0, waiting:0, complete:30, review:0, errors:0, note:'1行超量入库', over:1 },
  { code:'DEMO-P008', line:'12吋Bench', total:10000, pending:0, partial:0, waiting:4, complete:9996, review:0, errors:0, note:'尚有4行待入库' },
]
const countFields = [{key:'total',label:'申请行数'}] as const
const rates = [{key:'receipt',label:'申请行入库率'},{key:'conversion',label:'申请行转单率'}] as const
type Row = typeof rows[number]
type Rate = typeof rates[number]['key']
function ratio(row:Row, kind:Rate){return (row.complete+(kind==='conversion'?row.waiting:0))/row.total*100}
function tone(row:Row, kind:Rate){const n=row.complete+(kind==='conversion'?row.waiting:0);return n===row.total?'complete':n===0?'empty':n/row.total<.5?'early':'active'}
function progressLabel(row:Row, kind:Rate){const stage={empty:'尚未开始',early:'前期推进',active:'持续推进',complete:'已完成'}[tone(row,kind)];return `${stage}，${row.complete+(kind==='conversion'?row.waiting:0)} / ${row.total} 行，${Number(ratio(row,kind).toFixed(2))}%`}
const detail=ref<{title:string;message:string;level:'warning'|'danger'}|null>(null)
function showDetail(row:Row, kind:'review'|'error'|'over'){
  const info={
    review:{title:'数据待核对',message:`${row.review}条申请行的单据关联或数量换算待核实。这些行计入总申请行数，不计入入库率、转单率的分子。${row.errors?'其中1条已确认存在错误，右侧单独标红；不重复计入申请行数。':''}`,level:'warning'},
    error:{title:'已确认的数据错误',message:'示例：1条申请行的订单单位换算关系错误，暂时无法可靠核对。这一条包含在待核对行内；错误数字单独标红，进度条仍按完成比例采用红、黄、绿分段。',level:'danger'},
    over:{title:'超量入库提醒',message:'示例：订单数量10，净入库数量11。申请行已全部转单、入库，两个进度均为100%；超量入库单独以琥珀色提醒。此处仅展示配色方案，不新增正式报表的异常判断规则。',level:'warning'},
  } as const
  detail.value={...info[kind],title:`${row.code} · ${info[kind].title}`}
}
</script>

<template>
  <section class="progress-sample list-surface" aria-label="进度与异常配色样稿">
    <div class="progress-sample-heading"><h2>采购进度 · 总进度</h2><span>模拟数据</span></div>
    <div class="progress-key" aria-label="颜色含义">
      <span class="key-label">进度</span>
      <span><i class="key-dot early"></i>0%至不足50%</span>
      <span><i class="key-dot active"></i>50%至不足100%</span>
      <span><i class="key-dot complete"></i>已完成</span>
      <span class="key-divider"></span>
      <span class="key-label">异常</span>
      <span class="semantic-warning"><el-icon><Warning /></el-icon>待核对 / 提醒</span>
      <span class="semantic-danger"><el-icon><CircleClose /></el-icon>已确认错误</span>
    </div>
    <div class="progress-table-scroll" tabindex="0" aria-label="采购进度示例表格，可横向滚动">
      <table class="progress-table">
        <colgroup><col style="width:110px"><col style="width:120px"><col v-for="rate in rates" :key="rate.key" style="width:170px"><col v-for="field in countFields" :key="field.key" style="width:80px"><col style="width:80px"><col style="width:80px"><col style="width:152px"></colgroup>
        <thead><tr><th>产品线</th><th>项目编码</th><th v-for="rate in rates" :key="rate.key">{{rate.label}}</th><th v-for="field in countFields" :key="field.key">{{field.label}}</th><th>待核对</th><th>数据错误</th><th>提示</th></tr></thead>
        <tbody><tr v-for="row in rows" :key="row.code" :data-project="row.code">
          <td>{{row.line}}</td><td class="sample-project-code">{{row.code}}</td>
          <td v-for="rate in rates" :key="rate.key"><div class="sample-rate" :data-rate="rate.key" :data-tone="tone(row,rate.key)" :title="progressLabel(row,rate.key)"><span class="sample-rate-track" role="progressbar" :aria-label="row.code+' '+rate.label" :aria-valuenow="ratio(row,rate.key)" :aria-valuemin="0" :aria-valuemax="100" :aria-valuetext="progressLabel(row,rate.key)"><span class="sample-rate-fill" :style="{width:ratio(row,rate.key)+'%'}"></span></span><span class="sample-rate-number">{{ratio(row,rate.key).toFixed(1)}}%</span></div></td>
          <td v-for="field in countFields" :key="field.key" class="sample-number">{{row[field.key]||''}}</td>
          <td class="sample-number"><button v-if="row.review" class="sample-indicator warning" :aria-label="row.code+' 待核对 '+row.review+'行'" @click="showDetail(row,'review')"><el-icon><Warning /></el-icon>{{row.review}}</button></td>
          <td class="sample-number"><button v-if="row.errors" class="sample-indicator danger" :aria-label="row.code+' 已确认错误 '+row.errors+'行'" @click="showDetail(row,'error')"><el-icon><CircleClose /></el-icon>{{row.errors}}</button></td>
          <td><button v-if="row.over" class="sample-note semantic-warning" @click="showDetail(row,'over')"><el-icon><Warning /></el-icon>{{row.note}}</button><span v-else-if="row.errors" class="sample-note semantic-danger"><el-icon><CircleClose /></el-icon>{{row.note}}</span><span v-else-if="row.review" class="sample-note semantic-warning">{{row.note}}</span><span v-else-if="row.complete===row.total" class="sample-note semantic-success"><el-icon><CircleCheck /></el-icon>{{row.note}}</span><span v-else class="sample-note">{{row.note}}</span></td>
        </tr></tbody>
      </table>
    </div>
    <div class="compact-indicators" aria-label="窄屏异常指标示例"><span>异常数字</span><button class="sample-indicator warning" @click="showDetail(rows[4]!,'review')"><el-icon><Warning /></el-icon>待核对 2</button><button class="sample-indicator danger" @click="showDetail(rows[5]!,'error')"><el-icon><CircleClose /></el-icon>已确认错误 1</button></div>
    <div class="progress-sample-notes"><span><el-icon><InfoFilled /></el-icon>异常数字可点击查看原因；三种主题共用同一套状态色。</span><span>最后一行实际入库率99.96%，显示四舍五入为100.0%，仍保留进行中色。</span></div>
    <footer class="progress-sample-footer"><span>共 {{rows.length}} 个示例项目</span><span>入库率：已完成行 ÷ 申请行数 · 转单率：（待入库＋已完成）行 ÷ 申请行数</span></footer>
  </section>
  <el-dialog :model-value="Boolean(detail)" :title="detail?.title" width="520px" destroy-on-close @update:model-value="!$event&&(detail=null)"><p class="sample-detail" :class="detail?.level"><el-icon v-if="detail?.level==='danger'"><CircleClose /></el-icon><el-icon v-else><Warning /></el-icon>{{detail?.message}}</p><template #footer><el-button type="primary" @click="detail=null">知道了</el-button></template></el-dialog>
</template>

<style scoped>
.progress-sample{--progress-empty:#c83434;--progress-early:#c83434;--progress-active:#b68b00;--progress-complete:#087e65;gap:0;}
.progress-sample-heading{display:flex;align-items:center;gap:12px;min-height:30px;flex-shrink:0;}
.progress-sample-heading h2{margin:0;font-size:13px;font-weight:600;}.progress-sample-heading>span{margin-left:auto;color:var(--pms-text-muted);font-size:11px;}
.progress-key{display:flex;align-items:center;flex-wrap:wrap;gap:8px 14px;padding:8px 0 10px;flex-shrink:0;font-size:12px;border-bottom:1px solid var(--pms-border-soft);color:var(--pms-text-secondary);}
.progress-key>span{display:inline-flex;align-items:center;gap:5px;}.progress-key .key-label{color:var(--pms-text);font-weight:500;}.key-dot{display:inline-block;width:16px;height:6px;border-radius:3px;}.key-dot.empty{background:var(--progress-empty);}.key-dot.early{background:var(--progress-early);}.key-dot.active{background:var(--progress-active);}.key-dot.complete{background:var(--progress-complete);}.progress-key .key-divider{height:12px;width:1px;background:var(--pms-border);}
.progress-table-scroll{min-height:0;flex:1;overflow:auto;margin-top:8px;border:1px solid var(--pms-border);border-radius:4px;}
.progress-table{border-collapse:separate;border-spacing:0;table-layout:fixed;width:100%;min-width:1012px;font-size:13px;font-variant-numeric:tabular-nums;}
.progress-table th{position:sticky;top:0;z-index:1;background:var(--pms-surface-muted);color:var(--pms-text-secondary);height:30px;padding:0 8px;text-align:center;font-weight:500;border-bottom:1px solid var(--pms-border);white-space:nowrap;}
.progress-table td{height:32px;padding:0 8px;border-bottom:1px solid var(--pms-border-soft);border-right:1px solid var(--pms-border-soft);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.progress-table td:last-child{border-right:0;}.progress-table tbody tr:last-child td{border-bottom:0;}.progress-table tr:hover td{background:var(--preview-row-hover);}.sample-project-code{color:var(--pms-text);}.sample-number{text-align:right;}
.sample-rate{display:flex;align-items:center;gap:8px;}.sample-rate-track{display:block;height:6px;flex:1;min-width:44px;background:var(--pms-border-soft);border-radius:3px;overflow:hidden;}.sample-rate-fill{display:block;height:100%;background:var(--progress-active);border-radius:inherit;}.sample-rate[data-tone=empty] .sample-rate-fill{background:var(--progress-empty);}.sample-rate[data-tone=early] .sample-rate-fill{background:var(--progress-early);}.sample-rate[data-tone=complete] .sample-rate-fill{background:var(--progress-complete);}.sample-rate-number{min-width:48px;text-align:right;font-size:12px;color:var(--pms-text);}
.sample-rate[data-tone=empty] .sample-rate-number{color:var(--progress-empty);}
.sample-indicator{border:1px solid transparent;display:inline-flex;align-items:center;justify-content:flex-end;gap:5px;min-width:42px;min-height:24px;padding:0 6px;border-radius:3px;background:transparent;font:inherit;font-size:12px;cursor:pointer;}.sample-indicator.warning{color:var(--pms-warning);background:var(--pms-warning-soft);}.sample-indicator.danger{color:var(--pms-danger);background:var(--pms-danger-soft);}.sample-indicator:hover{border-color:currentColor;}.sample-note{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--pms-text-secondary);}.semantic-warning{color:var(--pms-warning);}.semantic-danger{color:var(--pms-danger);}.semantic-success{color:var(--pms-success);}button.sample-note{font-family:var(--pms-font);border:0;background:transparent;cursor:pointer;padding:0;}button.sample-note:hover{text-decoration:underline;}
.progress-sample-notes{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 18px;padding:9px 0;color:var(--pms-text-secondary);font-size:11px;line-height:1.7;}.progress-sample-notes>span{display:inline-flex;align-items:center;gap:5px;}.progress-sample-footer{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;min-height:26px;border-top:1px solid var(--pms-border-soft);padding-top:6px;font-size:11px;color:var(--pms-text-secondary);}
.sample-detail{display:flex;align-items:flex-start;gap:8px;}.sample-detail .el-icon{margin-top:5px;flex-shrink:0;}.sample-detail.warning .el-icon{color:var(--pms-warning);}.sample-detail.danger .el-icon{color:var(--pms-danger);}
.compact-indicators{display:none;align-items:center;flex-wrap:wrap;gap:6px 10px;padding-top:9px;font-size:12px;color:var(--pms-text-secondary);}
@media(max-width:1100px){.compact-indicators{display:flex;}}
@media(max-width:560px){.progress-key{gap:8px 10px;}.progress-key .key-divider{display:none;}.progress-sample-notes>span{display:block;}.progress-sample-footer{padding-bottom:3px;}}
</style>
