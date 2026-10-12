<script setup lang="ts">
import { computed, ref } from 'vue'
import { Document, TopRight } from '@element-plus/icons-vue'
import PmsPageGuideContent from './PmsPageGuideContent.vue'
import { pageGuides } from './registry'
import type { PageGuideKey } from './types'
import { guideTabHref, type GuideViewState } from './navigation'

const props = defineProps<{ page: PageGuideKey }>()
const guide = computed(() => pageGuides[props.page])
const open = ref(false)
const state = ref<GuideViewState>({ section: 'operations', group: '全部', search: '' })
const href = computed(() => guideTabHref(props.page, state.value))
</script>

<template>
  <template v-if="guide">
    <el-button class="pms-page-guide-button pms-button-auxiliary" :icon="Document" aria-haspopup="dialog" :aria-expanded="open" @click="open = true">说明</el-button>
    <el-dialog v-model="open" :title="`${guide.title}说明`" class="pms-page-guide-dialog" width="min(900px, 94vw)" align-center append-to-body destroy-on-close>
      <template #header><div class="pms-page-guide-heading"><el-icon><Document /></el-icon><strong>{{ guide.title }}</strong><span>页面说明</span><a class="pms-guide-tab-link" :href="href" target="_blank" rel="noopener noreferrer"><el-icon><TopRight /></el-icon>新页签打开</a></div></template>
      <div class="pms-page-guide-panel"><PmsPageGuideContent :guide="guide" @state-change="state = $event" /></div>
    </el-dialog>
  </template>
</template>

<style scoped>
.pms-page-guide-button{height:var(--pms-query-control-height,24px);font-size:var(--pms-query-font-size,12px)}
.pms-page-guide-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding-right:24px;color:var(--pms-text)}
.pms-page-guide-heading strong{font-size:15px}.pms-page-guide-heading>span{font-size:12px;color:var(--pms-text-muted)}
.pms-guide-tab-link{display:inline-flex;align-items:center;gap:4px;margin-left:auto;min-height:24px;box-sizing:border-box;padding:0 8px;border:1px solid var(--pms-border);border-radius:4px;background:var(--pms-info-soft);color:var(--pms-info);font:500 12px var(--pms-font);text-decoration:none;white-space:nowrap}
.pms-guide-tab-link:hover{border-color:var(--pms-info)}.pms-guide-tab-link:focus-visible{outline:2px solid var(--pms-info);outline-offset:2px}
.pms-page-guide-panel{flex:1;min-width:0;min-height:0}
</style>

<style>
.pms-page-guide-dialog{height:min(730px,calc(100dvh - 16px));max-height:calc(100dvh - 16px);display:flex;flex-direction:column;margin-top:0;margin-bottom:0}
.pms-page-guide-dialog .el-dialog__header{flex-shrink:0;margin:0;padding-bottom:12px}
.pms-page-guide-dialog .el-dialog__body{flex:1;display:flex;min-height:0;overflow:hidden;padding-top:0}
@media(max-height:500px){.pms-page-guide-dialog{padding:12px}}
</style>
