<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>角色管理</span>
          <el-button v-if="hasPermission('system:role:add')" type="primary" @click="openDialog()">新增角色</el-button>
        </div>
      </template>

      <el-table :data="roleList" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="role_name" label="角色名称" width="150" />
        <el-table-column prop="role_code" label="角色编码" width="150" />
        <el-table-column prop="data_scope" label="数据权限" width="150">
          <template #default="{ row }">
            <el-tag size="small">{{ ['', '仅本人', '本部门', '本部门及子部门', '全部'][row.data_scope] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="产品线" width="200">
          <template #default="{ row }">
            <template v-if="row.product_lines">
              <el-tag v-for="pl in row.product_lines.split(',')" :key="pl" size="small" style="margin:2px 4px 2px 0;">{{ productLineLabel(pl) }}</el-tag>
            </template>
            <el-tag v-else size="small" type="info">全部</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="hasPermission('system:role:edit')" link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="hasPermission('system:role:delete')" link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗（含权限配置） -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新增角色'" width="680px" top="4vh">
      <div class="dialog-body">
        <!-- 基础信息 -->
        <div class="form-section">
          <div class="section-title">基础信息</div>
          <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="角色名称" prop="role_name">
                  <el-input v-model="form.role_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="角色编码" prop="role_code">
                  <el-input v-model="form.role_code" :disabled="isEdit" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="数据权限">
                  <el-select v-model="form.data_scope" style="width: 100%;">
                    <el-option label="仅本人" :value="1" />
                    <el-option label="本部门" :value="2" />
                    <el-option label="本部门及子部门" :value="3" />
                    <el-option label="全部数据" :value="4" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="状态">
                  <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="产品线">
              <el-checkbox-group v-model="selectedProductLines">
                <el-checkbox
                  v-for="pl in visibleProductLines"
                  :key="pl.value"
                  :label="pl.label"
                  :value="pl.value"
                  :disabled="pl.status === 0"
                />
              </el-checkbox-group>
              <div style="font-size:12px;color:#909399;">不选 = 不限制（全部产品线）</div>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
        </div>

        <!-- 权限配置 -->
        <div class="perm-section">
          <div class="section-title">
            权限配置
            <el-checkbox v-model="checkAll" :indeterminate="isIndeterminate" @change="handleCheckAll" size="small" style="margin-left:auto">
              全选
            </el-checkbox>
          </div>
          <div class="perm-tree-wrap">
            <el-tree
              ref="permTreeRef"
              :data="permTree"
              node-key="id"
              :props="{ label: 'menu_name', children: 'children' }"
              show-checkbox
              default-expand-all
              :check-strictly="false"
              @check="handleTreeCheck"
            >
              <template #default="{ node, data }">
                <span :class="['perm-node', 'perm-type-' + data.menu_type]" :data-id="data.id">
                  {{ data.menu_type === 'M' ? '📂 ' : data.menu_type === 'C' ? '📄 ' : '' }}{{ node.label }}
                </span>
              </template>
            </el-tree>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="isEdit ? hasPermission('system:role:edit') : hasPermission('system:role:add')" type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { loadEnumOptions, type EnumOption } from '@/composables/useEnumOptions'

const authStore = useAuthStore()
const hasPermission = authStore.hasPermission

const roleList = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const permTreeRef = ref()
const permTree = ref<any[]>([])
const checkedMenuIds = ref<number[]>([])
const productLineOptions = ref<EnumOption[]>([])
const selectedProductLines = ref<string[]>([])
const visibleProductLines = computed(() => {
  const byValue = new Map(productLineOptions.value.map(item => [item.value, item]))
  selectedProductLines.value.forEach(value => {
    if (!byValue.has(value)) byValue.set(value, { value, label: value, status: 0 })
  })
  return Array.from(byValue.values()).filter(item => item.status !== 0 || selectedProductLines.value.includes(item.value))
})

function productLineLabel(value: string) {
  return productLineOptions.value.find(item => item.value === value)?.label || value
}

async function loadProductLines() {
  const definition = await loadEnumOptions('product_line')
  productLineOptions.value = definition.all_items
}

const form = reactive({
  id: 0,
  role_name: '',
  role_code: '',
  data_scope: 1,
  status: 1,
  remark: '',
})

const rules: FormRules = {
  role_name: [{ required: true, message: '请输入角色名称' }],
  role_code: [{ required: true, message: '请输入角色编码' }],
}

// 全选状态
const allLeafIds = computed(() => {
  const ids: number[] = []
  function walk(nodes: any[]) {
    for (const n of nodes) {
      if (!n.children || n.children.length === 0) {
        ids.push(n.id)
      } else {
        walk(n.children)
      }
    }
  }
  walk(permTree.value)
  return ids
})

const checkAll = ref(false)
const isIndeterminate = ref(false)

function updateCheckAllState() {
  if (!permTreeRef.value) return
  const checkedKeys = permTreeRef.value.getCheckedKeys() as number[]
  const checkedLeafCount = checkedKeys.filter((k: number) => allLeafIds.value.includes(k)).length
  const totalLeaf = allLeafIds.value.length
  checkAll.value = checkedLeafCount === totalLeaf && totalLeaf > 0
  isIndeterminate.value = checkedLeafCount > 0 && checkedLeafCount < totalLeaf
}

function handleCheckAll(val: boolean) {
  if (!permTreeRef.value) return
  if (val) {
    permTreeRef.value.setCheckedKeys(allLeafIds.value)
  } else {
    permTreeRef.value.setCheckedKeys([])
  }
  isIndeterminate.value = false
}

function handleTreeCheck(data: any, state: { checkedKeys: number[] }) {
  if (data.menu_type === 'B' && data.permission_code) {
    const parent = permTreeRef.value?.getNode(data.parent_id)?.data
    const siblings = parent?.children || []
    const isChecked = state.checkedKeys.includes(data.id)
    if (data.permission_code.endsWith(':view') && !isChecked) {
      siblings
        .filter((item: any) => item.menu_type === 'B' && item.id !== data.id)
        .forEach((item: any) => permTreeRef.value?.setChecked(item.id, false, false))
    } else if (!data.permission_code.endsWith(':view') && isChecked) {
      const viewPermission = siblings.find(
        (item: any) => item.menu_type === 'B' && item.permission_code?.endsWith(':view'),
      )
      if (viewPermission) permTreeRef.value?.setChecked(viewPermission.id, true, false)
    }
  }
  updateCheckAllState()
}

// ==================== 角色 CRUD ====================
async function fetchList() {
  roleList.value = (await request.get('/roles')) as any
}

async function openDialog(row?: any) {
  if (row ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  isEdit.value = !!row
  formRef.value?.resetFields()

  // 加载权限树
  permTree.value = (await request.get('/menus/tree')) as any

  if (row) {
    Object.assign(form, {
      id: row.id, role_name: row.role_name, role_code: row.role_code,
      data_scope: row.data_scope, status: row.status, remark: row.remark,
    })
    selectedProductLines.value = row.product_lines ? row.product_lines.split(',').filter((s: string) => s.trim()) : []
    // 加载该角色已有的权限
    const res: any = await request.get(`/roles/${row.id}/menus`)
    checkedMenuIds.value = res.menu_ids || []
  } else {
    Object.assign(form, { id: 0, role_name: '', role_code: '', data_scope: 1, status: 1, remark: '' })
    selectedProductLines.value = []
    checkedMenuIds.value = []
  }

  dialogVisible.value = true

  // 等待DOM渲染后设置已勾选的节点
  setTimeout(() => {
    if (permTreeRef.value) {
      // 只勾选叶子节点，避免父子联动时重复设置
      const leafChecked = checkedMenuIds.value.filter(id => allLeafIds.value.includes(id))
      permTreeRef.value.setCheckedKeys(leafChecked)
      updateCheckAllState()
    }
    // 将含B类型子节点的容器标记为横排
    markButtonContainers()
  }, 120)
}

async function handleSubmit() {
  if (isEdit.value ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 获取所有勾选的节点（含半选的父节点）
  const checkedKeys = permTreeRef.value?.getCheckedKeys() || []
  const halfCheckedKeys = permTreeRef.value?.getHalfCheckedKeys() || []
  const menuIds = [...checkedKeys, ...halfCheckedKeys]

  const payload = {
    role_name: form.role_name,
    role_code: form.role_code,
    data_scope: form.data_scope,
    product_lines: selectedProductLines.value.length > 0 ? selectedProductLines.value.join(',') : null,
    status: form.status,
    remark: form.remark,
    menu_ids: menuIds,
  }

  if (isEdit.value) {
    await request.put(`/roles/${form.id}`, payload)
    ElMessage.success('角色更新成功')
  } else {
    await request.post('/roles', payload)
    ElMessage.success('角色创建成功')
  }
  dialogVisible.value = false
  await authStore.fetchUser()
  if (!hasPermission('system:role:view')) {
    window.location.href = '/403'
    return
  }
  await fetchList()
}

async function handleDelete(id: number) {
  if (!hasPermission('system:role:delete')) return
  await ElMessageBox.confirm('确定删除该角色吗？', '提示', { type: 'warning' })
  await request.delete(`/roles/${id}`)
  ElMessage.success('删除成功')
  fetchList()
}

// 将包含B类型节点的children容器加上 inline-buttons class
function markButtonContainers() {
  const wrap = document.querySelector('.perm-tree-wrap')
  if (!wrap) return
  // 找到所有 B 类型节点
  const btnNodes = wrap.querySelectorAll('.perm-type-B')
  btnNodes.forEach((btn: Element) => {
    // B节点的父级 .el-tree-node 的父级 .el-tree-node__children 就是横排容器
    const treeNode = btn.closest('.el-tree-node')
    const childrenContainer = treeNode?.parentElement
    if (childrenContainer?.classList.contains('el-tree-node__children')) {
      childrenContainer.classList.add('inline-buttons')
    }
  })
}

onMounted(() => { fetchList(); loadProductLines() })
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-body {
  max-height: 70vh;
  overflow-y: auto;
}

.form-section,
.perm-section {
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
}

.perm-tree-wrap {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
}

.perm-node {
  font-size: 13px;
}
.perm-type-M { font-weight: 600; }
.perm-type-C { font-weight: 500; }
.perm-type-B { font-size: 12px; color: #606266; }

/* 按钮权限横排显示 */
.perm-tree-wrap :deep(.inline-buttons) {
  display: flex;
  flex-wrap: wrap;
  padding-left: 24px !important;
}
.perm-tree-wrap :deep(.inline-buttons > .el-tree-node) {
  width: auto;
  min-width: 80px;
  padding-left: 0 !important;
}
/* 隐藏B类型节点的展开箭头 */
.perm-tree-wrap :deep(.inline-buttons > .el-tree-node > .el-tree-node__content .el-tree-node__expand-icon) {
  display: none;
}
</style>
