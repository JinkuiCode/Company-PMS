<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>角色管理</span>
          <el-button type="primary" @click="openDialog()">新增角色</el-button>
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
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="warning" size="small" @click="openMenuDialog(row)">分配权限</el-button>
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色' : '新增角色'" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="角色名称" prop="role_name">
          <el-input v-model="form.role_name" />
        </el-form-item>
        <el-form-item label="角色编码" prop="role_code">
          <el-input v-model="form.role_code" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="数据权限">
          <el-select v-model="form.data_scope" style="width: 100%;">
            <el-option label="仅本人" :value="1" />
            <el-option label="本部门" :value="2" />
            <el-option label="本部门及子部门" :value="3" />
            <el-option label="全部数据" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配权限弹窗 -->
    <el-dialog v-model="menuDialogVisible" title="分配菜单权限" width="500px">
      <el-tree
        ref="treeRef"
        :data="menuTree"
        node-key="id"
        :props="{ label: 'menu_name', children: 'children' }"
        :default-checked-keys="checkedMenuIds"
        show-checkbox
        default-expand-all
      />
      <template #footer>
        <el-button @click="menuDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAssignMenus">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'

const roleList = ref([])
const menuTree = ref([])
const dialogVisible = ref(false)
const menuDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const treeRef = ref()
const checkedMenuIds = ref<number[]>([])
const currentRoleId = ref(0)

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

async function fetchList() {
  roleList.value = (await request.get('/roles')) as any
}

async function openDialog(row?: any) {
  isEdit.value = !!row
  formRef.value?.resetFields()
  if (row) {
    Object.assign(form, row)
  } else {
    Object.assign(form, { id: 0, role_name: '', role_code: '', data_scope: 1, status: 1, remark: '' })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (isEdit.value) {
    await request.put(`/roles/${form.id}`, { role_name: form.role_name, data_scope: form.data_scope, status: form.status, remark: form.remark })
    ElMessage.success('更新成功')
  } else {
    await request.post('/roles', form)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该角色吗？', '提示', { type: 'warning' })
  await request.delete(`/roles/${id}`)
  ElMessage.success('删除成功')
  fetchList()
}

async function openMenuDialog(row: any) {
  currentRoleId.value = row.id
  menuTree.value = (await request.get('/menus/tree')) as any
  const res: any = await request.get(`/roles/${row.id}/menus`)
  checkedMenuIds.value = res.menu_ids || []
  menuDialogVisible.value = true
}

async function handleAssignMenus() {
  const menuIds = treeRef.value.getCheckedKeys()
  await request.put(`/roles/${currentRoleId.value}`, { menu_ids: menuIds })
  ElMessage.success('权限分配成功')
  menuDialogVisible.value = false
}

onMounted(() => fetchList())
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
