<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>用户管理</span>
          <el-button type="primary" @click="openDialog()">新增用户</el-button>
        </div>
      </template>

      <el-table :data="userList" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="真实姓名" width="120" />
        <el-table-column prop="mobile" label="手机号" width="130" />
        <el-table-column prop="role_names" label="角色" :formatter="(r: any) => r.role_names?.join('，') || '-'" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="pageSize"
        layout="total, prev, pager, next"
        @current-change="fetchList"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="密码" :prop="isEdit ? '' : 'password'">
          <el-input v-model="form.password" type="password" :placeholder="isEdit ? '不填则不修改' : '请输入密码'" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.mobile" />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="form.dept_id" style="width: 100%;" clearable
            :data="deptList" :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            check-strictly
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_ids" multiple placeholder="请选择角色" style="width: 100%;">
            <el-option v-for="r in roleList" :key="r.id" :label="r.role_name" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'

const userList = ref([])
const roleList = ref<any[]>([])
const deptList = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const page = ref(1)
const pageSize = ref(15)
const total = ref(0)

const form = reactive({
  id: 0,
  username: '',
  real_name: '',
  password: '',
  mobile: '',
  dept_id: null as number | null,
  status: 1,
  role_ids: [] as number[],
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名' }],
  real_name: [{ required: true, message: '请输入真实姓名' }],
  password: [{ required: true, message: '请输入密码' }],
}

async function fetchList() {
  loading.value = true
  const res: any = await request.get('/users', { params: { page: page.value, page_size: pageSize.value } })
  userList.value = res.items
  total.value = res.total
  loading.value = false
}

async function fetchRoles() {
  roleList.value = (await request.get('/roles')) as any
  deptList.value = (await request.get('/depts/tree')) as any
}

function openDialog(row?: any) {
  isEdit.value = !!row
  formRef.value?.resetFields()
  if (row) {
    Object.assign(form, { id: row.id, username: row.username, real_name: row.real_name, mobile: row.mobile, dept_id: row.dept_id, status: row.status, role_ids: row.role_ids || [] })
    form.password = ''
  } else {
    Object.assign(form, { id: 0, username: '', real_name: '', password: '', mobile: '', dept_id: null, status: 1, role_ids: [] })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (isEdit.value) {
    await request.put(`/users/${form.id}`, { real_name: form.real_name, mobile: form.mobile, dept_id: form.dept_id, status: form.status, role_ids: form.role_ids, ...(form.password ? { password: form.password } : {}) })
    ElMessage.success('更新成功')
  } else {
    await request.post('/users', form)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该用户吗？', '提示', { type: 'warning' })
  await request.delete(`/users/${id}`)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(() => {
  fetchList()
  fetchRoles()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
