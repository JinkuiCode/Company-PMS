<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { PmsTextControl } from '../form-system'
import { findGuideEntries } from './registry'
import type { GuideSection, PageGuide } from './types'
import type { GuideViewState } from './navigation'

const props = defineProps<{ guide: PageGuide; initialState?: GuideViewState }>()
const emit = defineEmits<{ 'state-change': [state: GuideViewState] }>()
const section = ref<GuideSection>(props.initialState?.section || 'operations')
const search = ref(props.initialState?.search || '')
const group = ref(props.initialState?.group || '全部')
const scroll = ref<HTMLElement>()
const entries = computed(() => findGuideEntries(props.guide, section.value, search.value))
const groups = computed(() => ['全部', ...new Set(entries.value.map(item => item.group))])
const visible = computed(() => entries.value.filter(item => group.value === '全部' || item.group === group.value))
watch(() => props.guide, () => { search.value = ''; group.value = '全部'; section.value = 'operations' })
watch(section, () => { group.value = '全部' })
watch(groups, value => { if (!value.includes(group.value)) group.value = '全部' })
watch([section, group, search], () => { scroll.value?.scrollTo({ top: 0 }) })
watch([section, group, search], () => emit('state-change', { section: section.value, group: group.value, search: search.value }), { immediate: true })
</script>

<template>
  <div class="pms-guide-content">
    <div class="pms-guide-tools pms-query-density">
      <div class="pms-guide-tabs" role="group" aria-label="说明类型">
        <button :class="{ active: section === 'operations' }" :aria-pressed="section === 'operations'" @click="section = 'operations'">操作说明</button>
        <button :class="{ active: section === 'fields' }" :aria-pressed="section === 'fields'" @click="section = 'fields'">字段逻辑</button>
      </div>
      <PmsTextControl v-model="search" size="compact" clearable placeholder="搜索操作或字段" aria-label="搜索说明" :prefix-icon="Search" />
    </div>
    <div class="pms-guide-body">
      <nav class="pms-guide-outline" aria-label="说明分组">
        <button v-for="item in groups" :key="item" :class="{ active: group === item }" :aria-pressed="group === item" @click="group = item">{{ item }}</button>
      </nav>
      <div ref="scroll" class="pms-guide-scroll" tabindex="0" aria-label="说明内容">
        <template v-if="visible.length">
          <ol v-if="section === 'operations'" class="pms-guide-steps">
            <li v-for="(item, i) in visible" :key="item.label"><span class="pms-guide-index">{{ String(i + 1).padStart(2, '0') }}</span><div><h3>{{ item.label }}</h3><p>{{ item.logic }}</p></div></li>
          </ol>
          <table v-else class="pms-guide-fields">
            <thead><tr><th scope="col">字段</th><th scope="col">取值与计算逻辑</th></tr></thead>
            <tbody><tr v-for="item in visible" :key="item.label"><th scope="row"><span class="pms-guide-field-group">{{ item.group }}</span>{{ item.label }}</th><td>{{ item.logic }}</td></tr></tbody>
          </table>
        </template>
        <p v-else class="pms-guide-empty" role="status">没有匹配的说明</p>
      </div>
    </div>
    <footer class="pms-guide-footer">页面说明<span>仅解释业务规则，不改变数据或权限</span></footer>
  </div>
</template>

<style scoped>
.pms-guide-content{height:100%;min-height:0;display:flex;flex-direction:column;color:var(--pms-text);font:400 13px/1.75 var(--pms-font)}
.pms-guide-tools{display:flex;align-items:center;gap:12px;padding-bottom:12px;border-bottom:1px solid var(--pms-border-soft);flex-shrink:0}
.pms-guide-tabs{display:flex;gap:4px;flex-shrink:0}
.pms-guide-tabs button{font:500 12px var(--pms-font);height:24px;padding:0 10px;border:0;background:transparent;color:var(--pms-text-secondary);cursor:pointer;border-radius:4px}
.pms-guide-tabs button.active,.pms-guide-outline button.active{color:var(--pms-primary);background:var(--pms-primary-soft)}
.pms-guide-tools>.pms-form-control{flex:1;min-width:0}
.pms-guide-body{flex:1;min-height:0;display:flex}
.pms-guide-outline{width:136px;flex-shrink:0;padding:12px 12px 0 0;border-right:1px solid var(--pms-border-soft);display:flex;flex-direction:column;gap:4px;overflow:auto}
.pms-guide-outline button{text-align:left;font:500 12px var(--pms-font);border:0;background:transparent;color:var(--pms-text-secondary);padding:7px 10px;border-radius:4px;cursor:pointer}
.pms-guide-scroll{flex:1;min-width:0;overflow:auto;overscroll-behavior:contain;padding-left:16px}
.pms-guide-steps{list-style:none;padding:0;margin:0}
.pms-guide-steps li{display:flex;align-items:flex-start;gap:12px;padding:16px 0;border-bottom:1px solid var(--pms-border-soft)}
.pms-guide-index{font-size:12px;color:var(--pms-text-muted);font-variant-numeric:tabular-nums;line-height:24px}
h3{font-size:13px;font-weight:600;margin:0 0 5px}p{margin:0;color:var(--pms-text-secondary)}
.pms-guide-fields{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:12px}
.pms-guide-fields thead{position:sticky;top:0;background:var(--pms-surface-muted)}
.pms-guide-fields th,.pms-guide-fields td{border-bottom:1px solid var(--pms-border-soft);padding:12px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
.pms-guide-fields th{font-weight:500}.pms-guide-fields th:first-child{width:32%}.pms-guide-fields thead th{font-size:12px;color:var(--pms-text-secondary);padding:7px 8px;text-align:center}
.pms-guide-fields td{color:var(--pms-text-secondary)}.pms-guide-field-group{display:block;color:var(--pms-text-muted);font-size:11px;margin-bottom:4px}
.pms-guide-footer{display:flex;justify-content:space-between;gap:8px;padding-top:12px;border-top:1px solid var(--pms-border-soft);font-size:11px;color:var(--pms-text-muted);flex-shrink:0}
.pms-guide-empty{text-align:center;padding:48px 0}
@media(max-width:600px){.pms-guide-footer{flex-wrap:wrap}.pms-guide-outline{width:100px}.pms-guide-tools{gap:6px}.pms-guide-tabs button{padding:0 6px}}
</style>
