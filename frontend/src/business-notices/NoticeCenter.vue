<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, FolderOpened } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useBusinessNoticeStore } from './store'
import ReleaseCenter from '@/release-center/ReleaseCenter.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import MailDeliveries from './MailDeliveries.vue'
import { DEFAULT_PAGE_SIZE } from '@/config/listUi'
import request from '@/utils/request'
interface Notice { id:number; change_id:number; event:string; status:number; project_code:string; project_name:string; author_name:string; approver_name:string; created_at:string; read_at:string|null }
const emit = defineEmits<{ navigate: [] }>()
const auth = useAuthStore(), store = useBusinessNoticeStore(), router = useRouter()
const channel = ref('business'), unreadOnly = ref(false), page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const items = ref<Notice[]>([]), selected = ref<Notice|null>(null), selectedId = ref<number>(), state = ref('loading'), detailState = ref(''), error = ref(''), busy = ref(false)
const allowed = computed(() => auth.hasPermission('project:archive:view'))
const labels: Record<number,string> = { 2:'待审批', 3:'已通过', 4:'已退回', 5:'已撤回' }
const eventLabel = (item:Notice) => item.event === 'approved' ? '申请已通过' : item.event === 'rejected' ? '申请已退回' : item.status === 2 ? '等待你审批' : `原待办${labels[item.status] || '已结束'}`
const date = (value:string) => value.replace('T',' ').slice(0,16)
let serial = 0, detailSerial = 0
async function select(item: Notice) {
  const current = ++detailSerial; selectedId.value = item.id; selected.value = null; error.value = ''; detailState.value = 'loading'
  try {
    const data = await request.get<never,Notice>(`/business-notices/${item.id}`)
    if (current === detailSerial) { selected.value = data; detailState.value = 'ready' }
  } catch { if (current === detailSerial) detailState.value = 'error' }
}
async function load() {
  const current = ++serial, previous = selectedId.value
  ++detailSerial; selected.value = null; items.value = []; error.value = ''
  if (!allowed.value) { state.value = 'denied'; return }
  state.value = 'loading'
  try {
    const data = await request.get<never,{items:Notice[];total:number;unread:number}>('/business-notices', {params:{page:page.value,page_size:pageSize.value,unread_only:unreadOnly.value}})
    if (current !== serial) return
    items.value = data.items; total.value = data.total; state.value = 'ready'
    const item = data.items.find(row => row.id === previous) || data.items[0]
    if (item) void select(item)
  } catch { if (current === serial) state.value = 'error' }
}
async function markRead() {
  const item = selected.value, current = detailSerial
  if (!item || item.read_at || busy.value) return
  busy.value = true; error.value = ''
  try {
    await request.post(`/business-notices/${item.id}/read`)
    if (current !== detailSerial) return
    item.read_at = new Date().toISOString()
    const row = items.value.find(row => row.id === item.id); if (row) row.read_at = item.read_at
    void store.refresh()
    if (unreadOnly.value) await load()
  } catch { if (current === detailSerial) error.value = '保存已读失败，请重试' }
  finally { busy.value = false }
}
async function view() {
  if (!selected.value) return
  const id = selected.value.change_id
  const repeated = router.currentRoute.value.path === '/project/archive' && Number(router.currentRoute.value.query.change_id) === id
  await router.push({path:'/project/archive',query:{change_id:id}})
  if (repeated) window.dispatchEvent(new CustomEvent('pms:open-archive-change', {detail:id}))
  emit('navigate')
}
function refresh() { void store.refresh(); void load() }
function refreshVisible() { if (!document.hidden && channel.value === 'business') refresh() }
watch([page,pageSize,unreadOnly,allowed], () => void load(), {immediate:true})
watch([pageSize,unreadOnly], () => { page.value = 1 }, {flush:'sync'})
let timer: ReturnType<typeof setInterval>
onMounted(() => { window.addEventListener('focus',refreshVisible); document.addEventListener('visibilitychange',refreshVisible); window.addEventListener('pms:archive-change',refreshVisible); timer=setInterval(refreshVisible,60000) })
onBeforeUnmount(() => { ++serial; ++detailSerial; clearInterval(timer); window.removeEventListener('focus',refreshVisible); document.removeEventListener('visibilitychange',refreshVisible); window.removeEventListener('pms:archive-change',refreshVisible) })
</script>
<template>
  <el-tabs v-model="channel">
    <el-tab-pane label="业务消息" name="business">
      <div class="notice-toolbar"><el-radio-group v-model="unreadOnly" aria-label="消息范围" size="small" :disabled="!allowed"><el-radio-button :value="false">全部</el-radio-button><el-radio-button :value="true">未读 {{ store.known ? store.unread : '—' }}</el-radio-button></el-radio-group><span class="spacer"/><el-button class="pms-button-auxiliary" :icon="Refresh" :disabled="state === 'loading'" @click="refresh">刷新</el-button><PmsPageGuide page="businessNotices" /></div>
      <div v-if="state !== 'ready'" class="notice-state" :role="state === 'error' ? 'alert' : 'status'"><p>{{ state === 'loading' ? '正在读取通知…' : state === 'denied' ? '当前无权查看业务消息' : '业务消息读取失败，请重试' }}</p></div>
      <div v-else-if="!items.length" class="notice-state" role="status">{{ unreadOnly ? '暂无未读消息' : '暂无业务消息' }}</div>
      <div v-else class="notice-columns">
        <div class="notice-list" aria-label="业务消息列表"><button v-for="item in items" :key="item.id" class="notice-row" :class="{selected:selectedId === item.id}" :aria-pressed="selectedId === item.id" @click="select(item)"><span class="row-top"><strong>{{ item.project_code }}</strong><time>{{ date(item.created_at) }}</time></span><span class="row-name">{{ item.project_name }}</span><span class="row-bottom"><span>{{ eventLabel(item) }}</span><span v-if="!item.read_at" class="unread-dot" aria-label="未读" /></span></button></div>
        <section v-if="selected" class="notice-detail" aria-live="polite"><div class="detail-heading"><span class="status-tag" :class="{success:selected.status === 3,danger:selected.status === 4}">{{ labels[selected.status] }}</span><time>{{ date(selected.created_at) }}</time></div>
          <h2>{{ eventLabel(selected) }}</h2><p class="project-title">{{ selected.project_name }}</p><p class="project-code">{{ selected.project_code }}</p>
          <dl><dt>提交人</dt><dd>{{ selected.author_name }}</dd><dt>审批人</dt><dd>{{ selected.approver_name }}</dd></dl>
          <p class="notice-result">{{ selected.status === 2 ? '请查看拟变更内容后处理。' : selected.status === 3 ? '档案变更已生效，ERP 同步状态请到项目档案查看。' : selected.status === 4 ? '请在申请中查看退回意见，修改后重新提交。' : '提交人已撤回，本次申请不能再审批。' }}</p>
          <p v-if="error" role="alert">{{ error }}</p><div class="detail-actions"><el-button class="pms-button-navigation" :icon="FolderOpened" @click="view">查看申请</el-button><el-button type="success" plain :disabled="!!selected.read_at || busy" @click="markRead">{{ selected.read_at ? '已读' : '标为已读' }}</el-button></div>
          <MailDeliveries :key="selected.change_id" :change-id="selected.change_id" />
        </section>
        <section v-else class="notice-state" :role="detailState === 'error' ? 'alert' : 'status'">{{ detailState === 'error' ? '通知不存在、无权访问或读取失败，请刷新' : '正在读取详情…' }}</section>
      </div>
      <CustomPagination v-if="state === 'ready' && total" v-model="page" v-model:page-size="pageSize" :total="total" />
    </el-tab-pane>
    <el-tab-pane label="升级通知" name="release"><ReleaseCenter v-if="channel === 'release'" mode="notices" /></el-tab-pane>
  </el-tabs>
</template>
<style scoped src="./notices.css"></style>
