<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { useReleaseStore } from './store'
import CustomPagination from '@/components/CustomPagination.vue'
import { PmsFormField, PmsTextareaControl } from '@/form-system'
import { DEFAULT_PAGE_SIZE } from '@/config/listUi'
import { pageGuides } from '@/page-guide/registry'
import type { PageGuideKey } from '@/page-guide/types'
interface Release { id: number; version: string; title: string; summary: string; published_at: string;
  changes: { kind: string; title: string; description: string; guide: PageGuideKey }[] }
interface Notice { id: number; read_at: string | null; release: Release }
interface Delivery { id: number; user_name: string; read_at: string | null; status: string; error_message: string | null }
const props = defineProps<{ mode: 'about' | 'notices' }>()
const store = useReleaseStore(), auth = useAuthStore(), router = useRouter()
const state = ref('loading'), releases = ref<Release[]>([]), notices = ref<Notice[]>([])
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0), selectedId = ref<number>()
const selected = computed(() => releases.value.find(row => row.id === selectedId.value))
const selectedNotice = computed(() => notices.value.find(row => row.release.id === selectedId.value))
const isRead = computed(() => !!selectedNotice.value?.read_at)
const busy = ref(false), mailPreview = ref<{ subject: string; text: string } | null>(null)
const deliveries = ref<Delivery[]>([]), deliveryPage = ref(1), deliveryTotal = ref(0), deliveryState = ref('')
const deliveryPageSize = ref(DEFAULT_PAGE_SIZE)
const retryRow = ref<Delivery | null>(null), retryReason = ref(''), checkedNotReceived = ref(false)
const manage = computed(() => auth.hasPermission('system:release:manage'))
const mailLabels: Record<string, string> = { pending: '待投递', waiting: '等待配置', processing: '投递中', accepted: '服务器已接受', failed: '投递失败', unknown: '结果未知' }
let serial = 0, deliverySerial = 0
async function load() {
  const current = ++serial
  ++deliverySerial; state.value = 'loading'; releases.value = []; notices.value = []; selectedId.value = undefined
  mailPreview.value = null; deliveries.value = []
  try {
    await store.refresh()
    if (current !== serial) return
    if (!store.runtime) throw new Error('运行版本暂时无法读取')
    const data = await request.get<never, { total: number; items: (Notice | Release)[] }>(props.mode === 'notices' ? '/releases/notices' : '/releases', { params: { page: page.value, page_size: pageSize.value } })
    if (current !== serial) return
    total.value = data.total
    if (props.mode === 'notices') { notices.value = data.items as Notice[]; releases.value = notices.value.map(row => row.release) }
    else releases.value = data.items as Release[]
    selectedId.value = releases.value[0]?.id; state.value = 'ready'
  } catch { if (current === serial) state.value = 'error' }
}
async function markRead() {
  const notice = selectedNotice.value
  if (!notice || busy.value || isRead.value) return
  busy.value = true
  try {
    await request.post(`/releases/notices/${notice.id}/read`)
    notice.read_at = new Date().toISOString(); await store.refresh()
  } catch { /* Shared request feedback; keep this notice unread. */ }
  finally { busy.value = false }
}
async function preview() {
  const id = selectedId.value, current = serial
  if (!id) return
  busy.value = true
  try { const data = await request.get<never, { subject: string; text: string }>(`/releases/${id}/mail-preview`); if (current === serial && selectedId.value === id) mailPreview.value = data }
  catch { /* Shared request feedback; do not show a stale preview. */ }
  finally { busy.value = false }
}
async function loadDeliveries() {
  const current = ++deliverySerial, id = selectedId.value
  deliveries.value = []; deliveryTotal.value = 0
  if (!manage.value || props.mode !== 'notices' || !id) return
  deliveryState.value = 'loading'
  try {
    const result = await request.get<never, { total: number; items: Delivery[] }>(`/releases/${id}/deliveries`, { params: { page: deliveryPage.value, page_size: deliveryPageSize.value } })
    if (current !== deliverySerial || selectedId.value !== id) return
    deliveries.value = result.items; deliveryTotal.value = result.total; deliveryState.value = 'ready'
  } catch { if (current === deliverySerial) deliveryState.value = 'error' }
}
function openRetry(row: Delivery) { retryRow.value = row; retryReason.value = ''; checkedNotReceived.value = false }
async function retry() {
  if (!retryRow.value || !retryReason.value.trim() || (retryRow.value.status === 'unknown' && !checkedNotReceived.value)) return
  busy.value = true
  try {
    await request.post(`/releases/mail/${retryRow.value.id}/retry`, { reason: retryReason.value, checked_not_received: checkedNotReceived.value })
    retryRow.value = null; await loadDeliveries(); ElMessage.success('已重新加入邮件投递队列')
  } catch { /* Keep the entered reason available after a failed retry. */ }
  finally { busy.value = false }
}
function feedback() { void router.push('/feedback') }
function guide(key: PageGuideKey) { void router.push(`/page-guide/${key}`) }
const date = (value: string) => value.replace('T', ' ').slice(0, 16)
watch(() => props.mode, () => { page.value = 1; void load() }, { immediate: true })
watch([page, pageSize], () => void load())
watch(pageSize, () => { page.value = 1 }, { flush: 'sync' })
watch([selectedId, manage], () => { deliveryPage.value = 1; mailPreview.value = null; retryRow.value = null; void loadDeliveries() })
watch([deliveryPage, deliveryPageSize], () => void loadDeliveries())
watch(deliveryPageSize, () => { deliveryPage.value = 1 }, { flush: 'sync' })
onBeforeUnmount(() => { ++serial; ++deliverySerial })
</script>

<template>
  <section class="release-center">
    <header class="runtime-summary" v-if="store.runtime"><div class="product-line"><strong class="product-name">{{ store.runtime.product }}</strong><span class="runtime-version"><strong>{{ store.runtime.version }}</strong></span><span class="environment-tag" :class="{ warning: store.runtime.environment !== '正式环境' }">{{ store.runtime.environment }}</span></div><details v-if="store.runtime.technical && manage" class="technical-disclosure"><summary>技术信息</summary><dl class="technical-meta"><div><dt>构建标识</dt><dd>{{ store.runtime.technical.build_id || '未打包' }}</dd></div><div><dt>代码提交</dt><dd>{{ store.runtime.technical.commit || '未打包' }}</dd></div><div><dt>数据库版本</dt><dd>{{ store.runtime.technical.database_revision }}</dd></div></dl></details></header>
    <div v-if="state !== 'ready' || !selected" class="release-state" :role="state === 'error' ? 'alert' : 'status'"><strong>{{ state === 'loading' ? '正在加载更新内容' : state === 'error' ? '更新内容加载失败' : '暂无版本记录' }}</strong><p v-if="state === 'ready'">新的版本发布后，可在这里查看更新内容。</p><el-button v-if="state === 'error'" class="pms-button-auxiliary" @click="load">重新加载</el-button></div>
    <div v-else class="release-workspace">
      <nav class="version-sidebar" :aria-label="mode === 'notices' ? '升级通知版本' : '历史版本'"><div class="sidebar-caption">{{ mode === 'notices' ? '更新通知' : '历史版本' }}</div><ul class="version-list"><li v-for="row in releases" :key="row.id"><button class="version-button" :class="{ selected: row.id === selectedId }" :aria-pressed="row.id === selectedId" @click="selectedId = row.id"><span class="version-name">{{ row.version }}</span><span class="version-date">{{ date(row.published_at).slice(0, 10) }}</span><span v-if="mode === 'notices'" class="notice-state" :class="{ unread: !notices.find(notice => notice.release.id === row.id)?.read_at }">{{ notices.find(notice => notice.release.id === row.id)?.read_at ? '已读' : '未读' }}</span><span v-else class="version-note">{{ row.version === store.runtime?.version ? '当前运行' : '历史记录' }}</span></button></li></ul></nav>
      <div class="release-content"><article class="release-scroll"><div class="release-heading"><div class="release-eyebrow"><span>{{ selected.version }}</span><span v-if="mode === 'notices'" class="read-tag" :class="{ unread: !isRead }">{{ isRead ? '已读' : '未读' }}</span></div><h3>{{ selected.title }}</h3><p class="release-summary">{{ selected.summary }}</p><p class="release-published">发布于 {{ date(selected.published_at) }}</p></div>
        <section class="changes-section" aria-label="版本更新清单"><h4>本次更新</h4><ol class="change-list"><li v-for="(change, index) in selected.changes" :key="index" class="change-item"><span class="change-type" :class="change.kind === '新增' ? 'new' : 'adjusted'">{{ change.kind }}</span><div class="change-copy"><strong>{{ change.title }}</strong><p>{{ change.description }}</p><div class="change-guide"><span>{{ pageGuides[change.guide]?.title }}</span><button class="text-button" @click="guide(change.guide)">查看说明 →</button></div></div></li></ol></section>
        <section v-if="manage && mode === 'notices'" class="delivery-section"><h4>邮件投递</h4><p class="delivery-help">站内已读与邮件投递分别记录。邮件服务器接受投递，不代表用户已读。</p><p v-if="deliveryState === 'loading'" role="status">正在读取投递状态</p><p v-else-if="deliveryState === 'error'" role="alert">投递记录读取失败 <el-button link type="primary" @click="loadDeliveries">重试</el-button></p><table v-else class="delivery-table"><thead><tr><th>接收人</th><th>站内通知</th><th>邮件状态</th></tr></thead><tbody><tr v-for="row in deliveries" :key="row.id"><td>{{ row.user_name }}</td><td>{{ row.read_at ? '已读' : '未读' }}</td><td>{{ mailLabels[row.status] || row.status }}<p v-if="row.error_message">{{ row.error_message }}</p><el-button v-if="auth.hasPermission('system:release:retry') && ['unknown', 'waiting', 'failed'].includes(row.status)" link type="primary" :disabled="busy" @click="openRetry(row)">受控重试</el-button></td></tr></tbody></table><CustomPagination v-if="deliveryTotal > deliveryPageSize || deliveryPageSize !== DEFAULT_PAGE_SIZE || deliveryPage > 1" v-model="deliveryPage" v-model:page-size="deliveryPageSize" :total="deliveryTotal" /></section>
      </article><footer class="release-actions"><el-button class="pms-button-auxiliary" :disabled="busy" @click="preview">查看邮件预览</el-button><el-button v-if="auth.hasPermission('feedback:view')" class="pms-button-auxiliary" @click="feedback">问题反馈</el-button><el-button v-if="mode === 'notices'" type="primary" :disabled="isRead || busy" @click="markRead">{{ isRead ? '已读' : '标为已读' }}</el-button></footer></div>
    </div>
    <CustomPagination v-if="total > pageSize || pageSize !== DEFAULT_PAGE_SIZE || page > 1" v-model="page" v-model:page-size="pageSize" :total="total" />
    <el-dialog :model-value="!!mailPreview" title="邮件预览" width="min(720px,94vw)" append-to-body @update:model-value="mailPreview = null"><template v-if="mailPreview"><h3>{{ mailPreview.subject }}</h3><pre class="release-mail-preview">{{ mailPreview.text }}</pre></template></el-dialog>
    <el-dialog :model-value="!!retryRow" title="确认重试邮件" width="min(520px,94vw)" append-to-body :close-on-click-modal="false" :show-close="!busy" @update:model-value="!busy && (retryRow = null)"><PmsFormField field-id="release-retry-reason" label="重试原因" required><PmsTextareaControl v-model="retryReason" aria-label="重试原因" :disabled="busy" /></PmsFormField><el-checkbox v-if="retryRow?.status === 'unknown'" v-model="checkedNotReceived" :disabled="busy">已人工核查，确认用户未收到邮件</el-checkbox><template #footer><el-button class="pms-button-reset" :disabled="busy" @click="retryRow = null">取消</el-button><el-button type="primary" :disabled="!retryReason.trim() || (retryRow?.status === 'unknown' && !checkedNotReceived)" :loading="busy" @click="retry">确认重试</el-button></template></el-dialog>
  </section>
</template>

<style scoped src="./release-center.css"></style>
