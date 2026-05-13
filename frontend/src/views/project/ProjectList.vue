<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>项目列表</span>
          <el-button type="primary" @click="openDialog()">新增项目</el-button>
        </div>
      </template>

      <el-row :gutter="12" style="margin-bottom: 16px;">
        <el-col :span="6">
          <el-tree-select
            v-model="filterDeptId" placeholder="所属部门" clearable
            :data="deptList" :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            check-strictly style="width: 100%;" @change="fetchList"
          />
        </el-col>
        <el-col :span="4">
          <el-select v-model="filterStatus" placeholder="项目状态" clearable @change="fetchList" style="width: 100%;">
            <el-option label="进行中" :value="1" />
            <el-option label="已完结" :value="2" />
            <el-option label="暂停" :value="3" />
          </el-select>
        </el-col>
      </el-row>

      <el-table :data="projectList" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="project_code" label="项目编号" width="150" />
        <el-table-column prop="project_name" label="项目名称" width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="goProgress(row)">{{ row.project_name }}</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="dept_name" label="所属部门" width="100" />
        <el-table-column prop="pm_name" label="项目经理" width="100" />
        <el-table-column prop="total_progress" label="总进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.total_progress" :color="progressColor(row.total_progress)" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="['', '', 'success', 'warning'][row.status] || 'info'" size="small">
              {{ { 1: '进行中', 2: '已完结', 3: '暂停' }[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_count" label="任务数" width="80" />
        <el-table-column prop="budget" label="预算(万)" width="100" />
        <el-table-column prop="start_date" label="开始日期" width="110" />
        <el-table-column prop="end_date" label="结束日期" width="110" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page" :total="total" :page-size="pageSize"
        layout="total, prev, pager, next" @current-change="fetchList"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目' : '新增项目'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="项目编号" prop="project_code">
          <el-input v-model="form.project_code" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="项目名称" prop="project_name">
          <el-input v-model="form.project_name" />
        </el-form-item>
        <el-form-item label="所属部门" prop="dept_id">
          <el-tree-select
            v-model="form.dept_id" style="width: 100%;"
            :data="deptList" :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            check-strictly
          />
        </el-form-item>
        <el-form-item label="项目经理" prop="pm_id">
          <el-select v-model="form.pm_id" style="width: 100%;">
            <el-option v-for="u in userList" :key="u.id" :label="u.real_name + ' (' + u.username + ')'" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">进行中</el-radio>
            <el-radio :value="2">已完结</el-radio>
            <el-radio :value="3">暂停</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="开始日期">
              <el-date-picker v-model="form.start_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker v-model="form.end_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="预算(万)">
          <el-input-number v-model="form.budget" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const projectList = ref([])
const deptList = ref<any[]>([])
const userList = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const page = ref(1); const pageSize = ref(15); const total = ref(0)
const filterDeptId = ref(); const filterStatus = ref()

const form = reactive({
  id: 0, project_code: '', project_name: '', dept_id: 0, pm_id: 0,
  status: 1, start_date: '', end_date: '', budget: null as number | null, description: '',
})

const rules: FormRules = {
  project_code: [{ required: true, message: '请输入项目编号' }],
  project_name: [{ required: true, message: '请输入项目名称' }],
  dept_id: [{ required: true, message: '请选择部门' }],
  pm_id: [{ required: true, message: '请选择项目经理' }],
}

function progressColor(v: number) { return v < 30 ? '#F56C6C' : v < 80 ? '#E6A23C' : '#67C23A' }

async function fetchList() {
  loading.value = true
  const res: any = await request.get('/projects', { params: { page: page.value, page_size: pageSize.value, dept_id: filterDeptId.value, status: filterStatus.value } })
  projectList.value = res.items; total.value = res.total
  loading.value = false
}

async function fetchOptions() {
  deptList.value = (await request.get('/depts/tree')) as any
  const res: any = await request.get('/users', { params: { page: 1, page_size: 999 } })
  userList.value = res.items
}

function openDialog(row?: any) {
  isEdit.value = !!row; formRef.value?.resetFields()
  if (row) {
    Object.assign(form, { id: row.id, project_code: row.project_code, project_name: row.project_name, dept_id: row.dept_id, pm_id: row.pm_id, status: row.status, start_date: row.start_date, end_date: row.end_date, budget: row.budget, description: row.description })
  } else {
    Object.assign(form, { id: 0, project_code: '', project_name: '', dept_id: 0, pm_id: 0, status: 1, start_date: '', end_date: '', budget: null, description: '' })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload: any = { ...form }
  delete payload.id
  if (isEdit.value) {
    await request.put('/projects/' + form.id, payload); ElMessage.success('更新成功')
  } else {
    await request.post('/projects', form); ElMessage.success('创建成功')
  }
  dialogVisible.value = false; fetchList()
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该项目吗？任务数据也将被删除', '提示', { type: 'warning' })
  await request.delete('/projects/' + id); ElMessage.success('删除成功')
  fetchList()
}

function goProgress(row: any) {
  router.push({ name: 'ProjectProgress', params: { id: row.id }, query: { name: row.project_name } })
}

onMounted(() => { fetchList(); fetchOptions() })
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
