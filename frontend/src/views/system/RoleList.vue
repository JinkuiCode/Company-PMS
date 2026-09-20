<template>
  <div class="role-page pms-page pms-system-page">
    <section class="role-list-section pms-surface-section">
      <div class="page-header pms-section-header">
        <span class="pms-section-title">角色管理</span>
        <el-button v-if="hasPermission('system:role:add')" type="primary" size="small" @click="openDialog()">新增角色</el-button>
      </div>

      <el-table class="pms-dense-table" height="100%" :data="roleList" border stripe size="small">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="role_name" label="角色名称" width="150" />
        <el-table-column prop="role_code" label="角色编码" width="150" />
        <el-table-column prop="data_scope" label="数据权限" width="150">
          <template #default="{ row }">
            <span class="pms-status pms-status-neutral">{{ ['', '仅本人', '本部门', '本部门及子部门', '全部'][row.data_scope] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="产品类别" width="200">
          <template #default="{ row }">
            <template v-if="row.product_category_ids">
              <span v-for="pl in row.product_category_ids.split(',')" :key="pl" class="pms-chip role-product-chip">{{ productCategoryLabel(pl) }}</span>
            </template>
            <span v-else class="pms-chip">全部</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <span class="pms-status" :class="row.status === 1 ? 'pms-status-success' : 'pms-status-danger'">
              <span class="pms-status-dot"></span>
              {{ row.status === 1 ? '启用' : '禁用' }}
            </span>
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
    </section>

    <PmsFormDrawer v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新增角色'" :busy="saving">
      <div :inert="saving">
        <!-- 基础信息 -->
        <div class="form-section">
          <h3 class="pms-form-drawer__section">基础信息</h3>
          <el-form id="pms-role-form" ref="formRef" :model="form" :rules="rules" label-position="top" class="pms-standard-dialog-form" @submit.prevent="handleSubmit">
                <el-form-item prop="role_name">
                  <PmsFormField field-id="role-name" label="角色名称" required>
                    <PmsTextControl id="role-name" v-model="form.role_name" aria-label="角色名称" />
                  </PmsFormField>
                </el-form-item>
                <el-form-item prop="role_code">
                  <PmsFormField field-id="role-code" label="角色编码" required>
                    <PmsTextControl id="role-code" v-model="form.role_code" :disabled="isEdit" aria-label="角色编码" />
                  </PmsFormField>
                </el-form-item>
                <el-form-item>
                  <PmsFormField field-id="role-data-scope" label="数据权限">
                    <PmsSelectControl
                      id="role-data-scope"
                      :model-value="form.data_scope"
                      :options="dataScopeOptions"
                      aria-label="数据权限"
                      @update:model-value="form.data_scope = Number($event)"
                    />
                  </PmsFormField>
                </el-form-item>
                <el-form-item>
                  <PmsFormField field-id="role-status" label="状态">
                    <PmsSwitchControl
                      id="role-status"
                      :model-value="form.status === 1"
                      aria-label="角色状态"
                      @update:model-value="form.status = $event ? 1 : 0"
                    />
                  </PmsFormField>
                </el-form-item>
            <el-form-item>
              <PmsFormField field-id="role-product-categories" label="产品类别" hint="不选 = 不限制（全部产品类别）">
                <PmsCheckboxGroupControl
                  id="role-product-categories"
                  :model-value="selectedProductCategories"
                  :options="productCategoryCheckboxOptions"
                  aria-label="产品类别范围"
                  @update:model-value="selectedProductCategories = $event.map(String)"
                />
              </PmsFormField>
            </el-form-item>
                <el-form-item>
                  <PmsFormField field-id="role-home" label="登录后打开" hint="仅可选择本角色有查看权限的页面">
                    <PmsSelectControl id="role-home" :model-value="form.home_menu_id" :options="homeOptions" aria-label="登录后打开" @update:model-value="form.home_menu_id = Number($event)" />
                  </PmsFormField>
                </el-form-item>
                <el-form-item>
                  <PmsFormField field-id="role-home-priority" label="首页优先级" hint="多角色时数值高的优先，同值按角色ID">
                    <PmsNumberControl id="role-home-priority" :model-value="form.home_priority" :min="0" :max="999" :precision="0" aria-label="首页优先级" @update:model-value="form.home_priority = Number($event || 0)" />
                  </PmsFormField>
                </el-form-item>
            <el-form-item>
              <PmsFormField field-id="role-remark" label="备注">
                <PmsTextareaControl id="role-remark" v-model="form.remark" :rows="2" aria-label="角色备注" />
              </PmsFormField>
            </el-form-item>
          </el-form>
        </div>

        <!-- 权限配置 -->
        <div class="perm-section">
          <h3 class="pms-form-drawer__section role-permission-heading">
            权限配置
            <PmsCheckboxControl
              class="permission-check-all"
              :model-value="checkAll"
              :indeterminate="isIndeterminate"
              size="compact"
              aria-label="全选权限"
              @update:model-value="handleCheckAll"
            >
              全选
            </PmsCheckboxControl>
          </h3>
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
                  <el-icon v-if="data.menu_type === 'M'" class="perm-node-icon"><FolderOpened /></el-icon>
                  <el-icon v-else-if="data.menu_type === 'C'" class="perm-node-icon"><Document /></el-icon>
                  <el-icon v-else class="perm-node-icon"><Key /></el-icon>
                  {{ node.label }}
                </span>
              </template>
            </el-tree>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button v-if="isEdit ? hasPermission('system:role:edit') : hasPermission('system:role:add')" type="primary" :loading="saving" native-type="submit" form="pms-role-form">保存</el-button>
      </template>
    </PmsFormDrawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { loadEnumOptions, type EnumOption } from '@/composables/useEnumOptions'
import { Document, FolderOpened, Key } from '@element-plus/icons-vue'
import {
  PmsCheckboxControl,
  PmsCheckboxGroupControl,
  PmsFormField,
  PmsFormDrawer,
  PmsSelectControl,
  PmsNumberControl,
  PmsSwitchControl,
  PmsTextareaControl,
  PmsTextControl,
  type PmsOption,
} from '@/form-system'

const authStore = useAuthStore()
const hasPermission = authStore.hasPermission

const roleList = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const permTreeRef = ref()
const permTree = ref<any[]>([])
const checkedMenuIds = ref<number[]>([])
const productCategoryOptions = ref<EnumOption[]>([])
const selectedProductCategories = ref<string[]>([])
const visibleProductCategories = computed(() => {
  const byValue = new Map(productCategoryOptions.value.map(item => [item.value, item]))
  selectedProductCategories.value.forEach(value => {
    if (!byValue.has(value)) byValue.set(value, { value, label: value, status: 0 })
  })
  return Array.from(byValue.values()).filter(item => item.status !== 0 || selectedProductCategories.value.includes(item.value))
})
const productCategoryCheckboxOptions = computed<PmsOption[]>(() => visibleProductCategories.value.map(item => ({
  value: item.value,
  label: item.label,
  disabled: item.status === 0,
})))
const dataScopeOptions: PmsOption[] = [
  { label: '仅本人', value: 1 },
  { label: '本部门', value: 2 },
  { label: '本部门及子部门', value: 3 },
  { label: '全部数据', value: 4 },
]

function productCategoryLabel(value: string) {
  return productCategoryOptions.value.find(item => item.value === value)?.label || value
}

async function loadProductCategories() {
  const definition = await loadEnumOptions('product_category')
  productCategoryOptions.value = definition.all_items
}

const form = reactive({
  id: 0,
  role_name: '',
  role_code: '',
  data_scope: 1,
  status: 1,
  remark: '',
  home_menu_id: 0,
  home_priority: 0,
})

const homeOptions = computed<PmsOption[]>(() => {
  const options: PmsOption[] = [{ label: '自动选择可访问页面', value: 0 }]
  const selected = new Set(checkedMenuIds.value)
  function walk(nodes: any[], parentAvailable = true) {
    for (const node of nodes) {
      const available = parentAvailable && node.status === 1 && node.visible === 1 && selected.has(node.id)
      const permission = node.path ? router.resolve(node.path).meta.permission : undefined
      const view = node.permission_code === permission ? node : node.children?.find((child: any) => child.permission_code === permission)
      if (available && node.menu_type === 'C' && permission && view?.status === 1 && selected.has(view.id)) options.push({ label: node.menu_name, value: node.id })
      walk(node.children || [], available)
    }
  }
  walk(permTree.value)
  return options
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
  checkedMenuIds.value = [...checkedKeys, ...permTreeRef.value.getHalfCheckedKeys()]
  if (!homeOptions.value.some(option => option.value === form.home_menu_id)) form.home_menu_id = 0
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
  updateCheckAllState()
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
  if (saving.value) return
  if (row ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  isEdit.value = !!row
  formRef.value?.resetFields()

  // 加载权限树
  permTree.value = (await request.get('/menus/tree')) as any

  if (row) {
    Object.assign(form, {
      id: row.id, role_name: row.role_name, role_code: row.role_code,
      data_scope: row.data_scope, status: row.status, remark: row.remark,
      home_menu_id: row.home_menu_id || 0, home_priority: row.home_priority || 0,
    })
    selectedProductCategories.value = row.product_category_ids ? row.product_category_ids.split(',').filter((s: string) => s.trim()) : []
    // 加载该角色已有的权限
    const res: any = await request.get(`/roles/${row.id}/menus`)
    checkedMenuIds.value = res.menu_ids || []
  } else {
    Object.assign(form, { id: 0, role_name: '', role_code: '', data_scope: 1, status: 1, remark: '', home_menu_id: 0, home_priority: 0 })
    selectedProductCategories.value = []
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
  if (saving.value) return
  if (isEdit.value ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || saving.value) return

  // 获取所有勾选的节点（含半选的父节点）
  const checkedKeys = permTreeRef.value?.getCheckedKeys() || []
  const halfCheckedKeys = permTreeRef.value?.getHalfCheckedKeys() || []
  const menuIds = [...checkedKeys, ...halfCheckedKeys]

  const payload = {
    role_name: form.role_name,
    role_code: form.role_code,
    data_scope: form.data_scope,
    product_category_ids: selectedProductCategories.value.length > 0 ? selectedProductCategories.value.join(',') : null,
    status: form.status,
    remark: form.remark,
    menu_ids: menuIds,
    home_menu_id: form.home_menu_id || null,
    home_priority: form.home_priority,
  }

  saving.value = true
  try {
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
  } catch {
    // The request interceptor reports failures; preserve the draft for retry.
  } finally {
    saving.value = false
  }
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

onMounted(() => { fetchList(); loadProductCategories() })
</script>

<style scoped>
.page-header {
  flex: 0 0 auto;
}

.role-page {
  height: 100%;
  min-height: 0;
  padding: 0;
  border: 0;
  box-shadow: none;
}

.role-list-section {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.role-product-chip {
  margin: 2px 4px 2px 0;
}

.role-permission-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.perm-tree-wrap {
  padding: 8px 0;
}

.perm-node {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--pms-font-size-base);
}
.perm-type-M { font-weight: 600; }
.perm-type-C { font-weight: 500; }
.perm-type-B { color: var(--pms-text-secondary); font-size: var(--pms-font-size-sm); }
.perm-node-icon { color: var(--pms-text-muted); font-size: 14px; }
.permission-check-all { margin-left: auto; }

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
