<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>部门管理</span>
          <el-button type="primary" @click="openDialog()">新增部门</el-button>
        </div>
      </template>

      <el-table :data="deptTree" row-key="id" border stripe default-expand-all>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="dept_name" label="部门名称" width="200" />
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column prop="leader_id" label="负责人ID" width="100" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link type="primary" size="small" @click="openDialog({ parent_id: row.id })">添加子级</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑部门' : '新增部门'" width="500px">
      <el-form ref="formRef" :model="form" label-width="80px">
        <el-form-item label="上级部门">
          <el-tree-select
            v-model="form.parent_id"
            :data="deptTree"
            :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            placeholder="无（顶级部门）"
            check-strictly
            clearable
            style="width: 100%;"
          />
        </el-form-item>
        <el-form-item label="部门名称" prop="dept_name">
          <el-input v-model="form.dept_name" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
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

const deptTree = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  id: 0,
  parent_id: 0,
  dept_name: '',
  sort: 0,
  status: 1,
})

const rules: FormRules = {
  dept_name: [{ required: true, message: '请输入部门名称' }],
}

async function fetchList() {
  deptTree.value = (await request.get('/depts/tree')) as any
}

function openDialog(row?: any) {
  isEdit.value = !!(row && row.id)
  formRef.value?.resetFields()
  if (row && row.id) {
    Object.assign(form, row)
  } else {
    Object.assign(form, { id: 0, parent_id: row?.parent_id || 0, dept_name: '', sort: 0, status: 1 })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (isEdit.value) {
    await request.put(`/depts/${form.id}`, form)
    ElMessage.success('更新成功')
  } else {
    await request.post('/depts', form)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该部门吗？', '提示', { type: 'warning' })
  await request.delete(`/depts/${id}`)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(() => fetchList())
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
