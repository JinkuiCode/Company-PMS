<template>
  <div class="grid-layout-editor">
    <div class="layout-head"><span>显示 / 字段</span><span>冻结区域</span><span>列宽 (px)</span><span>顺序</span></div>
    <div class="layout-zones">
      <section v-for="zone in zones" :key="zone.value" class="layout-zone" @dragover.prevent @drop.prevent="drop(zone.value)">
        <h4>{{ zone.label }}</h4>
        <div v-for="field in zoneFields(zone.value).filter(matchesKeyword)" :key="field.id" class="layout-field" :draggable="!field.locked" :data-column="field.id" @dragstart="startDrag($event, field)" @dragend="dragged = null" @drop.stop.prevent="drop(zone.value, field.id)">
          <div class="layout-label">
            <PmsCheckboxControl :model-value="field.visible" :disabled="field.locked" :aria-label="`显示${field.label}列`" @update:model-value="change(field, { visible: Boolean($event) })" />
            <el-icon v-if="field.locked"><Lock /></el-icon><el-icon v-else class="drag-handle"><Rank /></el-icon><span :title="field.label">{{ field.label }}</span>
          </div>
          <PmsSelectControl :model-value="field.zone" :options="zones" :disabled="field.locked" size="compact" :aria-label="`${field.label}冻结区域`" @update:model-value="change(field, { zone: String($event) })" />
          <PmsNumberControl :model-value="field.width" :min="field.min" :max="field.max" :precision="0" :controls="false" :disabled="field.locked" size="compact" :aria-label="`${field.label}列宽`" @update:model-value="resize(field, $event)" />
          <div class="move-buttons"><el-button text :icon="ArrowUp" :disabled="field.locked || !canMove(field, -1)" :aria-label="`上移${field.label}`" :title="`上移${field.label}`" @click="move(field, -1)" /><el-button text :icon="ArrowDown" :disabled="field.locked || !canMove(field, 1)" :aria-label="`下移${field.label}`" :title="`下移${field.label}`" @click="move(field, 1)" /></div>
        </div>
      </section>
      <details class="hidden-fields" :open="Boolean(keyword)">
        <summary>未显示字段 ({{ modelValue.filter(f => !f.visible).length }})</summary>
        <section v-for="group in hiddenGroups" :key="group.label" class="layout-zone">
          <h4>{{ group.label }}</h4>
          <div v-for="field in group.fields" :key="field.id" class="hidden-field">
            <PmsCheckboxControl :model-value="false" :aria-label="`显示${field.label}列`" @update:model-value="change(field, { visible: true })">{{ field.label }}</PmsCheckboxControl>
          </div>
        </section>
      </details>
      <div v-if="!modelValue.some(matchesKeyword)" class="layout-empty">没有匹配的字段</div>
    </div>
    <p v-if="warning" class="layout-warning">冻结字段较多，中间滚动区域会变窄。</p>
  </div>
</template>
<script lang="ts">
export type LayoutField = { id: string; key?: string; label: string; group: string; zone: string; width: number; min: number; max: number; locked: boolean; visible: boolean; defaultVisible: boolean; defaultZone: string; defaultWidth: number; defaultOrder: number }
</script>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowUp, ArrowDown, Rank, Lock } from '@element-plus/icons-vue'
import { PmsSelectControl, PmsNumberControl, PmsCheckboxControl } from '@/form-system'
const props = defineProps<{ modelValue: LayoutField[]; keyword?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: LayoutField[]] }>()
const zones = [{ label: '左侧冻结', value: 'left' }, { label: '中间滚动', value: 'center' }, { label: '右侧冻结', value: 'right' }]
const dragged = ref<string | null>(null)
const warning = computed(() => props.modelValue.filter(f => f.visible && f.zone !== 'center').reduce((sum, f) => sum + f.width, 0) > 640)
const zoneFields = (zone: string) => props.modelValue.filter(f => f.visible && f.zone === zone).sort((a, b) => a.id === 'archive_selection' || b.id.endsWith('_actions') ? -1 : b.id === 'archive_selection' || a.id.endsWith('_actions') ? 1 : 0)
const matchesKeyword = (f: LayoutField) => `${f.label} ${f.id} ${f.group}`.toLowerCase().includes((props.keyword || '').trim().toLowerCase())
const hiddenGroups = computed(() => {
  const groups = new Map<string, LayoutField[]>()
  for (const field of props.modelValue.filter(f => !f.visible && matchesKeyword(f))) groups.set(field.group, [...(groups.get(field.group) || []), field])
  return Array.from(groups, ([label, fields]) => ({ label, fields }))
})
function change(field: LayoutField, patch: Partial<LayoutField>) { if (!field.locked) emit('update:modelValue', props.modelValue.map(f => f.id === field.id ? { ...f, ...patch } : f)) }
function resize(field: LayoutField, width: number | null | undefined) { if (width != null && Number.isFinite(width)) change(field, { width: Math.max(field.min, Math.min(field.max, Math.round(width))) }) }
function canMove(field: LayoutField, delta: number) { const list = zoneFields(field.zone); const other = list[list.findIndex(f => f.id === field.id) + delta]; return Boolean(other && !other.locked) }
function move(field: LayoutField, delta: number) {
  if (!canMove(field, delta)) return
  const next = [...props.modelValue], list = zoneFields(field.zone), other = list[list.findIndex(f => f.id === field.id) + delta]!
  const a = next.findIndex(f => f.id === field.id), b = next.findIndex(f => f.id === other.id)
  ;[next[a], next[b]] = [next[b]!, next[a]!]
  emit('update:modelValue', next)
}
function startDrag(event: DragEvent, field: LayoutField) { if (field.locked) return; dragged.value = field.id; event.dataTransfer?.setData('text/plain', field.id) }
function drop(zone: string, target?: string) {
  const field = props.modelValue.find(f => f.id === dragged.value)
  if (!field || field.locked || target === field.id) return
  const next = props.modelValue.filter(f => f.id !== field.id)
  next.splice(target ? next.findIndex(f => f.id === target) : next.length, 0, { ...field, zone })
  dragged.value = null
  emit('update:modelValue', next)
}
</script>
<style scoped>
.layout-head,.layout-field{display:grid;grid-template-columns:minmax(140px,1fr) 112px 72px 54px;gap:8px;align-items:center}
.layout-head{font-size:11px;color:var(--pms-text-muted);padding:0 4px 8px}.layout-zones{max-height:min(440px,55vh);overflow:auto}.layout-zone{padding:8px 0;min-height:44px;border-top:1px solid var(--pms-border-soft)}h4{font-size:11px;color:var(--pms-text-secondary);margin:0 0 6px;font-weight:500}.layout-field{padding:4px;border-radius:4px}.layout-field:hover{background:var(--pms-surface-muted)}.layout-label{display:flex;align-items:center;gap:6px;min-width:0;font-size:12px}.layout-label>span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.drag-handle{cursor:grab;color:var(--pms-text-muted)}.move-buttons{display:flex}.move-buttons :deep(.el-button){width:26px;height:26px;padding:0;margin:0}.layout-warning{font-size:12px;color:var(--pms-warning);margin:8px 0 0}.hidden-fields summary{cursor:pointer;font-size:12px;padding:10px 4px;color:var(--pms-text-secondary)}.hidden-field{padding:4px}.layout-empty{padding:12px;color:var(--pms-text-muted);font-size:12px}
</style>
