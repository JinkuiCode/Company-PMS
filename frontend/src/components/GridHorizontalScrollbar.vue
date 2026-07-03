<template>
  <div
    ref="scrollbarRef"
    v-show="scrollMax > 0"
    class="grid-horizontal-scrollbar"
    role="scrollbar"
    tabindex="0"
    :aria-label="label"
    aria-orientation="horizontal"
    :aria-valuemax="Math.round(scrollMax)"
    :aria-valuenow="Math.round(scrollLeft)"
    aria-valuemin="0"
    @pointerdown="onPointerDown"
    @keydown="onKeydown"
  >
    <div ref="trackRef" class="grid-horizontal-scrollbar-track">
      <div class="grid-horizontal-scrollbar-thumb" :style="thumbStyle" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{
  label?: string
  viewportSelector?: string
}>(), {
  label: '表格横向滚动条',
  viewportSelector: '.ag-body-horizontal-scroll-viewport',
})

const scrollbarRef = ref<HTMLDivElement>()
const trackRef = ref<HTMLDivElement>()
const viewportWidth = ref(0)
const trackWidth = ref(0)
const scrollMax = ref(0)
const scrollLeft = ref(0)

let viewport: HTMLElement | null = null
let scrollHandler: (() => void) | null = null
let rafId = 0
let timeoutId = 0
let observer: MutationObserver | null = null
let dragState: { startX: number; startLeft: number } | null = null

const thumbWidth = computed(() => {
  if (scrollMax.value <= 0 || trackWidth.value <= 0) return trackWidth.value
  const totalWidth = scrollMax.value + viewportWidth.value
  const proportionalWidth = trackWidth.value * (viewportWidth.value / totalWidth)
  return Math.min(trackWidth.value, Math.max(72, Math.round(proportionalWidth)))
})

const thumbLeft = computed(() => {
  const travel = Math.max(0, trackWidth.value - thumbWidth.value)
  if (!travel || scrollMax.value <= 0) return 0
  return Math.round((scrollLeft.value / scrollMax.value) * travel)
})

const thumbStyle = computed(() => ({
  width: `${thumbWidth.value}px`,
  transform: `translateX(${thumbLeft.value}px)`,
}))

function getNativeHorizontalViewport(): HTMLElement | null {
  const host = scrollbarRef.value?.parentElement
  return host?.querySelector(props.viewportSelector) || null
}

function clampScrollLeft(value: number) {
  return Math.max(0, Math.min(value, scrollMax.value))
}

function updateMetrics() {
  const viewport = getNativeHorizontalViewport()
  const track = trackRef.value
  if (!viewport || !track) return

  viewportWidth.value = viewport.clientWidth
  trackWidth.value = track.clientWidth
  scrollMax.value = Math.max(0, viewport.scrollWidth - viewport.clientWidth)
  scrollLeft.value = clampScrollLeft(viewport.scrollLeft)
}

function clearSchedule() {
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
  if (timeoutId) {
    window.clearTimeout(timeoutId)
    timeoutId = 0
  }
}

function refresh() {
  clearSchedule()
  nextTick(() => {
    bindViewport()
    updateMetrics()
    rafId = window.requestAnimationFrame(updateMetrics)
    timeoutId = window.setTimeout(updateMetrics, 180)
  })
}

function bindViewport() {
  const nextViewport = getNativeHorizontalViewport()
  if (!nextViewport || nextViewport === viewport) return

  if (viewport && scrollHandler) {
    viewport.removeEventListener('scroll', scrollHandler)
  }

  viewport = nextViewport
  scrollHandler = () => {
    scrollLeft.value = clampScrollLeft(nextViewport.scrollLeft)
  }
  nextViewport.addEventListener('scroll', scrollHandler, { passive: true })
}

function syncToGrid(nextScrollLeft: number) {
  const nextViewport = getNativeHorizontalViewport()
  if (!nextViewport) return
  nextViewport.scrollLeft = clampScrollLeft(nextScrollLeft)
  scrollLeft.value = nextViewport.scrollLeft
}

function scrollLeftFromPointer(clientX: number) {
  const track = trackRef.value
  if (!track) return scrollLeft.value
  const rect = track.getBoundingClientRect()
  const travel = Math.max(1, rect.width - thumbWidth.value)
  const localX = clientX - rect.left - thumbWidth.value / 2
  return clampScrollLeft((localX / travel) * scrollMax.value)
}

function onPointerDown(event: PointerEvent) {
  if (scrollMax.value <= 0) return
  const target = event.target as HTMLElement
  if (!target.closest('.grid-horizontal-scrollbar-thumb')) {
    syncToGrid(scrollLeftFromPointer(event.clientX))
  }
  dragState = { startX: event.clientX, startLeft: scrollLeft.value }
  scrollbarRef.value?.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  if (!dragState || trackWidth.value <= 0) return
  const travel = Math.max(1, trackWidth.value - thumbWidth.value)
  const delta = ((event.clientX - dragState.startX) / travel) * scrollMax.value
  syncToGrid(dragState.startLeft + delta)
}

function onPointerUp(event: PointerEvent) {
  dragState = null
  scrollbarRef.value?.releasePointerCapture?.(event.pointerId)
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
}

function onKeydown(event: KeyboardEvent) {
  if (scrollMax.value <= 0) return
  const step = 80
  const pageStep = Math.max(160, viewportWidth.value * 0.8)
  const keyMap: Record<string, number> = {
    ArrowLeft: scrollLeft.value - step,
    ArrowRight: scrollLeft.value + step,
    PageUp: scrollLeft.value - pageStep,
    PageDown: scrollLeft.value + pageStep,
    Home: 0,
    End: scrollMax.value,
  }
  if (!(event.key in keyMap)) return
  syncToGrid(keyMap[event.key])
  event.preventDefault()
}

onMounted(() => {
  const host = scrollbarRef.value?.parentElement
  if (host) {
    observer = new MutationObserver(refresh)
    observer.observe(host, { childList: true, subtree: true, attributes: true })
  }
  window.addEventListener('resize', refresh)
  refresh()
})

onBeforeUnmount(() => {
  clearSchedule()
  observer?.disconnect()
  if (viewport && scrollHandler) {
    viewport.removeEventListener('scroll', scrollHandler)
  }
  window.removeEventListener('resize', refresh)
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})

defineExpose({ refresh })
</script>

<style scoped>
.grid-horizontal-scrollbar {
  width: 100%;
  height: 20px;
  display: flex;
  align-items: center;
  margin-top: 6px;
  padding: 0 3px;
  cursor: pointer;
  user-select: none;
  touch-action: none;
  outline: none;
}

.grid-horizontal-scrollbar-track {
  position: relative;
  width: 100%;
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.34);
}

.grid-horizontal-scrollbar-thumb {
  position: absolute;
  inset: 1px auto 1px 0;
  min-width: 48px;
  border-radius: 999px;
  background: #94a3b8;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
  cursor: grab;
  transition: background-color 120ms ease-out;
  will-change: transform;
}

.grid-horizontal-scrollbar:hover .grid-horizontal-scrollbar-thumb,
.grid-horizontal-scrollbar:focus-visible .grid-horizontal-scrollbar-thumb {
  background: #64748b;
}

.grid-horizontal-scrollbar:focus-visible {
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.16);
}

.grid-horizontal-scrollbar-thumb:active {
  cursor: grabbing;
  background: var(--pms-primary);
}
</style>
