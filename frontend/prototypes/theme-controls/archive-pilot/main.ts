import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import '@fontsource-variable/noto-sans-sc/wght.css'
import 'element-plus/dist/index.css'
import '@/styles/pms-theme.css'
import '@/form-system/form-tokens.css'
import { provideGlobalGridOptions } from 'ag-grid-community'
import { PMS_GRID_OPTIONS } from '@/config/listUi'
import { useAuthStore } from '@/stores/auth'
import ProjectArchive from '@/views/project/ProjectArchive.vue'
import App from './App.vue'
import { installPilotAdapter, pilotUser } from './fixtures'
installPilotAdapter()
provideGlobalGridOptions(PMS_GRID_OPTIONS)
const pinia=createPinia()
const auth=useAuthStore(pinia)
auth.user=pilotUser
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/project/archive',component:ProjectArchive}]})
await router.push('/project/archive')
createApp(App).use(pinia).use(router).use(ElementPlus,{locale:zhCn}).mount('#app')
