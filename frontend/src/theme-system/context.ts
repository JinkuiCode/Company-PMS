import { inject, type InjectionKey } from 'vue'
import type { ThemeSession } from './core'
export const themeSessionKey:InjectionKey<ThemeSession>=Symbol('pms-theme-session')
export function useThemeSession(){const session=inject(themeSessionKey);if(!session)throw Error('PmsThemeProvider is required');return session}
