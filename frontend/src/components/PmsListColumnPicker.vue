<template>
  <el-popover v-model:visible="visible" placement="bottom-end" trigger="click" :width="580" popper-class="pms-list-column-picker-popper">
    <template #reference><el-button size="small" plain class="column-picker-trigger" :aria-label="`打开${ariaLabel}`"><el-icon style="margin-right:4px"><Setting /></el-icon>列设置</el-button></template>
    <div class="column-picker-panel" :aria-label="ariaLabel">
      <div class="column-picker-toolbar"><PmsTextControl v-model="keyword" size="compact" clearable placeholder="搜索字段" aria-label="搜索列字段" /><span class="column-picker-count">已选 {{ draft.filter(f => f.visible && !f.locked).length }} 项</span></div>
      <PmsGridLayoutEditor v-model="draft" :keyword="keyword" />
      <div class="column-picker-footer"><el-button size="small" text @click="restoreDefaults">恢复默认</el-button><div><el-button size="small" @click="visible = false">取消</el-button><el-button size="small" type="primary" :loading="saving" @click="save">保存</el-button></div></div>
    </div>
  </el-popover>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Setting } from '@element-plus/icons-vue'
import { PmsTextControl } from '@/form-system'
import PmsGridLayoutEditor, { type LayoutField } from './PmsGridLayoutEditor.vue'
import type { GridApi, ColDef, ColGroupDef } from 'ag-grid-community'
type ColumnPickerField = { key: string; label: string; value_type: string; list_available: boolean; quick_addable: boolean }
type ColumnPickerGroup = { key: string; label: string; fields: ColumnPickerField[] }
const props = defineProps<{ modelValue: string[]; groups: ColumnPickerGroup[]; defaultKeys: string[]; ariaLabel?: string; getGridApi?: () => GridApi | null | undefined; fieldColumnId?: (key: string) => string; columnDefinitions: (ColDef | ColGroupDef)[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]]; 'restore-defaults': []; 'layout-changed': [] }>()
const ariaLabel = computed(() => props.ariaLabel || '列设置')
const visible = ref(false), keyword = ref(''), saving = ref(false)
const draft = ref<LayoutField[]>([])
const lockedIds = new Set(['archive_selection', 'archive_actions', 'progress_actions'])
const columnId = (key: string) => props.fieldColumnId?.(key) || key
watch(visible, value => { if (value) openDraft() }, { flush: 'sync' })
function openDraft() {
  keyword.value = ''
  const api = props.getGridApi?.()
  if (!api || api.isDestroyed()) { draft.value = []; return }
  const metadata = new Map(props.groups.flatMap(g => g.fields.filter(f => f.list_available).map(f => [columnId(f.key), { ...f, group: g.label }] as const)))
  const definitions = new Map<string, ColDef>()
  const collect = (defs: (ColDef | ColGroupDef)[]) => defs.forEach(def => { if ('children' in def) collect(def.children); else definitions.set(def.colId || def.field || '', def) })
  collect(props.columnDefinitions)
  const defaultOrder = [...definitions.keys(), ...metadata.keys()].filter((id, i, ids) => ids.indexOf(id) === i)
  const ids = [...api.getColumnState().map(s => s.colId), ...metadata.keys()].filter((id, i, all) => all.indexOf(id) === i)
  draft.value = ids.flatMap(id => {
    const meta = metadata.get(id), def = definitions.get(id), column = api.getColumn(id)
    // Hidden policy fields without selectable metadata must not become available here.
    if (!meta && (!def || def.hide === true)) return []
    const locked = lockedIds.has(id), zone = column?.getPinned() || 'center'
    const defaultWidth = def?.initialWidth || def?.width || (meta?.value_type === 'long_text' ? 210 : 136)
    return [{ id, key: meta?.key, label: meta?.label || def?.headerName || '勾选列', group: meta?.group || '列表字段', zone,
      width: column?.getActualWidth() || defaultWidth, min: def?.minWidth || (locked ? defaultWidth : meta && !def ? (meta.value_type === 'long_text' ? 170 : 110) : 60), max: def?.maxWidth || 800, locked,
      visible: locked || (meta ? props.modelValue.includes(meta.key) : column?.isVisible() === true),
      defaultVisible: locked || (meta ? props.defaultKeys.includes(meta.key) : def?.hide !== true),
      defaultZone: def?.initialPinned || def?.pinned || 'center', defaultWidth, defaultOrder: defaultOrder.indexOf(id) } as LayoutField]
  })
}
function restoreDefaults() { draft.value = draft.value.map(f => ({ ...f, visible: f.defaultVisible, width: f.defaultWidth, zone: f.defaultZone })).sort((a, b) => a.defaultOrder - b.defaultOrder) }
async function save() {
  const api = props.getGridApi?.()
  if (!api || api.isDestroyed() || saving.value) return
  saving.value = true
  try {
    // Materialize selected dynamic columns before applying their draft layout.
    emit('update:modelValue', draft.value.filter(f => f.visible && f.key).map(f => f.key!))
    await nextTick()
    await nextTick()
    const state = ['left', 'center', 'right'].flatMap(zone => draft.value.filter(f => f.zone === zone).sort((a, b) => a.id === 'archive_selection' || b.id.endsWith('_actions') ? -1 : b.id === 'archive_selection' || a.id.endsWith('_actions') ? 1 : 0)).map(f => ({ colId: f.id, hide: !f.visible, pinned: f.zone === 'center' ? null : f.zone as 'left' | 'right', width: f.width, flex: null }))
    api.applyColumnState({ state: state.filter(s => api.getColumn(s.colId)), applyOrder: true })
    emit('layout-changed')
    visible.value = false
  } finally { saving.value = false }
}
</script>
<style scoped>
.column-picker-trigger{flex:0 0 auto}.column-picker-panel{display:grid;gap:12px}.column-picker-toolbar{display:flex;align-items:center;gap:12px}.column-picker-count{flex-shrink:0;color:var(--pms-text-secondary);font-size:12px}.column-picker-footer{display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--pms-border-soft);padding-top:10px}
</style>
