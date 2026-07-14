<template>
  <div class="dashboard pms-page pms-system-page">
    <el-row :gutter="16" class="stat-cards">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card pms-surface-section">
          <div class="stat-icon is-primary"><el-icon :size="24"><Folder /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_projects }}</div>
            <div class="stat-label">项目总数</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card pms-surface-section">
          <div class="stat-icon is-success"><el-icon :size="24"><List /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_tasks }}</div>
            <div class="stat-label">任务总数</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card pms-surface-section">
          <div class="stat-icon is-warning"><el-icon :size="24"><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.avg_progress }}%</div>
            <div class="stat-label">平均进度</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card pms-surface-section">
          <div class="stat-icon is-info"><el-icon :size="24"><CircleCheck /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ completionRate }}%</div>
            <div class="stat-label">完成率</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="12">
        <section class="chart-card pms-surface-section">
          <div class="pms-section-header"><span class="pms-section-title">项目状态分布</span></div>
          <v-chart :option="statusPieOption" class="dashboard-chart" autoresize />
        </section>
      </el-col>
      <el-col :xs="24" :lg="12">
        <section class="chart-card pms-surface-section">
          <div class="pms-section-header"><span class="pms-section-title">部门项目分布</span></div>
          <v-chart :option="deptBarOption" class="dashboard-chart" autoresize />
        </section>
      </el-col>
    </el-row>

    <section class="recent-table-card pms-surface-section">
      <div class="pms-section-header"><span class="pms-section-title">最近项目</span></div>
      <el-table class="pms-dense-table" :data="stats.recent_projects" stripe border size="small">
        <el-table-column prop="project_code" label="项目编号" width="150" />
        <el-table-column prop="project_name" label="项目名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="goProject(row.id)">{{ row.project_name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="dept_name" label="所属部门" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="pms-status" :class="statusMap[row.status]?.className ?? 'pms-status-neutral'">
              <span class="pms-status-dot"></span>
              {{ statusMap[row.status]?.text ?? '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="task_count" label="任务数" width="80" align="center" />
        <el-table-column label="总进度" width="200">
          <template #default="{ row }">
            <div class="pms-progress-cell">
              <span class="pms-progress-track">
                <span class="pms-progress-bar" :class="progressClass(row.total_progress)" :style="{ width: `${row.total_progress}%` }"></span>
              </span>
              <span class="pms-progress-value">{{ row.total_progress }}%</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>
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

const statusMap = reactive<Record<number, { text: string; className: string }>>({
  1: { text: '-', className: 'pms-status-info' },
  2: { text: '-', className: 'pms-status-success' },
  3: { text: '-', className: 'pms-status-warning' },
})

function progressClass(percentage: number): string {
  if (percentage < 30) return 'is-danger'
  if (percentage < 80) return 'is-warning'
  return 'is-success'
}

const chartColors = {
  primary: '#4f46e5',
  success: '#0f9f7a',
  warning: '#d97706',
  border: '#ffffff',
  text: '#667085',
  grid: '#edf1f6',
}

const chartTextStyle = {
  color: chartColors.text,
  fontFamily: 'Noto Sans SC, sans-serif',
  fontSize: 12,
}

// 饼图：状态分布
const statusPieOption = computed(() => ({
  textStyle: chartTextStyle,
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: chartTextStyle },
  series: [{
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['50%', '45%'],
    avoidLabelOverlap: false,
    itemStyle: { borderRadius: 4, borderColor: chartColors.border, borderWidth: 2 },
    label: { show: false },
    emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
    data: [
      { value: stats.value.status_distribution.ongoing, name: statusMap[1].text, itemStyle: { color: chartColors.primary } },
      { value: stats.value.status_distribution.finished, name: statusMap[2].text, itemStyle: { color: chartColors.success } },
      { value: stats.value.status_distribution.paused, name: statusMap[3].text, itemStyle: { color: chartColors.warning } },
    ],
  }],
}))

// 柱状图：部门分布
const deptBarOption = computed(() => ({
  textStyle: chartTextStyle,
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: stats.value.dept_distribution.map(d => d.dept_name),
    axisLabel: { ...chartTextStyle, rotate: stats.value.dept_distribution.length > 5 ? 30 : 0 },
    axisLine: { lineStyle: { color: chartColors.grid } },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: chartTextStyle,
    splitLine: { lineStyle: { color: chartColors.grid } },
  },
  series: [{
    type: 'bar',
    data: stats.value.dept_distribution.map(d => d.count),
    itemStyle: { color: chartColors.primary, borderRadius: [4, 4, 0, 0] },
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
  padding: 0;
  border: 0;
  box-shadow: none;
}

.stat-cards { margin-bottom: 16px; }
.chart-row { margin-bottom: 16px; }
.stat-cards :deep(.el-col),
.chart-row :deep(.el-col) { margin-bottom: 16px; }

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 88px;
  padding: 16px;
}
.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: var(--pms-radius);
}
.stat-icon.is-primary { color: var(--pms-primary); background: var(--pms-primary-soft); }
.stat-icon.is-success { color: var(--pms-success); background: var(--pms-success-soft); }
.stat-icon.is-warning { color: var(--pms-warning); background: var(--pms-warning-soft); }
.stat-icon.is-info { color: var(--pms-info); background: var(--pms-info-soft); }
.stat-info {
  min-width: 0;
}
.stat-value {
  color: var(--pms-text);
  font-size: 24px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.stat-label {
  margin-top: 4px;
  color: var(--pms-text-secondary);
  font-size: var(--pms-font-size-sm);
}

.chart-card {
  min-height: 366px;
}

.dashboard-chart {
  height: 320px;
}
</style>
