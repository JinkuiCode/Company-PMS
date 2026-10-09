import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import '@fontsource-variable/noto-sans-sc/wght.css'
import 'element-plus/dist/index.css'
import '../../src/styles/pms-theme.css'
import '../../src/form-system/form-tokens.css'
import Report from '../../src/views/reports/StockDetailList.vue'
import { useAuthStore } from '../../src/stores/auth'

const pinia = createPinia()
const auth = useAuthStore(pinia)
auth.user = { id: 1, username: 'fixture', real_name: '测试用户', dept_id: null, mobile: null,
  status: 1, role_codes: [], permissions: ['report:stock-detail:list', 'report:stock-detail:view', 'report:stock-detail:export'],
  data_scope: 1, product_category_ids: null, product_line_ids: [] }
createApp(Report).use(pinia).use(ElementPlus, { locale: zhCn }).mount('#app')
