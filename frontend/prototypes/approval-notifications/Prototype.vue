<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Bell, Refresh, FolderOpened } from '@element-plus/icons-vue'
import { themeTokens, THEMES, type ThemeId } from '../../src/theme-system/core'
import PmsTextareaControl from '../../src/form-system/components/PmsTextareaControl.vue'
import PmsCheckboxControl from '../../src/form-system/components/PmsCheckboxControl.vue'
import PmsFormField from '../../src/form-system/components/PmsFormField.vue'
import PmsPageGuide from '../../src/page-guide/PmsPageGuide.vue'
const open = ref(false), requestOpen = ref(false), channel = ref('business'), state = ref('normal'), theme = ref<ThemeId>('blue')
const unreadOnly = ref(false), selected = ref(1), opinion = ref(''), error = ref(''), saving = ref(false)
const delivery = ref('unknown'), manager = ref(false), retryOpen=ref(false), retryReason=ref(''), checked=ref(false)
const messages = ref([
  { id:1, code:'P2026-018', name:'精密装配线', event:'等待你审批', status:'待审批', time:'今天 16:20', author:'张明', actor:'李华', read:false },
  { id:2, code:'P2026-012', name:'自动检测工装', event:'申请已通过', status:'已通过', time:'今天 15:42', author:'李华', actor:'王宁', read:false },
  { id:3, code:'P2026-009', name:'包装线改造', event:'申请已退回', status:'已退回', time:'今天 14:18', author:'李华', actor:'王宁', read:true },
  { id:4, code:'P2026-003', name:'在线检测设备', event:'原待办已撤回', status:'已撤回', time:'昨天 17:05', author:'张明', actor:'李华', read:true },
])
const current = computed(() => messages.value.find(item => item.id === selected.value)!)
const items = computed(() => messages.value.filter(item => !unreadOnly.value || !item.read))
const unread = computed(() => messages.value.filter(item => !item.read).length)
const labels:Record<string,string> = { pending:'待投递', waiting:'等待邮件配置', processing:'投递中', accepted:'邮件服务器已接受', failed:'投递失败', unknown:'投递结果未知', suppressed:'已停止投递' }
watch(theme, id => { document.documentElement.dataset.pmsTheme = id; for (const [k,v] of Object.entries(themeTokens(id))) document.documentElement.style.setProperty(k,v) }, { immediate:true })
function show() { open.value=true; channel.value='business'; error.value=''; selected.value=1 }
function view() { opinion.value=''; error.value=''; requestOpen.value=true }
async function decide(approved:boolean) {
  if (!approved && !opinion.value.trim()) { error.value='退回时请填写意见'; return }
  saving.value=true; await new Promise(resolve => setTimeout(resolve,600)); current.value.status=approved?'已通过':'已退回'; current.value.event=approved?'申请已通过':'申请已退回'; saving.value=false; error.value=''
}
</script>

<template>
  <header class="prototype-header"><strong>PMS</strong><span>项目管理</span><el-badge :value="unread" :hidden="!unread"><el-button :icon="Bell" class="pms-button-navigation" aria-label="打开通知" @click="show">通知</el-button></el-badge></header>
  <main class="prototype-intro">
    <h1>审批通知 · 交互样稿</h1><p>从通知查看申请，在原审批页面处理。以下均为虚构数据。</p>
    <div class="prototype-controls">
      <label>状态 <select v-model="state" aria-label="预览状态"><option value="normal">正常</option><option value="loading">加载</option><option value="empty">空列表</option><option value="error">读取失败</option><option value="denied">无权访问</option></select></label>
      <label>主题 <select v-model="theme" aria-label="预览主题"><option v-for="(t,id) in THEMES" :key="id" :value="id">{{ t.name }}</option></select></label>
      <label><input v-model="manager" type="checkbox">预览投递管理权限</label>
      <label v-if="manager">邮件状态 <select v-model="delivery" aria-label="预览邮件状态"><option v-for="(label,key) in labels" :key="key" :value="key">{{ label }}</option></select></label>
    </div>
    <p class="prototype-note">样稿控制项仅用于本次评审，不进入业务界面。可切换三种主题、缩窄窗口，以及用 Tab / Enter / Escape 操作。</p>
    <el-button type="primary" :icon="Bell" @click="show">预览通知</el-button>
  </main>
  <el-dialog v-model="open" title="通知" width="min(900px, calc(100vw - 24px))" class="notice-prototype" align-center destroy-on-close>
    <el-tabs v-model="channel">
      <el-tab-pane label="业务消息" name="business">
        <div class="notice-toolbar"><el-radio-group v-model="unreadOnly" aria-label="消息范围" size="small"><el-radio-button :value="false">全部</el-radio-button><el-radio-button :value="true">未读 {{ unread }}</el-radio-button></el-radio-group><span class="spacer"/><el-button class="pms-button-auxiliary" :icon="Refresh" :disabled="state==='loading'" @click="state='normal'">刷新</el-button><PmsPageGuide page="businessNotices" /></div>
        <div v-if="state!=='normal'" class="notice-state" role="status"><p>{{ {loading:'正在读取通知…',empty:'暂无业务消息',error:'读取失败，请重试',denied:'当前无权查看业务消息'}[state] }}</p><el-button v-if="state==='error'" type="primary" plain @click="state='normal'">重试读取</el-button></div>
        <div v-else class="notice-columns">
          <div class="notice-list" aria-label="业务消息列表">
            <button v-for="item in items" :key="item.id" class="notice-row" :class="{ selected:selected===item.id }" :aria-pressed="selected===item.id" @click="selected=item.id">
              <span class="row-top"><strong>{{ item.code }}</strong><time>{{ item.time }}</time></span><span class="row-name">{{ item.name }}</span><span class="row-bottom"><span>{{ item.event }}</span><span v-if="!item.read" class="unread-dot" aria-label="未读" /></span>
            </button><p v-if="!items.length" class="notice-empty">暂无未读消息</p>
          </div>
          <section v-if="items.length" class="notice-detail" data-testid="notice-detail" aria-live="polite">
            <div class="detail-heading"><span class="status-tag" :class="{ success:current.status==='已通过', danger:current.status==='已退回' }">{{ current.status }}</span><time>{{ current.time }}</time></div>
            <h2>{{ current.event }}</h2><p class="project-title">{{ current.name }}</p><p class="project-code">{{ current.code }}</p>
            <dl><dt>提交人</dt><dd>{{ current.author }}</dd><dt>审批人</dt><dd>{{ current.actor }}</dd></dl>
            <p class="notice-result">{{ current.status==='待审批'?'请查看拟变更内容后处理。':current.status==='已通过'?'档案变更已生效，ERP 同步状态请到项目档案查看。':current.status==='已退回'?'请在申请中查看退回意见，修改后重新提交。':'提交人已撤回，本次申请不能再审批。' }}</p>
            <div class="detail-actions"><el-button class="pms-button-navigation" :icon="FolderOpened" @click="view">查看申请</el-button><el-button type="success" plain :disabled="current.read" @click="current.read=true">{{ current.read?'已读':'标为已读' }}</el-button></div>
            <details v-if="manager" class="delivery-details"><summary>邮件投递</summary><p>{{ labels[delivery] }}</p><p v-if="delivery==='unknown'">发送结果无法确认，系统不会自动重发。</p><p v-if="delivery==='failed'">收件人未配置有效邮箱。</p><p v-if="delivery==='waiting'">邮件配置关闭，已保留待投递记录。</p><p v-if="delivery==='suppressed'">申请已处理或收件人已无权访问。</p><el-button class="pms-button-reset" :disabled="['accepted','processing'].includes(delivery)" @click="retryReason='';checked=false;retryOpen=true">受控重试</el-button></details>
          </section>
        </div>
        <div v-if="state==='normal'" class="notice-footer"><el-pagination small layout="total, prev, pager, next" :total="items.length" :page-size="50" /></div>
      </el-tab-pane>
      <el-tab-pane label="升级通知" name="release"><div class="release-preview"><strong>v1.3.0 · 项目档案体验更新</strong><p>此频道保留现有升级说明、显式已读及邮件预览。</p><el-button class="pms-button-navigation" disabled>升级详情（示意）</el-button></div></el-tab-pane>
    </el-tabs>
  </el-dialog>
  <el-dialog v-model="requestOpen" title="档案变更申请" width="min(650px, calc(100vw - 24px))" align-center append-to-body :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
    <p>{{ current.code }} · {{ current.name }} <span class="status-tag">{{ current.status }}</span></p>
    <h3>拟变更内容</h3><table class="request-diff"><thead><tr><th>字段</th><th>原值</th><th>拟变更</th></tr></thead><tbody><tr><td>项目名称</td><td>{{ current.name }}</td><td>{{ current.name }}二期</td></tr></tbody></table>
    <p v-if="current.status==='已退回'">退回意见：请核对设备名称后重新提交。</p>
    <PmsFormField field-id="prototype-opinion" label="审批意见" :error="error"><PmsTextareaControl id="prototype-opinion" v-model="opinion" aria-label="审批意见" :rows="3" :readonly="current.status!=='待审批'" :disabled="saving" :error="!!error" placeholder="退回时必填" /></PmsFormField>
    <template #footer><el-button class="pms-button-reset" :disabled="saving" @click="requestOpen=false">关闭</el-button><el-button type="danger" plain :disabled="current.status!=='待审批'||saving" @click="decide(false)">退回</el-button><el-button type="success" plain :loading="saving" :disabled="current.status!=='待审批'" @click="decide(true)">通过</el-button></template>
  </el-dialog>
  <el-dialog v-model="retryOpen" title="确认重试邮件" width="min(520px, 94vw)" align-center append-to-body>
    <p v-if="delivery==='unknown'">结果未知时，请先核查收件人是否已收到，避免重复投递。</p>
    <PmsFormField field-id="prototype-retry" label="重试原因" required><PmsTextareaControl id="prototype-retry" v-model="retryReason" aria-label="重试原因" /></PmsFormField>
    <PmsCheckboxControl v-if="delivery==='unknown'" v-model="checked" aria-label="已人工核查，确认用户未收到邮件">已人工核查，确认用户未收到邮件</PmsCheckboxControl>
    <template #footer><el-button class="pms-button-reset" @click="retryOpen=false">取消</el-button><el-button type="primary" :disabled="!retryReason.trim()||(delivery==='unknown'&&!checked)" @click="delivery='pending';retryOpen=false">确认重试</el-button></template>
  </el-dialog>
</template>

<style scoped>
.prototype-header{height:44px;border-bottom:1px solid var(--pms-border);background:var(--pms-surface);display:flex;align-items:center;gap:12px;padding:0 20px;font-size:13px}.prototype-header strong{color:var(--pms-primary);font-size:17px}.prototype-header .el-badge{margin-left:auto}.prototype-intro{max-width:1020px;margin:36px auto;padding:0 20px;font-size:13px}h1{font-size:21px;font-weight:600;margin-bottom:10px}.prototype-intro p{color:var(--pms-text-secondary);line-height:1.8}.prototype-controls{display:flex;gap:20px;flex-wrap:wrap;margin:24px 0}.prototype-controls label{display:flex;align-items:center;gap:8px}.prototype-controls select{height:32px;border:1px solid var(--pms-border);border-radius:4px;padding:0 8px;background:var(--pms-surface);color:var(--pms-text)}.prototype-note{font-size:12px}.notice-toolbar{display:flex;gap:8px;align-items:center;padding-bottom:12px}.spacer{flex:1}.notice-columns{display:grid;grid-template-columns:310px minmax(0,1fr);min-height:390px;border:1px solid var(--pms-border);border-radius:6px;overflow:hidden}.notice-list{background:var(--pms-surface);border-right:1px solid var(--pms-border)}.notice-row{display:block;width:100%;border:0;border-bottom:1px solid var(--pms-border-soft);border-left:3px solid transparent;padding:14px 14px 12px;text-align:left;background:transparent;color:var(--pms-text);cursor:pointer;font-size:13px}.notice-row:hover{background:var(--pms-row-hover)}.notice-row.selected{background:var(--pms-primary-soft);border-left-color:var(--pms-primary)}.notice-row:focus-visible{outline:2px solid var(--pms-primary);outline-offset:-3px}.row-top,.row-bottom,.detail-heading{display:flex;justify-content:space-between;align-items:center;gap:8px}.row-top strong{font-size:12px;font-weight:500}.row-top time,.detail-heading time{font-size:11px;color:var(--pms-text-secondary)}.row-name{display:block;margin:7px 0;font-weight:500}.row-bottom{font-size:12px;color:var(--pms-text-secondary)}.unread-dot{width:6px;height:6px;background:var(--pms-primary);border-radius:50%}.notice-detail{color:var(--pms-text);padding:20px;min-width:0}.notice-detail h2{font-size:18px;margin:24px 0 14px}.project-title{font-weight:600;font-size:14px;margin:0 0 4px}.project-code{font-size:12px;color:var(--pms-text-secondary);margin:0}.notice-detail dl{display:grid;grid-template-columns:64px 1fr;gap:8px;font-size:12px;margin:22px 0}.notice-detail dt{color:var(--pms-text-secondary)}.notice-detail dd{margin:0}.notice-result{font-size:13px;line-height:1.8;margin-bottom:22px}.status-tag{display:inline-flex;border-radius:16px;padding:2px 8px;font-size:12px;color:var(--pms-text-secondary);background:var(--pms-surface-muted)}.status-tag.success{color:var(--pms-success);background:var(--pms-success-soft)}.status-tag.danger{color:var(--pms-danger);background:var(--pms-danger-soft)}.detail-actions{display:flex;gap:8px;flex-wrap:wrap}.detail-actions .el-button+.el-button{margin-left:0}.notice-footer{display:flex;justify-content:flex-end;padding-top:10px}.notice-state{min-height:390px;display:flex;flex-direction:column;justify-content:center;align-items:center}.notice-empty{padding:24px;text-align:center}.delivery-details{margin-top:24px;border-top:1px solid var(--pms-border-soft);padding-top:12px;font-size:12px;color:var(--pms-text-secondary)}.delivery-details summary{cursor:pointer;color:var(--pms-info)}.request-diff{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px}.request-diff td,.request-diff th{padding:9px;border-bottom:1px solid var(--pms-border-soft)}.request-diff th{background:var(--pms-surface-muted)}.release-preview{padding:20px;min-height:390px}@media(max-width:640px){.notice-columns{grid-template-columns:1fr}.notice-list{border-right:0;max-height:180px;overflow:auto;border-bottom:1px solid var(--pms-border)}.notice-detail{padding:14px}.notice-detail h2{margin-top:16px}.notice-state{min-height:300px}}
</style>
<style>.notice-prototype .el-dialog__body{max-height:calc(100dvh - 150px);overflow:auto}.notice-prototype .el-tabs__content{overflow:visible}</style>
