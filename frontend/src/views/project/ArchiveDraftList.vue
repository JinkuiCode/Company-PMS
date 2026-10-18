<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { PmsFormDrawer } from '@/form-system'
import PmsDataList from '@/components/PmsDataList.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import { DEFAULT_PAGE_SIZE } from '@/config/listUi'
import { archiveDraftApi, type DraftSummary } from '@/api/formDraft'
const props = defineProps<{ modelValue: boolean; resuming?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; resume: [id: string] }>()
const rows = ref<DraftSummary[]>([]), busy = ref(false), failed = ref(false)
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
let ticket = 0
async function load() {
  const current = ++ticket
  busy.value = true; failed.value = false; rows.value = []
  try {
    const result = await archiveDraftApi.list(page.value, pageSize.value)
    if (ticket !== current) return
    rows.value = result.items; total.value = result.total
    if (!rows.value.length && total.value && page.value > 1) { page.value = 1; void load() }
  } catch { if (ticket === current) failed.value = true }
  finally { if (ticket === current) busy.value = false }
}
async function remove(row: DraftSummary) {
  if (busy.value) return
  try { await ElMessageBox.confirm('删除后无法恢复，确定删除这份草稿吗？', '删除草稿', {type:'warning'}) } catch { return }
  busy.value = true
  try { await archiveDraftApi.delete(row.id, row.version); await load() }
  catch { busy.value = false }
}
watch(() => props.modelValue, value => {
  if (value) { page.value = 1; void load() }
  else { ticket++; busy.value = false; rows.value = [] }
})
function savedTime(value: string) { return new Date(value).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai', hour12:false}) }
</script>
<template>
  <PmsFormDrawer :model-value="modelValue" title="我的草稿" :busy="busy || resuming" @update:model-value="emit('update:modelValue', $event)">
    <PmsDataList :surface="false" :show-scrollbar="false" class="pms-dense-table">
      <template #grid>
        <p v-if="failed" role="alert" class="pms-list-load-error">草稿加载失败 <el-button class="pms-button-navigation" size="small" @click="load">重试</el-button></p>
        <el-table v-else :data="rows" v-loading="busy" empty-text="暂无草稿" size="small" class="pms-dense-table">
          <el-table-column label="项目" min-width="150" header-align="center" show-overflow-tooltip><template #default="{row}">
            <div>{{ row.project_name }}</div><div v-if="row.project_code">{{ row.project_code }}</div>
          </template></el-table-column>
          <el-table-column label="保存时间" width="100" header-align="center"><template #default="{row}">{{ savedTime(row.updated_at).split(' ')[0] }}<br />{{ savedTime(row.updated_at).split(' ')[1] }}</template></el-table-column>
          <el-table-column label="操作" width="128" header-align="center"><template #default="{row}">
            <el-button class="pms-button-navigation" link size="small" :disabled="busy || resuming" @click="emit('resume', row.id)">继续填写</el-button>
            <el-button type="danger" link size="small" aria-label="删除草稿" :disabled="busy || resuming" @click="remove(row)">删除</el-button>
          </template></el-table-column>
        </el-table>
      </template>
      <template #pagination><CustomPagination v-if="total" v-model="page" v-model:page-size="pageSize" :total="total" @update:model-value="load" @update:page-size="() => {page=1;load()}" /></template>
    </PmsDataList>
  </PmsFormDrawer>
</template>
