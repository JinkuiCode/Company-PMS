import { findGuideEntries } from './registry.ts'
import type { GuideSection, PageGuide, PageGuideKey } from './types'

export interface GuideViewState {
  section: GuideSection
  group: string
  search: string
}

export const guideDestinations = {
  archive: { permission: 'project:archive:view' },
  purchase: { permission: 'report:purchase:view' },
  inventory: { permission: 'report:inventory:view' },
  stock: { permission: 'report:stock-detail:list' },
} satisfies Record<PageGuideKey, { permission: string }>

export function isPublicGuidePath(path: string): boolean {
  return Object.keys(guideDestinations).some(page => path === `/page-guide/${page}`)
}

export function guideTabHref(page: PageGuideKey, state: GuideViewState): string {
  // Guide-only state stays in the fragment, separate from authentication and business queries.
  const hash = new URLSearchParams({ section: state.section, group: state.group, search: state.search })
  return `/page-guide/${page}#${hash}`
}

export function readGuideView(guide: PageGuide, hash: string): GuideViewState {
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  const section = params.get('section') === 'fields' ? 'fields' : 'operations'
  const search = params.get('search') || ''
  const requestedGroup = params.get('group') || '全部'
  const validGroup = findGuideEntries(guide, section, search).some(item => item.group === requestedGroup)
  return { section, search, group: validGroup ? requestedGroup : '全部' }
}
