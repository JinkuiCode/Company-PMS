import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import '@fontsource-variable/noto-sans-sc/wght.css'
import 'element-plus/dist/index.css'
import './styles/pms-theme.css'
import './form-system/form-tokens.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { provideGlobalGridOptions } from 'ag-grid-community'
import { PMS_GRID_OPTIONS } from './config/listUi'

provideGlobalGridOptions(PMS_GRID_OPTIONS)

const app = createApp(App)
app.use(ElementPlus, { locale: zhCn })
app.use(createPinia())
app.use(router)
app.mount('#app')
