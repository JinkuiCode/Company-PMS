<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { PmsFormField, PmsTextareaControl, PmsCheckboxControl } from '@/form-system'
import request from '@/utils/request'
interface Delivery { id: number; event: string; user_name: string; status: string; attempts: number; read_at: string | null; error_message: string | null }
const props = defineProps<{ changeId: number }>()
const auth = useAuthStore(), opened = ref(false), rows = ref<Delivery[]>([]), state = ref(''), busy = ref(false)
const retryRow = ref<Delivery | null>(null), reason = ref(''), checked = ref(false), failure = ref('')
const manage = computed(() => auth.hasPermission('project:archive:notification:manage'))
const mayRetry = computed(() => auth.hasPermission('project:archive:notification:retry'))
const labels: Record<string,string> = { pending:'待投递', waiting:'等待邮件配置', processing:'投递中', accepted:'邮件服务器已接受', failed:'投递失败', unknown:'投递结果未知', suppressed:'已停止投递' }
let serial = 0
async function load() {
  const current = ++serial; rows.value = []; state.value = 'loading'
  if (!opened.value || !manage.value) return
  try {
    const result = await request.get<never, { items: Delivery[] }>(`/business-notices/requests/${props.changeId}/deliveries`)
    if (current === serial) { rows.value = result.items; state.value = 'ready' }
  } catch { if (current === serial) state.value = 'error' }
}
function toggle(event: Event) { opened.value = (event.target as HTMLDetailsElement).open; void load() }
function openRetry(row: Delivery) { retryRow.value = row; reason.value = ''; checked.value = false; failure.value = '' }
async function retry() {
  const row = retryRow.value, current = serial
  if (!row || busy.value || !reason.value.trim() || (row.status === 'unknown' && !checked.value)) return
  busy.value = true
  try {
    await request.post(`/business-notices/deliveries/${row.id}/retry`, { reason: reason.value, checked_not_received: checked.value })
    if (current !== serial) return
    retryRow.value = null; await load(); ElMessage.success('已重新加入邮件投递队列')
  } catch { if (current === serial) failure.value = '重试未成功，请核对当前投递状态后再试' }
  finally { busy.value = false }
}
watch([() => props.changeId, manage], () => { retryRow.value = null; void load() })
onBeforeUnmount(() => { ++serial })
</script>
<template>
  <details v-if="manage" class="delivery-details" @toggle="toggle"><summary>邮件投递</summary>
    <p>站内已读和邮件投递分别记录。邮件服务器接受投递，不代表用户已读。</p>
    <p v-if="state === 'loading'" role="status">正在读取投递状态…</p>
    <p v-else-if="state === 'error'" role="alert">投递记录读取失败 <el-button class="pms-button-auxiliary" @click="load">重试</el-button></p>
    <div v-for="row in rows" :key="row.id" class="delivery-row">
      <p>{{ row.user_name }} · {{ labels[row.status] }} · {{ row.read_at ? '站内已读' : '站内未读' }}</p>
      <p v-if="row.error_message">{{ row.error_message }}</p>
      <p v-if="row.status === 'unknown'">发送结果无法确认，系统不会自动重发。</p>
      <el-button v-if="mayRetry && ['failed','unknown','waiting','suppressed'].includes(row.status)" class="pms-button-reset" :disabled="busy" @click="openRetry(row)">受控重试</el-button>
    </div>
    <p v-if="state === 'ready' && !rows.length">本申请暂无投递记录</p>
  </details>
  <el-dialog :model-value="!!retryRow" title="确认重试邮件" width="min(520px,94vw)" align-center append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="!busy && (retryRow = null)">
    <PmsFormField field-id="business-mail-retry" label="重试原因" required :error="failure"><PmsTextareaControl id="business-mail-retry" v-model="reason" aria-label="重试原因" :maxlength="500" :disabled="busy" /></PmsFormField>
    <PmsCheckboxControl v-if="retryRow?.status === 'unknown'" v-model="checked" :disabled="busy" aria-label="已人工核查，确认用户未收到邮件">已人工核查，确认用户未收到邮件</PmsCheckboxControl>
    <template #footer><el-button class="pms-button-reset" :disabled="busy" @click="retryRow = null">取消</el-button><el-button type="primary" :disabled="!reason.trim() || (retryRow?.status === 'unknown' && !checked)" :loading="busy" @click="retry">确认重试</el-button></template>
  </el-dialog>
</template>
<style scoped>
.delivery-details{margin-top:24px;border-top:1px solid var(--pms-border-soft);padding-top:12px;font-size:12px;color:var(--pms-text-secondary)}
.delivery-details summary{cursor:pointer;color:var(--pms-info)}.delivery-row{padding:8px 0;border-bottom:1px solid var(--pms-border-soft)}
</style>
