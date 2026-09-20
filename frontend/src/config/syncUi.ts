export const syncStatusOptions = [
  { value: 'queued', label: '等待同步' }, { value: 'running', label: '同步中' },
  { value: 'success', label: '同步成功' }, { value: 'failed', label: '同步失败' },
  { value: 'review', label: '待核查' }, { value: 'superseded', label: '已被新版本替代' },
]
export function archiveSyncLabel(value: unknown): string {
  if (!value) return '未同步'
  if (value === 'historical') return '金蝶历史档案'
  if (value === 'pending') return '同步中'
  return syncStatusOptions.find(item => item.value === value)?.label || String(value)
}
