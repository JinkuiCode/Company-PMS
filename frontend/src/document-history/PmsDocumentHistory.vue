<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ArrowDown, ArrowUp, Clock, Document, Lock, Refresh, Warning } from '@element-plus/icons-vue'
import { PmsSelectControl } from '@/form-system'
import CustomPagination from '@/components/CustomPagination.vue'
import { DEFAULT_PAGE_SIZE } from '@/config/listUi'
import request from '@/utils/request'

type Difference = { field_key: string; field_label: string; before_display: string; after_display: string; before_name_source?: string; after_name_source?: string }
type Event = { id: number; actor: string; created_at: string; action: string; action_label: string;
  status: string; status_label: string; source: string; summary: string; diff_items: Difference[] }
type Response = { total: number; items: Event[]; actions: { value: string; label: string }[] }
const props = defineProps<{ resource: 'archive' | 'project' | 'task' | 'feedback' | 'draft_management'; entityId: number | string; revision?: string | number }>()
const emit=defineEmits<{'access-denied':[status:403|404]}>()
const state = ref<'loading' | 'ready' | 'error' | 'denied'>('loading')
const action = ref(''), page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE)
const result = ref<Response>({ total: 0, items: [], actions: [] })
const expanded = ref(new Set<number>())
const choices = computed(() => [{ value: '', label: '全部操作' }, ...result.value.actions])
let serial = 0
function toggle(id: number) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  expanded.value = next
}
async function load() {
  const current = ++serial
  state.value = 'loading'
  result.value = { total: 0, items: [], actions: [] }
  expanded.value = new Set()
  try {
    const path=props.resource==='draft_management'
      ? `/archive-draft-management/${encodeURIComponent(String(props.entityId))}/history`
      : `/document-history/${props.resource}/${props.entityId}`
    const response = await request.get<never, Response>(path, {
      params: { page: page.value, page_size: pageSize.value, action: action.value || undefined },
    })
    if (current !== serial) return
    result.value = response
    state.value = 'ready'
  } catch (error: any) {
    if (current !== serial) return
    state.value = [403, 404].includes(error.response?.status) ? 'denied' : 'error'
    if(state.value==='denied')emit('access-denied',error.response.status)
  }
}
watch(() => [props.resource, props.entityId, props.revision], () => {
  action.value = ''; page.value = 1; void load()
}, { immediate: true })
watch(action, () => { page.value = 1; void load() })
watch([page, pageSize], () => void load())
watch(pageSize, () => { page.value = 1 }, { flush: 'sync' })
onBeforeUnmount(() => { ++serial })
function time(value: string) { return value.replace('T', ' ').slice(0, 19) }
</script>

<template>
  <section class="pms-document-history" aria-label="当前单据操作记录" :aria-busy="state === 'loading'">
    <div v-if="state !== 'ready'" class="history-state" :role="state === 'error' ? 'alert' : 'status'">
      <Clock v-if="state === 'loading'" /><Lock v-else-if="state === 'denied'" /><Warning v-else />
      <strong>{{ state === 'loading' ? '正在加载操作记录' : state === 'denied' ? '当前无权查看这张单据' : '操作记录加载失败' }}</strong>
      <p v-if="state === 'denied'">请联系管理员核对产品线和数据范围权限。</p>
      <el-button v-if="state === 'error'" class="pms-button-auxiliary" :icon="Refresh" @click="load">重新加载</el-button>
    </div>
    <template v-else>
      <div class="history-tools pms-query-density"><span>{{ result.total }} 条记录 · 时间倒序</span><PmsSelectControl v-model="action" size="compact" aria-label="筛选操作类型" placeholder="全部操作" :options="choices" /></div>
      <div v-if="!result.items.length" class="history-state"><Document /><strong>{{ action ? '当前筛选无记录' : '暂无操作记录' }}</strong><p>此处展示已留存的业务操作记录。</p><el-button v-if="action" class="pms-button-reset" @click="action = ''">重置筛选</el-button></div>
      <ol v-else class="history-timeline">
        <li v-for="row in result.items" :key="row.id" :class="{ 'is-failed': row.status === 'failed' }">
          <div class="history-event-title"><strong>{{ row.actor }}</strong><span>{{ row.action_label }}</span><span class="history-pill" :class="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : ''">{{ row.status_label }}</span><time>{{ time(row.created_at) }}</time></div>
          <p class="history-summary">{{ row.summary }}</p>
          <div class="history-meta"><span>{{ row.source }}</span><button v-if="row.diff_items.length" type="button" class="history-text-button" :aria-expanded="expanded.has(row.id)" :aria-controls="`history-diff-${row.id}`" @click="toggle(row.id)">{{ expanded.has(row.id) ? '收起' : '查看' }} {{ row.diff_items.length }} 项字段变化<ArrowUp v-if="expanded.has(row.id)" /><ArrowDown v-else /></button></div>
          <table v-if="expanded.has(row.id)" :id="`history-diff-${row.id}`" class="history-diff" aria-label="字段变化"><thead><tr><th scope="col">字段</th><th scope="col">原值</th><th scope="col">新值</th></tr></thead><tbody><tr v-for="field in row.diff_items" :key="field.field_key"><th scope="row">{{ field.field_label }}</th><td>{{ field.before_display }}</td><td>{{ field.after_display }}</td></tr></tbody></table>
          <details v-if="expanded.has(row.id) && row.diff_items.some(field => field.before_name_source === 'current' || field.after_name_source === 'current')" class="history-name-note"><summary>名称说明</summary><p>旧记录未保存名称的负责人或产品线，显示当前关联名称；已保存的历史名称保持原样。</p></details>
        </li>
      </ol>
      <CustomPagination v-if="result.total > pageSize || pageSize !== DEFAULT_PAGE_SIZE || page > 1" v-model="page" v-model:page-size="pageSize" :total="result.total" />
      <p class="history-foot">仅显示你有权查看的业务信息，操作记录不可修改。</p>
    </template>
  </section>
</template>

<style scoped>
.pms-document-history{padding:12px 0;min-height:240px;font-size:13px}.history-tools{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:20px;font-size:11px;color:var(--pms-text-secondary)}.history-tools .pms-form-control{width:116px}.history-timeline{list-style:none;margin:0;padding:0 0 0 7px}.history-timeline>li{position:relative;border-left:1px solid var(--pms-border);padding:0 0 24px 16px}.history-timeline>li:last-child{border-left-color:transparent;padding-bottom:8px}.history-timeline>li:before{content:'';position:absolute;left:-4px;top:6px;width:7px;height:7px;border:1px solid var(--pms-surface);border-radius:50%;background:var(--pms-primary)}.history-timeline>li.is-failed:before{background:var(--pms-danger)}.history-event-title{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.history-event-title strong{font-weight:600}.history-event-title time{margin-left:auto;color:var(--pms-text-secondary);font-size:11px;font-variant-numeric:tabular-nums}.history-summary{margin:6px 0;line-height:1.8;overflow-wrap:anywhere}.history-meta{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:11px;color:var(--pms-text-secondary)}.history-text-button{display:inline-flex;align-items:center;gap:4px;background:transparent;border:0;padding:2px 0;font:inherit;color:var(--pms-info);cursor:pointer}.history-text-button:hover{text-decoration:underline}.history-meta svg{width:11px;height:11px}.history-diff{width:100%;table-layout:fixed;border-collapse:collapse;margin-top:8px;font-size:13px}.history-diff th,.history-diff td{padding:6px 8px;border:1px solid var(--pms-border-soft);overflow-wrap:anywhere;white-space:normal}.history-diff thead th{text-align:center;background:var(--pms-bg-soft);font-weight:500;color:var(--pms-text-secondary)}.history-diff tbody th{text-align:left;font-weight:400}.history-diff td{color:var(--pms-text-secondary)}.history-diff td:last-child{color:var(--pms-text)}.history-pill{display:inline-flex;font-size:11px;line-height:18px;padding:0 6px;border-radius:20px;color:var(--pms-text-secondary);background:var(--pms-neutral-soft)}.history-pill.success{color:var(--pms-success);background:var(--pms-success-soft)}.history-pill.danger{color:var(--pms-danger);background:var(--pms-danger-soft)}.history-foot{font-size:11px;color:var(--pms-text-secondary);border-top:1px solid var(--pms-border-soft);padding:12px 0 0;margin-top:8px}.history-state{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;min-height:250px;padding:32px 16px;text-align:center}.history-state>svg{width:26px;height:26px;color:var(--pms-text-secondary)}.history-state strong{font-size:14px;font-weight:500}.history-state p{font-size:12px;color:var(--pms-text-secondary);line-height:1.8}
</style>
