import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import '@fontsource-variable/noto-sans-sc/wght.css'
import 'element-plus/dist/index.css'
import './styles/pms-theme.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(ElementPlus, { locale: zhCn })
app.use(createPinia())
app.use(router)
app.mount('#app')
