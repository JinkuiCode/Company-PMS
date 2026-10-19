import {onBeforeUnmount,shallowRef} from 'vue'
import {themeTokens} from './core'
import {useThemeSession} from './context'
export function useThemeTokens(){
  const session=useThemeSession()
  const tokens=shallowRef(themeTokens(session.theme))
  const stop=session.subscribe(()=>{tokens.value=themeTokens(session.theme)})
  onBeforeUnmount(stop)
  return tokens
}
