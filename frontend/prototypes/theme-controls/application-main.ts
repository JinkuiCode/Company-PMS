import {createApp} from 'vue'
import {createPinia} from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import '@fontsource-variable/noto-sans-sc/wght.css'
import 'element-plus/dist/index.css'
import '@/styles/pms-theme.css'
import '@/form-system/form-tokens.css'
import {provideGlobalGridOptions} from 'ag-grid-community'
import {PMS_GRID_OPTIONS} from '@/config/listUi'
import {AxiosError} from 'axios'
import request from '@/utils/request'
import {useAuthStore} from '@/stores/auth'
import App from '@/App.vue'
import router from '@/router'
import {isPublicGuidePath} from '@/page-guide/navigation'
import {fixtureResponse,themeUser} from '../../tests/fixtures/theme-application-api.mjs'

request.defaults.adapter=async config=>{
  const url=new URL(request.getUri(config),'http://isolated.local')
  const path=url.pathname.replace(/^\/api/,'')
  const method=(config.method||'GET').toUpperCase()
  try{
    if(method!=='GET'&&!path.endsWith('/preview')&&path!=='/form-drafts/archive-create')throw Error('独立主题预览不执行业务写入')
    const data=fixtureResponse(path,url.searchParams,method,typeof config.data==='string'?JSON.parse(config.data):config.data)
    return{data,status:200,statusText:'OK',headers:{},config}
  }catch(error){throw new AxiosError(String(error),'ISOLATED_ONLY',config,undefined,{data:{detail:String(error)},status:422,statusText:'Unprocessable Entity',headers:{},config})}
}
provideGlobalGridOptions(PMS_GRID_OPTIONS)
const pinia=createPinia(),auth=useAuthStore(pinia)
const publicGuide=isPublicGuidePath(location.pathname)
auth.user=publicGuide?null:themeUser
// The actual guard runs with a fixture marker on the isolated5184 origin only.
if(!publicGuide)localStorage.setItem('access_token','isolated-theme-preview')
await router.push(publicGuide?location.pathname+location.hash:'/reports/purchase-progress')
createApp(App).use(pinia).use(router).use(ElementPlus,{locale:zhCn}).mount('#app')
