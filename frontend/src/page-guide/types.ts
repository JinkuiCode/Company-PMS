export type PageGuideKey = 'archive' | 'purchase' | 'inventory' | 'stock' | 'feedback'
export type GuideSection = 'operations' | 'fields'
export interface GuideEntry { label: string; logic: string; group: string }
export interface PageGuide { title: string; operations: GuideEntry[]; fields: GuideEntry[] }
