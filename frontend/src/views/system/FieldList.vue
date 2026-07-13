<template>
  <div class="field-page">
    <!-- 左侧：按页面分组的字典分类 -->
    <div class="field-list-panel">
      <div class="panel-header">
        <span>字段管理</span>
        <el-button v-if="hasPermission('system:dict:add')" type="primary" size="small" @click="openDictDialog()">新增分类</el-button>
      </div>
      <el-input v-model="searchText" placeholder="搜索字段..." clearable size="small" style="padding: 8px 12px;" />
      <div class="field-list-wrap">
        <template v-for="(group, pageName) in groupedDicts" :key="pageName">
          <div class="group-title">{{ pageName }}</div>
          <div
            v-for="d in group" :key="d.id"
            :class="['field-item', { active: selectedDict?.id === d.id }]"
            @click="selectDict(d)"
          >
            <div class="field-item-name">{{ d.dict_name }}</div>
            <div class="field-item-meta">
              <el-tag size="small">{{ d.field_name }}</el-tag>
            </div>
          </div>
        </template>
        <div v-if="Object.keys(groupedDicts).length === 0" class="empty-tip">暂无数据</div>
      </div>
    </div>

    <!-- 右侧：枚举值管理 -->
    <div class="field-items-panel">
      <el-card v-if="selectedDict">
        <template #header>
          <div class="items-header">
            <div>
              <span style="font-weight:600">{{ selectedDict.dict_name }}</span>
              <el-tag size="small" style="margin-left:8px">{{ selectedDict.field_name }}</el-tag>
            </div>
            <el-button v-if="hasPermission('system:field:add')" type="primary" size="small" @click="openItemDialog()">新增枚举值</el-button>
          </div>
        </template>

        <el-table :data="dictItems" border stripe>
          <el-table-column prop="item_value" label="存储值" width="140" />
          <el-table-column prop="item_label" label="显示文本" width="160" />
          <el-table-column prop="sort" label="排序" width="80" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                {{ row.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button v-if="hasPermission('system:field:edit')" link type="primary" size="small" @click="openItemDialog(row)">编辑</el-button>
              <el-tooltip :content="row.status === 1 ? '禁用' : '启用'" placement="top">
                <el-button v-if="hasPermission('system:field:edit')" link :type="row.status === 1 ? 'warning' : 'success'" size="small" @click="handleToggleStatus(row)">
                  {{ row.status === 1 ? '禁用' : '启用' }}
                </el-button>
              </el-tooltip>
              <el-button v-if="hasPermission('system:field:delete')" link type="danger" size="small" @click="handleDeleteItem(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      <div v-else class="empty-state">
        <el-empty description="请从左侧选择一个字段" />
      </div>
    </div>

    <!-- 字典分类弹窗 -->
    <el-dialog v-model="dictDialogVisible" :title="isDictEdit ? '编辑字段分类' : '新增字段分类'" width="520px">
      <el-form ref="dictFormRef" :model="dictForm" :rules="dictRules" label-width="90px">
        <el-form-item label="字段编码" prop="dict_code">
          <el-input v-model="dictForm.dict_code" :disabled="isDictEdit" placeholder="如: product_type" />
        </el-form-item>
        <el-form-item label="字段名称" prop="dict_name">
          <el-input v-model="dictForm.dict_name" />
        </el-form-item>
        <el-form-item label="所属页面">
          <el-input v-model="dictForm.page_name" placeholder="如: 项目档案" />
        </el-form-item>
        <el-form-item label="数据库表">
          <el-input v-model="dictForm.table_name" placeholder="如: pms_project_archive" />
        </el-form-item>
        <el-form-item label="字段名">
          <el-input v-model="dictForm.field_name" placeholder="如: product_type" />
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

    <!-- 枚举值弹窗 -->
    <el-dialog v-model="itemDialogVisible" :title="isItemEdit ? '编辑枚举值' : '新增枚举值'" width="440px">
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-width="80px">
        <el-form-item label="存储值" prop="item_value">
          <el-input v-model="itemForm.item_value" placeholder="实际存储的值" />
        </el-form-item>
        <el-form-item label="显示文本" prop="item_label">
          <el-input v-model="itemForm.item_label" placeholder="前端显示的文字" />
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

// ==================== 字典分类（按页面分组） ====================
const dictList = ref<any[]>([])
const selectedDict = ref<any>(null)
const searchText = ref('')

const groupedDicts = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  const filtered = q
    ? dictList.value.filter(d =>
        d.dict_name.toLowerCase().includes(q) ||
        d.dict_code.toLowerCase().includes(q) ||
        (d.field_name || '').toLowerCase().includes(q))
    : dictList.value
  const groups: Record<string, any[]> = {}
  for (const d of filtered) {
    const page = d.page_name || '其他'
    if (!groups[page]) groups[page] = []
    groups[page].push(d)
  }
  return groups
})

async function fetchDicts() {
  dictList.value = (await request.get('/dicts')) as any
}

function selectDict(d: any) {
  selectedDict.value = d
  fetchItems()
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
  dict_code: [{ required: true, message: '请输入字段编码' }],
  dict_name: [{ required: true, message: '请输入字段名称' }],
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

// ==================== 枚举项 ====================
const dictItems = ref<any[]>([])

async function fetchItems() {
  if (!selectedDict.value) return
  dictItems.value = (await request.get(`/dicts/${selectedDict.value.id}/items`)) as any
}

// 枚举项弹窗
const itemDialogVisible = ref(false)
const isItemEdit = ref(false)
const itemFormRef = ref<FormInstance>()
const itemForm = reactive({ id: 0, item_value: '', item_label: '', sort: 0, status: 1 })
const itemRules: FormRules = {
  item_value: [{ required: true, message: '请输入存储值' }],
  item_label: [{ required: true, message: '请输入显示文本' }],
}

function openItemDialog(row?: any) {
  if (row ? !hasPermission('system:field:edit') : !hasPermission('system:field:add')) return
  isItemEdit.value = !!(row && row.id)
  itemFormRef.value?.resetFields()
  if (row && row.id) {
    Object.assign(itemForm, { id: row.id, item_value: row.item_value, item_label: row.item_label, sort: row.sort, status: row.status })
  } else {
    Object.assign(itemForm, { id: 0, item_value: '', item_label: '', sort: 0, status: 1 })
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

// 切换启用/禁用状态
async function handleToggleStatus(row: any) {
  if (!hasPermission('system:field:edit')) return
  const newStatus = row.status === 1 ? 0 : 1
  await request.put(`/dicts/items/${row.id}`, { status: newStatus })
  ElMessage.success(newStatus === 1 ? '已启用' : '已禁用')
  fetchItems()
}

async function handleDeleteItem(id: number) {
  if (!hasPermission('system:field:delete')) return
  await ElMessageBox.confirm('确定删除该枚举值吗？被数据引用的值无法删除。', '提示', { type: 'warning' })
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
.field-page { display: flex; gap: 16px; height: 100%; }

.field-list-panel {
  width: 280px; flex-shrink: 0; background: #fff;
  border-radius: 4px; border: 1px solid #ebeef5;
  display: flex; flex-direction: column; overflow: hidden;
}
.panel-header {
  padding: 14px 16px; font-size: 15px; font-weight: 600;
  border-bottom: 1px solid #ebeef5; color: #303133;
  display: flex; justify-content: space-between; align-items: center;
}
.field-list-wrap { flex: 1; overflow-y: auto; }
.group-title {
  padding: 10px 16px 4px; font-size: 12px; color: #909399;
  font-weight: 600; text-transform: uppercase;
}
.field-item {
  padding: 10px 16px 10px 24px; cursor: pointer;
  border-bottom: 1px solid #f5f5f5; transition: background 0.15s;
}
.field-item:hover { background: #f5f7fa; }
.field-item.active { background: #ecf5ff; border-left: 3px solid #409EFF; }
.field-item-name { font-size: 14px; font-weight: 500; color: #303133; }
.field-item-meta { font-size: 12px; color: #909399; margin-top: 4px; }
.empty-tip { padding: 40px 0; text-align: center; color: #909399; font-size: 13px; }

.field-items-panel { flex: 1; min-width: 0; }
.items-header { display: flex; justify-content: space-between; align-items: center; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 400px; background: #fff; border-radius: 4px; border: 1px solid #ebeef5; }
</style>
