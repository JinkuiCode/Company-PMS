<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useReleaseStore } from '@/release-center/store'
import { useRoute } from 'vue-router'
import { Document } from '@element-plus/icons-vue'
import PmsPageGuideContent from './PmsPageGuideContent.vue'
import { pageGuides } from './registry'
import { readGuideView } from './navigation'
import type { PageGuideKey } from './types'

const props = defineProps<{ page: PageGuideKey }>()
const route = useRoute()
const releases = useReleaseStore()
const recent = computed(() => releases.runtime?.page_updates?.[props.page])
onMounted(() => { void releases.refresh() })
const guide = computed(() => pageGuides[props.page])
const state = computed(() => readGuideView(guide.value, route.hash))
const previousTitle = document.title
watch(guide, value => { document.title = `${value.title} · 页面说明` }, { immediate: true })
onUnmounted(() => { document.title = previousTitle })
</script>

<template>
  <main class="pms-guide-page">
    <header class="pms-guide-page-heading"><el-icon><Document /></el-icon><h1>{{ guide.title }}</h1><span>页面说明</span><span v-if="recent">最近更新 {{ recent.version }}</span></header>
    <div class="pms-guide-page-content"><PmsPageGuideContent :key="route.fullPath" :guide="guide" :initial-state="state" /></div>
  </main>
</template>

<style scoped>
.pms-guide-page{height:100dvh;box-sizing:border-box;display:flex;flex-direction:column;padding:16px 24px;background:var(--pms-surface);color:var(--pms-text);font-family:var(--pms-font);overflow:hidden}
.pms-guide-page-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding-bottom:16px;flex-shrink:0}
.pms-guide-page-heading h1{margin:0;font-size:16px;font-weight:600;line-height:24px}.pms-guide-page-heading span{font-size:12px;color:var(--pms-text-muted)}
.pms-guide-page-content{flex:1;min-height:0;min-width:0}
@media(max-width:600px),(max-height:500px){.pms-guide-page{padding:12px}.pms-guide-page-heading{padding-bottom:10px}}
</style>
