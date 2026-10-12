// Isolated manual/browser test entry. It is not imported by the production App.
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import FixtureApp from './FixtureApp.vue'
createApp(FixtureApp).use(ElementPlus).mount('#app')
