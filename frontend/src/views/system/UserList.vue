<template>
  <div class="user-manage-page">
    <!-- 左侧：部门树 -->
    <div class="dept-panel">
      <div class="dept-panel-header">
        <span>部门架构</span>
      </div>
      <div class="dept-tree-wrap">
        <el-tree
          ref="deptTreeRef"
          :data="deptTreeData"
          node-key="id"
          :props="{ label: 'dept_name', children: 'children' }"
          highlight-current
          default-expand-all
          draggable
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
        <li @click="openDeptDialog(null, contextMenuDeptId)">新增子部门</li>
        <li v-if="contextMenuDeptId !== 0" @click="openDeptDialog(contextMenuDeptData)">编辑部门</li>
        <li v-if="contextMenuDeptId !== 0" class="danger" @click="handleDeleteDept(contextMenuDeptId)">删除部门</li>
      </ul>
    </Teleport>

    <!-- 右侧：用户列表 -->
    <div class="user-panel">
      <el-card>
        <template #header>
          <div class="page-header">
            <span>用户管理 <el-tag v-if="selectedDeptName" size="small" type="info" style="margin-left:8px">{{ selectedDeptName }}</el-tag></span>
            <el-button type="primary" @click="openUserDialog()">新增用户</el-button>
          </div>
        </template>

        <el-table :data="userList" v-loading="loading" border stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="用户名" width="110" />
          <el-table-column prop="real_name" label="真实姓名" width="100" />
          <el-table-column prop="mobile" label="手机号" width="125" />
          <el-table-column prop="dept_name" label="部门" width="110">
            <template #default="{ row }">{{ deptMap[row.dept_id] || '-' }}</template>
          </el-table-column>
          <el-table-column prop="role_names" label="角色" :formatter="(r: any) => r.role_names?.join('，') || '-'">
          </el-table-column>
          <el-table-column prop="status" label="状态" width="70">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                {{ row.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openUserDialog(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="handleDeleteUser(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="page"
          :total="total"
          :page-size="pageSize"
          layout="total, prev, pager, next"
          @current-change="fetchUserList"
          style="margin-top: 16px; justify-content: flex-end;"
        />
      </el-card>
    </div>

    <!-- 部门新增/编辑弹窗 -->
    <el-dialog v-model="deptDialogVisible" :title="isDeptEdit ? '编辑部门' : '新增部门'" width="460px">
      <el-form ref="deptFormRef" :model="deptForm" :rules="deptRules" label-width="80px">
        <el-form-item label="上级部门">
          <el-tree-select
            v-model="deptForm.parent_id"
            :data="deptSelectData"
            :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            placeholder="无（顶级部门）"
            check-strictly
            clearable
            style="width: 100%;"
          />
        </el-form-item>
        <el-form-item label="部门名称" prop="dept_name">
          <el-input v-model="deptForm.dept_name" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="deptForm.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="deptForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deptDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleDeptSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 用户新增/编辑弹窗 -->
    <el-dialog v-model="userDialogVisible" :title="isUserEdit ? '编辑用户' : '新增用户'" width="520px">
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="isUserEdit" />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="userForm.real_name" />
        </el-form-item>
        <el-form-item label="密码" :prop="isUserEdit ? '' : 'password'">
          <el-input v-model="userForm.password" type="password" :placeholder="isUserEdit ? '不填则不修改' : '请输入密码'" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="userForm.mobile" />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="userForm.dept_id" style="width: 100%;" clearable
            :data="deptSelectData" :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            check-strictly
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="userForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role_ids" multiple placeholder="请选择角色" style="width: 100%;">
            <el-option v-for="r in roleList" :key="r.id" :label="r.role_name" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUserSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { OfficeBuilding } from '@element-plus/icons-vue'
import request from '@/utils/request'

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
  const valid = await deptFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (isDeptEdit.value) {
    await request.put(`/depts/${deptForm.id}`, deptForm)
    ElMessage.success('部门更新成功')
  } else {
    await request.post('/depts', deptForm)
    ElMessage.success('部门创建成功')
  }
  deptDialogVisible.value = false
  await fetchDeptTree()
}

async function handleDeleteDept(id: number) {
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
const loading = ref(false)
const page = ref(1)
const pageSize = ref(15)
const total = ref(0)

// 用户弹窗
const userDialogVisible = ref(false)
const isUserEdit = ref(false)
const userFormRef = ref<FormInstance>()
const userForm = reactive({
  id: 0, username: '', real_name: '', password: '', mobile: '',
  dept_id: null as number | null, status: 1, role_ids: [] as number[],
})
const userRules: FormRules = {
  username: [{ required: true, message: '请输入用户名' }],
  real_name: [{ required: true, message: '请输入真实姓名' }],
  password: [{ required: true, message: '请输入密码' }],
}

async function fetchUserList() {
  loading.value = true
  const params: any = { page: page.value, page_size: pageSize.value }
  if (selectedDeptId.value !== null) params.dept_id = selectedDeptId.value
  const res: any = await request.get('/users', { params })
  userList.value = res.items
  total.value = res.total
  loading.value = false
}

async function fetchRoles() {
  roleList.value = (await request.get('/roles')) as any
}

function openUserDialog(row?: any) {
  isUserEdit.value = !!row
  userFormRef.value?.resetFields()
  if (row) {
    Object.assign(userForm, {
      id: row.id, username: row.username, real_name: row.real_name,
      mobile: row.mobile, dept_id: row.dept_id, status: row.status,
      role_ids: row.role_ids || [],
    })
    userForm.password = ''
  } else {
    Object.assign(userForm, {
      id: 0, username: '', real_name: '', password: '', mobile: '',
      dept_id: selectedDeptId.value, status: 1, role_ids: [],
    })
  }
  userDialogVisible.value = true
}

async function handleUserSubmit() {
  const valid = await userFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (isUserEdit.value) {
    await request.put(`/users/${userForm.id}`, {
      real_name: userForm.real_name, mobile: userForm.mobile,
      dept_id: userForm.dept_id, status: userForm.status,
      role_ids: userForm.role_ids,
      ...(userForm.password ? { password: userForm.password } : {}),
    })
    ElMessage.success('更新成功')
  } else {
    await request.post('/users', userForm)
    ElMessage.success('创建成功')
  }
  userDialogVisible.value = false
  fetchUserList()
}

async function handleDeleteUser(id: number) {
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
  display: flex;
  gap: 16px;
  height: 100%;
}

.dept-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dept-panel-header {
  padding: 14px 16px;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5;
  color: #303133;
}
.dept-tree-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.tree-node-label {
  font-size: 13px;
  user-select: none;
}

.user-panel {
  flex: 1;
  min-width: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 右键菜单 */
.context-menu {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.12);
  padding: 4px 0;
  min-width: 120px;
  list-style: none;
  margin: 0;
}
.context-menu li {
  padding: 7px 16px;
  font-size: 13px;
  cursor: pointer;
  color: #303133;
  transition: background 0.15s;
}
.context-menu li:hover {
  background: #f5f7fa;
  color: #409EFF;
}
.context-menu li.danger:hover {
  color: #F56C6C;
  background: #fef0f0;
}
</style>
