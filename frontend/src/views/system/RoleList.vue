<template>
  <div class="role-page pms-page pms-system-page">
    <section class="role-list-section pms-surface-section">
      <div class="page-header pms-section-header">
        <span class="pms-section-title">角色管理</span>
        <div class="pms-system-toolbar-actions">
          <el-button v-if="hasPermission('system:role:add')" type="primary" size="small" :disabled="opening" @click="openDialog()">新增角色</el-button>
          <PmsPageGuide page="roles" />
        </div>
      </div>

      <PmsQueryWorkspace entry-mode="document" v-model="queryDraft" list-key="system-role" :fields="queryFields" :defaults="queryDefaults" :loading="queryLoading" @query="submitQuery" @clear-columns="clearQueryColumns" />
      <div v-if="roleListState.failed.value" class="pms-list-load-error" role="alert">角色读取失败，请重试 <el-button link class="pms-button-navigation" @click="fetchList">重试</el-button></div>
      <el-table v-loading="queryLoading" class="pms-dense-table" height="100%" :data="filteredRoles" border stripe size="small">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="role_name" label="角色名称" width="150" :class-name="queryColumnClass('role_name')" :label-class-name="queryColumnClass('role_name')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'role_name',displayName:'角色名称'}" /></template></el-table-column>
        <el-table-column prop="role_code" label="角色编码" width="150" :class-name="queryColumnClass('role_code')" :label-class-name="queryColumnClass('role_code')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'role_code',displayName:'角色编码'}" /></template></el-table-column>
        <el-table-column prop="data_scope" label="数据权限" width="150" :class-name="queryColumnClass('data_scope')" :label-class-name="queryColumnClass('data_scope')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'data_scope',displayName:'数据权限'}" /></template>
          <template #default="{ row }">
            <span class="pms-status pms-status-neutral">{{ ['', '仅本人', '本部门', '本部门及子部门', '全部'][row.data_scope] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="授权产品线" width="200">
          <template #default="{ row }">
            <template v-if="row.product_line_ids?.length">
              <span v-for="pl in row.product_line_ids" :key="pl" class="pms-chip role-product-chip">{{ productLineLabel(pl) }}</span>
            </template>
            <span v-else class="pms-chip">未授权</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" :class-name="queryColumnClass('status')" :label-class-name="queryColumnClass('status')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'status',displayName:'状态'}" /></template>
          <template #default="{ row }">
            <span class="pms-status" :class="row.status === 1 ? 'pms-status-success' : 'pms-status-danger'">
              <span class="pms-status-dot"></span>
              {{ row.status === 1 ? '启用' : '禁用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" :class-name="queryColumnClass('remark')" :label-class-name="queryColumnClass('remark')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'remark',displayName:'备注'}" /></template></el-table-column>
        <el-table-column v-if="(Number(hasPermission('system:role:edit'))+Number(hasPermission('system:role:delete')))>0" label="操作" :width="pmsActionColumn(Number(hasPermission('system:role:edit'))+Number(hasPermission('system:role:delete'))).width" fixed="right">
          <template #default="{ row }">
            <el-button v-if="hasPermission('system:role:edit')" link type="primary" size="small" :disabled="opening" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="hasPermission('system:role:delete')" link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <PmsFormDrawer v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新增角色'" :busy="saving" :before-close="beforeClose">
      <div :inert="saving">
        <!-- 基础信息 -->
        <div class="form-section">
          <h3 class="pms-form-drawer__section">基础信息</h3>
          <el-form id="pms-role-form" ref="formRef" :model="form" :rules="rules" label-position="top" class="pms-standard-dialog-form" @submit.prevent="handleSubmit">
                <el-form-item prop="role_name">
                  <PmsFormField field-id="role-name" label="角色名称" required>
                    <PmsTextControl id="role-name" v-model="form.role_name" :disabled="saving" aria-label="角色名称" />
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
              <PmsFormField field-id="role-product-lines" label="授权产品线" hint="不勾选则无项目数据权限；多角色取并集">
                <PmsCheckboxGroupControl
                  id="role-product-lines"
                  :model-value="selectedProductLines"
                  :options="productLineCheckboxOptions"
                  aria-label="授权产品线"
                  @update:model-value="selectedProductLines = $event.map(String)"
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
        <el-button class="pms-button-reset" :disabled="saving" @click="closeDialog">取消</el-button>
        <el-button v-if="isEdit ? hasPermission('system:role:edit') : hasPermission('system:role:add')" class="pms-button-save" type="primary" :loading="saving" native-type="submit" form="pms-role-form">保存</el-button>
      </template>
    </PmsFormDrawer>
  </div>
</template>

<script setup lang="ts">
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { rolePermissionTree, canonicalPermissionIds, selectedPermissionLeaves } from './role-permission-tree'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import { useSystemQuery } from '@/query-system/system-adapter'
import { ref, reactive, onBeforeUnmount, onMounted, computed, toRef, nextTick } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { usePageLoad } from '@/composables/usePageLoad'
import { useFormSession } from '@/form-system/useFormSession'
import { pmsActionColumn } from '@/config/listUi'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { getRoleProductLines, type LineOption } from '@/api/productLine'
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
const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, submit: submitQuery, filterRows, clearColumns, columnContext, columnFilters, columnClass: queryColumnClass } = useSystemQuery(() => [
  { field: 'role_name', label: '角色名称', type: 'text' },
  { field: 'role_code', label: '角色编码', type: 'text' },
  { field: 'data_scope', label: '数据权限', type: 'enum', options: dataScopeOptions.map(o => ({value:Number(o.value),label:o.label})) },
  { field: 'status', label: '状态', type: 'enum', options: [{value:1,label:'启用'},{value:0,label:'禁用'}] },
  { field: 'remark', label: '备注', type: 'text' },
], ['role_name', 'status'], {ready:()=>roleListState.phase.value === 'ready' || roleListState.phase.value === 'empty'})
const filteredRoles = computed(() => filterRows(roleList.value))
function clearQueryColumns() { clearColumns() }
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const permTreeRef = ref()
const permTree = ref<any[]>([])
const productLineOptions = ref<LineOption[]>([])
const visibleProductLines = computed(() => {
  const byValue = new Map(productLineOptions.value.map(item => [String(item.value), item]))
  selectedProductLines.value.forEach(value => {
    if (!byValue.has(value)) byValue.set(value, { value: Number(value), label: value, disabled: true })
  })
  return Array.from(byValue.values()).filter(item => !item.disabled || selectedProductLines.value.includes(String(item.value)))
})
const productLineCheckboxOptions = computed<PmsOption[]>(() => visibleProductLines.value.map(item => ({
  value: String(item.value),
  label: item.label,
  disabled: !!item.disabled && !selectedProductLines.value.includes(String(item.value)),
})))
const dataScopeOptions: PmsOption[] = [
  { label: '仅本人', value: 1 },
  { label: '本部门', value: 2 },
  { label: '本部门及子部门', value: 3 },
  { label: '全部数据', value: 4 },
]

function productLineLabel(value: number) {
  return productLineOptions.value.find(item => item.value === Number(value))?.label || String(value)
}

async function loadProductLines() {
  try {
    const definition = await getRoleProductLines()
    productLineOptions.value = definition.items
    return true
  } catch {
    // The interceptor reports the error; do not treat failure as an empty grant list.
    return false
  }
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
  menu_ids: [] as number[],
  product_line_ids: [] as string[],
})
const checkedMenuIds = toRef(form, 'menu_ids')
const selectedProductLines = toRef(form, 'product_line_ids')
const roleFormSession = useFormSession({ draft: form, isConflict: (error: any) => error?.response?.status === 409 })
const initializing = ref(false)
const saving = computed(() => initializing.value || roleFormSession.busy.value)
let editorGeneration = 0
let active = true

async function canLeaveRole() {
  if (opening.value || saving.value) return false
  if (!dialogVisible.value) return true
  return roleFormSession.requestClose(async () => {
    try {
      await ElMessageBox.confirm('放弃尚未保存的角色修改？', '未保存修改', { type: 'warning' })
      return true
    } catch { return false }
  })
}
async function beforeClose(done: () => void) {
  if (await canLeaveRole()) done()
}
function closeDialog() { return beforeClose(() => { dialogVisible.value = false }) }
onBeforeRouteLeave(canLeaveRole)

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
  checkedMenuIds.value = canonicalPermissionIds([...checkedKeys, ...permTreeRef.value.getHalfCheckedKeys()])
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
  if (data.permission_code === 'business:data:all') { updateCheckAllState(); return }
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
const roleListState = usePageLoad()
const queryLoading = roleListState.loading
async function fetchList() {
  const ticket = roleListState.begin()
  try {
    const result = await request.get('/roles')
    if (!roleListState.isCurrent(ticket)) return
    roleList.value = result as any
    roleListState.succeed(ticket, roleList.value.length === 0)
  } catch (cause) {
    if (!roleListState.isCurrent(ticket)) return
    roleList.value = []
    roleListState.fail(ticket, cause)
  }
}

const opening = ref(false)
async function openDialog(row?: any) {
  if (saving.value || opening.value || dialogVisible.value) return
  if (row ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  opening.value = true
  const generation = ++editorGeneration
  try {
    if (!await loadProductLines()) return
    if (!active || generation !== editorGeneration) return
    await loadRoleDialog(row, generation)
  } catch {
    // Failed permission reads must not open a partially initialized editor.
    if (active && generation === editorGeneration) dialogVisible.value = false
  } finally {
    if (generation === editorGeneration) { opening.value = false; initializing.value = false }
  }
}

async function loadRoleDialog(row: any, generation: number) {
  const tree = rolePermissionTree((await request.get('/menus/tree')) as any)
  const selected = row ? (await request.get(`/roles/${row.id}/menus`) as any).menu_ids || [] : []
  if (!active || generation !== editorGeneration) return
  if (row ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  isEdit.value = !!row
  formRef.value?.resetFields()
  permTree.value = tree

  if (row) {
    Object.assign(form, {
      id: row.id, role_name: row.role_name, role_code: row.role_code,
      data_scope: row.data_scope, status: row.status, remark: row.remark,
      home_menu_id: row.home_menu_id || 0, home_priority: row.home_priority || 0,
    })
    selectedProductLines.value = (row.product_line_ids || []).map(String)
    // 加载该角色已有的权限
    checkedMenuIds.value = selected
  } else {
    Object.assign(form, { id: 0, role_name: '', role_code: '', data_scope: 1, status: 1, remark: '', home_menu_id: 0, home_priority: 0 })
    selectedProductLines.value = []
    checkedMenuIds.value = []
  }

  initializing.value = true
  dialogVisible.value = true
  await nextTick()
  if (!active || generation !== editorGeneration) return
  if (!permTreeRef.value) throw new Error('权限树未完成初始化')
  // Only existing selected leaves drive cascade; no automatic grant is added.
  permTreeRef.value.setCheckedKeys(selectedPermissionLeaves(checkedMenuIds.value, allLeafIds.value))
  updateCheckAllState()
  markButtonContainers()
  roleFormSession.capture()
}

async function handleSubmit() {
  if (saving.value) return
  if (isEdit.value ? !hasPermission('system:role:edit') : !hasPermission('system:role:add')) return
  const editing = isEdit.value
  const result = await roleFormSession.submit({
    validate: async () => {
      const valid = await formRef.value?.validate().catch(() => false)
      if (!valid || !permTreeRef.value) return false
      updateCheckAllState()
      return true
    },
    save: snapshot => {
      const payload = {
        role_name: snapshot.role_name, role_code: snapshot.role_code, data_scope: snapshot.data_scope,
        product_line_ids: snapshot.product_line_ids.map(Number), status: snapshot.status, remark: snapshot.remark,
        menu_ids: snapshot.menu_ids, home_menu_id: snapshot.home_menu_id || null, home_priority: snapshot.home_priority,
      }
      return editing ? request.put(`/roles/${snapshot.id}`, payload) : request.post('/roles', payload)
    },
  })
  if (result.status !== 'success') return
  ElMessage.success(editing ? '角色更新成功' : '角色创建成功')
  dialogVisible.value = false
  try {
    await authStore.fetchUser()
    if (!hasPermission('system:role:view')) {
      window.location.href = '/403'
      return
    }
    await fetchList()
  } catch {
    // The role was saved. A failed identity/list refresh must not repeat it.
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

onMounted(() => { fetchList(); loadProductLines() })
onBeforeUnmount(() => { active = false; ++editorGeneration; roleListState.invalidate() })
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
