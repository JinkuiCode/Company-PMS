export type PageGuideKey = 'archive' | 'archiveChanges' | 'archiveDrafts' | 'purchase' | 'inventory' | 'stock' | 'feedback' | 'users' | 'audit' | 'progress' | 'tasks'
export type GuideSection = 'operations' | 'fields'
export interface GuideEntry { label: string; logic: string; group: string }
export interface PageGuide { title: string; operations: GuideEntry[]; fields: GuideEntry[] }
