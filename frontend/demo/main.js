// 独立演示入口（不进生产 App，不影响 src/ 任何文件）
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import DemoApp from './DemoApp.vue'
createApp(DemoApp).use(ElementPlus).mount('#app')
