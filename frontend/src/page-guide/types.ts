export type PageGuideKey = 'businessNotices' | 'archive' | 'archiveChanges' | 'archiveDrafts' | 'purchase' | 'inventory' | 'stock' | 'feedback' | 'users' | 'roles' | 'enums' | 'audit' | 'progress' | 'tasks'
export type GuideSection = 'operations' | 'fields'
export interface GuideEntry { label: string; logic: string; group: string }
export interface PageGuide { title: string; operations: GuideEntry[]; fields: GuideEntry[] }
