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
        <div class="pms-system-toolbar-actions">
          <el-button v-if="hasPermission('system:user:add')" type="primary" size="small" @click="openUserDialog()">新增用户</el-button>
          <PmsPageGuide page="users" />
        </div>
      </div>

        <PmsQueryWorkspace entry-mode="document" v-model="queryDraft" list-key="system-user" :fields="queryFields" :defaults="queryDefaults" :loading="loading" :snapshot="() => ({ pageSize })" @query="runQuery" @clear-columns="clearQueryColumns" />
        <div v-if="userListState.failed.value" class="pms-list-load-error" role="alert">用户数据未完整读取，请重试 <el-button link class="pms-button-navigation" @click="fetchUserList">重试</el-button></div>
        <el-table class="pms-dense-table" height="100%" :data="pagedUsers" v-loading="loading" border stripe size="small">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="账号（工号）" width="120" :class-name="queryColumnClass('username')" :label-class-name="queryColumnClass('username')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'username',displayName:'账号（工号）'}" /></template></el-table-column>
          <el-table-column prop="real_name" label="员工姓名" width="100" :class-name="queryColumnClass('real_name')" :label-class-name="queryColumnClass('real_name')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'real_name',displayName:'员工姓名'}" /></template></el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip :class-name="queryColumnClass('email')" :label-class-name="queryColumnClass('email')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'email',displayName:'邮箱'}" /></template></el-table-column>
          <el-table-column prop="mobile" label="手机号" width="125" :class-name="queryColumnClass('mobile')" :label-class-name="queryColumnClass('mobile')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'mobile',displayName:'手机号'}" /></template></el-table-column>
          <el-table-column prop="dept_name" label="部门" width="110" :class-name="queryColumnClass('dept_id')" :label-class-name="queryColumnClass('dept_id')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'dept_id',displayName:'部门'}" /></template>
            <template #default="{ row }">{{ deptMap[row.dept_id] || '-' }}</template>
          </el-table-column>
          <el-table-column prop="role_names" label="角色" :formatter="(r: any) => r.role_names?.join('，') || '-'" :class-name="queryColumnClass('role_names')" :label-class-name="queryColumnClass('role_names')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'role_names',displayName:'角色'}" /></template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="70" :class-name="queryColumnClass('status')" :label-class-name="queryColumnClass('status')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'status',displayName:'状态'}" /></template>
            <template #default="{ row }">
              <span class="pms-status" :class="row.status === 1 ? 'pms-status-success' : 'pms-status-danger'">
                <span class="pms-status-dot"></span>
                {{ row.status === 1 ? '启用' : '禁用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column v-if="(Number(hasPermission('system:user:edit')||hasPermission('system:user:reset-password'))+Number(hasPermission('system:user:delete')))>0" label="操作" :width="pmsActionColumn(Number(hasPermission('system:user:edit')||hasPermission('system:user:reset-password'))+Number(hasPermission('system:user:delete'))).width" fixed="right">
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

    <PmsFormDrawer v-model="deptDialogVisible" :title="isDeptEdit ? '编辑部门' : '新增部门'" :busy="deptSaving" :before-close="beforeDeptClose">
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
        <el-form-item prop="leader_id">
          <PmsFormField field-id="dept-leader" label="部门负责人" required :error="deptLeaderError">
            <PmsSelectControl
              id="dept-leader"
              v-model="deptForm.leader_id"
              :options="deptLeaderOptions"
              :loading="deptLeadersLoading"
              :disabled="deptSaving || deptLeadersLoading || Boolean(deptLeaderError)"
              aria-label="部门负责人"
              aria-required="true"
              placeholder="请选择部门负责人"
              filterable
              clearable
            />
            <el-button v-if="deptLeaderError" class="pms-button-auxiliary" @click="loadDeptLeaders">重试</el-button>
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
        <el-button class="pms-button-reset" :disabled="deptSaving" @click="closeDeptDialog">取消</el-button>
        <el-button v-if="isDeptEdit ? hasPermission('system:user:edit') : hasPermission('system:user:add')" class="pms-button-save" type="primary" :loading="deptSaving" :disabled="deptLeadersLoading || Boolean(deptLeaderError)" native-type="submit" form="pms-dept-form">保存</el-button>
      </template>
    </PmsFormDrawer>

    <UserFormDrawer v-model="userDialogVisible" :user="editingUser" :departments="deptSelectData" :roles="roleOptions" :default-dept="selectedDeptId" @saved="handleUserSaved" />
  </div>
</template>

<script setup lang="ts">
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import { useSystemQuery, loadCompleteDataset } from '@/query-system/system-adapter'
import type { QueryCondition } from '@/query-system/core'
import { computed, ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { usePageLoad } from '@/composables/usePageLoad'
import { useFormSession } from '@/form-system/useFormSession'
import { pmsActionColumn } from '@/config/listUi'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { OfficeBuilding } from '@element-plus/icons-vue'
import CustomPagination from '@/components/CustomPagination.vue'
import UserFormDrawer from './UserFormDrawer.vue'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/config/listUi'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import {
  PmsFormDrawer,
  PmsFormField,
  PmsNumberControl,
  PmsSelectControl,
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
const deptForm = reactive({ id: 0, parent_id: 0, dept_name: '', leader_id: null as number | null, sort: 0, status: 1 })
const deptFormSession = useFormSession({ draft: deptForm, isConflict: (error: any) => error?.response?.status === 409 })
const deptSaving = deptFormSession.busy
const deptLeaderUsers = ref<Array<{ id: number; real_name: string; username: string }>>([])
const deptLegacyLeaderLabel = ref('')
const deptLeadersLoading = ref(false)
const deptLeaderError = ref('')
let deptLeaderRequest: AbortController | undefined
const deptLeaderOptions = computed<PmsOption[]>(() => {
  const options: PmsOption[] = deptLeaderUsers.value.map(user => ({
    value: user.id, label: `${user.real_name || user.username}（${user.username}）`,
  }))
  if (deptForm.leader_id != null && !options.some(option => option.value === deptForm.leader_id)) {
    options.push({ value: deptForm.leader_id, label: `${deptLegacyLeaderLabel.value || `用户${deptForm.leader_id}`}（不可选）`, disabled: true })
  }
  return options
})
const deptRules: FormRules = {
  dept_name: [{ required: true, message: '请输入部门名称' }],
  leader_id: [{ required: true, message: '请选择部门负责人', trigger: 'change' }, {
    validator: (_rule, value, callback) => callback(
      value != null && !deptLeaderUsers.value.some(user => user.id === value)
        ? new Error('请选择启用的PMS用户') : undefined,
    ), trigger: 'change',
  }],
}

async function loadDeptLeaders() {
  deptLeaderRequest?.abort()
  const controller = new AbortController()
  deptLeaderRequest = controller
  deptLeadersLoading.value = true
  deptLeaderError.value = ''
  deptLeaderUsers.value = []
  try {
    const users = await request.get('/users/options', { signal: controller.signal })
    if (deptLeaderRequest === controller && deptDialogVisible.value) deptLeaderUsers.value = users as any
  } catch {
    if (!controller.signal.aborted && deptLeaderRequest === controller && deptDialogVisible.value) {
      deptLeaderError.value = '无法加载负责人选项，请重试'
    }
  } finally {
    if (deptLeaderRequest === controller) deptLeadersLoading.value = false
  }
}
watch(deptDialogVisible, visible => {
  if (!visible) deptLeaderRequest?.abort()
})
onBeforeUnmount(() => deptLeaderRequest?.abort())

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
  try {
    await request.put(`/depts/${dragId}`, { parent_id: newParentId })
    ElMessage.success('部门层级已更新')
  } finally {
    await fetchDeptTree()
  }
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
async function canLeaveDepartment() {
  if (!deptDialogVisible.value) return true
  return deptFormSession.requestClose(async () => {
    try {
      await ElMessageBox.confirm('放弃尚未保存的部门修改？', '未保存修改', { type: 'warning' })
      return true
    } catch { return false }
  })
}

async function beforeDeptClose(done: () => void) {
  if (!await canLeaveDepartment()) return
  deptFormSession.restore()
  done()
}

function closeDeptDialog() {
  return beforeDeptClose(() => { deptDialogVisible.value = false })
}

onBeforeRouteLeave(canLeaveDepartment)

async function openDeptDialog(row?: any, parentId?: number) {
  if (deptSaving.value) return
  if (row ? !hasPermission('system:user:edit') : !hasPermission('system:user:add')) return
  if (deptDialogVisible.value && !await canLeaveDepartment()) return
  if (row ? !hasPermission('system:user:edit') : !hasPermission('system:user:add')) return
  contextMenuVisible.value = false
  isDeptEdit.value = !!(row && row.id)
  deptFormRef.value?.resetFields()
  if (row && row.id) {
    Object.assign(deptForm, { id: row.id, parent_id: row.parent_id ?? 0, dept_name: row.dept_name, leader_id: row.leader_id ?? null, sort: row.sort ?? 0, status: row.status ?? 1 })
    deptLegacyLeaderLabel.value = row.leader_label || ''
  } else {
    Object.assign(deptForm, { id: 0, parent_id: parentId ?? 0, dept_name: '', leader_id: null, sort: 0, status: 1 })
    deptLegacyLeaderLabel.value = ''
  }
  deptFormSession.capture()
  deptDialogVisible.value = true
  void loadDeptLeaders()
}

async function handleDeptSubmit() {
  if (deptSaving.value || deptLeadersLoading.value || deptLeaderError.value) return
  if (isDeptEdit.value ? !hasPermission('system:user:edit') : !hasPermission('system:user:add')) return
  const editing = isDeptEdit.value
  const result = await deptFormSession.submit({
    validate: async () => Boolean(await deptFormRef.value?.validate().catch(() => false)),
    save: snapshot => editing ? request.put(`/depts/${snapshot.id}`, snapshot) : request.post('/depts', snapshot),
    // The request interceptor reports the error; the session preserves input.
  })
  if (result.status !== 'success') return
  ElMessage.success(editing ? '部门更新成功' : '部门创建成功')
  deptDialogVisible.value = false
  try { await fetchDeptTree() } catch { /* List refresh failure must not resubmit a successful save. */ }
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
const userList = ref<any[]>([])
const roleList = ref<any[]>([])
const roleOptions = computed<PmsOption[]>(() => roleList.value.map(role => ({
  value: Number(role.id),
  label: String(role.role_name),
  disabled: role.status === 0,
})))
const userListState = usePageLoad()
const loading = userListState.loading
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, submit: submitQuery, topRows, pageRows, clearColumns, columnContext, columnFilters, columnClass: queryColumnClass } = useSystemQuery(() => [
  { field: 'username', label: '账号（工号）', type: 'text' },
  { field: 'real_name', label: '员工姓名', type: 'text' },
  { field: 'email', label: '邮箱', type: 'text' },
  { field: 'mobile', label: '手机号', type: 'text' },
  { field: 'dept_id', label: '部门', type: 'enum', options: Object.entries(deptMap.value).map(([value,label]) => ({value:Number(value),label})) },
  { field: 'role_names', label: '角色', type: 'text' },
  { field: 'status', label: '状态', type: 'enum', options: [{value:1,label:'启用'},{value:0,label:'禁用'}] },
], ['username', 'real_name', 'status'], {ready:()=>userListState.phase.value === 'ready' || userListState.phase.value === 'empty',pagination:{page,size:pageSize}})
const userQueryRecord = (row:any) => ({...row,role_names:row.role_names?.join('，') || ''})
const filteredUsers = computed(() => topRows(userList.value, userQueryRecord))
const total = computed(() => filteredUsers.value.length)
const pagedUsers = computed(() => pageRows(userList.value, userQueryRecord))
function runQuery(conditions: QueryCondition[], preferences: object) {
  submitQuery(conditions)
  const size = (preferences as {pageSize?:number}).pageSize
  if (size && PAGE_SIZE_OPTIONS.includes(size)) pageSize.value = size
  page.value = 1
}
function clearQueryColumns() { clearColumns() }
watch(userList, clearColumns, {flush:'sync'})

// 用户弹窗
const userDialogVisible = ref(false)
const editingUser = ref<any>(null)

async function fetchUserList() {
  const requestSerial = userListState.begin()
  const params: any = {}
  if (selectedDeptId.value !== null) params.dept_id = selectedDeptId.value
  try {
    const res = await loadCompleteDataset(async (page, pageSize) => await request.get('/users', { params: { ...params, page, page_size: pageSize } }) as any, 500, () => userListState.isCurrent(requestSerial), (row:any) => row.id)
    if (!userListState.isCurrent(requestSerial)) return
    userList.value = res.items
    userListState.succeed(requestSerial, userList.value.length === 0)
    page.value = Math.min(page.value, Math.max(1, Math.ceil(total.value / pageSize.value)))
  } catch (cause) {
    if (!userListState.isCurrent(requestSerial)) return
    userList.value = []
    userListState.fail(requestSerial, cause)
  }
}

function handlePageChange(value: number) {
  page.value = value
}

function handlePageSizeChange(value: number) {
  pageSize.value = value
  page.value = 1
}

async function fetchRoles() {
  roleList.value = (await request.get('/roles/options')) as any
}

function openUserDialog(row?: any) {
  // An open editor owns its target until it is closed through its draft guard.
  if (userDialogVisible.value) return
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
onBeforeUnmount(() => userListState.invalidate())
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
  padding: 0 var(--pms-panel-inset) var(--pms-query-inset);
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
