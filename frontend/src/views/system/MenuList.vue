<template>
  <div class="dict-page">
    <!-- 左侧：字典分类列表 -->
    <div class="dict-list-panel">
      <div class="panel-header">
        <span>数据字典</span>
        <el-button v-if="hasPermission('system:dict:add')" type="primary" size="small" @click="openDictDialog()">新增分类</el-button>
      </div>
      <el-input v-model="searchText" placeholder="搜索分类..." clearable size="small" style="padding: 8px 12px;" />
      <div class="dict-list-wrap">
        <div
          v-for="d in filteredDicts" :key="d.id"
          :class="['dict-item', { active: selectedDict?.id === d.id }]"
          @click="selectDict(d)"
        >
          <div class="dict-item-name">{{ d.dict_name }}</div>
          <div class="dict-item-meta">
            <span v-if="d.table_name" class="meta-table">{{ d.table_name }}</span>
            <el-tag v-if="d.page_name" size="small" type="info">{{ d.page_name }}</el-tag>
          </div>
        </div>
        <div v-if="filteredDicts.length === 0" class="empty-tip">暂无数据</div>
      </div>
    </div>

    <!-- 右侧：字段列表 -->
    <div class="dict-items-panel">
      <el-card v-if="selectedDict">
        <template #header>
          <div class="items-header">
            <div>
              <span style="font-weight:600">{{ selectedDict.dict_name }}</span>
              <el-tag size="small" style="margin-left:8px">{{ selectedDict.dict_code }}</el-tag>
              <span v-if="selectedDict.table_name" class="meta-text">
                表：{{ selectedDict.table_name }}
              </span>
            </div>
            <div>
              <el-button v-if="hasPermission('system:field:add')" type="primary" size="small" @click="openItemDialog()">新增字段</el-button>
              <el-button v-if="hasPermission('system:dict:edit')" size="small" @click="openDictDialog(selectedDict)">编辑分类</el-button>
              <el-button v-if="hasPermission('system:dict:delete')" type="danger" size="small" plain @click="handleDeleteDict(selectedDict.id)">删除分类</el-button>
            </div>
          </div>
        </template>

        <el-table :data="dictItems" border stripe size="small">
          <el-table-column prop="item_label" label="表单字段名" width="140" />
          <el-table-column prop="item_value" label="数据库列名" width="160">
            <template #default="{ row }">
              <code>{{ selectedDict.table_name }}.{{ row.item_value }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="field_type" label="字段类型" width="100">
            <template #default="{ row }">
              <el-tag :type="fieldTypeTag(row.field_type)" size="small">{{ fieldTypeLabel(row.field_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="180">
            <template #default="{ row }">
              <span v-if="row.description">{{ row.description }}</span>
              <span v-else style="color:#c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="sort" label="排序" width="70" />
          <el-table-column prop="status" label="状态" width="70">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                {{ row.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button v-if="hasPermission('system:field:edit')" link type="primary" size="small" @click="openItemDialog(row)">编辑</el-button>
              <el-button v-if="hasPermission('system:field:delete')" link type="danger" size="small" @click="handleDeleteItem(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      <div v-else class="empty-state">
        <el-empty description="请从左侧选择一个表单分类" />
      </div>
    </div>

    <!-- 字典分类弹窗 -->
    <el-dialog v-model="dictDialogVisible" :title="isDictEdit ? '编辑字典分类' : '新增字典分类'" width="520px">
      <el-form ref="dictFormRef" :model="dictForm" :rules="dictRules" label-width="90px">
        <el-form-item label="字典编码" prop="dict_code">
          <el-input v-model="dictForm.dict_code" :disabled="isDictEdit" placeholder="如: project_archive" />
        </el-form-item>
        <el-form-item label="表单名称" prop="dict_name">
          <el-input v-model="dictForm.dict_name" placeholder="如: 项目档案" />
        </el-form-item>
        <el-form-item label="数据库表">
          <el-input v-model="dictForm.table_name" placeholder="如: pms_project_archive" />
        </el-form-item>
        <el-form-item label="前端页面">
          <el-input v-model="dictForm.page_name" placeholder="如: 项目档案" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dictForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="dictForm.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="dictForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dictDialogVisible = false">取消</el-button>
        <el-button v-if="isDictEdit ? hasPermission('system:dict:edit') : hasPermission('system:dict:add')" type="primary" @click="handleDictSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 字段弹窗 -->
    <el-dialog v-model="itemDialogVisible" :title="isItemEdit ? '编辑字段' : '新增字段'" width="480px">
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-width="90px">
        <el-form-item label="表单字段名" prop="item_label">
          <el-input v-model="itemForm.item_label" placeholder="前端显示的字段名，如：项目编号" />
        </el-form-item>
        <el-form-item label="数据库列名" prop="item_value">
          <el-input v-model="itemForm.item_value" placeholder="数据库字段名，如：project_code" />
        </el-form-item>
        <el-form-item label="字段类型">
          <el-select v-model="itemForm.field_type" placeholder="选择字段类型" style="width:100%">
            <el-option label="文本" value="text" />
            <el-option label="数字" value="number" />
            <el-option label="日期" value="date" />
            <el-option label="枚举" value="enum" />
            <el-option label="下拉选择" value="select" />
            <el-option label="关联外键" value="relation" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="itemForm.description" type="textarea" :rows="2" placeholder="枚举值说明、外键引用等" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="itemForm.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="itemForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button v-if="isItemEdit ? hasPermission('system:field:edit') : hasPermission('system:field:add')" type="primary" @click="handleItemSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const hasPermission = authStore.hasPermission

// ==================== 字典分类 ====================
const dictList = ref<any[]>([])
const selectedDict = ref<any>(null)
const searchText = ref('')

const filteredDicts = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return dictList.value
  return dictList.value.filter(d =>
    d.dict_name.toLowerCase().includes(q) ||
    d.dict_code.toLowerCase().includes(q) ||
    (d.page_name || '').toLowerCase().includes(q)
  )
})

async function fetchDicts() {
  dictList.value = (await request.get('/dicts')) as any
}

function selectDict(d: any) {
  selectedDict.value = d
  if (hasPermission('system:field:view')) {
    fetchItems()
  } else {
    dictItems.value = []
  }
}

// 分类弹窗
const dictDialogVisible = ref(false)
const isDictEdit = ref(false)
const dictFormRef = ref<FormInstance>()
const dictForm = reactive({
  id: 0, dict_code: '', dict_name: '', table_name: '', field_name: '',
  page_name: '', description: '', sort: 0, status: 1,
})
const dictRules: FormRules = {
  dict_code: [{ required: true, message: '请输入字典编码' }],
  dict_name: [{ required: true, message: '请输入表单名称' }],
}

function openDictDialog(row?: any) {
  if (row ? !hasPermission('system:dict:edit') : !hasPermission('system:dict:add')) return
  isDictEdit.value = !!(row && row.id)
  dictFormRef.value?.resetFields()
  if (row && row.id) {
    Object.assign(dictForm, row)
  } else {
    Object.assign(dictForm, { id: 0, dict_code: '', dict_name: '', table_name: '', field_name: '', page_name: '', description: '', sort: 0, status: 1 })
  }
  dictDialogVisible.value = true
}

async function handleDictSubmit() {
  if (isDictEdit.value ? !hasPermission('system:dict:edit') : !hasPermission('system:dict:add')) return
  const valid = await dictFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (isDictEdit.value) {
    await request.put(`/dicts/${dictForm.id}`, dictForm)
    ElMessage.success('更新成功')
  } else {
    await request.post('/dicts', dictForm)
    ElMessage.success('创建成功')
  }
  dictDialogVisible.value = false
  fetchDicts()
}

async function handleDeleteDict(id: number) {
  if (!hasPermission('system:dict:delete')) return
  await ElMessageBox.confirm('确定删除该字典分类吗？分类下的所有字段记录也将被删除。', '提示', { type: 'warning' })
  try {
    await request.delete(`/dicts/${id}`)
    ElMessage.success('删除成功')
    if (selectedDict.value?.id === id) {
      selectedDict.value = null
      dictItems.value = []
    }
    fetchDicts()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

// ==================== 字段列表 ====================
const dictItems = ref<any[]>([])

async function fetchItems() {
  if (!selectedDict.value) return
  dictItems.value = (await request.get(`/dicts/${selectedDict.value.id}/items`)) as any
}

// 字段类型显示
function fieldTypeLabel(type: string | null): string {
  const map: Record<string, string> = { text: '文本', number: '数字', date: '日期', enum: '枚举', select: '下拉', relation: '关联' }
  return map[type || ''] || type || '-'
}
function fieldTypeTag(type: string | null): string {
  const map: Record<string, string> = { text: '', number: 'warning', date: 'success', enum: 'danger', select: 'info', relation: '' }
  return map[type || ''] || ''
}

// 字段弹窗
const itemDialogVisible = ref(false)
const isItemEdit = ref(false)
const itemFormRef = ref<FormInstance>()
const itemForm = reactive({ id: 0, item_value: '', item_label: '', field_type: '', description: '', sort: 0, status: 1 })
const itemRules: FormRules = {
  item_value: [{ required: true, message: '请输入数据库列名' }],
  item_label: [{ required: true, message: '请输入表单字段名' }],
}

function openItemDialog(row?: any) {
  if (row ? !hasPermission('system:field:edit') : !hasPermission('system:field:add')) return
  isItemEdit.value = !!(row && row.id)
  itemFormRef.value?.resetFields()
  if (row && row.id) {
    Object.assign(itemForm, { id: row.id, item_value: row.item_value, item_label: row.item_label, field_type: row.field_type || '', description: row.description || '', sort: row.sort, status: row.status })
  } else {
    Object.assign(itemForm, { id: 0, item_value: '', item_label: '', field_type: '', description: '', sort: 0, status: 1 })
  }
  itemDialogVisible.value = true
}

async function handleItemSubmit() {
  if (isItemEdit.value ? !hasPermission('system:field:edit') : !hasPermission('system:field:add')) return
  const valid = await itemFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (isItemEdit.value) {
    await request.put(`/dicts/items/${itemForm.id}`, itemForm)
    ElMessage.success('更新成功')
  } else {
    await request.post(`/dicts/${selectedDict.value.id}/items`, itemForm)
    ElMessage.success('创建成功')
  }
  itemDialogVisible.value = false
  fetchItems()
}

async function handleDeleteItem(id: number) {
  if (!hasPermission('system:field:delete')) return
  await ElMessageBox.confirm('确定删除该字段记录吗？', '提示', { type: 'warning' })
  try {
    await request.delete(`/dicts/items/${id}`)
    ElMessage.success('删除成功')
    fetchItems()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(() => fetchDicts())
</script>

<style scoped>
.dict-page { display: flex; gap: 16px; height: 100%; }

.dict-list-panel {
  width: 300px; flex-shrink: 0; background: #fff;
  border-radius: 4px; border: 1px solid #ebeef5;
  display: flex; flex-direction: column; overflow: hidden;
}
.panel-header {
  padding: 14px 16px; font-size: 15px; font-weight: 600;
  border-bottom: 1px solid #ebeef5; color: #303133;
  display: flex; justify-content: space-between; align-items: center;
}
.dict-list-wrap { flex: 1; overflow-y: auto; }
.dict-item {
  padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5;
  transition: background 0.15s;
}
.dict-item:hover { background: #f5f7fa; }
.dict-item.active { background: #ecf5ff; border-left: 3px solid #409EFF; }
.dict-item-name { font-size: 14px; font-weight: 500; color: #303133; }
.dict-item-meta { font-size: 12px; color: #909399; margin-top: 4px; display: flex; gap: 8px; align-items: center; }
.meta-table { font-family: monospace; color: #606266; }
.empty-tip { padding: 40px 0; text-align: center; color: #909399; font-size: 13px; }

.dict-items-panel { flex: 1; min-width: 0; }
.items-header { display: flex; justify-content: space-between; align-items: center; }
.meta-text { font-size: 12px; color: #909399; margin-left: 12px; font-family: monospace; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 400px; background: #fff; border-radius: 4px; border: 1px solid #ebeef5; }

code { background: #f5f7fa; padding: 2px 6px; border-radius: 3px; font-size: 12px; color: #606266; }
</style>
