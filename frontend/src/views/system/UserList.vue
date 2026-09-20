<template>
  <div class="user-manage-page pms-system-page pms-split-page">
    <!-- 左侧：部门树 -->
    <div class="dept-panel pms-surface-section">
      <div class="dept-panel-header pms-section-header">
        <span class="pms-section-title">部门架构</span>
      </div>
      <div class="dept-tree-wrap">
        <el-tree
          ref="deptTreeRef"
          :data="deptTreeData"
          node-key="id"
          :props="{ label: 'dept_name', children: 'children' }"
          highlight-current
          default-expand-all
          :draggable="hasPermission('system:user:edit')"
          :expand-on-click-node="false"
          @node-click="handleDeptClick"
          @node-drop="handleDeptDrop"
          @node-contextmenu="handleContextMenu"
        >
          <template #default="{ node, data }">
            <span class="tree-node-label">
              <el-icon v-if="data.id === 0" style="margin-right:4px"><OfficeBuilding /></el-icon>
              {{ node.label }}
            </span>
          </template>
        </el-tree>
      </div>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <ul
        v-show="contextMenuVisible"
        ref="contextMenuRef"
        class="context-menu"
        :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }"
      >
        <li v-if="hasPermission('system:user:add')" @click="openDeptDialog(null, contextMenuDeptId)">新增子部门</li>
        <li v-if="contextMenuDeptId !== 0 && hasPermission('system:user:edit')" @click="openDeptDialog(contextMenuDeptData)">编辑部门</li>
        <li v-if="contextMenuDeptId !== 0 && hasPermission('system:user:delete')" class="danger" @click="handleDeleteDept(contextMenuDeptId)">删除部门</li>
      </ul>
    </Teleport>

    <!-- 右侧：用户列表 -->
    <div class="user-panel pms-surface-section">
      <div class="page-header pms-section-header">
        <div class="user-panel-title">
          <span class="pms-section-title">用户管理</span>
          <span v-if="selectedDeptName" class="pms-chip">{{ selectedDeptName }}</span>
        </div>
        <el-button v-if="hasPermission('system:user:add')" type="primary" size="small" @click="openUserDialog()">新增用户</el-button>
      </div>

        <el-table class="pms-dense-table" height="100%" :data="userList" v-loading="loading" border stripe size="small">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="账号（工号）" width="120" />
          <el-table-column prop="real_name" label="员工姓名" width="100" />
          <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
          <el-table-column prop="mobile" label="手机号" width="125" />
          <el-table-column prop="dept_name" label="部门" width="110">
            <template #default="{ row }">{{ deptMap[row.dept_id] || '-' }}</template>
          </el-table-column>
          <el-table-column prop="role_names" label="角色" :formatter="(r: any) => r.role_names?.join('，') || '-'">
          </el-table-column>
          <el-table-column prop="status" label="状态" width="70">
            <template #default="{ row }">
              <span class="pms-status" :class="row.status === 1 ? 'pms-status-success' : 'pms-status-danger'">
                <span class="pms-status-dot"></span>
                {{ row.status === 1 ? '启用' : '禁用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button v-if="hasPermission('system:user:edit') || hasPermission('system:user:reset-password')" link type="primary" size="small" @click="openUserDialog(row)">{{ hasPermission('system:user:edit') ? '编辑' : '查看' }}</el-button>
              <el-button v-if="hasPermission('system:user:delete')" link type="danger" size="small" @click="handleDeleteUser(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="user-pagination">
          <CustomPagination
          :model-value="page"
          :total="total"
          :page-size="pageSize"
          @update:model-value="handlePageChange"
          @update:page-size="handlePageSizeChange"
          />
        </div>
    </div>

    <PmsFormDrawer v-model="deptDialogVisible" :title="isDeptEdit ? '编辑部门' : '新增部门'" :busy="deptSaving">
      <h3 class="pms-form-drawer__section">基本信息</h3>
      <el-form id="pms-dept-form" ref="deptFormRef" :model="deptForm" :rules="deptRules" label-position="top" class="pms-standard-dialog-form" @submit.prevent="handleDeptSubmit">
        <el-form-item>
          <PmsFormField field-id="dept-parent" label="上级部门">
            <PmsTreeSelectControl
              id="dept-parent"
              :model-value="deptForm.parent_id || undefined"
              :data="deptSelectData"
              :props="{ label: 'dept_name', value: 'id', children: 'children' }"
              placeholder="无（顶级部门）"
              aria-label="上级部门"
              :disabled="deptSaving"
              check-strictly
              clearable
              @update:model-value="deptForm.parent_id = Number($event || 0)"
            />
          </PmsFormField>
        </el-form-item>
        <el-form-item prop="dept_name">
          <PmsFormField field-id="dept-name" label="部门名称" required>
            <PmsTextControl id="dept-name" v-model="deptForm.dept_name" :disabled="deptSaving" aria-label="部门名称" />
          </PmsFormField>
        </el-form-item>
        <el-form-item>
          <PmsFormField field-id="dept-sort" label="排序">
            <PmsNumberControl id="dept-sort" v-model="deptForm.sort" :min="0" :disabled="deptSaving" aria-label="部门排序" />
          </PmsFormField>
        </el-form-item>
        <el-form-item>
          <PmsFormField field-id="dept-status" label="状态">
            <PmsSwitchControl
              id="dept-status"
              :model-value="deptForm.status === 1"
              aria-label="部门状态"
              :disabled="deptSaving"
              @update:model-value="deptForm.status = $event ? 1 : 0"
            />
          </PmsFormField>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="deptSaving" @click="deptDialogVisible = false">取消</el-button>
        <el-button v-if="isDeptEdit ? hasPermission('system:user:edit') : hasPermission('system:user:add')" type="primary" :loading="deptSaving" native-type="submit" form="pms-dept-form">保存</el-button>
      </template>
    </PmsFormDrawer>

    <UserFormDrawer v-model="userDialogVisible" :user="editingUser" :departments="deptSelectData" :roles="roleOptions" :default-dept="selectedDeptId" @saved="handleUserSaved" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { OfficeBuilding } from '@element-plus/icons-vue'
import CustomPagination from '@/components/CustomPagination.vue'
import UserFormDrawer from './UserFormDrawer.vue'
import { DEFAULT_PAGE_SIZE } from '@/config/listUi'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import {
  PmsFormDrawer,
  PmsFormField,
  PmsNumberControl,
  PmsSwitchControl,
  PmsTextControl,
  PmsTreeSelectControl,
  type PmsOption,
} from '@/form-system'

const authStore = useAuthStore()
const hasPermission = authStore.hasPermission

// ==================== 部门树 ====================
const deptTreeRef = ref()
const deptTreeData = ref<any[]>([])
const deptMap = ref<Record<number, string>>({})  // id -> dept_name 平铺映射

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuDeptId = ref(0)
const contextMenuDeptData = ref<any>(null)
const contextMenuRef = ref<HTMLElement>()

// 部门树（不含虚拟根）用于 tree-select
const deptSelectData = ref<any[]>([])

// 当前选中部门
const selectedDeptId = ref<number | null>(null)
const selectedDeptName = ref('')

// 部门弹窗
const deptDialogVisible = ref(false)
const isDeptEdit = ref(false)
const deptFormRef = ref<FormInstance>()
const deptSaving = ref(false)
const deptForm = reactive({ id: 0, parent_id: 0, dept_name: '', sort: 0, status: 1 })
const deptRules: FormRules = { dept_name: [{ required: true, message: '请输入部门名称' }] }

async function fetchDeptTree() {
  const tree = (await request.get('/depts/tree')) as any
  // 在树顶部插入"全部"虚拟节点
  const allNode = { id: 0, dept_name: '全部部门', children: tree }
  deptTreeData.value = [allNode]
  deptSelectData.value = tree   // 实际部门树，用于弹窗 tree-select
  // 构建平铺映射
  const map: Record<number, string> = {}
  function walk(nodes: any[]) {
    for (const n of nodes) {
      if (n.id !== 0) map[n.id] = n.dept_name
      if (n.children) walk(n.children)
    }
  }
  walk(tree)
  deptMap.value = map
}

function handleDeptClick(data: any) {
  if (data.id === 0) {
    selectedDeptId.value = null
    selectedDeptName.value = ''
  } else {
    selectedDeptId.value = data.id
    selectedDeptName.value = data.dept_name
  }
  page.value = 1
  fetchUserList()
}

// 拖拽调整部门层级
async function handleDeptDrop(draggingNode: any, dropNode: any, dropType: string) {
  if (!hasPermission('system:user:edit')) {
    await fetchDeptTree()
    return
  }
  const dragId = draggingNode.data.id
  if (dragId === 0) {
    ElMessage.warning('根节点不可拖拽')
    await fetchDeptTree()
    return
  }
  let newParentId = 0
  if (dropType === 'inner') {
    // 拖入目标节点内部，父级 = 目标节点
    newParentId = dropNode.data.id === 0 ? 0 : dropNode.data.id
  } else {
    // before / after：父级 = 目标节点的父节点
    const parentNode = deptTreeRef.value?.getNode(dropNode.data.id)?.parent
    const parentId = parentNode?.data?.id
    newParentId = (parentId === undefined || parentId === 0) ? 0 : parentId
  }
  await request.put(`/depts/${dragId}`, { parent_id: newParentId })
  ElMessage.success('部门层级已更新')
  await fetchDeptTree()
}

// 右键菜单
function handleContextMenu(event: MouseEvent, data: any) {
  event.preventDefault()
  contextMenuDeptId.value = data.id
  contextMenuDeptData.value = data
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuVisible.value = true
}

function closeContextMenu() {
  contextMenuVisible.value = false
}

onMounted(() => {
  document.addEventListener('click', closeContextMenu)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closeContextMenu)
})

// 部门弹窗
function openDeptDialog(row?: any, parentId?: number) {
  if (deptSaving.value) return
  if (row ? !hasPermission('system:user:edit') : !hasPermission('system:user:add')) return
  contextMenuVisible.value = false
  isDeptEdit.value = !!(row && row.id)
  deptFormRef.value?.resetFields()
  if (row && row.id) {
    Object.assign(deptForm, { id: row.id, parent_id: row.parent_id ?? 0, dept_name: row.dept_name, sort: row.sort ?? 0, status: row.status ?? 1 })
  } else {
    Object.assign(deptForm, { id: 0, parent_id: parentId ?? 0, dept_name: '', sort: 0, status: 1 })
  }
  deptDialogVisible.value = true
}

async function handleDeptSubmit() {
  if (deptSaving.value) return
  if (isDeptEdit.value ? !hasPermission('system:user:edit') : !hasPermission('system:user:add')) return
  const valid = await deptFormRef.value?.validate().catch(() => false)
  if (!valid || deptSaving.value) return
  deptSaving.value = true
  try {
    if (isDeptEdit.value) {
      await request.put(`/depts/${deptForm.id}`, deptForm)
      ElMessage.success('部门更新成功')
    } else {
      await request.post('/depts', deptForm)
      ElMessage.success('部门创建成功')
    }
    deptDialogVisible.value = false
    await fetchDeptTree()
  } catch {
    // Request interceptor reports the error; keep the draft available for retry.
  } finally {
    deptSaving.value = false
  }
}

async function handleDeleteDept(id: number) {
  if (!hasPermission('system:user:delete')) return
  contextMenuVisible.value = false
  if (id === 0) return
  await ElMessageBox.confirm('确定删除该部门吗？', '提示', { type: 'warning' })
  await request.delete(`/depts/${id}`)
  ElMessage.success('删除成功')
  // 若删除的是当前选中部门，清除筛选
  if (selectedDeptId.value === id) {
    selectedDeptId.value = null
    selectedDeptName.value = ''
  }
  await fetchDeptTree()
  fetchUserList()
}

// ==================== 用户列表 ====================
const userList = ref([])
const roleList = ref<any[]>([])
const roleOptions = computed<PmsOption[]>(() => roleList.value.map(role => ({
  value: Number(role.id),
  label: String(role.role_name),
  disabled: role.status === 0,
})))
const loading = ref(false)
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const total = ref(0)

// 用户弹窗
const userDialogVisible = ref(false)
const editingUser = ref<any>(null)

let listRequestSerial = 0
async function fetchUserList() {
  const requestSerial = ++listRequestSerial
  loading.value = true
  const params: any = { page: page.value, page_size: pageSize.value }
  if (selectedDeptId.value !== null) params.dept_id = selectedDeptId.value
  try {
    const res: any = await request.get('/users', { params })
    if (requestSerial !== listRequestSerial) return
    userList.value = res.items
    total.value = res.total
  } catch {
    if (requestSerial === listRequestSerial) { userList.value = []; total.value = 0 }
  } finally {
    if (requestSerial === listRequestSerial) loading.value = false
  }
}

function handlePageChange(value: number) {
  page.value = value
  fetchUserList()
}

function handlePageSizeChange(value: number) {
  pageSize.value = value
  page.value = 1
  fetchUserList()
}

async function fetchRoles() {
  roleList.value = (await request.get('/roles/options')) as any
}

function openUserDialog(row?: any) {
  if (row ? !authStore.hasAnyPermission('system:user:edit', 'system:user:reset-password') : !hasPermission('system:user:add')) return
  editingUser.value = row || null
  userDialogVisible.value = true
}

function handleUserSaved() {
  if (!hasPermission('system:user:view')) { window.location.href = '/'; return }
  void fetchUserList()
}

async function handleDeleteUser(id: number) {
  if (!hasPermission('system:user:delete')) return
  await ElMessageBox.confirm('确定删除该用户吗？', '提示', { type: 'warning' })
  await request.delete(`/users/${id}`)
  ElMessage.success('删除成功')
  fetchUserList()
}

onMounted(() => {
  fetchDeptTree()
  fetchUserList()
  fetchRoles()
})
</script>

<style scoped>
.user-manage-page {
  height: 100%;
}

.dept-panel {
  display: flex;
  flex-direction: column;
}
.dept-panel-header {
  flex: 0 0 auto;
}
.dept-tree-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.tree-node-label {
  display: inline-flex;
  align-items: center;
  font-size: var(--pms-font-size-base);
  user-select: none;
}

.user-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.user-panel :deep(.el-table) { flex: 1; min-height: 0; }
.user-pagination { flex-shrink: 0; }

.page-header {
  flex: 0 0 auto;
}

.user-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.user-pagination {
  padding: 0 12px 12px;
}

/* 右键菜单 */
.context-menu {
  position: fixed;
  z-index: 9999;
  background: var(--pms-surface);
  border: 1px solid var(--pms-border);
  border-radius: var(--pms-radius-sm);
  box-shadow: 0 10px 28px rgba(16, 24, 40, 0.14);
  padding: 4px 0;
  min-width: 120px;
  list-style: none;
  margin: 0;
}
.context-menu li {
  padding: 7px 16px;
  font-size: var(--pms-font-size-base);
  cursor: pointer;
  color: var(--pms-text);
  transition: background-color 120ms ease-out, color 120ms ease-out;
}
.context-menu li:hover {
  background: var(--pms-primary-soft);
  color: var(--pms-primary);
}
.context-menu li.danger:hover {
  color: var(--pms-danger);
  background: var(--pms-danger-soft);
}
</style>
