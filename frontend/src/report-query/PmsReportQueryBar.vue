<script setup lang="ts">
import { Search, RefreshLeft } from '@element-plus/icons-vue'
import PmsReportConditions from './PmsReportConditions.vue'
import type { ReportCondition, ReportField } from './state'
import './query-surface.css'
defineProps<{ conditions: ReportCondition[]; fields: ReportField[]; loading?: boolean; disabled?: boolean; invalid?: string }>()
const emit = defineEmits<{ query: []; reset: []; 'update:conditions': [value: ReportCondition[]] }>()
</script>
<template>
  <form class="pms-report-query-fields pms-report-query-bar" @submit.prevent="!disabled && !loading && !invalid && emit('query')">
    <slot />
      <el-tooltip :content="invalid || ''" :disabled="!invalid"><span><el-button size="small" type="primary" :icon="Search" :loading="loading" :disabled="disabled || loading || !!invalid" native-type="submit">查询</el-button></span></el-tooltip>
      <el-button size="small" :icon="RefreshLeft" :disabled="disabled" @click="emit('reset')">重置</el-button>
      <PmsReportConditions :model-value="conditions" :fields="fields" :disabled="disabled" trigger-label="添加条件" @update:model-value="emit('update:conditions',$event)" />
  </form>
</template>
