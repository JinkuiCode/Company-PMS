<script setup lang="ts">
import { ref } from 'vue'
import PurchaseOverviewList from './PurchaseOverviewList.vue'
import PurchaseProgressList from './PurchaseProgressList.vue'
import type { PurchaseDetailEntry } from '@/api/purchaseReport'
const mode = ref<'overview' | 'detail'>('overview')
const visitedDetail = ref(false), entry = ref<PurchaseDetailEntry>({ draft: null })
const overview = ref<InstanceType<typeof PurchaseOverviewList>>()
function openDetail(value?: PurchaseDetailEntry) {
  entry.value = value || overview.value?.detailEntry() || { draft: null }
  visitedDetail.value = true; mode.value = 'detail'
}
</script>
<template>
  <div class="purchase-report-workspace">
    <PurchaseOverviewList ref="overview" v-show="mode === 'overview'" @detail="openDetail">
      <template #view-switch><div class="purchase-view-switch" role="group" aria-label="报表视图"><button type="button" aria-pressed="true">总进度</button><button type="button" aria-pressed="false" @click="openDetail()">明细进度</button></div></template>
    </PurchaseOverviewList>
    <div v-if="visitedDetail" v-show="mode === 'detail'" class="purchase-detail-view">
      <PurchaseProgressList :entry="entry" :active="mode === 'detail'" @overview="mode = 'overview'">
        <template #view-switch><div class="purchase-view-switch" role="group" aria-label="报表视图"><button type="button" aria-pressed="false" @click="mode = 'overview'">总进度</button><button type="button" aria-pressed="true" @click="openDetail()">明细进度</button></div></template>
      </PurchaseProgressList>
    </div>
  </div>
</template>
<style scoped>
.purchase-report-workspace,.purchase-detail-view{display:flex;flex-direction:column;min-height:0;min-width:0;flex:1;height:100%}
.purchase-report-workspace :deep(.purchase-view-switch){display:flex;gap:2px;border:1px solid var(--pms-border);border-radius:4px;padding:1px;flex-shrink:0}
.purchase-report-workspace :deep(.purchase-view-switch button){height:22px;padding:0 9px;border:0;border-radius:3px;background:transparent;color:var(--pms-text-secondary);font:inherit;font-size:12px;white-space:nowrap;cursor:pointer}
.purchase-report-workspace :deep(.purchase-view-switch button[aria-pressed=true]){background:var(--pms-primary-soft);color:var(--pms-primary);font-weight:600}
</style>
