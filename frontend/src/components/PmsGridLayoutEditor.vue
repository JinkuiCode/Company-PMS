<template>
  <div class="grid-layout-editor">
    <div class="layout-head"><span>字段</span><span>冻结区域</span><span>列宽 (px)</span><span>顺序</span></div>
    <div class="layout-zones">
      <section v-for="zone in zones" :key="zone.value" class="layout-zone" @dragover.prevent @drop.prevent="drop($event, zone.value)">
        <h4>{{ zone.label }}</h4>
        <div v-for="field in zoneFields(zone.value).filter(matchesKeyword)" :key="field.id" class="layout-field" :draggable="!field.locked" :data-column="field.id" @dragstart="startDrag($event, field)" @dragend="dragged = null" @drop.stop.prevent="drop($event, zone.value, field.id)">
          <span class="layout-label" :title="field.label"><el-icon v-if="field.locked"><Lock /></el-icon><el-icon v-else class="drag-handle"><Rank /></el-icon>{{ field.label }}</span>
          <PmsSelectControl :model-value="field.zone" :options="zones" :disabled="field.locked" size="compact" :aria-label="`${field.label}冻结区域`" @update:model-value="pin(field.id, String($event))" />
          <PmsNumberControl :model-value="field.width" :min="field.min" :max="field.max" :precision="0" :controls="false" :disabled="field.locked" size="compact" :aria-label="`${field.label}列宽`" @update:model-value="resize(field.id, $event)" />
          <span class="move-buttons"><el-button text :icon="ArrowUp" :disabled="field.locked || !canMove(field, -1)" :aria-label="`上移${field.label}`" :title="`上移${field.label}`" @click="move(field, -1)" /><el-button text :icon="ArrowDown" :disabled="field.locked || !canMove(field, 1)" :aria-label="`下移${field.label}`" :title="`下移${field.label}`" @click="move(field, 1)" /></span>
        </div>
      </section>
    </div>
    <p v-if="warning" class="layout-warning">冻结字段较多，中间滚动区域会变窄。</p>
    <div class="layout-status" role="status">调整自动保存 · 当前账号及浏览器</div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import type { GridApi } from 'ag-grid-community'
import { ArrowUp, ArrowDown, Rank, Lock } from '@element-plus/icons-vue'
import { PmsSelectControl, PmsNumberControl } from '@/form-system'
const props = defineProps<{ getGridApi: () => GridApi | null | undefined; keyword?: string }>()
const emit = defineEmits<{ changed: [] }>()
type Field = { id: string; label: string; zone: string; width: number; min: number; max: number; locked: boolean }
const zones = [{ label: '左侧冻结', value: 'left' }, { label: '中间滚动', value: 'center' }, { label: '右侧冻结', value: 'right' }]
const fields = ref<Field[]>([])
const dragged = ref<string | null>(null)
const warning = ref(false)
const lockedIds = new Set(['archive_selection', 'archive_actions', 'progress_actions'])
let api: GridApi | null | undefined
function refresh() {
  if (!api || api.isDestroyed()) return
  fields.value = api.getAllDisplayedColumns().map(column => {
    const def = column.getColDef()
    return { id: column.getColId(), label: def.headerName || '勾选列', zone: column.getPinned() === 'right' ? 'right' : column.getPinned() ? 'left' : 'center', width: column.getActualWidth(), min: def.minWidth || 60, max: def.maxWidth || 800, locked: lockedIds.has(column.getColId()) }
  })
  warning.value = fields.value.filter(f => f.zone !== 'center').reduce((sum, f) => sum + f.width, 0) > 640
}
const zoneFields = (zone: string) => fields.value.filter(f => f.zone === zone)
const matchesKeyword = (field: Field) => `${field.label} ${field.id}`.toLowerCase().includes((props.keyword || '').trim().toLowerCase())
function apply(next: Field[]) {
  if (!api) return
  const state = zones.flatMap(z => next.filter(f => f.zone === z.value).sort((a, b) => a.id === 'archive_selection' || b.id.endsWith('_actions') ? -1 : b.id === 'archive_selection' || a.id.endsWith('_actions') ? 1 : 0)).map(f => ({ colId: f.id, pinned: f.zone === 'center' ? null : f.zone as 'left' | 'right', width: f.width, flex: null }))
  api.applyColumnState({ state, applyOrder: true })
  refresh()
  emit('changed')
}
function pin(id: string, zone: string) { if (zones.some(z => z.value === zone)) apply(fields.value.map(f => f.id === id && !f.locked ? { ...f, zone } : f)) }
function resize(id: string, width: number | null | undefined) {
  if (width == null || !Number.isFinite(width)) return
  apply(fields.value.map(f => f.id === id && !f.locked ? { ...f, width: Math.max(f.min, Math.min(f.max, Math.round(width))) } : f))
}
function canMove(field: Field, delta: number) { const list = zoneFields(field.zone); const other = list[list.findIndex(f => f.id === field.id) + delta]; return Boolean(other && !other.locked) }
function move(field: Field, delta: number) {
  if (!canMove(field, delta)) return
  const next = [...fields.value], index = next.findIndex(f => f.id === field.id)
  const other = fields.value.findIndex(f => f.id === zoneFields(field.zone)[zoneFields(field.zone).findIndex(f => f.id === field.id) + delta]!.id)
  ;[next[index], next[other]] = [next[other]!, next[index]!]
  apply(next)
}
function startDrag(event: DragEvent, field: Field) { if (field.locked) return; dragged.value = field.id; event.dataTransfer?.setData('text/plain', field.id) }
function drop(_event: DragEvent, zone: string, target?: string) {
  const field = fields.value.find(f => f.id === dragged.value)
  if (!field || field.locked || target === field.id) return
  const next = fields.value.filter(f => f.id !== field.id)
  const at = target ? next.findIndex(f => f.id === target) : next.length
  next.splice(at, 0, { ...field, zone })
  dragged.value = null
  apply(next)
}
onMounted(() => { api = props.getGridApi(); refresh(); api?.addEventListener('displayedColumnsChanged', refresh); api?.addEventListener('columnResized', refresh) })
onBeforeUnmount(() => { if (!api?.isDestroyed()) { api?.removeEventListener('displayedColumnsChanged', refresh); api?.removeEventListener('columnResized', refresh) } })
</script>
<style scoped>
.layout-head,.layout-field{display:grid;grid-template-columns:minmax(100px,1fr) 112px 72px 54px;gap:8px;align-items:center}
.layout-head{font-size:11px;color:var(--pms-text-muted);padding:0 4px 8px}.layout-zones{max-height:350px;overflow:auto}.layout-zone{padding:8px 0;min-height:44px;border-top:1px solid var(--pms-border-soft)}h4{font-size:11px;color:var(--pms-text-secondary);margin:0 0 6px;font-weight:500}.layout-field{padding:4px;border-radius:4px}.layout-field:hover{background:var(--pms-surface-muted)}.layout-label{display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:12px}.drag-handle{cursor:grab;color:var(--pms-text-muted)}.move-buttons{display:flex}.move-buttons :deep(.el-button){width:26px;height:26px;padding:0;margin:0}.layout-status{font-size:11px;color:var(--pms-text-secondary);padding-top:10px}.layout-warning{font-size:12px;color:var(--pms-warning)}
</style>
