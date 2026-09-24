<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { PmsSelectControl, PmsTextControl, PmsFormDrawer, PmsFormField } from '@/form-system'
import { cloneQuery } from './state'
const props = defineProps<{ storageKey: string; snapshot: () => object; disabled?: boolean }>()
const emit = defineEmits<{ restore: [value: unknown] }>()
type Plan = { version: 1; name: string; state: object }
const plans = ref<Plan[]>([]), selected = ref(''), opened = ref(false), name = ref('')
watch(() => props.storageKey, () => {
  selected.value = ''; plans.value = []
  try {
    const saved = JSON.parse(localStorage.getItem(props.storageKey) || '[]')
    if (!Array.isArray(saved) || saved.some(p => p.version !== 1 || typeof p.name !== 'string' || !p.state || typeof p.state !== 'object')) throw Error()
    plans.value = saved
  } catch { ElMessage.warning('查询方案格式无效，未自动应用，请重新保存') }
}, {immediate:true})
function restore() { const p = plans.value.find(p=>p.name === selected.value); if (p) emit('restore',cloneQuery(p.state)) }
function save() {
  if (!name.value.trim()) return
  const next = [...plans.value.filter(p=>p.name !== name.value.trim()), {version:1 as const,name:name.value.trim(),state:cloneQuery(props.snapshot())}]
  try { localStorage.setItem(props.storageKey,JSON.stringify(next)); plans.value=next; selected.value=name.value.trim(); opened.value=false; ElMessage.success('查询方案已保存') }
  catch { ElMessage.error('保存失败，请检查浏览器存储空间') }
}
defineExpose({ clearSelection: () => { selected.value = '' } })
</script>
<template>
  <div class="pms-report-plans">
    <PmsSelectControl v-model="selected" :options="plans.map(p=>({value:p.name,label:p.name}))" size="compact" placeholder="当前查询" clearable :disabled="disabled" aria-label="查询方案" @update:model-value="restore" />
    <el-button size="small" :disabled="disabled" @click="name = selected; opened = true">保存查询方案</el-button>
    <PmsFormDrawer v-model="opened" title="保存查询方案"><PmsFormField field-id="report-plan-name" label="方案名称" required><PmsTextControl id="report-plan-name" v-model="name" :maxlength="60" aria-label="方案名称" /></PmsFormField><p class="pms-report-plan-hint">保存当前条件、显示列、顺序、冻结、列宽和每页条数。加载方案后点击查询生效。</p><template #footer><el-button @click="opened = false">取消</el-button><el-button type="primary" :disabled="!name.trim()" @click="save">保存</el-button></template></PmsFormDrawer>
  </div>
</template>
<style scoped>
.pms-report-plans { display:flex; align-items:center; gap:8px; min-width:0; }
.pms-report-plans>.pms-form-control { width:180px; min-width:0; }
.pms-report-plan-hint { font-size:12px; line-height:1.8; color:var(--pms-text-muted); }
@media(max-width:700px) { .pms-report-plans>.pms-form-control { width:140px; } }
</style>
