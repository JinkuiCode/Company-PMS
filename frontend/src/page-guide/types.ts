export type PageGuideKey = 'archive' | 'archiveChanges' | 'purchase' | 'inventory' | 'stock' | 'feedback' | 'users'
export type GuideSection = 'operations' | 'fields'
export interface GuideEntry { label: string; logic: string; group: string }
export interface PageGuide { title: string; operations: GuideEntry[]; fields: GuideEntry[] }
