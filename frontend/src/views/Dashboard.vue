<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background:#e6f7ff;"><el-icon :size="28" color="#1890ff"><Folder /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_projects }}</div>
            <div class="stat-label">项目总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background:#f6ffed;"><el-icon :size="28" color="#52c41a"><List /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_tasks }}</div>
            <div class="stat-label">任务总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background:#fff7e6;"><el-icon :size="28" color="#faad14"><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.avg_progress }}%</div>
            <div class="stat-label">平均进度</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background:#fff1f0;"><el-icon :size="28" color="#ff4d4f"><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ completionRate }}%</div>
            <div class="stat-label">完成率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表行 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span class="card-title">项目状态分布</span></template>
          <v-chart :option="statusPieOption" style="height:320px;" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span class="card-title">部门项目分布</span></template>
          <v-chart :option="deptBarOption" style="height:320px;" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近项目表格 -->
    <el-card shadow="hover" class="recent-table-card">
      <template #header><span class="card-title">最近项目</span></template>
      <el-table :data="stats.recent_projects" stripe style="width:100%;">
        <el-table-column prop="project_code" label="项目编号" width="150" />
        <el-table-column prop="project_name" label="项目名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="goProject(row.id)">{{ row.project_name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="dept_name" label="所属部门" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type ?? 'info'">{{ statusMap[row.status]?.text ?? '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_count" label="任务数" width="80" align="center" />
        <el-table-column label="总进度" width="200">
          <template #default="{ row }">
            <el-progress :percentage="row.total_progress" :stroke-width="8" :color="progressColor" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Folder, List, TrendCharts, CircleCheck } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getDashboardStats, type DashboardStats } from '@/api/dashboard'
import { loadEnumOptions } from '@/composables/useEnumOptions'

// 按需注册 ECharts 模块
use([PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const router = useRouter()

const stats = ref<DashboardStats>({
  total_projects: 0, total_tasks: 0, avg_progress: 0,
  status_distribution: { ongoing: 0, finished: 0, paused: 0 },
  dept_distribution: [],
  nearing_deadline: [],
  recent_projects: [],
})

// 完成率 = 已完结项目 / 总项目
const completionRate = computed(() => {
  const total = stats.value.total_projects
  if (total === 0) return 0
  return Math.round((stats.value.status_distribution.finished / total) * 100)
})

const statusMap = reactive<Record<number, { text: string; type: string }>>({
  1: { text: '-', type: 'primary' },
  2: { text: '-', type: 'success' },
  3: { text: '-', type: 'warning' },
})

function progressColor(percentage: number): string {
  if (percentage < 30) return '#F56C6C'
  if (percentage < 80) return '#E6A23C'
  return '#67C23A'
}

// 饼图：状态分布
const statusPieOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['50%', '45%'],
    avoidLabelOverlap: false,
    itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
    label: { show: false },
    emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
    data: [
      { value: stats.value.status_distribution.ongoing, name: statusMap[1].text, itemStyle: { color: '#409EFF' } },
      { value: stats.value.status_distribution.finished, name: statusMap[2].text, itemStyle: { color: '#67C23A' } },
      { value: stats.value.status_distribution.paused, name: statusMap[3].text, itemStyle: { color: '#E6A23C' } },
    ],
  }],
}))

// 柱状图：部门分布
const deptBarOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: stats.value.dept_distribution.map(d => d.dept_name),
    axisLabel: { rotate: stats.value.dept_distribution.length > 5 ? 30 : 0 },
  },
  yAxis: { type: 'value', minInterval: 1 },
  series: [{
    type: 'bar',
    data: stats.value.dept_distribution.map(d => d.count),
    itemStyle: { color: '#409EFF', borderRadius: [4, 4, 0, 0] },
    barMaxWidth: 40,
  }],
}))

function goProject(id: number) {
  router.push({ name: 'ProjectProgress', params: { id } })
}

async function fetchStats() {
  stats.value = await getDashboardStats()
}

async function loadProjectStatuses() {
  const definition = await loadEnumOptions('project_status')
  Object.entries(definition.label_map).forEach(([value, label]) => {
    const status = Number(value)
    if (statusMap[status]) statusMap[status].text = label
  })
}

onMounted(() => { fetchStats(); loadProjectStatuses() })
</script>

<style scoped>
.dashboard {
  padding: 16px;
}

.stat-cards { margin-bottom: 16px; }
.chart-row { margin-bottom: 16px; }

.stat-card {
  cursor: default;
}
.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 16px;
}
.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}
.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.recent-table-card {
  /* Element Plus 默认样式即可 */
}
</style>
