<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import request from '@/utils/request'
import { PmsTextControl } from '@/form-system'
import CustomPagination from '@/components/CustomPagination.vue'

export interface OaEmployee { username: string; real_name: string }
const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; select: [employee: OaEmployee] }>()
const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const items = ref<OaEmployee[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
let serial = 0
let timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  const current = ++serial
  loading.value = true
  failed.value = false
  try {
    const result = await request.get('/users/oa-options', { params: { keyword: keyword.value.trim(), page: page.value, page_size: pageSize.value } }) as any
    if (current !== serial) return
    items.value = result.items
    total.value = result.total
  } catch {
    if (current === serial) { failed.value = true; items.value = []; total.value = 0 }
  } finally { if (current === serial) loading.value = false }
}
watch(() => props.modelValue, open => {
  clearTimeout(timer)
  if (open) { keyword.value = ''; page.value = 1; void load() }
  else { ++serial; loading.value = false }
})
watch(keyword, () => {
  clearTimeout(timer)
  ++serial
  if (props.modelValue) loading.value = true
  timer = setTimeout(() => { if (props.modelValue) { page.value = 1; void load() } }, 250)
})
onBeforeUnmount(() => { clearTimeout(timer); ++serial })
function select(row: OaEmployee) { emit('select', row); emit('update:modelValue', false) }
</script>

<template>
  <el-dialog :model-value="modelValue" title="引用 OA 员工" width="560px" append-to-body @update:model-value="emit('update:modelValue', $event)">
    <div class="oa-employee-picker">
      <PmsTextControl v-model="keyword" placeholder="搜索工号 / 员工姓名" aria-label="搜索 OA 员工" clearable />
      <div v-if="failed" class="pms-inline-error" role="alert">OA 员工读取失败，可重试或关闭后手工填写。<el-button link type="primary" @click="load">重试</el-button></div>
      <el-table :data="items" v-loading="loading" class="pms-dense-table" height="320px" border empty-text="没有可引用的员工" @row-dblclick="select">
        <el-table-column prop="username" label="账号（工号）" min-width="150" />
        <el-table-column prop="real_name" label="员工姓名" min-width="140" />
        <el-table-column label="操作" width="76"><template #default="{ row }"><el-button link type="primary" @click="select(row)">选择</el-button></template></el-table-column>
      </el-table>
      <CustomPagination :model-value="page" :total="total" :page-size="pageSize" @update:model-value="page = $event; load()" @update:page-size="pageSize = $event; page = 1; load()" />
    </div>
    <template #footer><el-button @click="emit('update:modelValue', false)">取消</el-button></template>
  </el-dialog>
</template>

<style scoped>
.oa-employee-picker { display: grid; gap: 12px; }
.pms-inline-error { color: var(--pms-danger); font-size: var(--pms-font-size-base); }
</style>
