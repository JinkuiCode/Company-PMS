export const THEMES = Object.freeze({
  blue: { name: '办公蓝', brand: '#2563eb', hover: '#1d4ed8', soft: '#eff6ff', accentBorder: '#bfdbfe', bg: '#f5f7fa', text: '#20242b', secondary: '#5f6b7a', muted: '#6f7b8b', border: '#dce1e7', line: '#eaf0f5', head: '#f5f7fa', rowHover: '#f5f8fc', selected: '#edf4ff' },
  teal: { name: '青绿', brand: '#0f766e', hover: '#115e59', soft: '#eaf5f1', accentBorder: '#b5dcd0', bg: '#f5f8f7', text: '#202824', secondary: '#586c64', muted: '#6b7c75', border: '#dce4e0', line: '#eaf0ec', head: '#f3f7f5', rowHover: '#f2f8f5', selected: '#eaf5f1' },
  graphite: { name: '石墨', brand: '#27272a', hover: '#09090b', soft: '#f0f0f3', accentBorder: '#ccccd4', bg: '#f7f7f8', text: '#202023', secondary: '#62626c', muted: '#72727c', border: '#e1e1e5', line: '#eeeef1', head: '#f5f5f6', rowHover: '#f6f6f8', selected: '#efeff3' },
})
export const normalizeTheme = value => Object.hasOwn(THEMES, value) ? value : 'blue'
export function createThemePreference(storage, environment, user) {
  const key = `pms-theme-preview:v1:${encodeURIComponent(environment)}:${encodeURIComponent(user)}`
  return {
    key,
    read() { try { return normalizeTheme(storage.getItem(key)) } catch { return 'blue' } },
    write(value) { try { storage.setItem(key, normalizeTheme(value)); return true } catch { return false } },
  }
}
export function applyTheme(element, value) {
  const id = normalizeTheme(value), t = THEMES[id]
  element.dataset.previewTheme = id
  const vars = {
    '--pms-primary': t.brand, '--pms-primary-hover': t.hover, '--pms-primary-soft': t.soft,
    '--preview-accent-border': t.accentBorder, '--pms-bg': t.bg, '--pms-text': t.text,
    '--pms-text-secondary': t.secondary, '--pms-text-muted': t.muted,
    '--pms-border': t.border, '--pms-border-soft': t.line, '--pms-surface-muted': t.head,
    '--preview-row-hover': t.rowHover, '--preview-selected': t.selected,
  }
  for (const [key, color] of Object.entries(vars)) element.style.setProperty(key, color)
  return id
}
